"""Arquivo de dados do painel público (``export/painel.json``).

A página (``site/``) lê só este arquivo, direto do navegador. Ele traz apenas o que a pessoa
precisa ver: os editais **abertos, ativos e que combinam com o perfil**, com prazo nos próximos
30 dias, e um resumo da saúde do robô. Contas que dependem do horário (quantos dias faltam, o
que já venceu) a página refaz na hora, por isso os prazos vão como data e hora absolutas, com o
fuso de Brasília (``-03:00``). O edital que o órgão publicou duas vezes vai uma vez só, com os
outros registros dele em ``repetidos`` (veja ``radar.repetidos``).

O objeto e o nome do órgão vão resumidos (a lista mostra só o começo). Quando o texto foi cortado, o
original vai também em ``objeto_completo`` e ``orgao_completo``, para a exportação para o Excel
levar o texto inteiro; quando não foi cortado, o campo nem aparece (o arquivo não cresce à toa).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from radar import repetidos
from radar.audit import STATUS_OK, RunLog, execucoes_diarias
from radar.config import Config
from radar.normalize import TZ, corta_texto, numero_do_edital, pncp_url
from radar.scoring import Scorer, edital_inativo, rotulo_nota
from radar.store import Store

VERSAO = 1
JANELA_DIAS = 30  # a carga inicial só cobre prazos de até 30 dias; o painel diz o mesmo
RESUMO_MAX = 220
ORGAO_MAX = 90
EXECUCOES_NO_PAINEL = 14


def iso_br(dt: datetime | None) -> str | None:
    """Horário de Brasília com o deslocamento explícito (a página não pode adivinhar o fuso)."""
    return dt.replace(tzinfo=TZ).isoformat(timespec="seconds") if dt else None


def _termo_legivel(cfg: Config, termo: str) -> str:
    return cfg.score.rotulos.get(termo) or termo.replace("*", "")


def _robo(runs: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    validas = execucoes_diarias(runs)
    ok = [r for r in validas if r["status"] in STATUS_OK and r["finished_at"]]
    recentes = [r for r in validas if r["started_at"] >= now - timedelta(days=30)]
    ultima = validas[-1] if validas else None
    return {
        "ultima_execucao_ok_em": iso_br(ok[-1]["finished_at"]) if ok else None,
        "execucoes_30d": len(recentes),
        "taxa_sucesso_30d_pct": (
            round(100 * sum(r["status"] in STATUS_OK for r in recentes) / len(recentes), 1)
            if recentes
            else None
        ),
        "ultima": (
            {
                "em": iso_br(ultima["started_at"]),
                "status": ultima["status"],
                "duracao_min": (
                    round(ultima["duration_s"] / 60, 1)
                    if ultima["duration_s"] is not None
                    else None
                ),
                "lidos": ultima["rows_read"],
                "novos": ultima["rows_new"],
                "prazos_corrigidos": ultima.get("prazos_alterados"),
                "situacoes_corrigidas": ultima.get("situacoes_alteradas"),
            }
            if ultima
            else None
        ),
        "ultimas": [
            {"em": iso_br(r["started_at"]), "status": r["status"]}
            for r in validas[-EXECUCOES_NO_PAINEL:]
        ],
    }


def build_painel(store: Store, scorer: Scorer, cfg: Config, now: datetime) -> dict[str, Any]:
    ate = now + timedelta(days=JANELA_DIAS)
    rows = store.current_state(
        "WHERE data_encerramento_proposta >= ? AND data_encerramento_proposta <= ?", [now, ate]
    )
    ativos = [r for r in rows if not edital_inativo(r)]
    nomes_modalidade = {
        r["modalidade_id"]: (r["modalidade_nome"] or "").replace(" - ", " ") for r in rows
    }

    relevantes = []
    for r in sorted(ativos, key=lambda r: (r["data_encerramento_proposta"], r["id"])):
        res = scorer.score(r, now)
        if res.relevante:
            relevantes.append((r, res))

    editais: list[dict[str, Any]] = []
    ocultos = 0
    # o edital publicado duas vezes (veja radar.repetidos) aparece uma vez, com o número e o link do outro
    for grupo in repetidos.agrupar(relevantes, lambda par: par[0]):
        (r, res), *outros = grupo
        valor = r["valor_estimado"]
        objeto = corta_texto(r["objeto"], RESUMO_MAX)
        orgao = corta_texto(r["orgao_razao_social"], ORGAO_MAX)
        edital = {
            "id": r["id"],
            "objeto": objeto,
            "orgao": orgao,
            "uf": r["uf"],
            "municipio": r["municipio"],
            "modalidade": (r["modalidade_nome"] or "").replace(" - ", " "),
            "numero": numero_do_edital(r) or None,
            "valor": round(valor, 2) if valor else None,
            "registro_de_precos": bool(r["srp"]),
            "abertura": iso_br(r["data_abertura_proposta"]),
            "prazo": iso_br(r["data_encerramento_proposta"]),
            "nota": res.score,
            "combina": rotulo_nota(res.score),
            "termos": [_termo_legivel(cfg, t) for t in res.fortes + res.fracos],
            "link": pncp_url(r),
        }
        # o texto inteiro só quando o resumo cortou alguma coisa
        if (r["objeto"] or "").strip() != objeto:
            edital["objeto_completo"] = r["objeto"].strip()
        if (r["orgao_razao_social"] or "").strip() != orgao:
            edital["orgao_completo"] = r["orgao_razao_social"].strip()
        if outros:
            edital["repetidos"] = [
                {
                    "id": o["id"],
                    "numero": numero_do_edital(o) or None,
                    "publicado": o["data_publicacao"].date().isoformat(),
                    "link": pncp_url(o),
                }
                for o, _ in outros
            ]
            ocultos += len(outros)
        editais.append(edital)

    return {
        "versao": VERSAO,
        "gerado_em": iso_br(now),
        "janela_dias": JANELA_DIAS,
        "perfil": {
            "nome": cfg.perfil.nome,
            "descricao": " ".join(cfg.perfil.descricao.split()),
            "ufs": cfg.ingestao.ufs,
            "modalidades": [
                nomes_modalidade.get(m, f"Modalidade {m}") for m in cfg.ingestao.modalidades
            ],
            "valor_min": cfg.filtros.valor_min,
            "valor_max": cfg.filtros.valor_max,
        },
        "totais": {"abertos": len(ativos), "combinam": len(editais), "repetidos": ocultos},
        "robo": _robo(RunLog(store).all(), now),
        "editais": editais,
    }


def escrever_painel(caminho: Path, painel: dict[str, Any]) -> None:
    """Grava com um edital por linha: o git guarda só as linhas que mudam de um dia para o outro."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    compacto = {"ensure_ascii": False, "separators": (",", ":")}
    cabecalho = {k: v for k, v in painel.items() if k != "editais"}
    linhas = ",\n".join(json.dumps(e, **compacto) for e in painel["editais"])
    texto = json.dumps(cabecalho, **compacto)[:-1] + ',"editais":[\n' + linhas + "\n]}\n"
    tmp = caminho.with_name(caminho.name + ".tmp")
    tmp.write_text(texto, encoding="utf-8", newline="\n")
    tmp.replace(caminho)


def export_painel(store: Store, scorer: Scorer, cfg: Config, now: datetime) -> int:
    painel = build_painel(store, scorer, cfg, now)
    escrever_painel(store.export_dir / "painel.json", painel)
    return len(painel["editais"])
