"""Envio de mensagens pelo Telegram Bot API (gratuito)."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

import httpx

from radar.audit import scrub_secrets

API = "https://api.telegram.org"
LIMITE_TELEGRAM = 4096


class AlertError(Exception):
    """Falha ao enviar o alerta (a mensagem nunca contém o token)."""


class TelegramNotifier:
    def __init__(
        self,
        token: str,
        chat_id: str,
        *,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        pausa_entre_mensagens_s: float = 1.0,
    ) -> None:
        if not token or not chat_id:
            raise AlertError("TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID são obrigatórios")
        self._token = token
        self._chat_id = chat_id
        self._http = http or httpx.Client(timeout=30)
        self._sleep = sleep
        self._pausa = pausa_entre_mensagens_s

    def _erro(self, msg: str) -> AlertError:
        return AlertError(scrub_secrets(msg, [self._token]))

    def send(self, text: str) -> None:
        if len(text) > LIMITE_TELEGRAM:
            raise self._erro(f"Mensagem com {len(text)} caracteres (limite {LIMITE_TELEGRAM})")
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        for tentativa in range(4):
            try:
                resp = self._http.post(f"{API}/bot{self._token}/sendMessage", json=payload)
            except httpx.HTTPError as exc:
                if tentativa == 3:
                    raise self._erro(
                        f"Falha de rede ao falar com o Telegram: {type(exc).__name__}"
                    ) from None
                self._sleep(2**tentativa)
                continue
            if resp.status_code == 429:
                espera = _retry_after(resp)
                if tentativa == 3:
                    raise self._erro("Telegram devolveu 429 repetidamente")
                self._sleep(espera)
                continue
            if resp.status_code >= 500:
                if tentativa == 3:
                    raise self._erro(f"Telegram indisponível (HTTP {resp.status_code})")
                self._sleep(2**tentativa)
                continue
            if resp.status_code != 200:
                raise self._erro(
                    f"Telegram recusou a mensagem (HTTP {resp.status_code}): {_descricao(resp)}"
                )
            return
        raise self._erro("Não foi possível enviar ao Telegram")  # pragma: no cover

    def send_many(self, messages: list[str]) -> None:
        for i, m in enumerate(messages):
            if i:
                self._sleep(self._pausa)
            self.send(m)


def _descricao(resp: httpx.Response) -> str:
    try:
        return str(resp.json().get("description", ""))[:200]
    except ValueError:
        return ""


def _retry_after(resp: httpx.Response) -> float:
    try:
        return float(resp.json()["parameters"]["retry_after"]) + 1
    except (ValueError, KeyError, TypeError):
        return 5.0


def notifier_from_env(env: dict[str, str] | None = None) -> TelegramNotifier | None:
    e = env if env is not None else os.environ
    token, chat = e.get("TELEGRAM_BOT_TOKEN", ""), e.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return None
    return TelegramNotifier(token, chat)


def discover_chats(token: str, http: httpx.Client | None = None) -> list[dict[str, Any]]:
    """Lê as últimas mensagens recebidas pelo bot para descobrir o chat_id."""
    client = http or httpx.Client(timeout=30)
    try:
        resp = client.get(f"{API}/bot{token}/getUpdates")
    except httpx.HTTPError as exc:
        raise AlertError(scrub_secrets(f"Falha de rede: {type(exc).__name__}", [token])) from None
    if resp.status_code != 200:
        raise AlertError(f"getUpdates falhou (HTTP {resp.status_code}): {_descricao(resp)}")
    chats: dict[int, dict[str, Any]] = {}
    for upd in resp.json().get("result", []):
        msg = upd.get("message") or upd.get("channel_post") or {}
        chat = msg.get("chat")
        if chat:
            chats[chat["id"]] = {"chat_id": chat["id"], "tipo": chat.get("type")}
    return list(chats.values())
