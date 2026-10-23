from __future__ import annotations

import re

import pytest

from radar.normalize import (
    COLUMNS,
    InvalidRecord,
    esta_gritando,
    fold,
    limpa_objeto,
    nome_do_orgao,
    normalize_item,
    pncp_url,
    row_hash,
    scrub_pii,
    suaviza_caixa,
    valor_confiavel,
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


# Os casos abaixo são os mesmos de site/src/lib/formatos.test.ts: as duas implementações precisam concordar.


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (None, None),
        (0, None),
        (0.04, None),
        (999, None),
        (float("nan"), None),
        (-5, None),
        (1_000, 1_000),
        (1_500.5, 1_500.5),
    ],
)
def test_valor_confiavel(valor, esperado):
    assert valor_confiavel(valor) == esperado


def test_limpa_objeto_tira_a_etiqueta_do_sistema():
    assert (
        limpa_objeto("[Portal de Compras Públicas] - CONTRATAÇÃO DE EMPRESA")
        == "CONTRATAÇÃO DE EMPRESA"
    )
    assert limpa_objeto("[LICITANET] Reforma da escola") == "Reforma da escola"
    assert limpa_objeto("Reforma da escola [lote 2]") == "Reforma da escola [lote 2]"
    assert limpa_objeto("[Publicenter]") == "[Publicenter]"  # nunca devolve texto vazio
    assert limpa_objeto("  Obra  ") == "Obra"
    assert limpa_objeto(None) == ""


def test_suaviza_caixa_alta_mantendo_siglas_e_numeros():
    assert (
        suaviza_caixa(
            "CONTRATAÇÃO DE EMPRESA ESPECIALIZADA PARA EXECUÇÃO DA OBRA DA UBS DO BAIRRO RURAL"
        )
        == "Contratação de Empresa Especializada para Execução da Obra da UBS do Bairro Rural"
    )
    assert suaviza_caixa("OBRAS NA RODOVIA PRC-467 E PRS-495 NO LOTE II") == (
        "Obras na Rodovia PRC-467 e PRS-495 no Lote II"
    )


def test_suaviza_caixa_nao_mexe_em_texto_normal_ou_curto():
    normal = "Contratação de empresa para a reforma da escola"
    assert suaviza_caixa(normal) == normal
    assert suaviza_caixa("Reforma da UBS e do CRAS") == "Reforma da UBS e do CRAS"
    assert suaviza_caixa("OBRA CIVIL") == "OBRA CIVIL"  # curto demais para ter certeza


def test_suaviza_caixa_pronome_colado_crase_e_letra_solta():
    assert suaviza_caixa("REFERE-SE A CONTRATAÇÃO DE EMPRESA LOCALIZADA À RUA DAS FLORES") == (
        "Refere-se a Contratação de Empresa Localizada à Rua das Flores"
    )
    assert suaviza_caixa("EXECUÇÃO DA OBRA NO BLOCO B A PARTIR DO PROJETO") == (
        "Execução da Obra no Bloco B a Partir do Projeto"
    )


def test_suaviza_caixa_restaura_acentos_so_nos_nomes_de_orgaos():
    assert suaviza_caixa("MUNICIPIO DE BONFINOPOLIS DE MINAS", restaura_acentos=True) == (
        "Município de Bonfinopolis de Minas"
    )
    assert suaviza_caixa(
        "TRIBUNAL DE JUSTICA DO ESTADO DE MINAS GERAIS", restaura_acentos=True
    ) == ("Tribunal de Justiça do Estado de Minas Gerais")
    assert (
        suaviza_caixa("MUNICIPIO DE BONFINOPOLIS DE MINAS") == "Municipio de Bonfinopolis de Minas"
    )


def test_suaviza_so_o_trecho_em_caixa_alta_de_um_texto_misto():
    assert suaviza_caixa(
        "Contratação de empresa visando o FORNECIMENTO DE MATERIAL E MÃO DE OBRA PARA REFORMA DA PRAÇA "
        "DR. JOÃO NEVES CAMARGO, destinados à Secretaria Municipal"
    ) == (
        "Contratação de empresa visando o Fornecimento de Material e Mão de Obra para Reforma da Praça "
        "Dr. João Neves Camargo, destinados à Secretaria Municipal"
    )
    assert (
        suaviza_caixa(
            "CONTRATAÇÃO DE EMPRESA PARA EXECUÇÃO DE MURO NA TRAVESSA TICO-TICO, NO JORDÃO-SP, conforme o Termo"
        )
        == "Contratação de Empresa para Execução de Muro na Travessa Tico-Tico, no Jordão-SP, conforme o Termo"
    )


