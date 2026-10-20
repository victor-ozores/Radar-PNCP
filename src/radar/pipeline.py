"""Orquestração: busca no PNCP, grava, pontua, alerta e registra a execução."""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from radar.alerts.render import Item, Resumo, build_digest
from radar.alerts.telegram import TelegramNotifier
from radar.audit import RunLog, RunRecord, scrub_secrets, write_status_files
from radar.config import Alerta, Config
from radar.export import export_all
from radar.normalize import TZ, InvalidRecord, normalize_item
from radar.pncp_client import PncpClient, PncpError
from radar.scoring import Scorer
from radar.store import Store, UpsertResult

log = logging.getLogger("radar.pipeline")

MODOS = ("daily", "backfill", "bootstrap")
DIAS_POR_BLOCO = 7


class PipelineError(Exception):
    """A execução não produziu dados utilizáveis."""


@dataclass
class RunOptions:
    data_dir: Path
    modo: str = "daily"
    trigger: str = "manual"
    dry_run: bool = False
    send_alerts: bool = True
    desde: date | None = None
    ate: date | None = None
    bootstrap_dias: int = 30
    simulate_failure: bool = False  # força uma falha para testar o alerta de erro


@dataclass
class Outcome:
    record: RunRecord
    mensagens: list[str] = field(default_factory=list)
    itens: list[Item] = field(default_factory=list)  # editais mostrados no resumo (para depuração)


def now_br() -> datetime:
    return datetime.now(TZ).replace(tzinfo=None, microsecond=0)


@dataclass(frozen=True)
class Serie:
    modalidade: int
    uf: str
    inicio: date | None
    fim: date

    @property
    def chave(self) -> str:
        base = f"{self.modalidade}/{self.uf}"
        return (
            f"{base}@{self.inicio:%Y%m%d}-{self.fim:%Y%m%d}"
            if self.inicio
            else f"{base}@ate{self.fim:%Y%m%d}"
        )


def _blocos(desde: date, ate: date, dias: int = DIAS_POR_BLOCO) -> list[tuple[date, date]]:
    out, ini = [], desde
    while ini <= ate:
        fim = min(ini + timedelta(days=dias - 1), ate)
        out.append((ini, fim))
        ini = fim + timedelta(days=1)
    return out


def plan_series(cfg: Config, opts: RunOptions, hoje: date) -> tuple[list[Serie], date, date]:
    """Lista as buscas da execução e devolve também a janela (início, fim) para auditoria."""
    ing = cfg.ingestao
    if opts.modo == "bootstrap":
        fim = hoje + timedelta(days=opts.bootstrap_dias)
        series = [Serie(m, u, None, fim) for m in ing.modalidades for u in ing.ufs]
        return series, hoje, fim
    if opts.modo == "backfill":
        if not (opts.desde and opts.ate) or opts.desde > opts.ate:
            raise PipelineError("backfill exige --desde e --ate válidos (desde <= ate)")
        desde, ate = opts.desde, opts.ate
    else:
        ate = hoje
        desde = hoje - timedelta(days=ing.lookback_dias - 1)
    series = [
        Serie(m, u, ini, fim)
        for ini, fim in _blocos(desde, ate)
        for m in ing.modalidades
        for u in ing.ufs
    ]
    return series, desde, ate


def _new_run_id(now: datetime) -> str:
    return f"{now:%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"


