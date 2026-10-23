from __future__ import annotations

import copy
import csv
import hashlib
import json
import re
from datetime import date, datetime, timedelta

import pytest

from helpers import FakeClient, FakeNotifier, load_sample_items
from radar.alerts.render import Item
from radar.audit import RunLog
from radar.normalize import SITUACAO_EXCLUIDA
from radar.pipeline import (
    PipelineError,
    RunOptions,
    plan_series,
    run_pipeline,
    selecionar_vencendo,
)
from radar.pncp_client import PncpRateLimited, PncpServerError
from radar.scoring import ScoreResult
from radar.store import Store

CPF = re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}")


@pytest.fixture
def cfg_pequena(cfg):
    """Mesmo perfil, mas só as buscas que a amostra cobre (pregão/concorrência em SP e RJ)."""
    c = cfg.model_copy(deep=True)
    c.ingestao.ufs = ["SP", "RJ"]
    c.ingestao.modalidades = [4, 6]
    return c


def opts(tmp_path, **kw):
    return RunOptions(data_dir=tmp_path / "data", trigger="teste", **kw)


def hashes(data_dir):
    return {
        str(p.relative_to(data_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((data_dir / "warehouse" / "contratacoes").glob("dt=*/part.parquet"))
    }


def test_execucao_diaria_completa(tmp_path, cfg_pequena, agora):
    notifier = FakeNotifier()
    out = run_pipeline(
        cfg_pequena, opts(tmp_path), client=FakeClient(), notifier=notifier, now=agora
    )
    rec, data = out.record, tmp_path / "data"

    # 4 buscas de novos (modalidade x UF) + as mesmas 4 de alterados (consulta por atualização)
    assert rec.status == "success" and rec.series_total == 8 and rec.series_ok == 8
    assert rec.rows_read == rec.rows_new == 20 and rec.rows_invalid == 0
    assert rec.rows_atualizacao == 0 and rec.prazos_alterados == 0
    assert rec.alert_sent and notifier.enviadas and rec.finished_at is not None
    assert hashes(data), "esperava partições Parquet"

    with open(data / "export" / "editais.csv", encoding="utf-8-sig", newline="") as fh:
        editais = list(csv.DictReader(fh))
    assert len(editais) == 20
    assert {"id", "score", "relevante", "motivos", "link_pncp"} <= set(editais[0])

    runs = RunLog(Store(data)).all()
    assert [r["status"] for r in runs] == ["success"]
    status = json.loads((data / "status.json").read_text(encoding="utf-8"))
    assert status["ultima_execucao"]["status"] == "success" and status["execucoes_total"] == 1
    badge = json.loads((data / "badge.json").read_text(encoding="utf-8"))
    assert badge["color"] == "brightgreen" and badge["schemaVersion"] == 1


def test_segunda_execucao_e_idempotente(tmp_path, cfg_pequena, agora):
    run_pipeline(
        cfg_pequena, opts(tmp_path), client=FakeClient(), notifier=FakeNotifier(), now=agora
    )
    antes = hashes(tmp_path / "data")

    notifier = FakeNotifier()
    out = run_pipeline(
        cfg_pequena,
        opts(tmp_path),
        client=FakeClient(),
        notifier=notifier,
        now=agora + timedelta(hours=24),
    )

    assert out.record.rows_new == 0 and out.record.rows_unchanged == 20
    assert hashes(tmp_path / "data") == antes  # nenhum byte mudou
    assert "Nenhum edital novo combina" in notifier.enviadas[0]  # avisa mesmo sem novidades
    assert len(RunLog(Store(tmp_path / "data")).all()) == 2


def test_falha_parcial_vira_partial_e_avisa(tmp_path, cfg_pequena, agora):
    client = FakeClient(falhas={(6, "RJ"): PncpRateLimited("429 persistente")})
    notifier = FakeNotifier()
    out = run_pipeline(cfg_pequena, opts(tmp_path), client=client, notifier=notifier, now=agora)

    rec = out.record
    assert rec.status == "partial" and rec.series_ok == 7
    assert (
        rec.series_failed[0]["serie"].startswith("6/RJ")
        and rec.series_failed[0]["erro"] == "PncpRateLimited"
    )
    assert "1 de 8 buscas falharam" in notifier.enviadas[0]
    badge = json.loads((tmp_path / "data" / "badge.json").read_text(encoding="utf-8"))
    assert badge["color"] == "yellow"


def test_todas_as_buscas_falhando_registra_falha_e_levanta(tmp_path, cfg_pequena, agora):
    client = FakeClient(falha_total=PncpRateLimited("429 persistente"))
    notifier = FakeNotifier()
    with pytest.raises(PipelineError, match="todas as 8 buscas falharam"):
        run_pipeline(cfg_pequena, opts(tmp_path), client=client, notifier=notifier, now=agora)

    runs = RunLog(Store(tmp_path / "data")).all()
    assert runs[0]["status"] == "failed" and runs[0]["error_type"] == "PipelineError"
    status = json.loads((tmp_path / "data" / "status.json").read_text(encoding="utf-8"))
    assert (
        status["ultima_execucao"]["status"] == "failed" and status["ultima_execucao_ok_em"] is None
    )
    assert notifier.enviadas == []  # o alerta de falha é do workflow (notify-failure)


def test_falha_simulada_fica_registrada(tmp_path, cfg_pequena, agora):
    with pytest.raises(PipelineError, match="simulada"):
        run_pipeline(
            cfg_pequena, opts(tmp_path, simulate_failure=True), client=FakeClient(), now=agora
        )
    assert RunLog(Store(tmp_path / "data")).all()[0]["status"] == "failed"


def test_erro_ao_enviar_alerta_falha_a_execucao_mas_guarda_os_dados(tmp_path, cfg_pequena, agora):
    notifier = FakeNotifier(falha=RuntimeError("telegram fora do ar"))
    with pytest.raises(RuntimeError):
        run_pipeline(cfg_pequena, opts(tmp_path), client=FakeClient(), notifier=notifier, now=agora)
    data = tmp_path / "data"
    assert hashes(data), "os editais já tinham sido gravados"
    assert RunLog(Store(data)).all()[0]["status"] == "failed"


def test_api_que_ignora_filtro_de_uf_e_detectada(tmp_path, cfg_pequena, agora):
    out = run_pipeline(
        cfg_pequena,
        opts(tmp_path),
        client=FakeClient(ignora_uf=True),
        notifier=FakeNotifier(),
        now=agora,
    )
    assert out.record.uf_mismatch > 0
    store = Store(tmp_path / "data")
    por_uf = {r["uf"] for r in store.current_state()}
    assert por_uf == {"SP", "RJ"}
    assert len(store.current_state()) == 20  # sem duplicar nem trocar de UF


def test_dry_run_nao_grava_nada(tmp_path, cfg_pequena, agora):
    notifier = FakeNotifier()
    out = run_pipeline(
        cfg_pequena, opts(tmp_path, dry_run=True), client=FakeClient(), notifier=notifier, now=agora
    )
    assert not (tmp_path / "data").exists()
    assert notifier.enviadas == [] and out.mensagens, "mostra prévia mas não envia"


def test_sem_notifier_roda_sem_alertar(tmp_path, cfg_pequena, agora):
    out = run_pipeline(cfg_pequena, opts(tmp_path), client=FakeClient(), notifier=None, now=agora)
    assert out.record.status == "success" and not out.record.alert_sent


def test_nenhum_cpf_chega_ao_warehouse(tmp_path, cfg_pequena, agora):
    itens = load_sample_items()
    itens[0]["objetoCompra"] = (
        "Reforma de escola. Responsável CPF 123.456.789-09, fone (11) 91234-5678"
    )
    itens[0]["processo"] = "Proc. 987.654.321-00"
    run_pipeline(
        cfg_pequena, opts(tmp_path), client=FakeClient(itens), notifier=FakeNotifier(), now=agora
    )

    store = Store(tmp_path / "data")
    texto = " ".join(
        str(v)
        for r in store.current_state()
        for v in (r["objeto"], r["processo"], r["informacao_complementar"])
    )
    assert not CPF.search(texto)
    csv_txt = (tmp_path / "data" / "export" / "editais.csv").read_text(encoding="utf-8-sig")
    assert not CPF.search(csv_txt) and "91234" not in csv_txt
    assert RunLog(store).all()[0]["pii_redactions"] >= 3


def test_registro_invalido_nao_derruba_a_execucao(tmp_path, cfg_pequena, agora):
    itens = load_sample_items()
    itens[0]["numeroControlePNCP"] = None
    out = run_pipeline(
        cfg_pequena, opts(tmp_path), client=FakeClient(itens), notifier=FakeNotifier(), now=agora
    )
    assert out.record.rows_invalid == 1 and out.record.rows_new == 19
    assert out.record.quality_warnings["registro_invalido"] == 1


def test_bootstrap_usa_proposta_e_nao_alerta(tmp_path, cfg_pequena, agora):
    client, notifier = FakeClient(), FakeNotifier()
    out = run_pipeline(
        cfg_pequena,
        opts(tmp_path, modo="bootstrap", send_alerts=False),
        client=client,
        notifier=notifier,
        now=agora,
    )
    assert {c[0] for c in client.chamadas} == {"proposta"}
    assert out.record.modo == "bootstrap" and out.record.rows_new == 20 and notifier.enviadas == []


def test_backfill_divide_em_blocos_e_valida_janela(cfg_pequena):
    o = RunOptions(data_dir=".", modo="backfill", desde=date(2026, 9, 1), ate=date(2026, 9, 20))
    series, ini, fim = plan_series(cfg_pequena, o, date(2026, 10, 17))
    blocos = {(s.inicio, s.fim) for s in series}
    assert blocos == {
        (date(2026, 9, 1), date(2026, 9, 7)),
        (date(2026, 9, 8), date(2026, 9, 14)),
        (date(2026, 9, 15), date(2026, 9, 20)),
    }
    assert (ini, fim) == (date(2026, 9, 1), date(2026, 9, 20))
    # o reprocessamento também lê os ALTERADOS do período (recupera prorrogações perdidas)
    assert {s.feed for s in series} == {"publicacao", "atualizacao"}
    with pytest.raises(PipelineError):
        plan_series(cfg_pequena, RunOptions(data_dir=".", modo="backfill"), date(2026, 10, 17))


def test_janela_diaria_cobre_o_lookback(cfg):
    series, ini, fim = plan_series(cfg, RunOptions(data_dir="."), date(2026, 10, 19))
    assert (ini, fim) == (date(2026, 10, 17), date(2026, 10, 19))  # hoje + 2 dias anteriores
    por_feed = len(cfg.ingestao.ufs) * len(cfg.ingestao.modalidades)
    assert len(series) == 2 * por_feed  # novos (publicação) e alterados (atualização)
    assert [s.feed for s in series[:por_feed]] == ["publicacao"] * por_feed  # novos primeiro


def test_carga_inicial_nao_consulta_alterados(cfg):
    series, _, _ = plan_series(cfg, RunOptions(data_dir=".", modo="bootstrap"), date(2026, 10, 19))
    assert {s.feed for s in series} == {"publicacao"}


def _alterado(sample, **mudancas):
    """Cópia do primeiro edital da amostra, como a consulta por atualização o devolveria."""
    item = dict(sample[0])
    item.update(mudancas)
    return item


def test_atualizacao_detecta_prorrogacao_e_suspensao(tmp_path, cfg_pequena, agora):
    """Medido em 21/10/2026: ~1% dos editais com prazo em até 7 dias tinha sido prorrogado."""
    amostra = load_sample_items()
    run_pipeline(
        cfg_pequena, opts(tmp_path), client=FakeClient(amostra), notifier=FakeNotifier(), now=agora
    )
    original = amostra[0]
    alterados = [
        _alterado(amostra, dataEncerramentoProposta="2026-12-10T09:59:00",
                  dataAtualizacaoGlobal="2026-10-20T16:01:00"),
        # outro edital: suspenso depois de publicado
        {**amostra[1], "situacaoCompraId": 4, "situacaoCompraNome": "Suspensa",
         "dataAtualizacaoGlobal": "2026-10-20T17:00:00"},
    ]  # fmt: skip
    cliente = FakeClient(amostra, atualizados=alterados)
    out = run_pipeline(
        cfg_pequena,
        opts(tmp_path),
        client=cliente,
        notifier=FakeNotifier(),
        now=agora + timedelta(hours=24),
    )

    rec = out.record
    assert rec.prazos_alterados == 1 and rec.situacoes_alteradas == 1
    assert rec.rows_updated == 2 and rec.rows_new == 0
    assert rec.rows_atualizacao == 2
    assert {c[0] for c in cliente.chamadas} == {"publicacao", "atualizacao"}
    guardado = Store(tmp_path / "data").current_state(
        "WHERE id = ?", [original["numeroControlePNCP"]]
    )[0]
    assert guardado["data_encerramento_proposta"] == datetime(2026, 12, 10, 9, 59)
    assert guardado["first_seen_at"] == agora  # continua sendo o mesmo edital, visto desde o dia 1
    # a execução fica registrada com os contadores novos
    assert RunLog(Store(tmp_path / "data")).all()[-1]["prazos_alterados"] == 1


def test_atualizacao_traz_edital_antigo_que_o_robo_nao_tinha(tmp_path, cfg_pequena, agora):
    """Edital publicado em maio e reaberto/alterado agora: só a consulta por atualização o traz."""
    amostra = load_sample_items()
    antigo = _alterado(
        amostra,
        numeroControlePNCP="11111111000111-1-000001/2026",
        dataPublicacaoPncp="2026-05-13T14:10:00",
        dataAtualizacaoGlobal="2026-10-20T10:00:00",
    )
    out = run_pipeline(
        cfg_pequena,
        opts(tmp_path),
        client=FakeClient(amostra, atualizados=[antigo]),
        notifier=FakeNotifier(),
        now=agora,
    )
    assert out.record.rows_new == 21  # 20 da amostra + o antigo
    assert (tmp_path / "data/warehouse/contratacoes/dt=2026-05-13/part.parquet").exists()


def test_atualizacao_ignora_edital_encerrado_que_nao_conheciamos(tmp_path, cfg_pequena, agora):
    """21/10/2026: 3.993 de 6.004 linhas da consulta eram homologações de processos já encerrados."""
    amostra = load_sample_items()
    encerrado = _alterado(
        amostra,
        numeroControlePNCP="33333333000133-1-000001/2026",
        dataPublicacaoPncp="2025-03-02T09:00:00",
        dataEncerramentoProposta="2025-03-20T10:00:00",
        dataAtualizacaoGlobal="2026-10-16T10:00:00",
    )
    out = run_pipeline(
        cfg_pequena,
        opts(tmp_path),
        client=FakeClient(amostra, atualizados=[encerrado]),
        notifier=FakeNotifier(),
        now=agora,
    )
    rec = out.record
    assert rec.rows_atualizacao == 1 and rec.rows_new == 20  # o encerrado não entrou
    assert rec.quality_warnings["atualizacao_encerrada_ignorada"] == 1
    assert not (tmp_path / "data/warehouse/contratacoes/dt=2025-03-02").exists()


def test_atualizacao_aplica_quando_um_edital_aberto_passa_a_encerrado(tmp_path, cfg_pequena, agora):
    """Prazo antecipado ou processo encerrado: o edital deixa de aparecer como aberto."""
    amostra = load_sample_items()
    run_pipeline(
        cfg_pequena, opts(tmp_path), client=FakeClient(amostra), notifier=FakeNotifier(), now=agora
    )
    agora2 = agora + timedelta(hours=24)
    antecipado = _alterado(
        amostra,
        dataEncerramentoProposta=(agora2 - timedelta(hours=4)).isoformat(timespec="seconds"),
        dataAtualizacaoGlobal=agora2.isoformat(timespec="seconds"),
    )
    out = run_pipeline(
        cfg_pequena,
        opts(tmp_path),
        client=FakeClient(amostra, atualizados=[antecipado]),
        notifier=FakeNotifier(),
        now=agora2,
    )
    assert out.record.prazos_alterados == 1  # estava aberto e agora encerrou: precisa ser gravado
    guardado = Store(tmp_path / "data").current_state(
        "WHERE id = ?", [amostra[0]["numeroControlePNCP"]]
    )
    assert guardado[0]["data_encerramento_proposta"] < agora2


def test_alterados_usam_um_periodo_proprio_menor(cfg):
    series, _, _ = plan_series(cfg, RunOptions(data_dir="."), date(2026, 10, 19))
    novos = {s.inicio for s in series if s.feed == "publicacao"}
    alterados = {s.inicio for s in series if s.feed == "atualizacao"}
    assert cfg.ingestao.lookback_dias == 3 and cfg.ingestao.lookback_atualizacao_dias == 2
    assert novos == {date(2026, 10, 17)} and alterados == {date(2026, 10, 18)}
    assert {s.fim for s in series} == {date(2026, 10, 19)}


def test_cabecalho_conta_os_novos_lidos_como_a_tabela_de_execucoes(tmp_path, cfg_pequena, agora):
    """O "novos lidos" do Telegram é o mesmo número de `rows_new` em pipeline_runs."""
    amostra = load_sample_items()
    extras = [
        _alterado(amostra, numeroControlePNCP=f"2222222200011{i}-1-00000{i}/2026") for i in range(3)
    ]
    notifier = FakeNotifier()
    out = run_pipeline(
        cfg_pequena,
        opts(tmp_path),
        client=FakeClient(amostra, atualizados=extras),
        notifier=notifier,
        now=agora,
    )
    assert out.record.rows_new == 23  # 20 da busca por publicação + 3 que só a atualização trouxe
    assert "entre 23 novos lidos hoje" in notifier.enviadas[0]


def test_alerta_leva_o_link_do_painel_da_configuracao(tmp_path, cfg_pequena, agora):
    notifier = FakeNotifier()
    run_pipeline(cfg_pequena, opts(tmp_path), client=FakeClient(), notifier=notifier, now=agora)
    assert (
        f'<a href="{cfg_pequena.alerta.painel_url}">Ver todos no painel</a>' in notifier.enviadas[0]
    )
    sem_link = cfg_pequena.model_copy(deep=True)
    sem_link.alerta.painel_url = None
    notifier2 = FakeNotifier()
    run_pipeline(
        sem_link, opts(tmp_path / "outro"), client=FakeClient(), notifier=notifier2, now=agora
    )
    assert "painel" not in notifier2.enviadas[0]


def test_falha_so_na_consulta_de_atualizacao_vira_partial(tmp_path, cfg_pequena, agora):
    client = FakeClient(falhas_atualizacao={(4, "SP"): PncpRateLimited("429 persistente")})
    notifier = FakeNotifier()
    out = run_pipeline(cfg_pequena, opts(tmp_path), client=client, notifier=notifier, now=agora)
    rec = out.record
    assert rec.status == "partial" and rec.series_ok == 7
    assert rec.series_failed[0]["serie"].startswith("atualizacao:4/SP")
    assert "atualizacao:4/SP" in notifier.enviadas[0]
    assert rec.rows_new == 20  # a coleta de novos não foi afetada


def test_prazos_chegando_so_lista_o_que_ainda_da_tempo_de_disputar(cfg, agora):
    """No Telegram real, a seção listava editais que venciam em poucas horas."""

    def item(id_, horas, relevante=True):
        row = {"id": id_, "data_encerramento_proposta": agora + timedelta(hours=horas)}
        return Item(row, ScoreResult(80, relevante, []))

    assert (cfg.alerta.prazo_minimo_dias, cfg.alerta.dias_prazo_proximo) == (2, 7)
    candidatos = [
        item("daqui_5h", 5),  # cedo demais
        item("daqui_30h", 30),  # cedo demais (menos de 2 dias)
        item("limite_minimo", 48),
        item("meio", 100),
        item("limite_maximo", 168),
        item("longe_demais", 169),
        item("irrelevante", 100, relevante=False),
        item("ja_no_resumo", 100),
    ]
    escolhidos = selecionar_vencendo(candidatos, agora, cfg.alerta, {"ja_no_resumo"})
    assert [i.row["id"] for i in escolhidos] == ["limite_minimo", "meio", "limite_maximo"]


def test_alerta_traz_vencendo_sem_repetir_os_novos(tmp_path, cfg_pequena, agora):
    """No dia 2, editais já conhecidos com prazo curto aparecem em 'Prazos chegando'."""
    itens = load_sample_items()
    for i in itens:
        i["objetoCompra"] = "Execução de obras de reforma predial"
        i["valorTotalEstimado"] = 900_000.0
        i["situacaoCompraId"], i["situacaoCompraNome"] = 1, "Divulgada no PNCP"
        i["dataEncerramentoProposta"] = (agora + timedelta(days=3)).isoformat(timespec="seconds")
    run_pipeline(
        cfg_pequena, opts(tmp_path), client=FakeClient(itens), notifier=FakeNotifier(), now=agora
    )

    notifier = FakeNotifier()
    run_pipeline(
        cfg_pequena, opts(tmp_path), client=FakeClient(itens), notifier=notifier,
        now=agora + timedelta(hours=1),
    )  # fmt: skip
    texto = "\n".join(notifier.enviadas)
    assert "Prazos chegando" in texto and "Nenhum edital novo combina" in texto
    assert datetime.fromisoformat(itens[0]["dataEncerramentoProposta"]).strftime("%d/%m") in texto


# --------------------------------------------------------------------- conferência semanal e no alerta


def _abertos(tmp_path, cfg, agora, dias=5, relevantes=False):
    """Guarda a amostra como editais abertos (prazo daqui a `dias`) e devolve os itens brutos."""
    itens = load_sample_items()
    for n, i in enumerate(itens, 1):
        i["situacaoCompraId"], i["situacaoCompraNome"] = 1, "Divulgada no PNCP"
        i["dataEncerramentoProposta"] = (agora + timedelta(days=dias)).isoformat(timespec="seconds")
        if relevantes:
            # texto diferente em cada um: edital com o mesmo texto, órgão, valor e prazo é "repetido"
            i["objetoCompra"] = f"Execução de obras de reforma predial, lote {n}"
            i["valorTotalEstimado"] = 900_000.0
    run_pipeline(cfg, opts(tmp_path), client=FakeClient(itens), notifier=FakeNotifier(), now=agora)
    return itens


def _id(item):
    return item["numeroControlePNCP"]


def _compras_chamadas(client):
    return [c for c in client.chamadas if c[0] == "compra"]


def _estado(tmp_path):
    return {r["id"]: r for r in Store(tmp_path / "data").current_state()}


def test_reconciliacao_usa_as_propostas_abertas_ate_a_janela_do_config(cfg):
    hoje = date(2026, 10, 19)
    series, inicio, fim = plan_series(cfg, RunOptions(data_dir=".", modo="reconcile"), hoje)
    assert len(series) == 16 and {s.feed for s in series} == {"publicacao"}
    assert (inicio, fim) == (hoje, hoje + timedelta(days=cfg.ingestao.reconciliacao_dias))
    assert {s.fim for s in series} == {fim} and {s.inicio for s in series} == {None}
    _, _, fim5 = plan_series(
        cfg, RunOptions(data_dir=".", modo="reconcile", reconciliar_dias=5), hoje
    )
    assert fim5 == hoje + timedelta(days=5)


def test_conferencia_semanal_corrige_o_que_a_listagem_nao_confirma(tmp_path, cfg_pequena, agora):
    itens = _abertos(tmp_path, cfg_pequena, agora)
    excluido, prorrogado, incerto, *na_listagem = itens
    mudou = {
        **prorrogado,
        "dataEncerramentoProposta": (agora + timedelta(days=40)).isoformat(timespec="seconds"),
    }
    client = FakeClient(
        na_listagem,
        compras={_id(excluido): None, _id(prorrogado): mudou, _id(incerto): PncpServerError("x")},
    )
    notifier = FakeNotifier()
    out = run_pipeline(
        cfg_pequena,
        opts(tmp_path, modo="reconcile"),
        client=client,
        notifier=notifier,
        now=agora + timedelta(days=1),
    )
    rec, estado = out.record, _estado(tmp_path)

    assert rec.status == "success" and rec.rows_read == len(na_listagem) and rec.rows_new == 0
    assert estado[_id(excluido)]["situacao_id"] == SITUACAO_EXCLUIDA
    assert estado[_id(prorrogado)]["data_encerramento_proposta"] == agora + timedelta(days=40)
    assert estado[_id(incerto)]["situacao_id"] == 1  # na dúvida, não mexe
    conferidos = {k: v for k, v in rec.quality_warnings.items() if k.startswith("conferido_")}
    assert conferidos == {
        "conferido_excluido": 1,
        "conferido_atualizado": 1,
        "conferido_incerto": 1,
    }
    assert rec.prazos_alterados == 1 and rec.situacoes_alteradas == 1
    assert len(_compras_chamadas(client)) == 3  # só os 3 que a listagem não trouxe
    assert notifier.enviadas == [] and not rec.alert_sent  # conferência não manda alerta


def test_conferencia_ignora_serie_que_falhou(tmp_path, cfg_pequena, agora):
    """Se a busca de 4/SP caiu, o que sumiu dela não prova nada: nenhuma consulta individual."""
    itens = _abertos(tmp_path, cfg_pequena, agora)
    client = FakeClient(itens, falhas={(4, "SP"): PncpRateLimited("429 persistente")})
    out = run_pipeline(
        cfg_pequena,
        opts(tmp_path, modo="reconcile"),
        client=client,
        notifier=FakeNotifier(),
        now=agora + timedelta(days=1),
    )
    assert out.record.status == "partial"
    assert _compras_chamadas(client) == []
    assert all(r["situacao_id"] == 1 for r in _estado(tmp_path).values())


def test_conferencia_para_quando_o_pncp_nao_responde(tmp_path, cfg_pequena, agora):
    itens = _abertos(tmp_path, cfg_pequena, agora)
    compras = {_id(i): PncpServerError("fora do ar") for i in itens}
    client = FakeClient([], compras=compras)  # a listagem veio vazia: tudo é suspeito
    out = run_pipeline(
        cfg_pequena,
        opts(tmp_path, modo="reconcile"),
        client=client,
        notifier=FakeNotifier(),
        now=agora + timedelta(days=1),
    )
    assert len(_compras_chamadas(client)) == 2  # duas respostas incertas seguidas: chega
    qw = out.record.quality_warnings
    assert qw["conferido_incerto"] == 2 and qw["conferencia_pendente"] == len(itens) - 2
    assert all(r["situacao_id"] == 1 for r in _estado(tmp_path).values())


def test_conferencia_respeita_o_maximo_por_execucao(tmp_path, cfg_pequena, agora):
    itens = _abertos(tmp_path, cfg_pequena, agora)
    cfg = cfg_pequena.model_copy(deep=True)
    cfg.ingestao.conferencias_max = 3
    client = FakeClient([])  # nada na listagem e nada na consulta individual: "excluído"
    out = run_pipeline(
        cfg,
        opts(tmp_path, modo="reconcile"),
        client=client,
        notifier=None,
        now=agora + timedelta(days=1),
    )
    qw = out.record.quality_warnings
    assert len(_compras_chamadas(client)) == 3
    assert qw["conferido_excluido"] == 3 and qw["conferencia_pendente"] == len(itens) - 3


def test_prazos_chegando_nao_lista_excluido_nem_prorrogado_e_corrige_o_guardado(
    tmp_path, cfg_pequena, agora
):
    itens = _abertos(tmp_path, cfg_pequena, agora, dias=3, relevantes=True)
    ordem = sorted(itens, key=_id)  # prazos iguais: "Prazos chegando" sai na ordem do id
    excluido, prorrogado = ordem[0], ordem[1]
    mudou = {
        **prorrogado,
        "dataEncerramentoProposta": (agora + timedelta(days=30)).isoformat(timespec="seconds"),
    }
    client = FakeClient(itens, compras={_id(excluido): None, _id(prorrogado): mudou})
    notifier = FakeNotifier()
    run_pipeline(
        cfg_pequena,
        opts(tmp_path),
        client=client,
        notifier=notifier,
        now=agora + timedelta(hours=1),
    )
    texto = "\n".join(notifier.enviadas)

    listados = set(re.findall(r"editais/(\d{14}/\d{4}/\d+)", texto))
    for fora in (excluido, prorrogado):
        endereco = f"{fora['orgaoEntidade']['cnpj']}/{fora['anoCompra']}/{fora['sequencialCompra']}"
        assert endereco not in listados
    assert len(listados) == 5  # a lista continua cheia: entraram os seguintes
    assert (
        "Mais 13 outros vencem nesse período" in texto
    )  # 20 na janela - 2 que saíram - 5 listados
    estado = _estado(tmp_path)
    assert estado[_id(excluido)]["situacao_id"] == SITUACAO_EXCLUIDA
    assert estado[_id(prorrogado)]["data_encerramento_proposta"] == agora + timedelta(days=30)
    assert len(_compras_chamadas(client)) == 7  # os 5 listados + os 2 que saíram


def test_erro_na_conferencia_do_alerta_nao_impede_o_alerta(tmp_path, cfg_pequena, agora):
    itens = _abertos(tmp_path, cfg_pequena, agora, dias=3, relevantes=True)
    client = FakeClient(itens, compras={_id(i): PncpServerError("fora do ar") for i in itens})
    notifier = FakeNotifier()
    out = run_pipeline(
        cfg_pequena,
        opts(tmp_path),
        client=client,
        notifier=notifier,
        now=agora + timedelta(hours=1),
    )
    assert out.record.alert_sent and "Prazos chegando" in "\n".join(notifier.enviadas)
    assert len(_compras_chamadas(client)) == 2  # parou depois de 2 incertas seguidas
    assert all(r["situacao_id"] == 1 for r in _estado(tmp_path).values())


def test_conferencia_do_alerta_respeita_o_orcamento_e_a_previa_nao_confere(
    tmp_path, cfg_pequena, agora
):
    itens = _abertos(tmp_path, cfg_pequena, agora, dias=3, relevantes=True)
    cfg = cfg_pequena.model_copy(deep=True)
    cfg.ingestao.conferencias_alerta_max = 2
    client = FakeClient(itens)
    run_pipeline(
        cfg, opts(tmp_path), client=client, notifier=FakeNotifier(), now=agora + timedelta(hours=1)
    )
    assert len(_compras_chamadas(client)) == 2

    previa = FakeClient(itens)
    run_pipeline(
        cfg_pequena,
        opts(tmp_path, dry_run=True),
        client=previa,
        notifier=None,
        now=agora + timedelta(hours=2),
    )
    assert _compras_chamadas(previa) == []  # a prévia não grava, então também não confere


# --------------------------------------------------------------------- edital publicado duas vezes


def _gemeos(agora, dias=5, n=2):
    """Registros do mesmo edital no PNCP (órgão, texto, valor e prazo iguais); o último é o republicado."""
    base = load_sample_items()[0]
    cnpj = base["orgaoEntidade"]["cnpj"]
    registros = []
    for k in range(n):
        r = copy.deepcopy(base)
        seq = 101 + 9 * k
        r.update(
            numeroControlePNCP=f"{cnpj}-1-{seq:06d}/2026",
            sequencialCompra=seq,
            anoCompra=2026,
            numeroCompra="34" if k == 0 else f"34/2026REPUBLICADO{k}",
            dataPublicacaoPncp=(agora - timedelta(days=3, hours=-3 * k)).isoformat(
                timespec="seconds"
            ),
            objetoCompra="Execução de obras de reforma predial",
            valorTotalEstimado=900_000.0,
            dataEncerramentoProposta=(agora + timedelta(days=dias)).isoformat(timespec="seconds"),
            situacaoCompraId=1,
            situacaoCompraNome="Divulgada no PNCP",
        )
        registros.append(r)
    return registros


def _cnpj():
    return load_sample_items()[0]["orgaoEntidade"]["cnpj"]


def test_alerta_mostra_uma_vez_o_edital_publicado_duas_vezes(tmp_path, cfg_pequena, agora):
    original, republicado = _gemeos(agora)
    notifier = FakeNotifier()
    out = run_pipeline(
        cfg_pequena,
        opts(tmp_path),
        client=FakeClient([original, republicado]),
        notifier=notifier,
        now=agora,
    )
    texto = "\n".join(notifier.enviadas)

    assert texto.count("🏛") == 1 and "<b>1</b> edital novo combina com o perfil" in texto
    assert out.record.rows_relevant_new == 2  # o registro da execução conta os dois, a mensagem um
    # o principal é o publicado por último; o original vira "também publicado como"
    assert f"{_cnpj()}/2026/110" in texto
    assert (
        f'🔁 Também publicado como <a href="https://pncp.gov.br/app/editais/{_cnpj()}/2026/101">'
        in texto
    )
    assert "nº 34/2026</a>" in texto


def test_republicacao_de_edital_que_o_robo_ja_tinha_traz_o_numero_do_antigo(
    tmp_path, cfg_pequena, agora
):
    original, republicado = _gemeos(agora)
    run_pipeline(
        cfg_pequena,
        opts(tmp_path),
        client=FakeClient([original]),
        notifier=FakeNotifier(),
        now=agora - timedelta(days=1),
    )
    notifier = FakeNotifier()
    run_pipeline(
        cfg_pequena,
        opts(tmp_path),
        client=FakeClient([original, republicado]),
        notifier=notifier,
        now=agora,
    )
    texto = "\n".join(notifier.enviadas)
    assert "<b>1</b> edital novo combina" in texto and texto.count("🏛") == 1
    assert "nº 34/2026</a>" in texto  # o antigo, que já estava guardado
    assert "Prazos chegando" not in texto  # e não volta na outra seção como se fosse outro edital


def test_prazos_chegando_confere_os_dois_registros_e_nao_cita_o_excluido(
    tmp_path, cfg_pequena, agora
):
    original, republicado = _gemeos(agora)
    run_pipeline(
        cfg_pequena,
        opts(tmp_path),
        client=FakeClient([original, republicado]),
        notifier=FakeNotifier(),
        now=agora,
    )
    client = FakeClient([original, republicado], compras={_id(original): None})  # o PNCP excluiu
    notifier = FakeNotifier()
    run_pipeline(
        cfg_pequena,
        opts(tmp_path),
        client=client,
        notifier=notifier,
        now=agora + timedelta(hours=1),
    )
    texto = "\n".join(notifier.enviadas)

    assert "Prazos chegando" in texto and texto.count("🏛") == 1
    assert "🔁" not in texto  # o outro registro foi excluído: não é "também publicado como"
    assert _estado(tmp_path)[_id(original)]["situacao_id"] == SITUACAO_EXCLUIDA
    assert len(_compras_chamadas(client)) == 2  # cada registro foi conferido


def test_prazos_chegando_com_os_dois_registros_vivos_cita_o_outro(tmp_path, cfg_pequena, agora):
    original, republicado = _gemeos(agora)
    run_pipeline(
        cfg_pequena,
        opts(tmp_path),
        client=FakeClient([original, republicado]),
        notifier=FakeNotifier(),
        now=agora,
    )
    client = FakeClient([original, republicado])
    notifier = FakeNotifier()
    run_pipeline(
        cfg_pequena,
        opts(tmp_path),
        client=client,
        notifier=notifier,
        now=agora + timedelta(hours=1),
    )
    texto = "\n".join(notifier.enviadas)

    assert texto.count("🏛") == 1 and f"{_cnpj()}/2026/110" in texto
    assert "🔁 Também publicado como" in texto and "nº 34/2026</a>" in texto
    assert len(_compras_chamadas(client)) == 2


def test_tres_registros_do_mesmo_edital_viram_um_com_e_mais_um(tmp_path, cfg_pequena, agora):
    notifier = FakeNotifier()
    run_pipeline(
        cfg_pequena,
        opts(tmp_path),
        client=FakeClient(_gemeos(agora, n=4)),
        notifier=notifier,
        now=agora,
    )
    texto = "\n".join(notifier.enviadas)
    assert texto.count("🏛") == 1 and texto.count("🔁") == 1 and " e mais 1" in texto
