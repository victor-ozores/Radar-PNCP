"""Arquivo de dados do painel público (``export/painel.json``).

A página (``site/``) lê só este arquivo, direto do navegador. Ele traz apenas o que a pessoa
precisa ver: os editais **abertos, ativos e que combinam com o perfil**, com prazo nos próximos
30 dias, e um resumo da saúde do robô. Contas que dependem do horário (quantos dias faltam, o
que já venceu) a página refaz na hora, por isso os prazos vão como data e hora absolutas, com o
fuso de Brasília (``-03:00``).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from radar.audit import STATUS_OK, RunLog
from radar.config import Config
from radar.normalize import TZ, corta_texto, pncp_url
from radar.scoring import Scorer, edital_inativo
from radar.store import Store

VERSAO = 1
JANELA_DIAS = 30  # a carga inicial só cobre prazos de até 30 dias; o painel diz o mesmo
RESUMO_MAX = 220
EXECUCOES_NO_PAINEL = 14


def iso_br(dt: datetime | None) -> str | None:
    """Horário de Brasília com o deslocamento explícito (a página não pode adivinhar o fuso)."""
    return dt.replace(tzinfo=TZ).isoformat(timespec="seconds") if dt else None


def rotulo_nota(nota: int) -> str:
    """Nota 0-100 em linguagem de gente: o painel não mostra o número."""
    if nota >= 80:
        return "muito"
    if nota >= 60:
        return "combina"
    return "parcial"


def _termo_legivel(cfg: Config, termo: str) -> str:
    return cfg.score.rotulos.get(termo) or termo.replace("*", "")


def _simulada(run: dict[str, Any]) -> bool:
    # execuções antigas não tinham a coluna `simulado`: reconhece pelo texto do erro
    return bool(run.get("simulado")) or "simulada" in (run.get("error_message") or "").lower()


def _robo(runs: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    validas = sorted(
        (r for r in runs if r["modo"] == "daily" and not _simulada(r)),
        key=lambda r: r["started_at"],
    )
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

    editais: list[dict[str, Any]] = []
    for r in sorted(ativos, key=lambda r: (r["data_encerramento_proposta"], r["id"])):
        res = scorer.score(r, now)
        if not res.relevante:
            continue
        valor = r["valor_estimado"]
        editais.append(
            {
                "id": r["id"],
                "objeto": corta_texto(r["objeto"], RESUMO_MAX),
                "orgao": corta_texto(r["orgao_razao_social"], 90),
                "uf": r["uf"],
                "municipio": r["municipio"],
                "modalidade": (r["modalidade_nome"] or "").replace(" - ", " "),
                "valor": round(valor, 2) if valor else None,
                "registro_de_precos": bool(r["srp"]),
                "abertura": iso_br(r["data_abertura_proposta"]),
                "prazo": iso_br(r["data_encerramento_proposta"]),
                "nota": res.score,
                "combina": rotulo_nota(res.score),
                "termos": [_termo_legivel(cfg, t) for t in res.fortes + res.fracos],
                "link": pncp_url(r),
            }
        )

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
        "totais": {"abertos": len(ativos), "combinam": len(editais)},
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