def run_pipeline(
    cfg: Config,
    opts: RunOptions,
    *,
    client: PncpClient,
    notifier: TelegramNotifier | None = None,
    now: datetime | None = None,
    secrets: list[str] | None = None,
) -> Outcome:
    if opts.modo not in MODOS:
        raise PipelineError(f"modo inválido: {opts.modo}")
    now = now or now_br()
    store = Store(opts.data_dir)
    scorer = Scorer(cfg)
    rec = RunRecord(run_id=_new_run_id(now), trigger=opts.trigger, modo=opts.modo, started_at=now)
    outcome = Outcome(rec)
    erro: Exception | None = None

    try:
        if opts.simulate_failure:
            raise PipelineError("falha simulada (--simulate-failure) para testar o alerta")
        series, rec.window_start, rec.window_end = plan_series(cfg, opts, now.date())
        rec.series_total = len(series)
        log.info(
            "execução iniciada",
            extra={
                "ctx": {
                    "run_id": rec.run_id,
                    "modo": opts.modo,
                    "series": len(series),
                    "janela": f"{rec.window_start}..{rec.window_end}",
                    "dry_run": opts.dry_run,
                }
            },
        )
        ingerido = _ingest(cfg, opts, client, store, series, rec, now)

        if rec.series_total and rec.series_ok == 0:
            raise PipelineError(f"todas as {rec.series_total} buscas falharam")
        rec.status = "partial" if rec.series_failed else "success"

        if opts.modo == "daily":
            outcome.mensagens = _alertar(
                cfg, opts, store, scorer, ingerido, rec, now, notifier, outcome
            )
    except Exception as exc:  # registra a falha antes de propagar
        erro = exc
        rec.status = "failed"
        rec.error_type = type(exc).__name__
        rec.error_message = scrub_secrets(str(exc), secrets)[:500]
        log.error(
            "execução falhou", extra={"ctx": {"erro": rec.error_type, "msg": rec.error_message}}
        )
    finally:
        _copia_stats(client, rec)
        rec.finished_at = now_br()
        rec.duration_s = round((rec.finished_at - rec.started_at).total_seconds(), 1)
        if not opts.dry_run:
            RunLog(store).save(rec)
            export_all(store, scorer, cfg, now)
            write_status_files(store, rec.finished_at)
        store.close()

    log.info(
        "execução concluída", extra={"ctx": {"status": rec.status, "duracao_s": rec.duration_s}}
    )
    if erro:
        raise erro
    return outcome


# ------------------------------------------------------------------------- ingestão


@dataclass
class Ingerido:
    """O que a ingestão trouxe: todas as linhas válidas e os ids que são novos no warehouse."""

    linhas: dict[str, dict[str, Any]]
    new_ids: list[str]


def _ingest(
    cfg: Config,
    opts: RunOptions,
    client: PncpClient,
    store: Store,
    series: list[Serie],
    rec: RunRecord,
    now: datetime,
) -> Ingerido:
    fetched: dict[str, dict[str, Any]] = {}
    avisos: Counter[str] = Counter()
    total = UpsertResult()

    for s in series:
        linhas: dict[str, dict[str, Any]] = {}
        falha: PncpError | None = None
        try:
            paginas = (
                client.iter_proposta(s.fim, s.modalidade, s.uf)
                if opts.modo == "bootstrap"
                else client.iter_publicacao(s.inicio, s.fim, s.modalidade, s.uf)  # type: ignore[arg-type]
            )
            for pagina in paginas:
                for bruto in pagina:
                    rec.rows_read += 1
                    try:
                        row, pii, avisos_item = normalize_item(bruto)
                    except InvalidRecord:
                        rec.rows_invalid += 1
                        avisos["registro_invalido"] += 1
                        continue
                    rec.pii_redactions += pii
                    avisos.update(avisos_item)
                    uf_row = (row["uf"] or "").upper()
                    if not uf_row:
                        avisos["uf_ausente"] += 1
                    elif uf_row != s.uf:
                        rec.uf_mismatch += 1  # a API ignorou o filtro de UF?
                        continue
                    linhas[row["id"]] = row
        except PncpError as exc:
            falha = exc

        # grava o que chegou, mesmo que a série tenha caído no meio (upsert é idempotente)
        if linhas:
            fetched.update(linhas)
            if not opts.dry_run:
                total.merge(store.upsert(list(linhas.values()), now))
        if falha:
            rec.series_failed.append(
                {"serie": s.chave, "erro": type(falha).__name__, "msg": str(falha)[:200]}
            )
            log.warning(
                "série falhou", extra={"ctx": {"serie": s.chave, "erro": type(falha).__name__}}
            )
        else:
            rec.series_ok += 1
            log.info("série concluída", extra={"ctx": {"serie": s.chave, "linhas": len(linhas)}})

    if opts.dry_run:
        total.new_ids = list(fetched)
    rec.rows_new = len(total.new_ids)
    rec.rows_updated = len(total.updated_ids)
    rec.rows_unchanged = total.unchanged
    rec.quality_warnings = dict(avisos)
    return Ingerido(fetched, total.new_ids)


