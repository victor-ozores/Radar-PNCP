from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from helpers import FakeClient, FakeNotifier, load_sample_items
from radar.painel import JANELA_DIAS, _robo, build_painel, iso_br, rotulo_nota
from radar.pipeline import PipelineError, RunOptions, run_pipeline
from radar.scoring import Scorer
from radar.store import Store


@pytest.fixture
def cfg_pequena(cfg):
    c = cfg.model_copy(deep=True)
    c.ingestao.ufs = ["SP", "RJ"]
    c.ingestao.modalidades = [4, 6]
    return c


def edital(base, numero, objeto, prazo, **extra):
    item = dict(base)
    item.update(
        numeroControlePNCP=f"1000000000{numero:04d}-1-000{numero}/2026",
        objetoCompra=objeto,
        valorTotalEstimado=900_000.0,
        dataEncerramentoProposta=prazo.isoformat(timespec="seconds"),
        situacaoCompraId=1,
        situacaoCompraNome="Divulgada no PNCP",
    )
    item.update(extra)
    return item


def roda(tmp_path, cfg, itens, agora, **kw):
    opts = RunOptions(data_dir=tmp_path / "data", trigger="teste", **kw)
    return run_pipeline(cfg, opts, client=FakeClient(itens), notifier=FakeNotifier(), now=agora)


def le_painel(tmp_path):
    return json.loads((tmp_path / "data" / "export" / "painel.json").read_text(encoding="utf-8"))


def test_painel_so_traz_relevantes_ativos_e_dentro_da_janela(tmp_path, cfg_pequena, agora):
    base = load_sample_items()[0]  # concorrência eletrônica em SP
    obra = "Execução de obras de reforma predial da escola municipal"
    itens = [
        edital(base, 1, obra, agora + timedelta(days=10)),  # entra
        edital(base, 2, obra, agora + timedelta(days=10), situacaoCompraId=4,
               situacaoCompraNome="Suspensa"),  # suspenso
        edital(base, 3, obra, agora + timedelta(days=JANELA_DIAS + 10)),  # fora da janela de 30 dias
        edital(base, 4, obra, agora - timedelta(days=1)),  # prazo já passou
        edital(base, 5, "Registro de preços para aquisição de materiais de construção",
               agora + timedelta(days=5)),  # compra: ativo e aberto, mas não combina
    ]  # fmt: skip
    roda(tmp_path, cfg_pequena, itens, agora)
    painel = le_painel(tmp_path)

    assert [e["id"] for e in painel["editais"]] == [itens[0]["numeroControlePNCP"]]
    # "abertos" é o denominador honesto: ativos com prazo na janela (o entra e a compra)
    assert painel["totais"] == {"abertos": 2, "combinam": 1}
    assert painel["janela_dias"] == 30


def test_campos_e_fuso_do_painel(tmp_path, cfg_pequena, agora):
    base = load_sample_items()[0]
    obra = "Execução de obras de reforma predial da escola municipal"
    itens = [
        edital(base, 1, obra, agora + timedelta(days=20), registroPreco=False, srp=True),
        edital(base, 2, obra + " no bairro", agora + timedelta(days=3)),
    ]
    roda(tmp_path, cfg_pequena, itens, agora)
    painel = le_painel(tmp_path)
    em_3_dias, em_20_dias = painel["editais"]  # ordenados pelo prazo: o que vence antes vem antes

    assert em_3_dias["prazo"] == iso_br(agora + timedelta(days=3))
    assert em_20_dias["prazo"] == iso_br(agora + timedelta(days=20))
    # fuso explícito: a página não pode adivinhar o horário de Brasília
    assert painel["gerado_em"].endswith("-03:00")
    assert all(e["prazo"].endswith("-03:00") for e in painel["editais"])
    # palavras em linguagem de gente, e o link público do PNCP
    assert {"obra", "reforma"} <= set(em_3_dias["termos"])
    assert em_3_dias["link"].startswith("https://pncp.gov.br/app/editais/")
    assert em_3_dias["combina"] in {"muito", "combina", "parcial"} and 0 < em_3_dias["nota"] <= 100
    assert em_20_dias["registro_de_precos"] is True and em_3_dias["registro_de_precos"] is False