def test_sigla_solta_no_meio_de_texto_normal_nao_vira_grito():
    assert suaviza_caixa("Reforma da UBS e do CRAS com projeto da SABESP") == (
        "Reforma da UBS e do CRAS com projeto da SABESP"
    )


def test_numeros_no_meio_nao_quebram_o_trecho_em_maiusculas():
    assert suaviza_caixa("OBRAS NA RUA 7 DE SETEMBRO NO BAIRRO CENTRO") == (
        "Obras na Rua 7 de Setembro no Bairro Centro"
    )


def test_esta_gritando():
    assert esta_gritando("CONTRATAÇÃO DE EMPRESA")
    assert esta_gritando("Obra na PRAÇA DA MATRIZ CENTRAL de novo")  # trecho longo no meio
    assert not esta_gritando("Contratação de Empresa Especializada")
    assert not esta_gritando("OBRA")
    assert not esta_gritando("Reforma da UBS e do CRAS")


def test_mantem_as_siglas_conhecidas_dentro_do_trecho_em_caixa_alta():
    assert suaviza_caixa("CONSTRUÇÃO DE CRECHE PADRÃO FNDE NO MUNICÍPIO DE BANDEIRA") == (
        "Construção de Creche Padrão FNDE no Município de Bandeira"
    )


# Os mesmos casos estão em site/src/lib/formatos.test.ts: as duas pontas precisam concordar.
CASOS_NOME_DO_ORGAO = [
    ("MUNICIPIO DE IBIRITE", "Ibirité", "Município de Ibirité"),
    (
        "MUNICIPIO DA ESTANCIA TURISTICA DE OLIMPIA",
        "Olímpia",
        "Município da Estância Turística de Olímpia",
    ),
    (
        "MUNICIPIO DE MARECHAL CANDIDO RONDON",
        "Marechal Cândido Rondon",
        "Município de Marechal Cândido Rondon",
    ),
    (
        "Prefeitura de Capao Bonito",
        "Capão Bonito",
        "Prefeitura de Capão Bonito",
    ),  # já em caixa normal
    ("CAMARA MUNICIPAL DE RIO BRANCO", "Rio Branco", "Câmara Municipal de Rio Branco"),
    # nome da cidade que começa por palavra pequena: a suavização o deixaria "para de Minas"
    ("MUNICIPIO DE PARA DE MINAS", "Pará de Minas", "Município de Pará de Minas"),
    # só vale a cidade inteira, na ordem: o "para" solto continua preposição
    (
        "FUNDO PARA O MUNICIPIO DE PARA DE MINAS",
        "Pará de Minas",
        "Fundo para o Município de Pará de Minas",
    ),
    # a cidade não aparece no nome do órgão, ou não se sabe qual é: nada além da suavização
    (
        "TRIBUNAL DE JUSTICA DO ESTADO DE MINAS GERAIS",
        "Belo Horizonte",
        "Tribunal de Justiça do Estado de Minas Gerais",
    ),
    ("MUNICIPIO DE IBIRITE", None, "Município de Ibirite"),
    ("MUNICIPIO DE IBIRITE", "", "Município de Ibirite"),
]


@pytest.mark.parametrize(("orgao", "municipio", "esperado"), CASOS_NOME_DO_ORGAO)
def test_nome_do_orgao_usa_a_grafia_da_cidade_do_edital(orgao, municipio, esperado):
    assert nome_do_orgao(orgao, municipio) == esperado


def test_nome_do_orgao_sem_texto_e_idempotente():
    assert nome_do_orgao(None, "Ibirité") == ""
    pronto = nome_do_orgao("MUNICIPIO DE IBIRITE", "Ibirité")
    assert nome_do_orgao(pronto, "Ibirité") == pronto