def _copia_stats(client: PncpClient, rec: RunRecord) -> None:
    st = client.stats
    rec.api_calls, rec.retries = st.api_calls, st.retries
    rec.http_429, rec.http_5xx = st.http_429, st.http_5xx


# ------------------------------------------------------------------------- alerta


def _ordem(item: Item) -> tuple[int, float, str]:
    return (-item.result.score, -(item.row.get("valor_estimado") or 0), item.row["id"])


def janela_de_prazo(alerta: Alerta, now: datetime) -> tuple[datetime, datetime]:
    """Intervalo em que o prazo de propostas precisa cair para entrar em "Prazos chegando"."""
    return (
        now + timedelta(days=alerta.prazo_minimo_dias),
        now + timedelta(days=alerta.dias_prazo_proximo),
    )


def selecionar_vencendo(
    candidatos: list[Item], now: datetime, alerta: Alerta, ja_no_resumo: set[str]
) -> list[Item]:
    """Relevantes que vencem dentro da janela, do prazo mais próximo ao mais distante."""
    inicio, fim = janela_de_prazo(alerta, now)
    return sorted(
        (
            i
            for i in candidatos
            if i.result.relevante
            and i.row["id"] not in ja_no_resumo
            and i.row.get("data_encerramento_proposta")
            and inicio <= i.row["data_encerramento_proposta"] <= fim
        ),
        key=lambda i: (i.row["data_encerramento_proposta"], i.row["id"]),
    )[: alerta.max_vencendo]


def _alertar(
    cfg: Config,
    opts: RunOptions,
    store: Store,
    scorer: Scorer,
    ingerido: Ingerido,
    rec: RunRecord,
    now: datetime,
    notifier: TelegramNotifier | None,
    outcome: Outcome,
) -> list[str]:
    fetched, new_ids = ingerido.linhas, ingerido.new_ids
    alerta = cfg.alerta

    novos = [Item(fetched[i], scorer.score(fetched[i], now)) for i in new_ids if i in fetched]
    relevantes = sorted((i for i in novos if i.result.relevante), key=_ordem)
    rec.rows_relevant_new = len(relevantes)
    top = relevantes[: alerta.top_n]

    if opts.dry_run:
        candidatos = [Item(r, scorer.score(r, now)) for r in fetched.values()]
    else:
        inicio, fim = janela_de_prazo(alerta, now)
        estado = store.current_state(
            "WHERE data_encerramento_proposta >= ? AND data_encerramento_proposta <= ?",
            [inicio, fim],
        )
        candidatos = [Item(r, scorer.score(r, now)) for r in estado]
    vencendo = selecionar_vencendo(candidatos, now, alerta, {i.row["id"] for i in top})

    resumo = Resumo(
        analisados=len(fetched),
        novos=len(new_ids),
        relevantes_novos=len(relevantes),
        series_total=rec.series_total,
        series_falhas=[f["serie"].split("@")[0] for f in rec.series_failed],
        prazo_min_dias=alerta.prazo_minimo_dias,
        prazo_max_dias=alerta.dias_prazo_proximo,
    )
    outcome.itens = top + vencendo
    mensagens: list[str] = []
    if top or vencendo or alerta.enviar_quando_vazio or rec.series_failed:
        mensagens = build_digest(top, vencendo, resumo, now, cfg.perfil.nome)

    if mensagens and opts.send_alerts and not opts.dry_run:
        if notifier is None:
            log.warning("alerta ignorado: Telegram não configurado")
        else:
            notifier.send_many(mensagens)
            rec.alert_sent = True
    return mensagens