def test_arquivo_tem_um_edital_por_linha_e_e_json_valido(tmp_path, cfg_pequena, agora):
    base = load_sample_items()[0]
    itens = [
        edital(base, n, "Execução de obras de reforma predial", agora + timedelta(days=n))
        for n in (1, 2, 3)
    ]
    roda(tmp_path, cfg_pequena, itens, agora)
    texto = (tmp_path / "data" / "export" / "painel.json").read_text(encoding="utf-8")

    linhas = texto.splitlines()
    assert sum('"id":"' in ln for ln in linhas) == 3  # um por linha: diff pequeno no git
    json.loads(texto)  # e o conjunto continua sendo JSON
    assert "\r" not in texto  # LF também no Windows


def test_robo_ignora_falha_simulada_carga_inicial_e_execucoes_antigas_de_teste(
    tmp_path, cfg_pequena, agora
):
    base = load_sample_items()[0]
    itens = [edital(base, 1, "Execução de obras de reforma predial", agora + timedelta(days=9))]
    with pytest.raises(PipelineError):
        roda(tmp_path, cfg_pequena, itens, agora, simulate_failure=True)
    roda(
        tmp_path,
        cfg_pequena,
        itens,
        agora + timedelta(hours=1),
        modo="bootstrap",
        send_alerts=False,
    )
    roda(tmp_path, cfg_pequena, itens, agora + timedelta(hours=2))

    robo = le_painel(tmp_path)["robo"]
    assert len(robo["ultimas"]) == 1 and robo["ultimas"][0]["status"] == "success"
    assert robo["execucoes_30d"] == 1 and robo["taxa_sucesso_30d_pct"] == 100.0
    assert robo["ultima_execucao_ok_em"].endswith("-03:00")
    assert robo["ultima"]["novos"] == 0  # o dado já estava lá desde a carga inicial


def test_execucao_antiga_sem_a_coluna_simulado_tambem_fica_de_fora():
    agora = datetime(2026, 10, 21, 12, 0)

    def run(status, **extra):
        base = {"modo": "daily", "status": status, "started_at": agora - timedelta(hours=5),
                "finished_at": agora - timedelta(hours=4), "duration_s": 60.0, "rows_read": 10,
                "rows_new": 1, "error_message": None, "simulado": None}  # fmt: skip
        return {**base, **extra}

    robo = _robo(
        [run("success"), run("failed", error_message="falha simulada (--simulate-failure) ...")],
        agora,
    )
    assert [r["status"] for r in robo["ultimas"]] == ["success"]
    assert robo["taxa_sucesso_30d_pct"] == 100.0


def test_painel_sem_dados_nao_quebra(tmp_path, cfg):
    painel = build_painel(Store(tmp_path), Scorer(cfg), cfg, datetime(2026, 10, 21, 12, 0))
    assert painel["editais"] == [] and painel["totais"] == {"abertos": 0, "combinam": 0}
    assert painel["robo"]["ultima"] is None and painel["robo"]["taxa_sucesso_30d_pct"] is None


@pytest.mark.parametrize(
    ("nota", "rotulo"),
    [
        (100, "muito"),
        (80, "muito"),
        (79, "combina"),
        (60, "combina"),
        (59, "parcial"),
        (40, "parcial"),
    ],
)
def test_rotulo_da_nota(nota, rotulo):
    assert rotulo_nota(nota) == rotulo


def test_perfil_do_painel_vem_do_config(tmp_path, cfg_pequena, agora):
    base = load_sample_items()[0]
    roda(
        tmp_path,
        cfg_pequena,
        [edital(base, 1, "Execução de obras", agora + timedelta(days=4))],
        agora,
    )
    perfil = le_painel(tmp_path)["perfil"]
    assert perfil["ufs"] == ["SP", "RJ"] and perfil["valor_min"] == 100_000
    assert perfil["modalidades"][0].startswith("Concorrência")  # nome vindo dos dados, sem " - "
    assert "demonstração" not in perfil["nome"]  # o aviso de perfil fictício é da página
