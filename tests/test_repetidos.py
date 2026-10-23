from __future__ import annotations

from datetime import datetime

import pytest

from radar.repetidos import Indice, agrupar

PRAZO = datetime(2026, 10, 28, 9, 0)
TEXTO = "Registro de preço para contratação de empresa especializada em manutenção predial"


def linha(id_: str, **extra):
    base = {
        "id": id_,
        "orgao_cnpj": "46694121000181",
        "objeto": TEXTO,
        "valor_estimado": 7_346_618.38,
        "data_encerramento_proposta": PRAZO,
        "data_publicacao": datetime(2026, 10, 5, 9, 4),
    }
    return {**base, **extra}


def ids(grupos):
    return [[r["id"] for r in g] for g in grupos]


def agrupa(*rows):
    return ids(agrupar(rows, lambda r: r))


def test_texto_igual_sem_olhar_acento_caixa_pontuacao_e_etiqueta_do_sistema():
    a = linha(
        "a",
        objeto="[LICITANET] - REGISTRO DE PREÇO PARA CONTRATAÇÃO DE EMPRESA ESPECIALIZADA, EM MANUTENÇÃO PREDIAL.",
    )
    b = linha(
        "b",
        objeto="registro de preco para contratacao de empresa especializada em manutencao predial",
    )
    assert sorted(agrupa(a, b)[0]) == ["a", "b"] and len(agrupa(a, b)) == 1


@pytest.mark.parametrize(
    "mudanca",
    [
        {"orgao_cnpj": "12345678000190"},
        {"valor_estimado": 7_346_618.39},  # um centavo
        {"data_encerramento_proposta": datetime(2026, 10, 28, 9, 1)},  # um minuto
        {"objeto": "Construção de uma creche municipal com quatro salas"},
    ],
)
def test_orgao_valor_prazo_e_texto_diferentes_nao_juntam(mudanca):
    assert len(agrupa(linha("a"), linha("b", **mudanca))) == 2


def test_republicacao_que_so_acrescenta_um_trecho_ao_texto_junta():
    """Achado em 22/10/2026 (Castro/PR): a 2ª versão acrescentou "Processo nº 38603/2026"."""
    curto = linha("629", objeto=TEXTO + ".")
    longo = linha("628", objeto=TEXTO + ". Processo nº 38603/2026.")
    assert agrupa(curto, longo) == [["629", "628"]] or agrupa(curto, longo) == [["628", "629"]]
    assert len(agrupa(curto, longo)) == 1
    assert len(agrupa(longo, curto)) == 1  # a ordem de chegada não muda quem junta


def test_so_vale_palavra_inteira_e_texto_curto_nao_prova_nada():
    assert (
        len(
            agrupa(linha("a", objeto="Reforma da escola"), linha("b", objeto="Reformas da escolas"))
        )
        == 2
    )
    assert (
        len(
            agrupa(
                linha("a", objeto="Obra"), linha("b", objeto="Obra de reforma da escola municipal")
            )
        )
        == 2
    )
    # "reforma da escola" tem 17 letras: já serve, desde que apareça inteiro dentro do outro
    longo = linha("b", objeto="Execução de reforma da escola municipal Pedro Álvares")
    assert len(agrupa(linha("a", objeto="Reforma da escola"), longo)) == 1


def test_sem_valor_so_junta_o_texto_inteiro_igual():
    sem_valor = {"valor_estimado": None}
    assert len(agrupa(linha("a", **sem_valor), linha("b", **sem_valor))) == 1
    com_trecho = linha(
        "b", objeto=TEXTO + " lote 2", **sem_valor
    )  # "Lote 1" e "Lote 2" não viram um só
    assert len(agrupa(linha("a", **sem_valor), com_trecho)) == 2


def test_sem_orgao_texto_ou_prazo_nunca_e_tratado_como_repetido():
    for falta in (
        {"orgao_cnpj": None},
        {"objeto": ""},
        {"objeto": None},
        {"data_encerramento_proposta": None},
    ):
        assert len(agrupa(linha("x", **falta), linha("y", **falta))) == 2


def test_agrupar_poe_o_publicado_por_ultimo_primeiro_e_mantem_a_ordem_dos_grupos():
    original = linha("101", data_publicacao=datetime(2026, 10, 5, 9, 4))
    republicado = linha("110", data_publicacao=datetime(2026, 10, 5, 12, 37))
    outro = linha("200", objeto="Construção de uma creche municipal")
    assert agrupa(original, outro, republicado) == [["110", "101"], ["200"]]


def test_publicados_no_mesmo_instante_desempatam_pelo_id():
    mesmo = datetime(2026, 10, 5, 9, 0)
    assert agrupa(linha("a", data_publicacao=mesmo), linha("b", data_publicacao=mesmo)) == [
        ["b", "a"]
    ]


def test_agrupar_aceita_qualquer_item_que_tenha_uma_linha():
    itens = [("a", linha("a")), ("b", linha("b", data_publicacao=datetime(2026, 10, 6)))]
    (grupo,) = agrupar(itens, lambda par: par[1])
    assert [nome for nome, _ in grupo] == ["b", "a"]


def test_indice_acha_o_outro_registro_e_nunca_a_propria_linha():
    antigo = linha("101")
    outro_edital = linha("200", objeto="Construção de uma creche municipal")
    sem_orgao = linha("300", orgao_cnpj=None)
    indice = Indice([antigo, outro_edital, sem_orgao])

    novo = linha("110", objeto=TEXTO + " Processo nº 5")
    assert [r["id"] for r in indice.iguais_a(novo)] == ["101"]
    assert indice.iguais_a(antigo) == []  # ele mesmo não conta
    assert indice.iguais_a(sem_orgao) == []
    assert indice.iguais_a(linha("111", valor_estimado=1.0)) == []
