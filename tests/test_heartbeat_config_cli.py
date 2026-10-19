from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from radar.cli import JsonFormatter, build_parser, load_dotenv, main
from radar.config import Config, load_config
from radar.heartbeat import check_heartbeat

AGORA = datetime(2026, 10, 19, 10, 0, 0)


def grava_status(pasta, ok_em: datetime | None):
    (pasta / "status.json").write_text(
        json.dumps({"ultima_execucao_ok_em": ok_em.isoformat() if ok_em else None}),
        encoding="utf-8",
    )


def test_log_json_traz_o_fuso_no_horario():
    """No log da nuvem o horário saía em UTC sem aviso, enquanto o run_id usa Brasília."""
    import logging
    import re

    rec = logging.LogRecord("radar", logging.INFO, __file__, 1, "olá", None, None)
    rec.ctx = {"serie": "6/SP"}
    saida = json.loads(JsonFormatter().format(rec))
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d", saida["ts"])
    assert saida["msg"] == "olá" and saida["serie"] == "6/SP"


def test_heartbeat_ok_dentro_do_limite(tmp_path):
    grava_status(tmp_path, AGORA - timedelta(hours=25))
    r = check_heartbeat(tmp_path, AGORA, 26)
    assert r.ok and r.horas == 25.0


def test_heartbeat_alerta_depois_de_26h(tmp_path):
    grava_status(tmp_path, AGORA - timedelta(hours=27))
    r = check_heartbeat(tmp_path, AGORA, 26)
    assert not r.ok and r.horas == 27.0


def test_heartbeat_sem_status_ou_sem_sucesso(tmp_path):
    assert not check_heartbeat(tmp_path, AGORA).ok
    grava_status(tmp_path, None)
    assert not check_heartbeat(tmp_path, AGORA).ok


def test_config_do_repositorio_e_valida(cfg):
    assert isinstance(cfg, Config)
    assert cfg.ingestao.tamanho_pagina <= 50 and cfg.ingestao.intervalo_minimo_s >= 1


@pytest.mark.parametrize(
    "mudanca",
    [
        lambda c: c["ingestao"].update(ufs=["SPP"]),
        lambda c: c["ingestao"].update(modalidades=[14]),
        lambda c: c["ingestao"].update(tamanho_pagina=100),
        lambda c: c["filtros"].update(valor_min=10, valor_max=5),
        lambda c: c["score"].update(termos_fortes=[], termos_fracos=[]),
        lambda c: c.update(chave_desconhecida=1),
    ],
)
def test_config_invalida_e_rejeitada(tmp_path, mudanca):
    import yaml

    from helpers import ROOT

    bruto = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    mudanca(bruto)
    arq = tmp_path / "c.yaml"
    arq.write_text(yaml.safe_dump(bruto, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_config(arq)


def test_dotenv_nao_sobrescreve_ambiente(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('# comentário\nRADAR_A=1\nRADAR_B="dois"\nRADAR_C=\n', encoding="utf-8")
    monkeypatch.setenv("RADAR_A", "do-ambiente")
    monkeypatch.delenv("RADAR_B", raising=False)
    load_dotenv(env)
    import os

    assert os.environ["RADAR_A"] == "do-ambiente" and os.environ["RADAR_B"] == "dois"


def test_cli_check_config_e_parser(capsys):
    assert main(["check-config"]) == 0
    assert "config.yaml válido" in capsys.readouterr().out
    args = build_parser().parse_args(["backfill", "--desde", "2026-09-01", "--ate", "2026-09-07"])
    assert args.desde.isoformat() == "2026-09-01" and args.no_alerts


def test_notify_failure_sem_telegram_configurado(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert main(["notify-failure", "--data-dir", str(tmp_path)]) == 2
    assert "Telegram não configurado" in capsys.readouterr().out
