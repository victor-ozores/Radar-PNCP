"""Apoios de teste: fixtures reais da API, cliente falso e notificador falso."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

from radar.pncp_client import ClientStats, PncpError

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "pncp_publicacao_sample.json"


def load_sample_items() -> list[dict[str, Any]]:
    return copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8"))["data"])


class FakeClient:
    """Imita o PncpClient: devolve os itens da amostra que casam com modalidade e UF."""

    def __init__(
        self,
        items: list[dict[str, Any]] | None = None,
        *,
        ignora_uf: bool = False,
        falhas: dict[tuple[int, str], Exception] | None = None,
        falha_total: Exception | None = None,
        atualizados: list[dict[str, Any]] | None = None,
        falhas_atualizacao: dict[tuple[int, str], Exception] | None = None,
    ) -> None:
        self.items = items if items is not None else load_sample_items()
        self.ignora_uf = ignora_uf
        self.falhas = falhas or {}
        self.falha_total = falha_total
        # o que a consulta por ATUALIZAÇÃO devolve (por padrão, nada: a maioria dos testes ignora)
        self.atualizados = atualizados or []
        self.falhas_atualizacao = falhas_atualizacao or {}
        self.stats = ClientStats()
        self.chamadas: list[tuple[str, int | None, str | None]] = []

    def _paginas(
        self,
        modalidade: int | None,
        uf: str | None,
        base: list[dict[str, Any]],
        falhas: dict[tuple[int, str], Exception],
    ) -> Iterator[list[dict[str, Any]]]:
        self.stats.api_calls += 1
        if self.falha_total:
            raise self.falha_total
        if (modalidade, uf) in falhas:
            raise falhas[(modalidade, uf)]
        itens = [
            i
            for i in base
            if (modalidade is None or i["modalidadeId"] == modalidade)
            and (self.ignora_uf or uf is None or i["unidadeOrgao"]["ufSigla"] == uf)
        ]
        if itens:
            yield itens

    def iter_publicacao(self, inicio: date, fim: date, modalidade: int, uf: str | None = None):
        self.chamadas.append(("publicacao", modalidade, uf))
        return self._paginas(modalidade, uf, self.items, self.falhas)

    def iter_atualizacao(self, inicio: date, fim: date, modalidade: int, uf: str | None = None):
        self.chamadas.append(("atualizacao", modalidade, uf))
        return self._paginas(modalidade, uf, self.atualizados, self.falhas_atualizacao)

    def iter_proposta(self, fim: date, modalidade: int | None = None, uf: str | None = None):
        self.chamadas.append(("proposta", modalidade, uf))
        return self._paginas(modalidade, uf, self.items, self.falhas)

    def close(self) -> None:
        pass


class FakeNotifier:
    def __init__(self, falha: Exception | None = None) -> None:
        self.enviadas: list[str] = []
        self.falha = falha

    def send(self, text: str) -> None:
        if self.falha:
            raise self.falha
        self.enviadas.append(text)

    def send_many(self, messages: list[str]) -> None:
        for m in messages:
            self.send(m)


__all__ = ["FakeClient", "FakeNotifier", "PncpError", "load_sample_items"]
