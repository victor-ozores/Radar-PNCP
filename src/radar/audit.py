"""Auditoria das execuções: tabela ``pipeline_runs``, ``status.json`` e ``badge.json``."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from radar import __version__
from radar.store import Store, read_parquet_rows, write_parquet

RUN_SCHEMA: dict[str, str] = {
    "run_id": "VARCHAR",
    "trigger": "VARCHAR",
    "modo": "VARCHAR",
    "started_at": "TIMESTAMP",
    "finished_at": "TIMESTAMP",
    "duration_s": "DOUBLE",
    "status": "VARCHAR",
    "window_start": "DATE",
    "window_end": "DATE",
    "series_total": "INTEGER",
    "series_ok": "INTEGER",
    "series_failed": "VARCHAR",
    "api_calls": "INTEGER",
    "retries": "INTEGER",
    "http_429": "INTEGER",
    "http_5xx": "INTEGER",
    "rows_read": "INTEGER",
    "rows_invalid": "INTEGER",
    "rows_new": "INTEGER",
    "rows_updated": "INTEGER",
    "rows_unchanged": "INTEGER",
    "rows_atualizacao": "INTEGER",
    "prazos_alterados": "INTEGER",
    "situacoes_alteradas": "INTEGER",
    "rows_relevant_new": "INTEGER",
    "uf_mismatch": "INTEGER",
    "pii_redactions": "INTEGER",
    "quality_warnings": "VARCHAR",
    "alert_sent": "BOOLEAN",
    "simulado": "BOOLEAN",
    "error_type": "VARCHAR",
    "error_message": "VARCHAR",
    "git_sha": "VARCHAR",
    "version": "VARCHAR",
}

STATUS_OK = {"success", "partial"}  # a execução terminou e os dados estão frescos

_TOKEN_LIKE = re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b")  # token de bot do Telegram


def scrub_secrets(text: str, secrets: list[str] | None = None) -> str:
    """Remove tokens conhecidos e qualquer coisa com cara de token de bot."""
    for s in secrets or []:
        if s:
            text = text.replace(s, "***")
    return _TOKEN_LIKE.sub("***", text)


@dataclass
class RunRecord:
    run_id: str
    trigger: str
    modo: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_s: float | None = None
    status: str = "running"
    window_start: date | None = None
    window_end: date | None = None
    series_total: int = 0
    series_ok: int = 0
    series_failed: list[dict[str, str]] = field(default_factory=list)
    api_calls: int = 0
    retries: int = 0
    http_429: int = 0
    http_5xx: int = 0
    rows_read: int = 0
    rows_invalid: int = 0
    rows_new: int = 0
    rows_updated: int = 0
    rows_unchanged: int = 0
    rows_atualizacao: int = 0  # linhas lidas da consulta por data de atualização
    prazos_alterados: int = 0  # prorrogações (ou antecipações) detectadas em editais já guardados
    situacoes_alteradas: int = 0  # suspensões, revogações e anulações detectadas
    rows_relevant_new: int = 0
    uf_mismatch: int = 0
    pii_redactions: int = 0
    quality_warnings: dict[str, int] = field(default_factory=dict)
    alert_sent: bool = False
    simulado: bool = False  # falha de teste (--simulate-failure): fica fora das métricas
    error_type: str | None = None
    error_message: str | None = None
    git_sha: str | None = field(
        default_factory=lambda: os.environ.get("GITHUB_SHA", "")[:7] or None
    )
    version: str = __version__

    def to_row(self) -> dict[str, Any]:
        d = asdict(self)
        d["series_failed"] = json.dumps(self.series_failed, ensure_ascii=False)
        d["quality_warnings"] = json.dumps(
            self.quality_warnings, ensure_ascii=False, sort_keys=True
        )
        return d


class RunLog:
    """Histórico de execuções em um único Parquet pequeno (uma linha por execução)."""

    def __init__(self, store: Store) -> None:
        self.store = store
        self.path = store.data_dir / "warehouse" / "pipeline_runs" / "runs.parquet"

    def all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return read_parquet_rows(self.store.conn, self.path)

    def save(self, rec: RunRecord) -> None:
        rows = {r["run_id"]: r for r in self.all()}
        rows[rec.run_id] = rec.to_row()
        write_parquet(
            self.store.conn, list(rows.values()), RUN_SCHEMA, self.path, "started_at, run_id"
        )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def simulada(run: dict[str, Any]) -> bool:
    """Falha de mentirinha (`--simulate-failure`). As antigas não tinham a coluna: vê pelo texto do erro."""
    return bool(run.get("simulado")) or "simulada" in (run.get("error_message") or "").lower()


def execucoes_diarias(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """As execuções diárias de verdade, da mais antiga para a mais recente.

    Carga inicial, reprocessamento, conferência semanal e falha simulada ficam de fora: o vigia e o
    painel perguntam "a rotina do dia rodou?", e uma conferência de domingo não responde isso.
    """
    return sorted(
        (r for r in runs if r["modo"] == "daily" and not simulada(r)), key=lambda r: r["started_at"]
    )


def build_status(runs: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    # a última de qualquer modo: é a que o alerta de falha precisa mostrar
    ultima = max(runs, key=lambda r: r["started_at"]) if runs else None
    diarias = execucoes_diarias(runs)
    ok = [r for r in diarias if r["status"] in STATUS_OK and r["finished_at"]]
    ultimo_ok = ok[-1] if ok else None
    janela = [r for r in diarias if r["started_at"] >= now - timedelta(days=30)]
    sucesso_30d = (
        round(100 * sum(r["status"] in STATUS_OK for r in janela) / len(janela), 1)
        if janela
        else None
    )
    return {
        "gerado_em": now.isoformat(timespec="seconds"),
        "ultima_execucao": (
            {
                k: ultima[k]
                for k in ("run_id", "status", "trigger", "modo", "started_at", "finished_at")
            }
            | {
                "error_type": ultima["error_type"],
                "error_message": ultima["error_message"],
            }
            if ultima
            else None
        ),
        "ultima_execucao_ok_em": ultimo_ok["finished_at"].isoformat(timespec="seconds")
        if ultimo_ok
        else None,
        "ultima_execucao_ok_run_id": ultimo_ok["run_id"] if ultimo_ok else None,
        "execucoes_total": len(diarias),
        "execucoes_ok": len(ok),
        "taxa_sucesso_30d_pct": sucesso_30d,
    }


def build_badge(status: dict[str, Any]) -> dict[str, Any]:
    ultima = status.get("ultima_execucao")
    ok_em = status.get("ultima_execucao_ok_em")
    if not ultima or not ok_em:
        return {
            "schemaVersion": 1,
            "label": "última execução",
            "message": "sem dados",
            "color": "lightgrey",
        }
    dt = datetime.fromisoformat(ok_em)
    cor = {"success": "brightgreen", "partial": "yellow"}.get(ultima["status"], "red")
    msg = dt.strftime("%d/%m %H:%M BRT")
    if ultima["status"] == "failed":
        msg = f"falhou (último ok {msg})"
    return {"schemaVersion": 1, "label": "última execução", "message": msg, "color": cor}


def write_status_files(store: Store, now: datetime) -> dict[str, Any]:
    status = build_status(RunLog(store).all(), now)
    write_json(store.data_dir / "status.json", status)
    write_json(store.data_dir / "badge.json", build_badge(status))
    return status
