"""Armazenamento: Parquet particionado por dia de publicação, consultado com DuckDB.

* Sem arquivo ``.duckdb``: cada execução abre um DuckDB em memória e lê/escreve Parquet.
* Idempotente: reexecutar a mesma janela não muda nenhum byte. Só reescreve uma partição
  quando alguma linha é nova ou mudou (comparação por ``row_hash``).
* Determinístico: linhas ordenadas por ``id`` e nenhum timestamp de execução dentro de linhas
  que não mudaram (``first_seen_at`` e ``last_changed_at`` são preservados).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb

from radar.normalize import COLUMNS

SCHEMA: dict[str, str] = {
    "id": "VARCHAR",
    "ano_compra": "INTEGER",
    "sequencial_compra": "INTEGER",
    "numero_compra": "VARCHAR",
    "processo": "VARCHAR",
    "objeto": "VARCHAR",
    "informacao_complementar": "VARCHAR",
    "modalidade_id": "INTEGER",
    "modalidade_nome": "VARCHAR",
    "modo_disputa_nome": "VARCHAR",
    "srp": "BOOLEAN",
    "situacao_id": "INTEGER",
    "situacao_nome": "VARCHAR",
    "valor_estimado": "DOUBLE",
    "valor_homologado": "DOUBLE",
    "data_publicacao": "TIMESTAMP",
    "data_abertura_proposta": "TIMESTAMP",
    "data_encerramento_proposta": "TIMESTAMP",
    "data_atualizacao_global": "TIMESTAMP",
    "orgao_cnpj": "VARCHAR",
    "orgao_razao_social": "VARCHAR",
    "esfera_id": "VARCHAR",
    "poder_id": "VARCHAR",
    "uf": "VARCHAR",
    "municipio": "VARCHAR",
    "codigo_ibge": "VARCHAR",
    "unidade_nome": "VARCHAR",
    "link_origem": "VARCHAR",
    "amparo_legal": "VARCHAR",
    "dt": "DATE",
    "row_hash": "VARCHAR",
    "first_seen_at": "TIMESTAMP",
    "last_changed_at": "TIMESTAMP",
}
assert list(SCHEMA) == COLUMNS, "SCHEMA e COLUMNS precisam andar juntos"


@dataclass
class UpsertResult:
    new_ids: list[str] = field(default_factory=list)
    updated_ids: list[str] = field(default_factory=list)
    unchanged: int = 0
    partitions_written: int = 0
    prazo_alterado: int = 0  # editais que já tínhamos e cujo prazo de propostas mudou
    situacao_alterada: int = 0  # idem para a situação (suspensa, revogada, anulada...)

    def merge(self, other: UpsertResult) -> None:
        self.new_ids += other.new_ids
        self.updated_ids += other.updated_ids
        self.unchanged += other.unchanged
        self.partitions_written += other.partitions_written
        self.prazo_alterado += other.prazo_alterado
        self.situacao_alterada += other.situacao_alterada


def sql_quote(path: Path | str) -> str:
    return str(path).replace("\\", "/").replace("'", "''")


def write_parquet(
    conn: duckdb.DuckDBPyConnection,
    rows: list[dict[str, Any]],
    schema: dict[str, str],
    path: Path,
    order_by: str,
) -> None:
    """Grava ``rows`` em Parquet de forma atômica (arquivo temporário + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = list(schema)
    ddl = ", ".join(f'"{c}" {t}' for c, t in schema.items())
    conn.execute("DROP TABLE IF EXISTS _w")
    conn.execute(f"CREATE TEMP TABLE _w ({ddl})")
    if rows:
        placeholders = ", ".join("?" for _ in cols)
        conn.executemany(
            f"INSERT INTO _w VALUES ({placeholders})", [[r.get(c) for c in cols] for r in rows]
        )
    tmp = path.with_name(path.name + ".tmp")
    conn.execute(
        f"COPY (SELECT * FROM _w ORDER BY {order_by}) TO '{sql_quote(tmp)}' "
        "(FORMAT PARQUET, COMPRESSION ZSTD)"
    )
    os.replace(tmp, path)
    conn.execute("DROP TABLE _w")


def read_parquet_rows(
    conn: duckdb.DuckDBPyConnection, path: Path | str, where: str = ""
) -> list[dict[str, Any]]:
    cur = conn.execute(f"SELECT * FROM read_parquet('{sql_quote(path)}') {where}")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


class Store:
    def __init__(self, data_dir: Path | str) -> None:
        self.data_dir = Path(data_dir)
        self.contratacoes_dir = self.data_dir / "warehouse" / "contratacoes"
        self.export_dir = self.data_dir / "export"
        self.conn = duckdb.connect(":memory:")

    # ------------------------------------------------------------------ escrita

    def partition_path(self, dt: date) -> Path:
        return self.contratacoes_dir / f"dt={dt.isoformat()}" / "part.parquet"

    def upsert(self, rows: list[dict[str, Any]], now: datetime) -> UpsertResult:
        """Insere novas linhas e atualiza as que mudaram. ``now`` é o horário da execução."""
        result = UpsertResult()
        por_dia: dict[date, dict[str, dict[str, Any]]] = {}
        for r in rows:
            por_dia.setdefault(r["dt"], {})[r["id"]] = r  # último vence dentro do lote

        for dt, incoming in sorted(por_dia.items()):
            path = self.partition_path(dt)
            existentes = (
                {r["id"]: r for r in read_parquet_rows(self.conn, path)} if path.exists() else {}
            )
            alterado = False
            for id_, nova in incoming.items():
                atual = existentes.get(id_)
                if atual is None:
                    nova = {**nova, "first_seen_at": now, "last_changed_at": now}
                    existentes[id_] = nova
                    result.new_ids.append(id_)
                    alterado = True
                elif atual["row_hash"] != nova["row_hash"]:
                    if atual["data_encerramento_proposta"] != nova["data_encerramento_proposta"]:
                        result.prazo_alterado += 1
                    if atual["situacao_id"] != nova["situacao_id"]:
                        result.situacao_alterada += 1
                    existentes[id_] = {
                        **nova,
                        "first_seen_at": atual["first_seen_at"],
                        "last_changed_at": now,
                    }
                    result.updated_ids.append(id_)
                    alterado = True
                else:
                    result.unchanged += 1
            if alterado:
                write_parquet(self.conn, list(existentes.values()), SCHEMA, path, "id")
                result.partitions_written += 1
        return result

    # ------------------------------------------------------------------ leitura

    def has_data(self) -> bool:
        return self.contratacoes_dir.exists() and any(
            self.contratacoes_dir.glob("dt=*/part.parquet")
        )

    def current_state_sql(self) -> str:
        """SQL do estado atual: uma linha por edital (a versão mais recente)."""
        glob = sql_quote(self.contratacoes_dir / "dt=*" / "part.parquet")
        return (
            f"SELECT * FROM read_parquet('{glob}', union_by_name=true) "
            "QUALIFY row_number() OVER (PARTITION BY id "
            "ORDER BY data_atualizacao_global DESC NULLS LAST, dt DESC) = 1"
        )

    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        cur = self.conn.execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]

    def current_state(
        self, where: str = "", params: list[Any] | None = None
    ) -> list[dict[str, Any]]:
        if not self.has_data():
            return []
        sql = f"SELECT * FROM ({self.current_state_sql()}) {where}"
        return self.query(sql, params)

    def close(self) -> None:
        self.conn.close()
