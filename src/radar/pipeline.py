"""Orquestração: busca no PNCP, grava, pontua, alerta e registra a execução."""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from radar import repetidos
from radar.alerts.render import Item, Resumo, build_digest
from radar.alerts.telegram import TelegramNotifier
from radar.audit import RunLog, RunRecord, scrub_secrets, write_status_files
from radar.conferencia import ATUALIZADO, EXCLUIDO, INCERTO, conferir_no_pncp
from radar.config import Alerta, Config
from radar.export import export_all
from radar.normalize import TZ, InvalidRecord, normalize_item
from radar.pncp_client import PncpClient, PncpError
from radar.scoring import Scorer, edital_inativo
from radar.store import Store, UpsertResult

log = logging.getLogger("radar.pipeline")

MODOS = ("daily", "backfill", "bootstrap", "reconcile")
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
    reconciliar_dias: int | None = None  # None: usa `ingestao.reconciliacao_dias` do config
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
    feed: str = "publicacao"  # "publicacao" (novos) ou "atualizacao" (alterados)

    @property
    def chave(self) -> str:
        base = f"{self.modalidade}/{self.uf}"
        if self.feed != "publicacao":
            base = f"{self.feed}:{base}"
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
    if opts.modo in ("bootstrap", "reconcile"):
        dias = opts.bootstrap_dias
        if opts.modo == "reconcile":
            dias = opts.reconciliar_dias or ing.reconciliacao_dias
        fim = hoje + timedelta(days=dias)
        series = [Serie(m, u, None, fim) for m in ing.modalidades for u in ing.ufs]
        return series, hoje, fim
    if opts.modo == "backfill":
        if not (opts.desde and opts.ate) or opts.desde > opts.ate:
            raise PipelineError("backfill exige --desde e --ate válidos (desde <= ate)")
        desde, ate = opts.desde, opts.ate
        desde_alt = desde  # no backfill, o mesmo período vale para novos e alterados
    else:
        ate = hoje
        desde = hoje - timedelta(days=ing.lookback_dias - 1)
        desde_alt = hoje - timedelta(days=ing.lookback_atualizacao_dias - 1)
    novos = [
        Serie(m, u, ini, fim)
        for ini, fim in _blocos(desde, ate)
        for m in ing.modalidades
        for u in ing.ufs
    ]
    # Depois dos novos, os ALTERADOS: pega prorrogações, suspensões e revogações de editais
    # publicados em qualquer data (a consulta por publicação não os traz de volta).
    alterados = [
        Serie(m, u, ini, fim, feed="atualizacao")
        for ini, fim in _blocos(desde_alt, ate)
        for m in ing.modalidades
        for u in ing.ufs
    ]
    return novos + alterados, desde, ate


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
    rec = RunRecord(
        run_id=_new_run_id(now),
        trigger=opts.trigger,
        modo=opts.modo,
        started_at=now,
        simulado=opts.simulate_failure,
    )
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

        if opts.modo == "reconcile" and not opts.dry_run:
            _reconciliar(cfg, client, store, ingerido, rec, now)
        if opts.modo == "daily":
            outcome.mensagens = _alertar(
                cfg, opts, client, store, scorer, ingerido, rec, now, notifier, outcome
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
    ids_publicacao: set[str] = field(default_factory=set)  # só o que a consulta por publicação leu


def _paginas(client: PncpClient, opts: RunOptions, s: Serie):
    if opts.modo in ("bootstrap", "reconcile"):
        return client.iter_proposta(s.fim, s.modalidade, s.uf)
    if s.feed == "atualizacao":
        return client.iter_atualizacao(s.inicio, s.fim, s.modalidade, s.uf)  # type: ignore[arg-type]
    return client.iter_publicacao(s.inicio, s.fim, s.modalidade, s.uf)  # type: ignore[arg-type]


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
    ids_publicacao: set[str] = set()
    avisos: Counter[str] = Counter()
    total = UpsertResult()
    # Ids que ainda estão abertos para propostas. A consulta por atualização devolve TODA alteração,
    # inclusive homologações de processos encerrados há meses (21/10/2026: 3.993 de 6.004 linhas
    # eram assim); só nos interessa o que está aberto ou que já tínhamos como aberto.
    abertos_conhecidos: set[str] = set()
    if any(s.feed == "atualizacao" for s in series):
        abertos_conhecidos = {
            r["id"] for r in store.current_state("WHERE data_encerramento_proposta >= ?", [now])
        }

    for s in series:
        linhas: dict[str, dict[str, Any]] = {}
        falha: PncpError | None = None
        try:
            for pagina in _paginas(client, opts, s):
                for bruto in pagina:
                    if s.feed == "atualizacao":
                        rec.rows_atualizacao += 1
                    else:
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
                    if s.feed == "atualizacao":
                        fim = row["data_encerramento_proposta"]
                        if not ((fim and fim >= now) or row["id"] in abertos_conhecidos):
                            avisos["atualizacao_encerrada_ignorada"] += 1
                            continue
                    linhas[row["id"]] = row
        except PncpError as exc:
            falha = exc

        abertos_conhecidos.update(
            i
            for i, r in linhas.items()
            if r["data_encerramento_proposta"] and r["data_encerramento_proposta"] >= now
        )
        # grava o que chegou, mesmo que a série tenha caído no meio (upsert é idempotente)
        if linhas:
            fetched.update(linhas)
            if s.feed != "atualizacao":
                ids_publicacao.update(linhas)
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
        total.new_ids = [i for i in fetched if i in ids_publicacao]
    rec.rows_new = len(total.new_ids)
    rec.rows_updated = len(total.updated_ids)
    rec.rows_unchanged = total.unchanged
    rec.prazos_alterados = total.prazo_alterado
    rec.situacoes_alteradas = total.situacao_alterada
    rec.quality_warnings = dict(avisos)
    return Ingerido(fetched, total.new_ids, ids_publicacao)


def _copia_stats(client: PncpClient, rec: RunRecord) -> None:
    st = client.stats
    rec.api_calls, rec.retries = st.api_calls, st.retries
    rec.http_429, rec.http_5xx = st.http_429, st.http_5xx


# ------------------------------------------------------------------------- conferência no PNCP

#: Depois de tantas respostas incertas seguidas (PNCP lento ou bloqueando), para de conferir:
#: cada consulta pode gastar minutos de espera, e o dia não pode ficar preso nisso.
INCERTOS_SEGUIDOS_PARA_PARAR = 2


def _reconciliar(
    cfg: Config,
    client: PncpClient,
    store: Store,
    ingerido: Ingerido,
    rec: RunRecord,
    now: datetime,
) -> None:
    """Confere no PNCP os editais que o robô guarda como abertos mas a listagem não trouxe.

    A listagem acabou de ser relida e gravada (corrigindo prazo, valor e situação do que veio). O que
    sobra, guardado como aberto e ausente dela, é excluído do PNCP ou teve o prazo levado para além
    da janela: só a consulta individual diz qual dos dois.
    """
    ing = cfg.ingestao
    limite = datetime.combine(rec.window_end, time.max).replace(microsecond=0)
    falharam = {
        (int(m), uf) for m, uf in (f["serie"].split("@")[0].split("/") for f in rec.series_failed)
    }  # série que falhou não prova ausência
    guardados = store.current_state(
        "WHERE data_encerramento_proposta >= ? AND data_encerramento_proposta <= ?", [now, limite]
    )
    suspeitos = sorted(
        (
            r
            for r in guardados
            if not edital_inativo(r)
            and r["modalidade_id"] in ing.modalidades
            and (r["uf"] or "").upper() in ing.ufs
            and (r["modalidade_id"], (r["uf"] or "").upper()) not in falharam
            and r["id"] not in ingerido.linhas
        ),
        key=lambda r: (r["data_encerramento_proposta"], r["id"]),  # o que vence antes primeiro
    )
    contagem: Counter[str] = Counter()
    incertos_seguidos = 0
    conferidos = 0
    for r in suspeitos[: ing.conferencias_max]:
        c = conferir_no_pncp(client, store, r, now)
        conferidos += 1
        contagem[c.resultado] += 1
        rec.rows_updated += len(c.gravado.updated_ids)
        rec.prazos_alterados += c.gravado.prazo_alterado
        rec.situacoes_alteradas += c.gravado.situacao_alterada
        incertos_seguidos = incertos_seguidos + 1 if c.resultado == INCERTO else 0
        if incertos_seguidos >= INCERTOS_SEGUIDOS_PARA_PARAR:
            break
    rec.quality_warnings.update({f"conferido_{k}": n for k, n in contagem.items()})
    if len(suspeitos) > conferidos:
        rec.quality_warnings["conferencia_pendente"] = len(suspeitos) - conferidos
    log.info(
        "conferência no PNCP concluída",
        extra={"ctx": {"suspeitos": len(suspeitos), "conferidos": conferidos, **contagem}},
    )


def _conferir_vencendo(
    grupos: list[list[Item]],
    client: PncpClient,
    store: Store,
    scorer: Scorer,
    cfg: Config,
    ja_no_resumo: set[str],
    now: datetime,
) -> tuple[list[Item], int]:
    """Confere no PNCP os primeiros de "Prazos chegando" antes de listá-los.

    Cada grupo é um edital que pode ter sido publicado mais de uma vez (veja ``radar.repetidos``) e
    cada registro dele é conferido, para que o "também publicado como" nunca aponte para um edital
    excluído. Registro excluído, ou prorrogado para fora da janela, sai (e o guardado é corrigido).
    O publicado por último que valer é o principal. Só quando a conferência não rola (sem consultas
    sobrando, ou o PNCP não responde) o guardado é aceito como está. Grupo em que nenhum registro vale
    sai da lista. Devolve a lista e quantos editais ficaram na janela, para o "mais N" da mensagem.
    """
    alerta = cfg.alerta
    orcamento = cfg.ingestao.conferencias_alerta_max
    escolhidos: list[Item] = []
    fora = 0
    consultas = 0
    incertos_seguidos = 0
    for grupo in grupos:  # em ordem de prazo
        if len(escolhidos) >= alerta.max_vencendo:
            break
        vivos: list[Item] = []  # conferidos e valem
        sem_conferir: list[Item] = []  # sem consulta, ou o PNCP não respondeu
        for item in grupo:
            if consultas < orcamento and incertos_seguidos < INCERTOS_SEGUIDOS_PARA_PARAR:
                consultas += 1
                c = conferir_no_pncp(client, store, item.row, now)
                incertos_seguidos = incertos_seguidos + 1 if c.resultado == INCERTO else 0
                if c.resultado == EXCLUIDO:
                    continue
                if c.resultado == ATUALIZADO and c.row is not None:
                    novo = Item(c.row, scorer.score(c.row, now))
                    if not selecionar_vencendo([novo], now, alerta, ja_no_resumo):
                        continue  # prorrogado para depois da janela, suspenso ou deixou de combinar
                    item = novo
                (sem_conferir if c.resultado == INCERTO else vivos).append(item)
            else:
                sem_conferir.append(item)
        validos = vivos or sem_conferir  # na dúvida de todos, vale o guardado
        if not validos:
            fora += 1
            continue
        principal, *outros = validos
        principal.iguais = [i.row for i in outros]
        escolhidos.append(principal)
    return escolhidos, len(grupos) - fora


# ------------------------------------------------------------------------- alerta


def _ordem(item: Item) -> tuple[int, float, str]:
    return (-item.result.score, -(item.row.get("valor_estimado") or 0), item.row["id"])


def _um_por_edital(itens: list[Item], antigos: repetidos.Indice) -> list[Item]:
    """Um item por edital: o publicado por último, com os outros registros dele em ``iguais``.

    Além dos que vieram juntos, entra o registro mais antigo que o robô já tinha (a republicação de um
    edital de ontem aparece como novo, mas não é uma oportunidade nova).
    """
    unicos: list[Item] = []
    for grupo in repetidos.agrupar(itens, lambda i: i.row):
        principal, *outros = grupo
        no_grupo = {i.row["id"] for i in grupo}
        principal.iguais = [i.row for i in outros] + [
            r for r in antigos.iguais_a(principal.row) if r["id"] not in no_grupo
        ]
        unicos.append(principal)
    return unicos


def janela_de_prazo(alerta: Alerta, now: datetime) -> tuple[datetime, datetime]:
    """Intervalo em que o prazo de propostas precisa cair para entrar em "Prazos chegando"."""
    return (
        now + timedelta(days=alerta.prazo_minimo_dias),
        now + timedelta(days=alerta.dias_prazo_proximo),
    )


def selecionar_vencendo(
    candidatos: list[Item], now: datetime, alerta: Alerta, ja_no_resumo: set[str]
) -> list[Item]:
    """Todos os relevantes que vencem dentro da janela, do prazo mais próximo ao mais distante."""
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
    )


