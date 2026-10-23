from __future__ import annotations

from datetime import datetime, timedelta
from html.parser import HTMLParser

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


def item(i: int = 1, score: int = 88, **over) -> Item:
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
    return Item({**row, **over}, ScoreResult(score, True, []))


def test_valores_em_reais():
    assert fmt_valor(79068.49) == "R$ 79,1 mil"
    assert fmt_valor(850_000) == "R$ 850 mil"
    assert fmt_valor(1_200_000) == "R$ 1,2 mi"
    assert fmt_valor(20_000_000) == "R$ 20 mi"
    assert fmt_valor(None) == "valor não informado"
    assert fmt_valor(0) == "valor não informado"


def test_valor_simbolico_e_arredondamento_na_virada_do_milhao():
    assert fmt_valor(0.04) == "valor não informado"  # visto nos dados reais: não é o valor da obra
    assert fmt_valor(999) == "valor não informado"
    assert fmt_valor(1_000) == "R$ 1 mil"
    assert fmt_valor(999_999) == "R$ 1 mi"  # não vira "R$ 1000 mil"


def test_prazos():
    assert "hoje" in fmt_prazo(AGORA + timedelta(hours=3), AGORA)
    assert "amanhã" in fmt_prazo(AGORA + timedelta(days=1), AGORA)
    assert "em 4 dias" in fmt_prazo(AGORA + timedelta(days=4), AGORA)
    assert fmt_prazo(None, AGORA) == "prazo não informado"


def test_prazo_diz_ate_quando_e_desde_quando_se_as_propostas_ainda_nao_abriram():
    fim = AGORA + timedelta(days=10)
    assert fmt_prazo(fim, AGORA) == "propostas até 27/10 07:17 (em 10 dias)"
    assert fmt_prazo(fim, AGORA, AGORA - timedelta(days=1)).startswith("propostas até")
    assert fmt_prazo(fim, AGORA, AGORA + timedelta(days=2)) == (
        "propostas de 19/10 até 27/10 07:17 (em 10 dias)"
    )


def test_item_escapa_html_e_traz_links():
    html = item_html(item(objeto="Obra <script>alert(1)</script> & cia"), AGORA)
    assert "<script>" not in html and "&lt;script&gt;" in html and "&amp; cia" in html
    assert 'href="https://pncp.gov.br/app/editais/12345678000190/2026/1"' in html
    assert "sistema de origem" in html
    assert item_html(item(link_origem=None), AGORA).count("<a ") == 1  # só o link do PNCP


def test_link_de_origem_estranho_e_ignorado():
    assert "javascript" not in item_html(item(link_origem="javascript:alert(1)"), AGORA)


def test_item_usa_a_etiqueta_em_vez_do_numero_da_nota():
    assert item_html(item(score=100), AGORA).startswith("<b>Combina muito</b> · ")
    assert item_html(item(score=70), AGORA).startswith("<b>Combina</b> · ")
    assert item_html(item(score=45), AGORA).startswith("<b>Combina em parte</b> · ")
    assert "Nota" not in item_html(item(score=100), AGORA)


def test_item_traz_modalidade_numero_e_registro_de_precos():
    html = item_html(
        item(modalidade_nome="Pregão - Eletrônico", numero_compra="12", srp=True), AGORA
    )
    assert "📄 Pregão Eletrônico nº 12/2026" in html and "registro de preços" in html
    sem = item_html(item(modalidade_nome="Concorrência - Eletrônica", srp=False), AGORA)
    assert "📄 Concorrência Eletrônica" in sem and "registro de preços" not in sem
    assert "nº" not in sem  # sem número de compra, não inventa
    ja_com_ano = item_html(
        item(modalidade_nome="Pregão - Eletrônico", numero_compra="12/2026"), AGORA
    )
    assert "nº 12/2026" in ja_com_ano and "2026/2026" not in ja_com_ano


def test_item_em_caixa_alta_vira_texto_normal():
    html = item_html(
        item(
            objeto="[LICITANET] - CONTRATAÇÃO DE EMPRESA PARA REFORMA DA ESCOLA MUNICIPAL",
            orgao_razao_social="MUNICIPIO DE LAMBARI",
        ),
        AGORA,
    )
    assert "Contratação de Empresa para Reforma da Escola Municipal" in html
    assert "LICITANET" not in html  # a etiqueta do sistema que publicou não diz nada sobre a obra
    assert "🏛 Município de Lambari" in html


