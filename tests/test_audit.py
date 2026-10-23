from __future__ import annotations

from datetime import datetime, timedelta

from radar.audit import build_badge, build_status, execucoes_diarias, simulada

AGORA = datetime(2026, 10, 25, 13, 0)  # domingo, dia da conferência semanal


def _run(run_id, modo="daily", status="success", dias_atras=0.0, **extra):
    inicio = AGORA - timedelta(days=dias_atras)
    return {
        "run_id": run_id,
        "trigger": "schedule",
        "modo": modo,
        "started_at": inicio,
        "finished_at": inicio + timedelta(minutes=14),
        "status": status,
        "error_type": None,
        "error_message": None,
        **extra,
    }


def test_so_a_rotina_diaria_de_verdade_conta():
    runs = [
        _run("carga", modo="bootstrap", dias_atras=9),
        _run("a", dias_atras=3),
        _run("conferencia", modo="reconcile", dias_atras=1),
        _run("teste", status="failed", dias_atras=2, simulado=True),
        _run("b", dias_atras=2.5),
        # linha de antes da coluna `simulado`: só o texto do erro entrega que era de mentirinha
        _run("antiga", status="failed", dias_atras=5, error_message="Falha simulada para teste"),
    ]
    assert [r["run_id"] for r in execucoes_diarias(runs)] == ["a", "b"]  # da mais antiga p/ a nova
    assert simulada(runs[3]) and simulada(runs[5]) and not simulada(runs[1])


def test_conferencia_de_domingo_que_falha_nao_estraga_o_vigia():
    runs = [
        _run("sab", dias_atras=1),
        _run("dom", modo="reconcile", status="failed", error_type="PncpServerError"),
    ]
    st = build_status(runs, AGORA + timedelta(minutes=30))

    # o alerta de falha precisa da última execução, seja qual for o modo...
    assert st["ultima_execucao"]["run_id"] == "dom" and st["ultima_execucao"]["modo"] == "reconcile"
    assert st["ultima_execucao"]["status"] == "failed"
    # ...mas "quando a rotina do dia rodou bem" só olha as diárias
    assert st["ultima_execucao_ok_run_id"] == "sab"
    assert st["ultima_execucao_ok_em"] == "2026-10-24T13:14:00"
    assert (st["execucoes_total"], st["execucoes_ok"]) == (1, 1)
    assert st["taxa_sucesso_30d_pct"] == 100.0
    assert st["gerado_em"] == "2026-10-25T13:30:00"


def test_carga_inicial_nao_vira_ultima_execucao_ok():
    st = build_status([_run("carga", modo="bootstrap")], AGORA)
    assert st["ultima_execucao"]["run_id"] == "carga"
    assert st["ultima_execucao_ok_em"] is None and st["ultima_execucao_ok_run_id"] is None
    assert (st["execucoes_total"], st["execucoes_ok"], st["taxa_sucesso_30d_pct"]) == (0, 0, None)


def test_status_sem_nenhuma_execucao():
    st = build_status([], AGORA)
    assert st["ultima_execucao"] is None and st["ultima_execucao_ok_em"] is None
    assert (st["execucoes_total"], st["execucoes_ok"], st["taxa_sucesso_30d_pct"]) == (0, 0, None)


def test_taxa_de_sucesso_olha_30_dias_e_ignora_falha_simulada():
    runs = [
        _run("velha", status="failed", dias_atras=40),  # fora da janela de 30 dias
        _run("ok1", dias_atras=3),
        _run("ok2", dias_atras=2),
        _run("falha", status="failed", dias_atras=1),
        _run("teste", status="failed", dias_atras=0.5, simulado=True),
    ]
    st = build_status(runs, AGORA)
    assert st["taxa_sucesso_30d_pct"] == 66.7  # 2 de 3: a velha e a de teste não entram
    assert (st["execucoes_total"], st["execucoes_ok"]) == (4, 2)
    assert st["ultima_execucao_ok_run_id"] == "ok2"


def test_selo_mostra_a_hora_do_ultimo_ok_e_a_cor_da_ultima_execucao():
    selo = build_badge(build_status([_run("a")], AGORA))
    assert selo == {
        "schemaVersion": 1,
        "label": "última execução",
        "message": "25/10 13:14 BRT",
        "color": "brightgreen",
    }
    assert build_badge(build_status([_run("a", status="partial")], AGORA))["color"] == "yellow"

    falhou = build_badge(build_status([_run("a", dias_atras=1), _run("b", status="failed")], AGORA))
    assert falhou["color"] == "red" and falhou["message"] == "falhou (último ok 24/10 13:14 BRT)"

    vazio = build_badge(build_status([], AGORA))
    assert vazio["message"] == "sem dados" and vazio["color"] == "lightgrey"
