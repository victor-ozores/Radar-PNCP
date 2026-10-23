"""Edital publicado duas vezes no PNCP: mesmo órgão, valor, prazo e o mesmo texto.

Em 22/10/2026, cerca de 5% dos editais abertos tinham um "gêmeo" assim. Dos pares conferidos no PNCP,
2 de 3 estavam com os dois ativos (o órgão republica com outro número, por exemplo "34" e
"34/2026REPUBLICADO", ou publica duas vezes em minutos) e em 1 o original tinha sido excluído (a
conferência semanal cuida desse). Os dois são registros de verdade, então nenhum some: o painel e o
Telegram mostram o edital uma vez, com o número e o link do outro. O que foi publicado por último
fica como principal, porque uma republicação costuma ser a versão que vale.

O que conta como "o mesmo texto": igual, sem olhar acento, caixa nem pontuação, ou um dentro do outro
(a republicação costuma só acrescentar um trecho, como "Processo nº 38603/2026"). Órgão, valor (ao
centavo) e prazo (ao minuto) precisam bater sempre. Sem valor, só vale o texto inteiro igual, porque
sobraria pouco para provar que são o mesmo edital ("Lote 1" e "Lote 2" não podem virar um só). Um
texto curto demais ("obra") não prova nada. Na dúvida, não junta: mostrar o mesmo edital duas vezes
é um incômodo; esconder um edital diferente seria um erro.

Só entra na conta o que já passou pelos filtros (aberto, ativo, que combina com o perfil).
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any, TypeVar

from radar.normalize import fold, limpa_objeto

T = TypeVar("T")

TEXTO_MINIMO = 12  # caracteres: um texto menor que isto não prova que são o mesmo edital
_SEM_LETRA_NEM_NUMERO = re.compile(r"[^a-z0-9]+")


def _balde(row: dict[str, Any]) -> tuple[tuple[Any, ...], str] | None:
    """(onde procurar o gêmeo, texto normalizado). ``None`` quando não dá para afirmar nada."""
    cnpj, prazo, valor = (
        row.get("orgao_cnpj"),
        row.get("data_encerramento_proposta"),
        row.get("valor_estimado"),
    )
    texto = _SEM_LETRA_NEM_NUMERO.sub(" ", fold(limpa_objeto(row.get("objeto")))).strip()
    if not (cnpj and prazo and texto):
        return None
    return ((cnpj, valor, prazo) if valor is not None else (cnpj, None, prazo, texto)), texto


def _parecidos(a: str, b: str) -> bool:
    """Textos iguais, ou o menor (com palavras inteiras) dentro do maior."""
    if a == b:
        return True
    curto, longo = sorted((a, b), key=len)
    return len(curto) >= TEXTO_MINIMO and f" {curto} " in f" {longo} "


def _publicado(row: dict[str, Any]) -> tuple[datetime, str]:
    return (row.get("data_publicacao") or datetime.min, row["id"])


def agrupar(itens: Iterable[T], linha: Callable[[T], dict[str, Any]]) -> list[list[T]]:
    """Junta os gêmeos. Os grupos seguem a ordem em que o primeiro de cada um aparece em ``itens``.

    Dentro do grupo, o publicado por último vem primeiro (é o principal). Quem não tem gêmeo fica
    sozinho no seu grupo. ``linha`` extrai a linha do edital de cada item (a própria linha, ou
    ``lambda i: i.row`` quando o item é um ``Item`` do alerta). O resultado não depende da ordem de
    ``itens``, a não ser pela ordem dos grupos.
    """
    itens = list(itens)
    preparados = [_balde(linha(i)) for i in itens]
    grupo_de: dict[int, int] = {}
    por_balde: dict[tuple[Any, ...], list[tuple[str, int]]] = defaultdict(
        list
    )  # (texto mais longo, grupo)
    novos = 0
    # do texto mais longo para o mais curto: o curto entra no grupo do longo que o contém
    for pos in sorted(
        range(len(itens)), key=lambda p: -len(preparados[p][1]) if preparados[p] else 0
    ):
        if (p := preparados[pos]) is not None:
            balde, texto = p
            achado = next((g for longo, g in por_balde[balde] if _parecidos(texto, longo)), None)
            if achado is not None:
                grupo_de[pos] = achado
                continue
            por_balde[balde].append((texto, novos))
        grupo_de[pos] = novos
        novos += 1
    membros: dict[int, list[T]] = {}
    for pos, item in enumerate(itens):
        membros.setdefault(grupo_de[pos], []).append(item)
    return [sorted(g, key=lambda i: _publicado(linha(i)), reverse=True) for g in membros.values()]


class Indice:
    """Linhas já guardadas, para achar o gêmeo mais antigo de um edital novo."""

    def __init__(self, rows: Iterable[dict[str, Any]]) -> None:
        self._baldes: dict[tuple[Any, ...], list[tuple[str, dict[str, Any]]]] = defaultdict(list)
        for r in rows:
            if (p := _balde(r)) is not None:
                self._baldes[p[0]].append((p[1], r))

    def iguais_a(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        """Os outros registros do mesmo edital (sem contar a própria linha)."""
        if (p := _balde(row)) is None:
            return []
        balde, texto = p
        return [
            r
            for t, r in self._baldes.get(balde, [])
            if r["id"] != row["id"] and _parecidos(texto, t)
        ]
