"""Conferência individual de editais contra o PNCP, que é a fonte.

As listagens (por publicação, por alteração, por propostas abertas) não contam tudo. Medido em
22/10/2026, em 8 de 837 editais com prazo em até 7 dias que o robô guardava como abertos:

* 2 tinham sido **excluídos** do PNCP: a consulta individual responde 410 e nenhuma listagem avisa;
* 6 tiveram o **prazo prorrogado** (e o valor corrigido) antes de o robô acompanhar as alterações.

A consulta individual traz exatamente o mesmo conteúdo da listagem (``row_hash`` igual em 10 de 10
editais), então comparar o hash basta para saber se algo mudou.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from radar.normalize import (
    SITUACAO_EXCLUIDA,
    SITUACAO_EXCLUIDA_NOME,
    InvalidRecord,
    normalize_item,
    partes_do_id,
    row_hash,
)
from radar.pncp_client import PncpClient, PncpError
from radar.store import Store, UpsertResult

IGUAL = "igual"  # o PNCP diz o mesmo que o guardado
ATUALIZADO = "atualizado"  # mudou (prazo, valor, situação...): o guardado foi corrigido
EXCLUIDO = "excluido"  # o PNCP não tem mais o edital: o guardado foi marcado como excluído
INCERTO = "incerto"  # não deu para saber (rede, limite, resposta estranha): nada foi mexido


@dataclass
class Conferido:
    resultado: str
    row: dict[str, Any] | None = None  # a linha como ficou (corrigida ou marcada como excluída)
    gravado: UpsertResult = field(default_factory=UpsertResult)


def marcar_excluido(store: Store, row: dict[str, Any], now: datetime) -> Conferido:
    """Tira o edital das listas sem apagar a linha (o histórico continua no Parquet)."""
    nova = {**row, "situacao_id": SITUACAO_EXCLUIDA, "situacao_nome": SITUACAO_EXCLUIDA_NOME}
    nova["row_hash"] = row_hash(nova)
    return Conferido(EXCLUIDO, nova, store.upsert([nova], now))


def conferir_no_pncp(
    client: PncpClient, store: Store, row: dict[str, Any], now: datetime
) -> Conferido:
    """Pergunta ao PNCP pelo edital e corrige o que estiver velho. Nunca decide por causa de um erro."""
    partes = partes_do_id(row["id"])
    if partes is None:
        return Conferido(INCERTO)
    try:
        bruto = client.get_compra(*partes)
    except PncpError:
        return Conferido(INCERTO)
    if bruto is None:
        return marcar_excluido(store, row, now)
    try:
        atual, _, _ = normalize_item(bruto)
    except InvalidRecord:
        return Conferido(INCERTO)
    if atual["row_hash"] == row["row_hash"]:
        return Conferido(IGUAL, row)
    return Conferido(ATUALIZADO, atual, store.upsert([atual], now))
