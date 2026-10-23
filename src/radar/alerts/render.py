"""Monta as mensagens do alerta em HTML do Telegram (limite de 4096 caracteres por mensagem)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from html import escape
from typing import Any

from radar.normalize import (
    corta_texto as _corta,
)
from radar.normalize import (
    limpa_objeto,
    nome_do_orgao,
    numero_do_edital,
    pncp_url,
    suaviza_caixa,
    valor_confiavel,
)
from radar.scoring import ScoreResult, rotulo_nota

MAX_MSG = 3800  # margem sobre o limite de 4096 do Telegram

ROTULOS = {"muito": "Combina muito", "combina": "Combina", "parcial": "Combina em parte"}


@dataclass
class Item:
    row: dict[str, Any]
    result: ScoreResult
    #: os outros registros do mesmo edital no PNCP (publicado duas vezes), veja radar.repetidos
    iguais: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Resumo:
    novos: int = 0  # editais que o robô viu pela primeira vez nesta execução
    relevantes_novos: int = 0  # destes, quantos combinam com o perfil
    vencendo_total: int = 0  # quantos relevantes vencem na janela de "Prazos chegando"
    series_total: int = 0
    series_falhas: list[str] = field(default_factory=list)
    prazo_min_dias: int | None = None  # janela de "Prazos chegando", para o título da seção
    prazo_max_dias: int | None = None
    painel_url: str | None = None  # endereço do painel público (opcional)


def _br(n: float, casas: int = 1) -> str:
    s = f"{n:.{casas}f}".replace(".", ",")
    return s[:-2] if s.endswith(",0") else s


def fmt_valor(v: float | None) -> str:
    v = valor_confiavel(v)
    if v is None:
        return "valor não informado"
    if v >= 999_500:  # 999.999 não vira "1000 mil"
        return f"R$ {_br(v / 1_000_000)} mi"
    return f"R$ {_br(v / 1_000, 0 if v >= 100_000 else 1)} mil"


def fmt_prazo(fim: datetime | None, agora: datetime, abertura: datetime | None = None) -> str:
    if not fim:
        return "prazo não informado"
    dias = (fim.date() - agora.date()).days
    quando = "hoje" if dias == 0 else ("amanhã" if dias == 1 else f"em {dias} dias")
    desde = f"de {abertura:%d/%m} " if abertura and abertura > agora else ""
    return f"propostas {desde}até {fim:%d/%m} {fim:%H:%M} ({quando})"


def _numero(r: dict[str, Any]) -> str:
    """Ex.: "nº 12/2026" (ou vazio, se o órgão não preencheu um número que preste)."""
    numero = numero_do_edital(r)
    return f"nº {numero}" if numero else ""


def _edital(r: dict[str, Any]) -> str:
    """Ex.: "Pregão Eletrônico nº 12/2026", como a equipe de orçamentos costuma identificar o edital."""
    modalidade = (r.get("modalidade_nome") or "").replace(" - ", " ").strip()
    return " ".join(p for p in (modalidade, _numero(r)) if p)


def item_html(item: Item, agora: datetime) -> str:
    r = item.row
    rotulo = ROTULOS[rotulo_nota(item.result.score)]
    # corta antes de suavizar: o que decide se está "gritando" é o trecho que a pessoa vai ler
    objeto = suaviza_caixa(_corta(limpa_objeto(r.get("objeto")), 170))
    orgao = nome_do_orgao(_corta(r.get("orgao_razao_social"), 70), r.get("municipio"))
    local = " / ".join(x for x in (r.get("municipio"), r.get("uf")) if x)
    links = []
    if u := pncp_url(r):
        links.append(f'<a href="{escape(u, quote=True)}">PNCP</a>')
    if (o := r.get("link_origem")) and o.startswith(("http://", "https://")):
        links.append(f'<a href="{escape(o, quote=True)}">sistema de origem</a>')

    dinheiro = [f"💰 {fmt_valor(r.get('valor_estimado'))}"]
    if edital := _edital(r):
        dinheiro.append(f"📄 {escape(edital)}")
    if r.get("srp"):
        dinheiro.append("registro de preços")

    linhas = [
        f"<b>{rotulo}</b> · {escape(objeto)}",
        f"🏛 {escape(orgao)}" + (f" · 📍 {escape(local)}" if local else ""),
        " · ".join(dinheiro),
        f"⏰ {fmt_prazo(r.get('data_encerramento_proposta'), agora, r.get('data_abertura_proposta'))}",
    ]
    if links:
        linhas.append("🔗 " + " · ".join(links))
    if item.iguais:
        linhas.append(_linha_dos_iguais(item.iguais))
    return "\n".join(linhas)


MAX_IGUAIS = 2  # os que passam disso viram "e mais N"


def _linha_dos_iguais(iguais: list[dict[str, Any]]) -> str:
    """ "🔁 Também publicado como nº 36/2026", com o link de cada registro no PNCP."""
    partes = []
    for r in iguais[:MAX_IGUAIS]:
        numero = numero_do_edital(r)
        texto = escape(f"nº {numero}" if numero else "outro registro")
        url = pncp_url(r)
        partes.append(f'<a href="{escape(url, quote=True)}">{texto}</a>' if url else texto)
    resto = len(iguais) - MAX_IGUAIS
    return (
        "🔁 Também publicado como " + " · ".join(partes) + (f" e mais {resto}" if resto > 0 else "")
    )


def _chunk(blocos: list[str], limite: int = MAX_MSG) -> list[str]:
    msgs: list[str] = []
    atual = ""
    for b in blocos:
        if len(b) > limite:
            b = b[: limite - 1] + "…"
        if atual and len(atual) + 2 + len(b) > limite:
            msgs.append(atual)
            atual = b
        else:
            atual = f"{atual}\n\n{b}" if atual else b
    if atual:
        msgs.append(atual)
    return msgs


def _link_do_painel(resumo: Resumo, texto: str) -> str | None:
    if not resumo.painel_url:
        return None
    return f'🔎 <a href="{escape(resumo.painel_url, quote=True)}">{escape(texto)}</a>'


def build_digest(
    novos: list[Item],
    vencendo: list[Item],
    resumo: Resumo,
    agora: datetime,
    perfil: str,
) -> list[str]:
    topo = [f"<b>📡 Radar PNCP · {agora:%d/%m/%Y}</b>"]
    lidos = f"{resumo.novos} {'novo lido' if resumo.novos == 1 else 'novos lidos'} hoje"
    if novos:
        n = resumo.relevantes_novos
        quem = "edital novo combina" if n == 1 else "editais novos combinam"
        linha = f"<b>{n}</b> {quem} com o perfil, entre {lidos}."
        if len(novos) < n:
            linha += f" Os {len(novos)} que mais combinam:"
        topo.append(linha)
    else:
        topo.append(f"✅ Nenhum edital novo combina com o perfil hoje ({lidos}).")
    if resumo.series_falhas:
        topo.append(
            f"⚠️ {len(resumo.series_falhas)} de {resumo.series_total} buscas falharam: "
            f"{escape(', '.join(resumo.series_falhas[:6]))}. Os dados podem estar incompletos."
        )
    if link := _link_do_painel(resumo, "Ver todos no painel"):
        topo.append(link)

    blocos = ["\n".join(topo)]
    blocos += [item_html(i, agora) for i in novos]
    if vencendo:
        titulo = "<b>⏳ Prazos chegando</b>"
        if resumo.prazo_min_dias is not None and resumo.prazo_max_dias is not None:
            titulo += f" (vencem em {resumo.prazo_min_dias} a {resumo.prazo_max_dias} dias)"
        blocos.append(titulo)
        blocos += [item_html(i, agora) for i in vencendo]
        mais = resumo.vencendo_total - len(vencendo)
        if mais > 0:
            outros = "outro vence" if mais == 1 else "outros vencem"
            texto = f"Mais {mais} {outros} nesse período"
            blocos.append(_link_do_painel(resumo, f"{texto}: ver no painel") or f"<i>{texto}.</i>")
    blocos.append(f"<i>Perfil: {escape(perfil)}</i>")
    return _chunk(blocos)


def _quando(iso: str) -> str:
    """ "2026-10-22T12:31:23" vira "22/10/2026 12:31" (horário de Brasília); texto estranho passa como veio."""
    try:
        return f"{datetime.fromisoformat(iso):%d/%m/%Y %H:%M}"
    except ValueError:
        return iso


def failure_message(
    run_url: str | None, error_type: str | None, error_message: str | None, ultimo_ok: str | None
) -> str:
    linhas = ["<b>🚨 Radar PNCP: a execução falhou</b>"]
    if error_type:
        linhas.append(f"Erro: <code>{escape(error_type)}</code>")
    if error_message:
        linhas.append(escape(_corta(error_message, 400)))
    linhas.append(f"Último sucesso: {escape(_quando(ultimo_ok)) if ultimo_ok else 'sem registro'}")
    if run_url:
        linhas.append(f'<a href="{escape(run_url, quote=True)}">Ver a execução no GitHub</a>')
    return "\n".join(linhas)


def heartbeat_message(ultimo_ok: str | None, horas: float | None, limite_h: float) -> str:
    quando = (
        f"há {horas:.0f} h ({escape(_quando(ultimo_ok))})"
        if (ultimo_ok and horas is not None)
        else "nunca"
    )
    return (
        "<b>🫀 Radar PNCP: o robô não rodou</b>\n"
        f"Última execução com sucesso: {quando}. Limite: {limite_h:.0f} h.\n"
        "Confira se o agendamento do GitHub Actions continua ativo."
    )
