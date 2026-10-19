from __future__ import annotations

import httpx
import pytest

from radar.alerts.telegram import AlertError, TelegramNotifier, discover_chats, notifier_from_env

# Montado em tempo de execução para não parecer um token real a scanners de segredos (gitleaks).
TOKEN = "123456789:" + "A" + "b" * 34


def notifier(handler, sleeps=None):
    http = httpx.Client(transport=httpx.MockTransport(handler))
    registro = sleeps if sleeps is not None else []
    return TelegramNotifier(
        TOKEN, "42", http=http, sleep=registro.append, pausa_entre_mensagens_s=0.5
    )


def test_envia_html_para_o_chat_certo():
    vistos = []

    def handler(req: httpx.Request) -> httpx.Response:
        vistos.append((str(req.url), req.read().decode()))
        return httpx.Response(200, json={"ok": True})

    notifier(handler).send("<b>oi</b>")
    url, corpo = vistos[0]
    assert url == f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    assert '"parse_mode":"HTML"' in corpo.replace(" ", "") and '"chat_id":"42"' in corpo.replace(
        " ", ""
    )


def test_erro_do_telegram_nao_vaza_o_token():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"ok": False, "description": "Bad Request: can't parse entities"}
        )

    with pytest.raises(AlertError) as exc:
        notifier(handler).send("<b>quebrado")
    assert TOKEN not in str(exc.value) and "can't parse entities" in str(exc.value)


def test_erro_de_rede_nao_vaza_o_token():
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"falha em {req.url}", request=req)

    with pytest.raises(AlertError) as exc:
        notifier(handler).send("oi")
    assert TOKEN not in str(exc.value)
    assert exc.value.__cause__ is None and exc.value.__suppress_context__


def test_429_respeita_retry_after():
    respostas = iter([httpx.Response(429, json={"parameters": {"retry_after": 7}})])
    sleeps: list[float] = []

    def handler(req: httpx.Request) -> httpx.Response:
        try:
            return next(respostas)
        except StopIteration:
            return httpx.Response(200, json={"ok": True})

    notifier(handler, sleeps).send("oi")
    assert sleeps == [8.0]


def test_mensagem_grande_demais_e_recusada_antes_de_enviar():
    def handler(req: httpx.Request) -> httpx.Response:
        raise AssertionError("não deveria chamar a API")

    with pytest.raises(AlertError, match="limite 4096"):
        notifier(handler).send("x" * 5000)


def test_send_many_pausa_entre_mensagens():
    sleeps: list[float] = []
    n = notifier(lambda req: httpx.Response(200, json={"ok": True}), sleeps)
    n.send_many(["a", "b", "c"])
    assert sleeps == [0.5, 0.5]


def test_notifier_from_env():
    assert notifier_from_env({}) is None
    assert notifier_from_env({"TELEGRAM_BOT_TOKEN": TOKEN, "TELEGRAM_CHAT_ID": "42"}) is not None


def test_descobre_chat_id():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"result": [{"message": {"chat": {"id": 99, "type": "private"}}},
                             {"message": {"chat": {"id": 99, "type": "private"}}}]},
        )  # fmt: skip

    http = httpx.Client(transport=httpx.MockTransport(handler))
    assert discover_chats(TOKEN, http) == [{"chat_id": 99, "tipo": "private"}]
