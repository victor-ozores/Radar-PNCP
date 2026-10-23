from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from helpers import FakeClient, load_sample_items
from radar.conferencia import ATUALIZADO, EXCLUIDO, IGUAL, INCERTO, conferir_no_pncp
from radar.normalize import SITUACAO_EXCLUIDA, normalize_item
from radar.pncp_client import PncpClientError, PncpRateLimited, PncpServerError
from radar.scoring import edital_inativo
from radar.store import Store

AGORA = datetime(2026, 10, 22, 12, 0)
DEPOIS = AGORA + timedelta(days=1)


@pytest.fixture
def guardado(tmp_path):
    """Um edital da amostra real já guardado, como o robô o veria depois de uma execução."""
    store = Store(tmp_path)
    bruto = load_sample_items()[0]
    row, _, _ = normalize_item(bruto)
    store.upsert([row], AGORA)
    return store, bruto, store.current_state()[0]


def test_edital_igual_ao_do_pncp_nao_mexe_em_nada(guardado):
    store, bruto, row = guardado
    c = conferir_no_pncp(FakeClient([bruto]), store, row, DEPOIS)
    assert c.resultado == IGUAL
    assert store.current_state()[0]["last_changed_at"] == AGORA  # nenhuma gravação


def test_prazo_prorrogado_e_valor_corrigido_sao_gravados(guardado):
    """Achado em 22/10/2026: prazo de 23/10 virou 06/11 e o valor mudou, e o robô não soube."""
    store, bruto, row = guardado
    novo = {
        **bruto,
        "dataEncerramentoProposta": "2026-11-06T09:00:00",
        "valorTotalEstimado": 123_456.0,
    }
    c = conferir_no_pncp(FakeClient([novo]), store, row, DEPOIS)

    assert c.resultado == ATUALIZADO and c.gravado.prazo_alterado == 1
    atual = store.current_state()[0]
    assert atual["data_encerramento_proposta"] == datetime(2026, 11, 6, 9, 0)
    assert atual["valor_estimado"] == 123_456.0
    assert (
        atual["first_seen_at"] == AGORA and atual["last_changed_at"] == DEPOIS
    )  # historia preservada


def test_edital_excluido_do_pncp_sai_das_listas_mas_a_linha_fica(guardado):
    """Achado em 22/10/2026: HTTP 410 'A contratação informada foi excluída'."""
    store, _, row = guardado
    c = conferir_no_pncp(FakeClient([]), store, row, DEPOIS)  # o PNCP não conhece mais

    assert c.resultado == EXCLUIDO and c.gravado.situacao_alterada == 1
    guardado_agora = store.current_state()
    assert len(guardado_agora) == 1  # a linha continua no Parquet
    assert guardado_agora[0]["situacao_id"] == SITUACAO_EXCLUIDA
    assert edital_inativo(guardado_agora[0])
    assert guardado_agora[0]["first_seen_at"] == AGORA


def test_conferir_de_novo_um_excluido_nao_regrava(guardado):
    store, _, row = guardado
    conferir_no_pncp(FakeClient([]), store, row, DEPOIS)
    de_novo = store.current_state()[0]
    c = conferir_no_pncp(FakeClient([]), store, de_novo, DEPOIS + timedelta(days=1))
    assert c.resultado == EXCLUIDO and c.gravado.updated_ids == []  # já estava marcado


@pytest.mark.parametrize(
    "erro", [PncpServerError("5xx"), PncpRateLimited("429"), PncpClientError("400", 400)]
)
def test_erro_da_consulta_nunca_decide_nada(guardado, erro):
    store, bruto, row = guardado
    client = FakeClient([bruto], compras={row["id"]: erro})
    c = conferir_no_pncp(client, store, row, DEPOIS)
    assert c.resultado == INCERTO
    assert (
        store.current_state()[0]["situacao_id"] == row["situacao_id"]
    )  # nada marcado como excluído


def test_id_fora_do_padrao_nao_gera_consulta(guardado):
    store, _, row = guardado
    client = FakeClient([])
    assert (
        conferir_no_pncp(client, store, {**row, "id": "id-estranho"}, DEPOIS).resultado == INCERTO
    )
    assert client.chamadas == []


def test_resposta_sem_data_de_publicacao_e_incerta(guardado):
    store, bruto, row = guardado
    quebrado = {k: v for k, v in bruto.items() if k != "dataPublicacaoPncp"}
    c = conferir_no_pncp(FakeClient([bruto], compras={row["id"]: quebrado}), store, row, DEPOIS)
    assert c.resultado == INCERTO
