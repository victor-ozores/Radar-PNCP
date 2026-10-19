"""Vigia: detecta quando o robô deixou de rodar (cron pulado, workflow desativado)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class HeartbeatResult:
    ok: bool
    horas: float | None
    ultimo_ok: str | None


def check_heartbeat(data_dir: Path | str, now: datetime, max_horas: float = 26) -> HeartbeatResult:
    """``ok`` é falso se a última execução bem-sucedida passou de ``max_horas`` (ou não existe)."""
    path = Path(data_dir) / "status.json"
    if not path.exists():
        return HeartbeatResult(False, None, None)
    status = json.loads(path.read_text(encoding="utf-8"))
    ultimo = status.get("ultima_execucao_ok_em")
    if not ultimo:
        return HeartbeatResult(False, None, None)
    horas = (now - datetime.fromisoformat(ultimo)).total_seconds() / 3600
    return HeartbeatResult(horas <= max_horas, round(horas, 1), ultimo)
