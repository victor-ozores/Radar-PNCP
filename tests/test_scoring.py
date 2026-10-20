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


def test_compra_de_material_nao_vira_relevante(scorer):
    """Medido em 19/10/2026: 167 dos 1.685 relevantes eram compra de material com 'aquisição'."""
    compras = [
        "Registro de preços para aquisição de materiais de construção",
        # "obra" vinha do nome da secretaria que pediu a compra de tintas
        "Aquisição de tintas para demarcação viária, atendendo a Secretaria de Serviços e Obras",
    ]
    for objeto in compras:
        r = scorer.score(linha(objeto=objeto), AGORA)
        assert not r.relevante and "termos de exclusão" in " ".join(r.motivos), objeto
    # obra de verdade, com vários termos fortes, segue relevante mesmo citando material
    obra = "Execução de obras de reforma e ampliação, incluindo a aquisição de materiais"
    assert scorer.score(linha(objeto=obra), AGORA).relevante


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