def test_orgao_leva_o_acento_da_cidade_do_proprio_edital():
    """O órgão chega sem acento ("IBIRITE"); a cidade do mesmo edital vem certa ("Ibirité")."""
    html = item_html(item(orgao_razao_social="MUNICIPIO DE IBIRITE", municipio="Ibirité"), AGORA)
    assert "🏛 Município de Ibirité · 📍 Ibirité / SP" in html


def _outro_registro(i: int, **over) -> dict:
    return {
        "id": f"outro-{i}",
        "orgao_cnpj": "12345678000190",
        "ano_compra": 2026,
        "sequencial_compra": 100 + i,
        "numero_compra": f"{i}",
        **over,
    }


def test_edital_publicado_duas_vezes_diz_o_numero_e_leva_ao_outro_registro():
    it = item()
    assert "🔁" not in item_html(it, AGORA)  # sem gêmeo, nada a dizer
    it.iguais = [_outro_registro(9, numero_compra="34/2026REPUBLICADO")]
    html = item_html(it, AGORA)
    assert html.splitlines()[-1] == (
        '🔁 Também publicado como <a href="https://pncp.gov.br/app/editais/12345678000190/2026/109">'
        "nº 34/2026REPUBLICADO</a>"
    )


def test_registro_repetido_sem_numero_ou_sem_link_nao_inventa_nada():
    it = item()
    it.iguais = [_outro_registro(1, numero_compra="x" * 40)]
    assert item_html(it, AGORA).endswith(">outro registro</a>")
    it.iguais = [{"id": "sem-link", "numero_compra": None, "ano_compra": None}]
    assert item_html(it, AGORA).splitlines()[-1] == "🔁 Também publicado como outro registro"


def test_muitos_registros_repetidos_viram_e_mais_n():
    it = item()
    it.iguais = [_outro_registro(i) for i in range(1, 5)]
    ultima = item_html(it, AGORA).splitlines()[-1]
    assert ultima.count("<a ") == 2 and ultima.endswith(" e mais 2")


def test_item_avisa_quando_as_propostas_ainda_vao_abrir():
    html = item_html(item(data_abertura_proposta=AGORA + timedelta(days=2)), AGORA)
    assert "propostas de 19/10 até 21/10" in html


def test_cabecalho_nao_mistura_as_contas():
    """Achado no Telegram real: dizia 'mostrando 10 de 909 analisados' para 108 relevantes."""
    novos = [item(i) for i in range(1, 11)]
    topo = build_digest(novos, [], Resumo(novos=909, relevantes_novos=108), AGORA, "P")[0]
    assert "<b>108</b> editais novos combinam com o perfil, entre 909 novos lidos hoje." in topo
    assert "Os 10 que mais combinam:" in topo
    # quando todos cabem, não promete "os que mais combinam"
    todos = build_digest(novos[:3], [], Resumo(novos=50, relevantes_novos=3), AGORA, "P")[0]
    assert "que mais combinam" not in todos and "<b>3</b> editais novos combinam" in todos
    um = build_digest(novos[:1], [], Resumo(novos=1, relevantes_novos=1), AGORA, "P")[0]
    assert "<b>1</b> edital novo combina" in um and "1 novo lido hoje" in um


def test_corta_no_fim_da_palavra_e_nao_deixa_ponto_solto():
    longo = "Contratação de empresa especializada para a execução de obras de pavimentação " * 5
    html = item_html(item(objeto=longo), AGORA)
    primeira = html.split("\n")[0]
    assert primeira.startswith("<b>Combina muito</b> · ")
    assert primeira.endswith("…") and not primeira.endswith(" …")
    corpo = primeira.removeprefix("<b>Combina muito</b> · ").removesuffix("…")
    assert corpo.split(" ")[-1] in longo.split(" ")  # última palavra inteira, não picada


def test_digest_dentro_do_limite_do_telegram():
    novos = [item(i, objeto="Obra " + "x" * 400) for i in range(1, 31)]
    msgs = build_digest(novos, novos[:5], Resumo(novos=900, relevantes_novos=30), AGORA, "Perfil")
    assert len(msgs) > 1
    assert all(len(m) <= 4096 for m in msgs)
    assert msgs[0].startswith("<b>📡 Radar PNCP · 17/10/2026</b>")


def test_titulo_dos_prazos_mostra_a_janela():
    resumo = Resumo(novos=10, prazo_min_dias=2, prazo_max_dias=7)
    com = "\n".join(build_digest([], [item()], resumo, AGORA, "P"))
    assert "Prazos chegando</b> (vencem em 2 a 7 dias)" in com
    sem = "\n".join(build_digest([], [item()], Resumo(novos=10), AGORA, "P"))
    assert "Prazos chegando</b>" in sem and "vencem em" not in sem


