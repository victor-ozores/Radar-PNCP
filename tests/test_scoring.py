from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from radar.scoring import Scorer, compile_term

AGORA = datetime(2026, 10, 17, 7, 17)


def linha(**over):
    base = {
        "objeto": "Contratação de empresa para execução de obras de reforma predial",
        "uf": "SP",
        "modalidade_id": 6,
        "modalidade_nome": "Pregão - Eletrônico",
        "valor_estimado": 1_000_000.0,
        "situacao_id": 1,
        "situacao_nome": "Divulgada no PNCP",
        "data_encerramento_proposta": AGORA + timedelta(days=5),
    }
    return {**base, **over}


@pytest.fixture
def scorer(cfg):
    return Scorer(cfg)


def test_edital_tipico_de_engenharia_e_relevante(scorer):
    r = scorer.score(linha(), AGORA)
    # obras + reforma (35 cada) + SP (10) + pregão (5) + valor na faixa (15) = 100, limitado a 100
    assert r.score == 100 and r.relevante
    assert any("termos fortes" in m for m in r.motivos)


def test_pontuacao_exata_com_um_termo_forte(scorer):
    r = scorer.score(linha(objeto="Construção de quadra poliesportiva"), AGORA)
    assert r.score == 35 + 10 + 5 + 15  # forte + SP + pregão + valor na faixa
    assert r.relevante


def test_sem_termo_do_perfil_zera(scorer):
    r = scorer.score(linha(objeto="Aquisição de cadeiras de escritório"), AGORA)
    assert r.score == 0 and not r.relevante


def test_so_termo_fraco_nao_basta(scorer):
    r = scorer.score(linha(objeto="Serviço de pintura de salas"), AGORA)
    assert r.score == 8 + 10 + 5 + 15 and not r.relevante


def test_termo_negativo_derruba(scorer):
    r = scorer.score(linha(objeto="Reforma de refeitório e fornecimento de uniformes"), AGORA)
    assert "termos de exclusão" in " ".join(r.motivos)
    assert not r.relevante


def test_valor_nao_informado_e_neutro_e_sinalizado(scorer):
    r = scorer.score(linha(objeto="Construção de quadra", valor_estimado=None), AGORA)
    assert r.score == 35 + 10 + 5 and r.relevante
    assert "valor_nao_informado" in r.flags


def test_valor_fora_da_faixa_penaliza(scorer):
    r = scorer.score(linha(objeto="Construção de quadra", valor_estimado=5_000.0), AGORA)
    assert r.score == 35 + 10 + 5 - 15
    assert "valor_fora_da_faixa" in r.flags


def test_prazo_encerrado_e_situacao_inativa_zeram(scorer):
    vencido = scorer.score(linha(data_encerramento_proposta=AGORA - timedelta(hours=1)), AGORA)
    assert vencido.score == 0 and "encerrado" in vencido.flags
    for sid in (2, 3, 4):
        assert scorer.score(linha(situacao_id=sid), AGORA).score == 0
    por_nome = scorer.score(linha(situacao_id=None, situacao_nome="Revogada"), AGORA)
    assert por_nome.score == 0


def test_uf_fora_do_perfil_nao_ganha_bonus(scorer):
    r = scorer.score(linha(objeto="Construção de quadra", uf="AM"), AGORA)
    assert r.score == 35 + 5 + 15


def test_coringa_e_fronteira_de_palavra():
    p = compile_term("obra*")
    assert p.search("execucao de obras") and p.search("obra civil")
    assert not p.search("cobra") and not p.search("manobra")
    assert compile_term("manutencao predial").search("servico de manutencao   predial")
    assert compile_term("genero* alimenticio*").search("generos alimenticios para escolas")


def test_acentos_e_caixa_nao_atrapalham(scorer):
    r = scorer.score(linha(objeto="MANUTENÇÃO PREDIAL e INSTALAÇÕES ELÉTRICAS"), AGORA)
    assert r.relevante and any("manutencao predial" in m for m in r.motivos)


def test_aquisicao_depois_de_um_nucleo_de_obra_so_penaliza(scorer):
    """'Execução de obra ... incluindo a aquisição' é obra: a aquisição vem DEPOIS, e só pesa -40."""
    obra_com_tintas = "Execução de obra de pintura com aquisição de tintas especiais"
    r = scorer.score(linha(objeto=obra_com_tintas), AGORA)
    assert "compra" not in r.flags  # não é zerada pela regra firme...
    assert not r.relevante and "termos de exclusão" in " ".join(
        r.motivos
    )  # ...mas a penalidade pesa
    # com termos fortes de sobra, a obra segue relevante mesmo citando material
    obra = "Execução de obras de reforma e ampliação, incluindo a aquisição de materiais"
    assert scorer.score(linha(objeto=obra), AGORA).relevante


