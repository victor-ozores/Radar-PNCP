from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

import pytest

from radar.normalize import normalize_item
from radar.store import Store

T1 = datetime(2026, 10, 17, 7, 17, 0)
T2 = T1 + timedelta(days=1)


@pytest.fixture
def rows(sample_items):
    return [normalize_item(i)[0] for i in sample_items]


def hashes(store: Store) -> dict[str, str]:
    return {
        str(p.relative_to(store.data_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(store.contratacoes_dir.glob("dt=*/part.parquet"))
    }


def test_primeira_carga_cria_particoes_por_dia(tmp_path, rows):
    store = Store(tmp_path)
    res = store.upsert(rows, T1)
    assert len(res.new_ids) == len(rows) and res.updated_ids == [] and res.unchanged == 0
    assert (tmp_path / "warehouse/contratacoes/dt=2026-10-16/part.parquet").exists()
    assert len(store.current_state()) == len(rows)


def test_reexecutar_a_mesma_janela_nao_muda_nenhum_byte(tmp_path, rows):
    store = Store(tmp_path)
    store.upsert(rows, T1)
    antes = hashes(store)

    res = store.upsert(rows, T2)  # outro "agora", mesmo conteúdo

    assert res.new_ids == [] and res.updated_ids == []
    assert res.unchanged == len(rows) and res.partitions_written == 0
    assert hashes(store) == antes
    assert len(store.current_state()) == len(rows)  # sem duplicar


def test_parquet_e_deterministico_em_pastas_diferentes(tmp_path, rows):
    a, b = Store(tmp_path / "a"), Store(tmp_path / "b")
    a.upsert(rows, T1)
    b.upsert(list(reversed(rows)), T1)  # ordem de chegada diferente
    ha, hb = hashes(a), hashes(b)
    assert ha == hb


def test_mudanca_atualiza_e_preserva_first_seen(tmp_path, rows):
    store = Store(tmp_path)
    store.upsert(rows, T1)
    alvo = dict(rows[0])
    alvo["situacao_id"], alvo["situacao_nome"] = 2, "Revogada"
    from radar.normalize import row_hash

    alvo["row_hash"] = row_hash(alvo)

    res = store.upsert([alvo], T2)

    assert res.updated_ids == [alvo["id"]] and res.new_ids == []
    atual = store.current_state("WHERE id = ?", [alvo["id"]])[0]
    assert atual["situacao_nome"] == "Revogada"
    assert atual["first_seen_at"] == T1 and atual["last_changed_at"] == T2


def test_estado_atual_fica_com_a_versao_mais_recente(tmp_path, rows):
    store = Store(tmp_path)
    antigo = dict(rows[0])
    novo = {**antigo, "dt": antigo["dt"] + timedelta(days=1), "objeto": "versão nova",
            "data_atualizacao_global": antigo["data_atualizacao_global"] + timedelta(hours=3)}  # fmt: skip
    store.upsert([antigo], T1)
    store.upsert([novo], T2)  # mesma id em outra partição
    estado = store.current_state("WHERE id = ?", [antigo["id"]])
    assert len(estado) == 1 and estado[0]["objeto"] == "versão nova"


def test_estado_vazio_sem_dados(tmp_path):
    assert Store(tmp_path).current_state() == []