def test_prazos_avisam_quantos_outros_ficaram_de_fora():
    resumo = Resumo(novos=1, vencendo_total=40, painel_url="https://exemplo.github.io/radar/")
    texto = "\n".join(build_digest([], [item(1), item(2)], resumo, AGORA, "P"))
    assert "Mais 38 outros vencem nesse período" in texto
    um = "\n".join(build_digest([], [item()], Resumo(novos=1, vencendo_total=2), AGORA, "P"))
    assert "Mais 1 outro vence nesse período" in um and "<a" not in um.split("Mais 1")[1]
    todos = "\n".join(build_digest([], [item()], Resumo(novos=1, vencendo_total=1), AGORA, "P"))
    assert "Mais" not in todos  # nada ficou de fora


def test_link_do_painel_so_aparece_se_configurado():
    com = build_digest(
        [item()],
        [],
        Resumo(novos=5, relevantes_novos=1, painel_url="https://x.github.io/Radar/"),
        AGORA,
        "P",
    )[0]
    assert '🔎 <a href="https://x.github.io/Radar/">Ver todos no painel</a>' in com
    sem = build_digest([item()], [], Resumo(novos=5, relevantes_novos=1), AGORA, "P")[0]
    assert "painel" not in sem


def test_digest_vazio_confirma_que_o_robo_rodou():
    msgs = build_digest([], [], Resumo(novos=412), AGORA, "Perfil")
    assert (
        len(msgs) == 1 and "Nenhum edital novo combina" in msgs[0] and "412 novos lidos" in msgs[0]
    )


def test_digest_avisa_series_com_falha():
    resumo = Resumo(novos=10, series_total=16, series_falhas=["6/SP", "6/RJ"])
    msgs = build_digest([item()], [], resumo, AGORA, "Perfil")
    assert "2 de 16 buscas falharam" in msgs[0] and "6/SP" in msgs[0]


class _SoMarcasDoTelegram(HTMLParser):
    """O Telegram aceita só <b>, <i>, <a href> e <code> (e rejeita a mensagem inteira se o HTML estiver torto)."""

    PERMITIDAS = {"b", "i", "a", "code"}

    def __init__(self) -> None:
        super().__init__()
        self.abertas: list[str] = []
        self.erros: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.PERMITIDAS:
            self.erros.append(f"marca não permitida: <{tag}>")
        if tag == "a":
            href = dict(attrs).get("href") or ""
            if not href.startswith(("http://", "https://")):
                self.erros.append(f"link estranho: {href!r}")
        self.abertas.append(tag)

    def handle_endtag(self, tag):
        if not self.abertas or self.abertas.pop() != tag:
            self.erros.append(f"fechou </{tag}> fora de ordem")


def test_todas_as_mensagens_sao_html_valido_para_o_telegram():
    novos = [
        item(
            i,
            objeto="OBRA <b>& CIA</b> “aspas” 'simples' " + "X" * 30,
            orgao_razao_social="MUNICIPIO D'OESTE & FILHOS",
            municipio="Brás <Pires>",
            modalidade_nome="Pregão - Eletrônico",
            numero_compra="1",
            srp=True,
            data_abertura_proposta=AGORA + timedelta(days=1),
        )
        for i in range(1, 13)
    ]
    resumo = Resumo(
        novos=500,
        relevantes_novos=50,
        vencendo_total=20,
        series_total=16,
        series_falhas=["6/SP"],
        prazo_min_dias=2,
        prazo_max_dias=7,
        painel_url="https://x.github.io/Radar/?a=1&b=2",
    )
    for msg in build_digest(novos, novos[:5], resumo, AGORA, "Perfil <teste> & cia"):
        parser = _SoMarcasDoTelegram()
        parser.feed(msg)
        assert parser.erros == [] and parser.abertas == [], (parser.erros, parser.abertas)
        assert len(msg) <= 4096


def test_mensagem_de_falha_escapa_e_mostra_ultimo_ok():
    m = failure_message(
        "https://github.com/x/y/actions/runs/1",
        "PncpRateLimited",
        "erro <b>",
        "2026-10-16T07:20:00",
    )
    assert "&lt;b&gt;" in m and "actions/runs/1" in m
    assert "Último sucesso: 16/10/2026 07:20" in m  # data legível, não o ISO cru
    assert "sem registro" in failure_message(None, None, None, None)
    assert "Último sucesso: ontem &lt;" in failure_message(None, None, None, "ontem <")


def test_mensagem_de_heartbeat():
    assert "há 30 h (16/10/2026 07:20)" in heartbeat_message("2026-10-16T07:20:00", 30.4, 26)
    assert "nunca" in heartbeat_message(None, None, 26)