@pytest.mark.parametrize(
    "objeto",
    [
        # caso real de 20/10/2026 (Porto Barreiro): 3 termos fortes somavam +70 e davam nota 56
        "AQUISIÇÃO DE MATERIAIS DE CONSTRUÇÃO VISANDO A AMPLIAÇÃO, REFORMA E MANUTENÇÃO DOS "
        "ESTABELECIMENTOS PÚBLICOS E ATENDIMENTO AS DEMAIS DEMANDAS DA ADMINISTRAÇÃO MUNICIPAL",
        "Registro de preços para futura e eventual aquisição de areias e pedras destinadas à "
        "execução de obras",
        "[Portal de Compras Públicas] - REGISTRO DE PREÇOS PARA AQUISIÇÃO DE TINTAS PARA REFORMA",
        "Fornecimento de materiais de construção, para autarquia de Serviço Autônomo de Água",
        "SRP AQUISIÇÃO DE MATERIAL PARA CONSTRUÇÃO E REFORMA DE ESCOLAS",
        "REGISTRO DE PREÇOS PARA A FUTURA E EVENTUAL AQUISIÇÃO DE MATERIAIS DE CONSTRUÇÃO",
        "Contratação para aquisição de materiais de construção e reforma",
        "Aquisições de materiais para obras de ampliação",
        # a regra olha o que o texto pede PRIMEIRO, não o começo literal (achado de 21/10/2026)
        "Pregão eletrônico visando o registro de preços para futuras aquisições de materiais",
        "Contratação de empresa para aquisição de equipamentos de informática e drone",
        "Contratação de empresa especializada na locação de máquinas pesadas para obras",
        "Materiais para manutenção e conservação predial (134 itens)",
    ],
)
def test_texto_que_pede_compra_ou_locacao_primeiro_zera_a_nota(scorer, objeto):
    r = scorer.score(linha(objeto=objeto), AGORA)
    assert r.score == 0 and not r.relevante and "compra" in r.flags
    assert "compra ou locação" in " ".join(r.motivos)


@pytest.mark.parametrize(
    "objeto",
    [
        "Contratação de empresa especializada para execução de obra de reforma, incluindo "
        "a aquisição de materiais",
        "Execução de obras de pavimentação, com fornecimento de materiais e mão de obra",
        "Contratação de empresa de engenharia para fornecimento e instalação de elevadores",
        "Registro de preços para contratação de empresa especializada em serviços de "
        "manutenção predial",
        # fornecimento + mão de obra / empreitada é contrato de obra
        "Contratação de empresa para fornecimento de materiais e mão de obra para a construção "
        "da escola",
        "Contratação sob empreitada global, com fornecimento de materiais, para reforma da creche",
        # fornecimento e aplicação/montagem é serviço
        "Registro de preços para o fornecimento e aplicação de massa asfáltica para recapeamento",
    ],
)
def test_obra_ou_servico_que_cita_material_continua_valendo(scorer, objeto):
    r = scorer.score(linha(objeto=objeto), AGORA)
    assert r.relevante and "compra" not in r.flags


def test_regra_de_compra_e_configuravel(cfg):
    from radar.config import Compra

    desligada = cfg.model_copy(deep=True)
    desligada.score.compra = Compra()
    objeto = "Aquisição de materiais para obras de reforma e ampliação"
    assert not Scorer(cfg).score(linha(objeto=objeto), AGORA).relevante
    # sem a regra, só a penalidade de -40 age e os três termos fortes a cobrem (o que a regra evita)
    assert Scorer(desligada).score(linha(objeto=objeto), AGORA).relevante


def test_termos_novos_enxergam_obras_que_o_perfil_perdia(scorer):
    """Medido em 21/10/2026 nos editais abertos: 21 de recapeamento, 15 de calçamento, 14 de muro."""
    for objeto in (
        "Execução de recapeamento asfáltico em vias urbanas",
        "Contratação de empresa para execução de calçamento intertravado",
        "Execução de muro de contenção na Travessa Tico-Tico",
        "Serviços de terraplenagem para implantação de loteamento",
        "Execução de serviços de implantação de rede coletora de esgoto",
    ):
        assert scorer.score(linha(objeto=objeto), AGORA).relevante, objeto


@pytest.mark.parametrize(
    "objeto",
    [
        "Contratação de empresa para fornecimento e instalação de tenda 10 x 10 para escolas",
        "Contratação de empresa especializada para iluminação natalina da praça",
        "Registro de preços para locação de banheiros químicos para obras e eventos",
    ],
)
def test_assuntos_que_nao_sao_obra_ficam_de_fora(scorer, objeto):
    assert not scorer.score(linha(objeto=objeto), AGORA).relevante


def test_mao_de_obra_nao_conta_como_obra(scorer):
    """Achado em dados reais (19/10/2026): contratos de limpeza e vigilância trazem 'mão de obra'."""
    limpeza = (
        "Serviços continuados de limpeza e asseio, com fornecimento de MÃO DE OBRA e materiais"
    )
    assert scorer.score(linha(objeto=limpeza), AGORA).score == 0
    assert scorer.score(linha(objeto="Serviço com mão-de-obra especializada"), AGORA).score == 0
    # obra de verdade continua pontuando, mesmo junto de "mão de obra"
    real = "Execução de obra de ampliação, incluindo mão de obra e materiais"
    assert scorer.score(linha(objeto=real), AGORA).relevante