def _alertar(
    cfg: Config,
    opts: RunOptions,
    client: PncpClient,
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
    # o mesmo edital publicado duas vezes (veja radar.repetidos) aparece uma vez, com o número do outro
    abertos = store.current_state("WHERE data_encerramento_proposta >= ?", [now])
    antigos = repetidos.Indice(r for r in abertos if not edital_inativo(r))
    novos_unicos = _um_por_edital(relevantes, antigos)
    top = novos_unicos[: alerta.top_n]
    ids_no_resumo = {r["id"] for i in top for r in [i.row, *i.iguais]}

    if opts.dry_run:
        candidatos = [Item(r, scorer.score(r, now)) for r in fetched.values()]
    else:
        inicio, fim = janela_de_prazo(alerta, now)
        estado = store.current_state(
            "WHERE data_encerramento_proposta >= ? AND data_encerramento_proposta <= ?",
            [inicio, fim],
        )
        candidatos = [Item(r, scorer.score(r, now)) for r in estado]
    grupos = repetidos.agrupar(
        selecionar_vencendo(candidatos, now, alerta, ids_no_resumo), lambda i: i.row
    )
    if (
        opts.dry_run
    ):  # a prévia não grava nada, então também não confere (conferir corrige o guardado)
        vencendo, vencendo_total = [], len(grupos)
        for grupo in grupos[: alerta.max_vencendo]:
            grupo[0].iguais = [i.row for i in grupo[1:]]
            vencendo.append(grupo[0])
    else:
        vencendo, vencendo_total = _conferir_vencendo(
            grupos, client, store, scorer, cfg, ids_no_resumo, now
        )

    resumo = Resumo(
        novos=len(new_ids),
        relevantes_novos=len(novos_unicos),
        vencendo_total=vencendo_total,
        series_total=rec.series_total,
        series_falhas=[f["serie"].split("@")[0] for f in rec.series_failed],
        prazo_min_dias=alerta.prazo_minimo_dias,
        prazo_max_dias=alerta.dias_prazo_proximo,
        painel_url=alerta.painel_url,
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
