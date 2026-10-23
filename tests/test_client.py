from __future__ import annotations

from datetime import date

import httpx
import pytest

from radar.pncp_client import (
    PncpClient,
    PncpClientError,
    PncpError,
    PncpRateLimited,
    PncpServerError,
)

HTML_429 = "<html><body><h2>Limite de requisições excedido</h2></body></html>"


def make_client(handler, **kw):
    sleeps: list[float] = []
    relogio = {"t": 0.0}

    def sleep(s: float) -> None:
        sleeps.append(s)
        relogio["t"] += s

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = PncpClient(http=http, sleep=sleep, clock=lambda: relogio["t"], **kw)
    return client, sleeps


def pagina(n: int, total: int, itens: int = 2) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "data": [{"numeroControlePNCP": f"p{n}-{i}"} for i in range(itens)],
            "totalPaginas": total,
            "numeroPagina": n,
            "paginasRestantes": total - n,
            "empty": False,
        },
    )


def test_paginacao_e_parametros():
    vistos: list[dict[str, str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        q = dict(req.url.params)
        vistos.append(q)
        return pagina(int(q["pagina"]), 2)

    client, _ = make_client(handler)
    paginas = list(client.iter_publicacao(date(2026, 10, 15), date(2026, 10, 17), 6, "SP"))

    assert [len(p) for p in paginas] == [2, 2]
    assert vistos[0]["dataInicial"] == "20261015"  # yyyyMMdd; ISO daria 422
    assert vistos[0]["dataFinal"] == "20261017"
    assert vistos[0]["codigoModalidadeContratacao"] == "6"
    assert vistos[0]["uf"] == "SP"
    assert vistos[0]["tamanhoPagina"] == "50"
    assert [v["pagina"] for v in vistos] == ["1", "2"]


def test_proposta_usa_so_data_final():
    vistos: list[dict[str, str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        vistos.append(dict(req.url.params))
        return pagina(1, 1)

    client, _ = make_client(handler)
    list(client.iter_proposta(date(2026, 10, 31), 6, "SP"))
    assert "dataInicial" not in vistos[0]
    assert vistos[0]["dataFinal"] == "20261031"


def test_atualizacao_usa_o_endpoint_de_alterados_com_os_mesmos_parametros():
    chamadas: list[tuple[str, dict[str, str]]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        chamadas.append((req.url.path, dict(req.url.params)))
        return pagina(int(req.url.params["pagina"]), 2)

    client, _ = make_client(handler)
    paginas = list(client.iter_atualizacao(date(2026, 10, 20), date(2026, 10, 21), 4, "MG"))

    assert len(paginas) == 2
    caminho, params = chamadas[0]
    assert caminho.endswith("/contratacoes/atualizacao")  # e não /publicacao
    assert params["dataInicial"] == "20261020" and params["dataFinal"] == "20261021"
    assert params["codigoModalidadeContratacao"] == "4" and params["uf"] == "MG"
    assert params["tamanhoPagina"] == "50"


def test_204_e_lista_vazia():
    client, _ = make_client(lambda req: httpx.Response(204))
    assert list(client.iter_publicacao(date(2026, 10, 16), date(2026, 10, 16), 2, "SP")) == []
    assert client.stats.http_204 == 1


def test_429_html_espera_e_recupera():
    respostas = iter([httpx.Response(429, text=HTML_429), httpx.Response(429, text=HTML_429)])

    def handler(req: httpx.Request) -> httpx.Response:
        try:
            return next(respostas)
        except StopIteration:
            return pagina(1, 1)

    client, sleeps = make_client(handler, backoff_429_s=[30, 60, 120])
    paginas = list(client.iter_publicacao(date(2026, 10, 16), date(2026, 10, 16), 6, "SP"))

    assert len(paginas) == 1
    assert 30 in sleeps and 60 in sleeps
    assert client.stats.http_429 == 2
    assert client.stats.retries == 2


def test_429_persistente_levanta_rate_limited():
    client, sleeps = make_client(
        lambda req: httpx.Response(429, text=HTML_429), backoff_429_s=[30, 60, 120]
    )
    with pytest.raises(PncpRateLimited):
        list(client.iter_publicacao(date(2026, 10, 16), date(2026, 10, 16), 6, "SP"))
    assert [s for s in sleeps if s >= 30] == [30, 60, 120]
    assert client.stats.http_429 == 4


def test_5xx_tenta_de_novo():
    respostas = iter([httpx.Response(503), httpx.Response(502)])

    def handler(req: httpx.Request) -> httpx.Response:
        try:
            return next(respostas)
        except StopIteration:
            return pagina(1, 1)

    client, sleeps = make_client(handler)
    assert len(list(client.iter_publicacao(date(2026, 10, 16), date(2026, 10, 16), 6, "SP"))) == 1
    assert 2 in sleeps and 4 in sleeps
    assert client.stats.http_5xx == 2


def test_5xx_esgota_tentativas():
    client, _ = make_client(lambda req: httpx.Response(500), max_tentativas_5xx=3)
    with pytest.raises(PncpServerError):
        list(client.iter_publicacao(date(2026, 10, 16), date(2026, 10, 16), 6, "SP"))
    assert client.stats.api_calls == 3


def test_erro_de_rede_vira_server_error():
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede", request=req)

    client, _ = make_client(handler, max_tentativas_5xx=2)
    with pytest.raises(PncpServerError):
        list(client.iter_publicacao(date(2026, 10, 16), date(2026, 10, 16), 6, "SP"))
    assert client.stats.net_errors == 2


def test_400_nao_repete():
    client, sleeps = make_client(
        lambda req: httpx.Response(400, json={"message": "Tamanho de página inválido"})
    )
    with pytest.raises(PncpClientError, match="400"):
        list(client.iter_publicacao(date(2026, 10, 16), date(2026, 10, 16), 6, "SP"))
    assert client.stats.api_calls == 1
    assert sleeps == []


def test_200_que_nao_e_json():
    client, _ = make_client(lambda req: httpx.Response(200, text="<html>manutenção</html>"))
    with pytest.raises(PncpError, match="não é JSON"):
        list(client.iter_publicacao(date(2026, 10, 16), date(2026, 10, 16), 6, "SP"))


def test_intervalo_minimo_entre_chamadas():
    def handler(req: httpx.Request) -> httpx.Response:
        return pagina(int(req.url.params["pagina"]), 3)

    client, sleeps = make_client(handler, intervalo_minimo_s=4.0)
    list(client.iter_publicacao(date(2026, 10, 16), date(2026, 10, 16), 6, "SP"))
    # 3 páginas = 3 chamadas; a primeira não espera, as outras duas esperam o intervalo
    assert sleeps == [4.0, 4.0]


def test_limite_de_paginas_protege_contra_loop():
    client, _ = make_client(
        lambda req: pagina(1, 999), max_paginas_por_serie=3, intervalo_minimo_s=1.0
    )
    with pytest.raises(PncpError, match="Limite de 3 páginas"):
        list(client.iter_publicacao(date(2026, 10, 16), date(2026, 10, 16), 6, "SP"))


def test_consulta_individual_devolve_o_edital():
    vistos: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        vistos.append(req.url.path)
        return httpx.Response(200, json={"numeroControlePNCP": "12345678000190-1-000055/2026"})

    client, _ = make_client(handler)
    edital = client.get_compra("12345678000190", 2026, 55)
    assert edital == {"numeroControlePNCP": "12345678000190-1-000055/2026"}
    assert vistos[0].endswith("/orgaos/12345678000190/compras/2026/55")


@pytest.mark.parametrize("status", [404, 410])
def test_edital_excluido_ou_inexistente_volta_como_none(status):
    """Medido em 22/10/2026: excluído do PNCP = 410 'A contratação informada foi excluída'."""

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"message": "A contratação informada foi excluída."})

    client, _ = make_client(handler)
    assert client.get_compra("12345678000190", 2026, 100) is None


def test_outros_erros_4xx_da_consulta_individual_continuam_sendo_erro():
    client, _ = make_client(lambda req: httpx.Response(400, text="requisição inválida"))
    with pytest.raises(PncpClientError) as erro:
        client.get_compra("12345678000190", 2026, 1)
    assert erro.value.status == 400
