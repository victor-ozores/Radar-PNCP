from __future__ import annotations

from datetime import datetime, timedelta

from radar.alerts.render import (
    Item,
    Resumo,
    build_digest,
    failure_message,
    fmt_prazo,
    fmt_valor,
    heartbeat_message,
    item_html,
)
from radar.scoring import ScoreResult

AGORA = datetime(2026, 10, 17, 7, 17)


def item(i: int = 1, **over) -> Item:
    row = {
        "id": f"id-{i}",
        "objeto": f"Reforma predial número {i}",
        "orgao_razao_social": "PREFEITURA MUNICIPAL DE TESTE",
        "municipio": "Campinas",
        "uf": "SP",
        "valor_estimado": 1_200_000.0,
        "data_encerramento_proposta": AGORA + timedelta(days=4, hours=2),
        "orgao_cnpj": "12345678000190",
        "ano_compra": 2026,
        "sequencial_compra": i,
        "link_origem": "https://compras.exemplo.gov.br/edital/1",
    }
    return Item({**row, **over}, ScoreResult(88, True, []))


def test_valores_em_reais():
    assert fmt_valor(79068.49) == "R$ 79,1 mil"
    assert fmt_valor(850_000) == "R$ 850 mil"
    assert fmt_valor(1_200_000) == "R$ 1,2 mi"
    assert fmt_valor(20_000_000) == "R$ 20 mi"
    assert fmt_valor(None) == "valor não informado"
    assert fmt_valor(0) == "valor não informado"


def test_prazos():
    assert "hoje" in fmt_prazo(AGORA + timedelta(hours=3), AGORA)
    assert "amanhã" in fmt_prazo(AGORA + timedelta(days=1), AGORA)
    assert "em 4 dias" in fmt_prazo(AGORA + timedelta(days=4), AGORA)
    assert fmt_prazo(None, AGORA) == "prazo não informado"


def test_item_escapa_html_e_traz_links():
    html = item_html(item(objeto="Obra <script>alert(1)</script> & cia"), AGORA)
    assert "<script>" not in html and "&lt;script&gt;" in html and "&amp; cia" in html
    assert 'href="https://pncp.gov.br/app/editais/12345678000190/2026/1"' in html
    assert "sistema de origem" in html
    assert item_html(item(link_origem=None), AGORA).count("<a ") == 1  # só o link do PNCP


def test_link_de_origem_estranho_e_ignorado():
    assert "javascript" not in item_html(item(link_origem="javascript:alert(1)"), AGORA)


def test_cabecalho_nao_mistura_as_contas():
    """Achado no Telegram real: dizia 'mostrando 10 de 909 analisados' para 108 relevantes."""
    novos = [item(i) for i in range(1, 11)]
    topo = build_digest(novos, [], Resumo(analisados=909, relevantes_novos=108), AGORA, "P")[0]
    assert "<b>108</b> editais novos combinam com o perfil, entre 909 analisados." in topo
    assert "Os 10 de maior nota:" in topo
    # quando todos cabem, não promete "os de maior nota"
    todos = build_digest(novos[:3], [], Resumo(analisados=50, relevantes_novos=3), AGORA, "P")[0]
    assert "Os 3 de maior nota" not in todos and "<b>3</b> editais novos combinam" in todos
    um = build_digest(novos[:1], [], Resumo(analisados=50, relevantes_novos=1), AGORA, "P")[0]
    assert "<b>1</b> edital novo combina" in um


def test_nota_vem_rotulada_e_o_texto_corta_no_fim_da_palavra():
    longo = "Contratação de empresa especializada para a execução de obras de pavimentação " * 5
    html = item_html(item(objeto=longo), AGORA)
    primeira = html.split("\n")[0]
    assert primeira.startswith("<b>Nota 88</b> · ")
    assert primeira.endswith("…") and not primeira.endswith(" …")
    corpo = primeira.removeprefix("<b>Nota 88</b> · ").removesuffix("…")
    assert corpo.split(" ")[-1] in longo.split(" ")  # última palavra inteira, não picada


def test_digest_dentro_do_limite_do_telegram():
    novos = [item(i, objeto="Obra " + "x" * 400) for i in range(1, 31)]
    msgs = build_digest(
        novos, novos[:5], Resumo(analisados=900, relevantes_novos=30), AGORA, "Perfil"
    )
    assert len(msgs) > 1
    assert all(len(m) <= 4096 for m in msgs)
    assert msgs[0].startswith("<b>📡 Radar PNCP · 17/10/2026</b>")


def test_titulo_dos_prazos_mostra_a_janela():
    resumo = Resumo(analisados=10, prazo_min_dias=2, prazo_max_dias=7)
    com = "\n".join(build_digest([], [item()], resumo, AGORA, "P"))
    assert "Prazos chegando</b> (vencem em 2 a 7 dias)" in com
    sem = "\n".join(build_digest([], [item()], Resumo(analisados=10), AGORA, "P"))
    assert "Prazos chegando</b>" in sem and "vencem em" not in sem


def test_digest_vazio_confirma_que_o_robo_rodou():
    msgs = build_digest([], [], Resumo(analisados=412), AGORA, "Perfil")
    assert len(msgs) == 1 and "Nenhum edital novo relevante" in msgs[0] and "412" in msgs[0]


def test_digest_avisa_series_com_falha():
    resumo = Resumo(analisados=10, series_total=16, series_falhas=["6/SP", "6/RJ"])
    msgs = build_digest([item()], [], resumo, AGORA, "Perfil")
    assert "2 de 16 buscas falharam" in msgs[0] and "6/SP" in msgs[0]


def test_mensagem_de_falha_escapa_e_mostra_ultimo_ok():
    m = failure_message(
        "https://github.com/x/y/actions/runs/1",
        "PncpRateLimited",
        "erro <b>",
        "2026-10-16T07:20:00",
    )
    assert "&lt;b&gt;" in m and "actions/runs/1" in m and "2026-10-16" in m
    assert "sem registro" in failure_message(None, None, None, None)


def test_mensagem_de_heartbeat():
    assert "há 30 h" in heartbeat_message("2026-10-16T07:20:00", 30.4, 26)
    assert "nunca" in heartbeat_message(None, None, 26)
