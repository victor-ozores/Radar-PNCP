from __future__ import annotations

from datetime import datetime

import pytest

from helpers import ROOT, load_sample_items
from radar.config import Config, load_config

#: "agora" fixo dos testes: o dia seguinte à publicação da amostra real (16/10/2026)
AGORA = datetime(2026, 10, 17, 7, 17, 0)


@pytest.fixture(autouse=True)
def isola_segredos(monkeypatch):
    """Nenhum teste pode enxergar o .env nem as variáveis reais do Telegram.

    Sem isso, `main()` carregaria o .env do desenvolvedor e um teste de falha mandaria
    uma mensagem de verdade para o chat dele.
    """
    monkeypatch.setattr("radar.cli.load_dotenv", lambda *a, **k: None)
    for var in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture(scope="session")
def cfg() -> Config:
    return load_config(ROOT / "config.yaml")


@pytest.fixture
def sample_items():
    return load_sample_items()


@pytest.fixture
def agora() -> datetime:
    return AGORA
