"""O filtro contra editais REAIS do PNCP (coletados em 19-21/10/2026).

Cada caso do arquivo ``fixtures/casos_reais_filtro.json`` é um edital verdadeiro com o rótulo que
eu dei a ele (obra ou serviço que interessa ao perfil, ou compra/locação/outro assunto que não).
Os rótulos são um julgamento e devem ser revisados por quem faz orçamentos. Quando o perfil
mudar e um caso quebrar, o teste mostra qual edital e por quê; decida se o rótulo ou a regra errou.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from helpers import ROOT
from radar.scoring import Scorer

AGORA = datetime(2026, 10, 21, 12, 0, 0)
ARQUIVO = ROOT / "tests" / "fixtures" / "casos_reais_filtro.json"
CASOS = json.loads(ARQUIVO.read_text(encoding="utf-8"))["casos"]


def linha(caso: dict) -> dict:
    return {
        "objeto": caso["objeto"],
        "uf": caso["uf"],
        "modalidade_id": caso["modalidade_id"],
        "modalidade_nome": caso["modalidade_nome"],
        "valor_estimado": caso["valor_estimado"],
        "situacao_id": 1,
        "situacao_nome": "Divulgada no PNCP",
        "data_encerramento_proposta": AGORA + timedelta(days=10),
    }


@pytest.fixture(scope="module")
def scorer(cfg_modulo):
    return Scorer(cfg_modulo)


@pytest.fixture(scope="module")
def cfg_modulo():
    from radar.config import load_config

    return load_config(ROOT / "config.yaml")


@pytest.mark.parametrize("caso", CASOS, ids=lambda c: f"{c['grupo']}: {c['objeto'][:50]}")
def test_edital_real(scorer, caso):
    r = scorer.score(linha(caso), AGORA)
    assert r.relevante == caso["esperado_relevante"], (
        f"{caso['motivo']} | nota {r.score} | {' | '.join(r.motivos)} | {caso['objeto'][:160]}"
    )


def test_arquivo_tem_casos_dos_dois_lados():
    esperados = [c["esperado_relevante"] for c in CASOS]
    assert len(CASOS) >= 50 and any(esperados) and not all(esperados)
    assert {"compra", "locacao", "obra_pavimento", "obra_com_fornecimento"} <= {
        c["grupo"] for c in CASOS
    }
