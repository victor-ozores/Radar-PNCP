from __future__ import annotations

import re

import pytest

from radar.normalize import (
    COLUMNS,
    InvalidRecord,
    fold,
    normalize_item,
    pncp_url,
    row_hash,
    scrub_pii,
)


def test_normaliza_toda_a_amostra_real(sample_items):
    for bruto in sample_items:
        row, _, _ = normalize_item(bruto)
        assert list(row) == COLUMNS
        assert row["id"] == bruto["numeroControlePNCP"]
        assert row["dt"] == row["data_publicacao"].date()
        assert row["uf"] in {"SP", "RJ"}


def test_mapeia_campos_aninhados(sample_items):
    bruto = sample_items[0]
    row, _, _ = normalize_item(bruto)
    assert row["uf"] == bruto["unidadeOrgao"]["ufSigla"]
    assert row["municipio"] == bruto["unidadeOrgao"]["municipioNome"]
    assert row["orgao_cnpj"] == bruto["orgaoEntidade"]["cnpj"]
    assert row["orgao_razao_social"] == bruto["orgaoEntidade"]["razaoSocial"]
    assert row["valor_estimado"] == bruto["valorTotalEstimado"]
    assert row["situacao_id"] == bruto["situacaoCompraId"]


def test_allowlist_descarta_usuario_e_campos_extras(sample_items):
    row, _, _ = normalize_item(sample_items[0])
    assert not any("usuario" in c for c in row)
    assert "REDACTED" not in str(row.values())  # valor do usuarioNome não vaza
    assert "fontesOrcamentarias" not in row and "linkProcessoEletronico" not in row


def test_scrub_remove_cpf_email_e_telefone():
    texto = (
        "Contato: joao@empresa.com.br, tel (11) 91234-5678, CPF 123.456.789-09 e CPF: 12345678909."
    )
    limpo, hits = scrub_pii(texto)
    assert hits == 4
    assert "123.456.789-09" not in limpo and "joao@" not in limpo and "91234" not in limpo
    assert "12345678909" not in limpo


def test_scrub_preserva_numeros_legitimos():
    texto = "Processo 0009490-72.2026.4.03.8000, CNPJ 12.345.678/0001-90, edital 90005/2026, R$ 1.234.567,89"
    limpo, hits = scrub_pii(texto)
    assert hits == 0 and limpo == texto


def test_pii_no_objeto_e_contada(sample_items):
    bruto = sample_items[0]
    bruto["objetoCompra"] = "Reforma. Falar com maria@prefeitura.gov.br (21) 98888-7777"
    row, pii, _ = normalize_item(bruto)
    assert pii == 2
    assert "maria@" not in row["objeto"] and "98888" not in row["objeto"]


def test_registro_sem_id_ou_sem_data_publicacao(sample_items):
    sem_id = {**sample_items[0], "numeroControlePNCP": None}
    with pytest.raises(InvalidRecord):
        normalize_item(sem_id)
    sem_data = {**sample_items[0], "dataPublicacaoPncp": "lixo"}
    with pytest.raises(InvalidRecord):
        normalize_item(sem_data)


def test_avisos_de_qualidade(sample_items):
    bruto = sample_items[0]
    bruto["dataAberturaProposta"] = "2026-10-20T08:00:00"
    bruto["dataEncerramentoProposta"] = "2026-10-18T08:00:00"
    bruto["valorTotalEstimado"] = -5
    bruto["objetoCompra"] = "   "
    row, _, avisos = normalize_item(bruto)
    assert "encerramento_antes_da_abertura" in avisos
    assert "valor_negativo" in avisos and row["valor_estimado"] is None
    assert "objeto_vazio" in avisos


def test_valor_nulo_ou_zero_continua_valido_e_vira_metrica(sample_items):
    nulo = {**sample_items[0], "valorTotalEstimado": None}
    row, _, avisos = normalize_item(nulo)
    assert row["valor_estimado"] is None and avisos == ["valor_ausente"]
    # achado nos dados reais: "sem valor" costuma chegar como 0
    zero = {**sample_items[0], "valorTotalEstimado": 0}
    row, _, avisos = normalize_item(zero)
    assert row["valor_estimado"] is None and avisos == ["valor_zero"]


def test_hash_estavel_e_sensivel_ao_conteudo(sample_items):
    a, _, _ = normalize_item(sample_items[0])
    b, _, _ = normalize_item(sample_items[0])
    assert a["row_hash"] == b["row_hash"] == row_hash(a)
    bruto = {**sample_items[0], "objetoCompra": "outro objeto"}
    c, _, _ = normalize_item(bruto)
    assert c["row_hash"] != a["row_hash"]


def test_fold_remove_acento_e_caixa():
    assert fold("  Manutenção   PREDIAL ") == "manutencao predial"
    assert fold(None) == ""


def test_url_publica_do_pncp(sample_items):
    row, _, _ = normalize_item(sample_items[0])
    assert re.fullmatch(r"https://pncp\.gov\.br/app/editais/\d{14}/\d{4}/\d+", pncp_url(row))
