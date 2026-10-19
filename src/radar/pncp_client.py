"""Cliente da API de consulta do PNCP.

É o único módulo que conhece URL, parâmetros e quirks da API. Comportamentos validados
em chamadas reais (19/10/2026):

* sem autenticação; datas em ``yyyyMMdd`` (ISO devolve 422);
* ``codigoModalidadeContratacao`` é obrigatório em ``/publicacao`` (400 sem ele);
* ``tamanhoPagina`` aceita 10 a 50;
* 204 sem corpo significa "nenhum registro", não é erro;
* 429 vem com corpo HTML e sem ``Retry-After``; a janela de bloqueio durou menos de 75 s.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

log = logging.getLogger("radar.pncp")

BASE_URL = "https://pncp.gov.br/api/consulta/v1"


class PncpError(Exception):
    """Falha ao consultar o PNCP."""


class PncpClientError(PncpError):
    """Resposta 4xx (exceto 429): a requisição está errada, repetir não adianta."""


class PncpRateLimited(PncpError):
    """429 persistente depois de esgotar o backoff."""


class PncpServerError(PncpError):
    """5xx ou falha de rede persistente depois de esgotar as tentativas."""


@dataclass
class ClientStats:
    api_calls: int = 0
    retries: int = 0
    http_429: int = 0
    http_5xx: int = 0
    http_204: int = 0
    net_errors: int = 0


def fmt_date(d: date) -> str:
    return d.strftime("%Y%m%d")


class PncpClient:
    def __init__(
        self,
        *,
        base_url: str = BASE_URL,
        tamanho_pagina: int = 50,
        intervalo_minimo_s: float = 4.0,
        backoff_429_s: list[float] | tuple[float, ...] = (30, 60, 120),
        max_tentativas_5xx: int = 4,
        timeout_s: float = 60,
        max_paginas_por_serie: int = 400,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.tamanho_pagina = tamanho_pagina
        self.intervalo_minimo_s = intervalo_minimo_s
        self.backoff_429_s = list(backoff_429_s)
        self.max_tentativas_5xx = max_tentativas_5xx
        self.max_paginas_por_serie = max_paginas_por_serie
        self.stats = ClientStats()
        self._http = http or httpx.Client(
            timeout=timeout_s, headers={"Accept": "application/json"}, follow_redirects=True
        )
        self._sleep = sleep
        self._clock = clock
        self._last_call: float | None = None

    # ------------------------------------------------------------------ API pública

    def iter_publicacao(
        self, data_inicial: date, data_final: date, modalidade: int, uf: str | None = None
    ) -> Iterator[list[dict[str, Any]]]:
        """Páginas de contratações por data de publicação (uma lista de itens por página)."""
        params: dict[str, Any] = {
            "dataInicial": fmt_date(data_inicial),
            "dataFinal": fmt_date(data_final),
            "codigoModalidadeContratacao": modalidade,
        }
        if uf:
            params["uf"] = uf
        yield from self._paginate("/contratacoes/publicacao", params)

    def iter_proposta(
        self, data_final: date, modalidade: int | None = None, uf: str | None = None
    ) -> Iterator[list[dict[str, Any]]]:
        """Páginas de contratações com recebimento de propostas aberto até ``data_final``."""
        params: dict[str, Any] = {"dataFinal": fmt_date(data_final)}
        if modalidade is not None:
            params["codigoModalidadeContratacao"] = modalidade
        if uf:
            params["uf"] = uf
        yield from self._paginate("/contratacoes/proposta", params)

    # ------------------------------------------------------------------ internos

    def _paginate(self, path: str, params: dict[str, Any]) -> Iterator[list[dict[str, Any]]]:
        pagina = 1
        while pagina <= self.max_paginas_por_serie:
            body = self._get(
                path, {**params, "pagina": pagina, "tamanhoPagina": self.tamanho_pagina}
            )
            if body is None:  # 204: sem registros
                return
            data = body.get("data") or []
            if data:
                yield data
            restantes = body.get("paginasRestantes")
            total_paginas = body.get("totalPaginas")
            if body.get("empty") or not data:
                return
            if restantes is not None:
                if restantes <= 0:
                    return
            elif total_paginas is not None and pagina >= total_paginas:
                return
            pagina += 1
        raise PncpError(
            f"Limite de {self.max_paginas_por_serie} páginas atingido em {path} {params}"
        )

    def _throttle(self) -> None:
        if self._last_call is not None:
            espera = self.intervalo_minimo_s - (self._clock() - self._last_call)
            if espera > 0:
                self._sleep(espera)
        self._last_call = self._clock()

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any] | None:
        url = f"{self.base_url}{path}"
        tentativas_429 = 0
        tentativas_5xx = 0
        while True:
            self._throttle()
            self.stats.api_calls += 1
            try:
                resp = self._http.get(url, params=params)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                self.stats.net_errors += 1
                tentativas_5xx += 1
                if tentativas_5xx >= self.max_tentativas_5xx:
                    raise PncpServerError(f"Falha de rede em {path}: {type(exc).__name__}") from exc
                self._backoff(2**tentativas_5xx, f"erro de rede ({type(exc).__name__})")
                continue

            status = resp.status_code
            if status == 204:
                self.stats.http_204 += 1
                return None
            if status == 429:
                self.stats.http_429 += 1
                if tentativas_429 >= len(self.backoff_429_s):
                    raise PncpRateLimited(
                        f"429 persistente em {path} após {tentativas_429} esperas"
                    )
                espera = self.backoff_429_s[tentativas_429]
                tentativas_429 += 1
                self._backoff(espera, "429 (limite de requisições)")
                continue
            if status >= 500:
                self.stats.http_5xx += 1
                tentativas_5xx += 1
                if tentativas_5xx >= self.max_tentativas_5xx:
                    raise PncpServerError(f"HTTP {status} persistente em {path}")
                self._backoff(2**tentativas_5xx, f"HTTP {status}")
                continue
            if status >= 400:
                raise PncpClientError(f"HTTP {status} em {path}: {_resumo(resp)}")
            try:
                body = resp.json()
            except ValueError as exc:
                raise PncpError(f"Resposta 200 não é JSON em {path}: {_resumo(resp)}") from exc
            if not isinstance(body, dict):
                raise PncpError(f"JSON inesperado em {path}: {type(body).__name__}")
            return body

    def _backoff(self, segundos: float, motivo: str) -> None:
        self.stats.retries += 1
        log.warning("tentando de novo", extra={"ctx": {"espera_s": segundos, "motivo": motivo}})
        self._sleep(segundos)

    def close(self) -> None:
        self._http.close()


def _resumo(resp: httpx.Response, limite: int = 200) -> str:
    texto = resp.text.replace("\n", " ").strip()
    return texto[:limite]
