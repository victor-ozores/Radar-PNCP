"""Monta as mensagens do alerta em HTML do Telegram (limite de 4096 caracteres por mensagem)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from html import escape
from typing import Any

from radar.normalize import pncp_url
from radar.scoring import ScoreResult

MAX_MSG = 3800  # margem sobre o limite de 4096 do Telegram


@dataclass
class Item:
    row: dict[str, Any]
    result: ScoreResult


@dataclass
class Resumo:
    analisados: int = 0
    novos: int = 0
    relevantes_novos: int = 0
    series_total: int = 0
    series_falhas: list[str] = field(default_factory=list)
    prazo_min_dias: int | None = None  # janela de "Prazos chegando", para o título da seção
    prazo_max_dias: int | None = None


def _br(n: float, casas: int = 1) -> str:
    s = f"{n:.{casas}f}".replace(".", ",")
    return s[:-2] if s.endswith(",0") else s


def fmt_valor(v: float | None) -> str:
    if not v:
        return "valor não informado"
    if v >= 1_000_000:
        return f"R$ {_br(v / 1_000_000)} mi"
    if v >= 1_000:
        return f"R$ {_br(v / 1_000, 0 if v >= 100_000 else 1)} mil"
    return f"R$ {_br(v, 0)}"


def fmt_prazo(fim: datetime | None, agora: datetime) -> str:
    if not fim:
        return "prazo não informado"
    dias = (fim.date() - agora.date()).days
    quando = "hoje" if dias == 0 else ("amanhã" if dias == 1 else f"em {dias} dias")
    return f"prazo {fim:%d/%m} {fim:%H:%M} ({quando})"


def _corta(texto: str | None, limite: int) -> str:
    t = (texto or "").strip()
    if len(t) <= limite:
        return t
    corte = t[: limite - 1]
    if " " in corte[limite // 2 :]:  # não deixa a última palavra cortada no meio
        corte = corte.rsplit(" ", 1)[0]
    return corte.rstrip(" ,;:-") + "…"


def item_html(item: Item, agora: datetime) -> str:
    r = item.row
    local = " / ".join(x for x in (r.get("municipio"), r.get("uf")) if x)
    links = []
    if u := pncp_url(r):
        links.append(f'<a href="{escape(u, quote=True)}">PNCP</a>')
    if (o := r.get("link_origem")) and o.startswith(("http://", "https://")):
        links.append(f'<a href="{escape(o, quote=True)}">sistema de origem</a>')
    linhas = [
        f"<b>Nota {item.result.score}</b> · {escape(_corta(r.get('objeto'), 170))}",
        f"🏛 {escape(_corta(r.get('orgao_razao_social'), 70))}"
        + (f" · 📍 {escape(local)}" if local else ""),
        f"💰 {fmt_valor(r.get('valor_estimado'))} · ⏰ {fmt_prazo(r.get('data_encerramento_proposta'), agora)}",
    ]
    if links:
        linhas.append("🔗 " + " · ".join(links))
    return "\n".join(linhas)


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


def build_digest(
    novos: list[Item],
    vencendo: list[Item],
    resumo: Resumo,
    agora: datetime,
    perfil: str,
) -> list[str]:
    topo = [f"<b>📡 Radar PNCP · {agora:%d/%m/%Y}</b>"]
    if novos:
        n = resumo.relevantes_novos
        quem = "edital novo combina" if n == 1 else "editais novos combinam"
        linha = f"<b>{n}</b> {quem} com o perfil, entre {resumo.analisados} analisados."
        if len(novos) < n:
            linha += f" Os {len(novos)} de maior nota:"
        topo.append(linha)
    else:
        topo.append(f"✅ Nenhum edital novo relevante hoje ({resumo.analisados} analisados).")
    if resumo.series_falhas:
        topo.append(
            f"⚠️ {len(resumo.series_falhas)} de {resumo.series_total} buscas falharam: "
            f"{escape(', '.join(resumo.series_falhas[:6]))}. Os dados podem estar incompletos."
        )

    blocos = ["\n".join(topo)]
    blocos += [item_html(i, agora) for i in novos]
    if vencendo:
        titulo = "<b>⏳ Prazos chegando</b>"
        if resumo.prazo_min_dias is not None and resumo.prazo_max_dias is not None:
            titulo += f" (vencem em {resumo.prazo_min_dias} a {resumo.prazo_max_dias} dias)"
        blocos.append(titulo)
        blocos += [item_html(i, agora) for i in vencendo]
    blocos.append(f"<i>Perfil: {escape(perfil)}</i>")
    return _chunk(blocos)


def failure_message(
    run_url: str | None, error_type: str | None, error_message: str | None, ultimo_ok: str | None
) -> str:
    linhas = ["<b>🚨 Radar PNCP: a execução falhou</b>"]
    if error_type:
        linhas.append(f"Erro: <code>{escape(error_type)}</code>")
    if error_message:
        linhas.append(escape(_corta(error_message, 400)))
    linhas.append(f"Último sucesso: {escape(ultimo_ok) if ultimo_ok else 'sem registro'}")
    if run_url:
        linhas.append(f'<a href="{escape(run_url, quote=True)}">Ver a execução no GitHub</a>')
    return "\n".join(linhas)


def heartbeat_message(ultimo_ok: str | None, horas: float | None, limite_h: float) -> str:
    quando = (
        f"há {horas:.0f} h ({escape(ultimo_ok)})" if (ultimo_ok and horas is not None) else "nunca"
    )
    return (
        "<b>🫀 Radar PNCP: o robô não rodou</b>\n"
        f"Última execução com sucesso: {quando}. Limite: {limite_h:.0f} h.\n"
        "Confira se o agendamento do GitHub Actions continua ativo."
    )
