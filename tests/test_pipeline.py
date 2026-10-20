from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import date, datetime, timedelta

import pytest

from helpers import FakeClient, FakeNotifier, load_sample_items
from radar.alerts.render import Item
from radar.audit import RunLog
from radar.pipeline import (
    PipelineError,
    RunOptions,
    plan_series,
    run_pipeline,
    selecionar_vencendo,
)
from radar.pncp_client import PncpRateLimited
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

    assert rec.status == "success" and rec.series_total == 4 and rec.series_ok == 4
    assert rec.rows_read == rec.rows_new == 20 and rec.rows_invalid == 0
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
    assert "Nenhum edital novo relevante" in notifier.enviadas[0]  # avisa mesmo sem novidades
    assert len(RunLog(Store(tmp_path / "data")).all()) == 2


def test_falha_parcial_vira_partial_e_avisa(tmp_path, cfg_pequena, agora):
    client = FakeClient(falhas={(6, "RJ"): PncpRateLimited("429 persistente")})
    notifier = FakeNotifier()
    out = run_pipeline(cfg_pequena, opts(tmp_path), client=client, notifier=notifier, now=agora)

    rec = out.record
    assert rec.status == "partial" and rec.series_ok == 3
    assert (
        rec.series_failed[0]["serie"].startswith("6/RJ")
        and rec.series_failed[0]["erro"] == "PncpRateLimited"
    )
    assert "1 de 4 buscas falharam" in notifier.enviadas[0]
    badge = json.loads((tmp_path / "data" / "badge.json").read_text(encoding="utf-8"))
    assert badge["color"] == "yellow"


def test_todas_as_buscas_falhando_registra_falha_e_levanta(tmp_path, cfg_pequena, agora):
    client = FakeClient(falha_total=PncpRateLimited("429 persistente"))
    notifier = FakeNotifier()
    with pytest.raises(PipelineError, match="todas as 4 buscas falharam"):
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
    with pytest.raises(PipelineError):
        plan_series(cfg_pequena, RunOptions(data_dir=".", modo="backfill"), date(2026, 10, 17))


def test_janela_diaria_cobre_o_lookback(cfg):
    series, ini, fim = plan_series(cfg, RunOptions(data_dir="."), date(2026, 10, 19))
    assert (ini, fim) == (date(2026, 10, 17), date(2026, 10, 19))  # hoje + 2 dias anteriores
    assert len(series) == len(cfg.ingestao.ufs) * len(cfg.ingestao.modalidades)


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
    assert "Prazos chegando" in texto and "Nenhum edital novo relevante" in texto
    assert datetime.fromisoformat(itens[0]["dataEncerramentoProposta"]).strftime("%d/%m") in texto
