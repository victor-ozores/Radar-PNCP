"""Exporta CSVs estáveis para o Power BI (fonte única: o Parquet do warehouse)."""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from radar.audit import RunLog
from radar.config import Config
from radar.normalize import pncp_url
from radar.scoring import Scorer
from radar.store import Store

EDITAIS_COLS = [
    "id",
    "objeto",
    "orgao",
    "uf",
    "municipio",
    "esfera",
    "modalidade_id",
    "modalidade",
    "situacao",
    "valor_estimado",
    "data_publicacao",
    "data_abertura_proposta",
    "data_encerramento_proposta",
    "dias_para_encerrar",
    "score",
    "relevante",
    "motivos",
    "flags",
    "link_pncp",
    "link_origem",
    "primeira_vez_visto",
]


def _fmt(v: Any) -> Any:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, datetime):
        return v.isoformat(sep=" ")
    if isinstance(v, date):
        return v.isoformat()
    return v


def write_csv(path: Path, cols: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: _fmt(r.get(c)) for c in cols})
    tmp.replace(path)


def export_editais(store: Store, scorer: Scorer, cfg: Config, now: datetime) -> int:
    ex = cfg.export
    corte_pub = now.date() - timedelta(days=ex.dias_historico)
    corte_fim = now - timedelta(days=ex.dias_apos_encerramento)
    rows = store.current_state(
        "WHERE dt >= ? OR data_encerramento_proposta >= ? ORDER BY id", [corte_pub, corte_fim]
    )
    saida: list[dict[str, Any]] = []
    for r in rows:
        res = scorer.score(r, now)
        fim = r.get("data_encerramento_proposta")
        saida.append(
            {
                "id": r["id"],
                "objeto": r["objeto"],
                "orgao": r["orgao_razao_social"],
                "uf": r["uf"],
                "municipio": r["municipio"],
                "esfera": r["esfera_id"],
                "modalidade_id": r["modalidade_id"],
                "modalidade": r["modalidade_nome"],
                "situacao": r["situacao_nome"],
                "valor_estimado": r["valor_estimado"],
                "data_publicacao": r["data_publicacao"],
                "data_abertura_proposta": r["data_abertura_proposta"],
                "data_encerramento_proposta": fim,
                "dias_para_encerrar": (fim.date() - now.date()).days if fim else None,
                "score": res.score,
                "relevante": res.relevante,
                "motivos": " | ".join(res.motivos),
                "flags": ",".join(res.flags),
                "link_pncp": pncp_url(r),
                "link_origem": r["link_origem"],
                "primeira_vez_visto": r["first_seen_at"],
            }
        )
    write_csv(store.export_dir / "editais.csv", EDITAIS_COLS, saida)
    return len(saida)


RUNS_COLS = [
    "run_id", "trigger", "modo", "started_at", "finished_at", "duration_s", "status",
    "window_start", "window_end", "series_total", "series_ok", "series_failed", "api_calls",
    "retries", "http_429", "http_5xx", "rows_read", "rows_invalid", "rows_new", "rows_updated",
    "rows_unchanged", "rows_relevant_new", "uf_mismatch", "pii_redactions", "quality_warnings",
    "alert_sent", "error_type", "error_message", "git_sha", "version",
]  # fmt: skip


def export_runs(store: Store) -> int:
    runs = sorted(RunLog(store).all(), key=lambda r: r["started_at"])
    write_csv(store.export_dir / "pipeline_runs.csv", RUNS_COLS, runs)
    return len(runs)


def export_all(store: Store, scorer: Scorer, cfg: Config, now: datetime) -> dict[str, int]:
    return {
        "editais": export_editais(store, scorer, cfg, now),
        "pipeline_runs": export_runs(store),
    }
