"""Transforma o JSON bruto do PNCP em uma linha plana e segura (LGPD).

Princípios:
* **allowlist**: só viram coluna os campos listados aqui; o resto é descartado (inclusive
  ``usuarioNome``, que pode ser o nome de uma pessoa);
* **scrub de PII** no texto livre (CPF, e-mail, telefone);
* datas ficam como horário de Brasília sem fuso (a API já devolve assim).
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")

#: Colunas na ordem em que são gravadas. ``first_seen_at`` e ``last_changed_at`` são
#: preenchidas pelo store; ``row_hash`` identifica o conteúdo para detectar mudanças.
COLUMNS: list[str] = [
    "id",
    "ano_compra",
    "sequencial_compra",
    "numero_compra",
    "processo",
    "objeto",
    "informacao_complementar",
    "modalidade_id",
    "modalidade_nome",
    "modo_disputa_nome",
    "srp",
    "situacao_id",
    "situacao_nome",
    "valor_estimado",
    "valor_homologado",
    "data_publicacao",
    "data_abertura_proposta",
    "data_encerramento_proposta",
    "data_atualizacao_global",
    "orgao_cnpj",
    "orgao_razao_social",
    "esfera_id",
    "poder_id",
    "uf",
    "municipio",
    "codigo_ibge",
    "unidade_nome",
    "link_origem",
    "amparo_legal",
    "dt",
    "row_hash",
    "first_seen_at",
    "last_changed_at",
]

_DATE_FIELDS = (
    "data_publicacao",
    "data_abertura_proposta",
    "data_encerramento_proposta",
    "data_atualizacao_global",
)

MAX_OBJETO = 2000
MAX_COMPLEMENTAR = 500


class InvalidRecord(ValueError):
    """Registro sem os campos mínimos (id ou data de publicação)."""


# --------------------------------------------------------------------------- texto


def fold(text: str | None) -> str:
    """Minúsculas, sem acento e com espaços colapsados (para comparação)."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


_CPF_FORMATADO = re.compile(r"(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)")
_CPF_COM_ROTULO = re.compile(r"(?i)(\bcpf\b\W{0,12})\d{11}(?!\d)")
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_FONE_DDD = re.compile(r"\(\d{2}\)\s*9?\d{4}[-\s]?\d{4}(?!\d)")
_FONE_ROTULO = re.compile(
    r"(?i)\b(?:tel(?:efone)?|fone|cel(?:ular)?|whatsapp|contato)\b\W{0,6}"
    r"(?:\(?\d{2}\)?\s*)?9?\d{4}[-\s]?\d{4}(?!\d)"
)


def scrub_pii(text: str) -> tuple[str, int]:
    """Troca CPF, e-mail e telefone por marcadores. Devolve (texto, quantidade de trocas)."""
    hits = 0

    def sub(pattern: re.Pattern[str], repl: str | Any, s: str) -> str:
        nonlocal hits
        novo, n = pattern.subn(repl, s)
        hits += n
        return novo

    text = sub(_CPF_FORMATADO, "[CPF]", text)
    text = sub(_CPF_COM_ROTULO, r"\1[CPF]", text)
    text = sub(_EMAIL, "[e-mail]", text)
    text = sub(_FONE_DDD, "[telefone]", text)
    text = sub(_FONE_ROTULO, "[telefone]", text)
    return text, hits


def _limpa(texto: Any, limite: int) -> tuple[str | None, int]:
    if texto is None:
        return None, 0
    t = re.sub(r"\s+", " ", str(texto)).strip()
    if not t:
        return None, 0
    t, hits = scrub_pii(t)
    return t[:limite], hits


# --------------------------------------------------------------------------- datas


def parse_dt(valor: Any) -> datetime | None:
    if not valor:
        return None
    try:
        dt = datetime.fromisoformat(str(valor))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(TZ).replace(tzinfo=None)
    return dt.replace(microsecond=0)


def _num(valor: Any) -> float | None:
    if valor is None:
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _get(d: dict[str, Any] | None, *chaves: str) -> Any:
    cur: Any = d
    for k in chaves:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


# --------------------------------------------------------------------------- linha


def normalize_item(raw: dict[str, Any]) -> tuple[dict[str, Any], int, list[str]]:
    """Converte um item bruto. Devolve (linha, redações de PII, avisos de qualidade).

    Levanta ``InvalidRecord`` quando faltam id ou data de publicação.
    """
    avisos: list[str] = []
    pii = 0

    id_ = raw.get("numeroControlePNCP")
    if not id_:
        raise InvalidRecord("sem numeroControlePNCP")

    datas: dict[str, datetime | None] = {
        "data_publicacao": parse_dt(raw.get("dataPublicacaoPncp")),
        "data_abertura_proposta": parse_dt(raw.get("dataAberturaProposta")),
        "data_encerramento_proposta": parse_dt(raw.get("dataEncerramentoProposta")),
        "data_atualizacao_global": parse_dt(raw.get("dataAtualizacaoGlobal")),
    }
    if datas["data_publicacao"] is None:
        raise InvalidRecord(f"{id_}: sem dataPublicacaoPncp válida")
    for campo, bruto in (
        ("data_abertura_proposta", raw.get("dataAberturaProposta")),
        ("data_encerramento_proposta", raw.get("dataEncerramentoProposta")),
        ("data_atualizacao_global", raw.get("dataAtualizacaoGlobal")),
    ):
        if bruto and datas[campo] is None:
            avisos.append(f"data_ilegivel:{campo}")
    abertura, fim = datas["data_abertura_proposta"], datas["data_encerramento_proposta"]
    if abertura and fim and fim < abertura:
        avisos.append("encerramento_antes_da_abertura")

    objeto, h1 = _limpa(raw.get("objetoCompra"), MAX_OBJETO)
    compl, h2 = _limpa(raw.get("informacaoComplementar"), MAX_COMPLEMENTAR)
    processo, h3 = _limpa(raw.get("processo"), 100)
    pii += h1 + h2 + h3
    if not objeto:
        avisos.append("objeto_vazio")

    valor = _num(raw.get("valorTotalEstimado"))
    if valor is None:
        avisos.append("valor_ausente")
    elif valor < 0:
        avisos.append("valor_negativo")
        valor = None
    elif valor == 0:
        # no PNCP "sem valor" costuma vir como 0 (orçamento sigiloso ou não informado)
        avisos.append("valor_zero")
        valor = None

    row: dict[str, Any] = {
        "id": str(id_),
        "ano_compra": raw.get("anoCompra"),
        "sequencial_compra": raw.get("sequencialCompra"),
        "numero_compra": _str(raw.get("numeroCompra")),
        "processo": processo,
        "objeto": objeto,
        "informacao_complementar": compl,
        "modalidade_id": raw.get("modalidadeId"),
        "modalidade_nome": raw.get("modalidadeNome"),
        "modo_disputa_nome": raw.get("modoDisputaNome"),
        "srp": raw.get("srp"),
        "situacao_id": raw.get("situacaoCompraId"),
        "situacao_nome": raw.get("situacaoCompraNome"),
        "valor_estimado": valor,
        "valor_homologado": _num(raw.get("valorTotalHomologado")),
        **datas,
        "orgao_cnpj": _get(raw, "orgaoEntidade", "cnpj"),
        "orgao_razao_social": _get(raw, "orgaoEntidade", "razaoSocial"),
        "esfera_id": _get(raw, "orgaoEntidade", "esferaId"),
        "poder_id": _get(raw, "orgaoEntidade", "poderId"),
        "uf": _get(raw, "unidadeOrgao", "ufSigla"),
        "municipio": _get(raw, "unidadeOrgao", "municipioNome"),
        "codigo_ibge": _str(_get(raw, "unidadeOrgao", "codigoIbge")),
        "unidade_nome": _get(raw, "unidadeOrgao", "nomeUnidade"),
        "link_origem": _str(raw.get("linkSistemaOrigem")),
        "amparo_legal": _get(raw, "amparoLegal", "nome"),
    }
    row["dt"] = datas["data_publicacao"].date()  # type: ignore[union-attr]
    row["row_hash"] = row_hash(row)
    row["first_seen_at"] = None
    row["last_changed_at"] = None
    return row, pii, avisos


def _str(valor: Any) -> str | None:
    return None if valor is None or valor == "" else str(valor)


def _jsonable(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def row_hash(row: dict[str, Any]) -> str:
    """Hash do conteúdo (ignora colunas de controle) para detectar alterações."""
    conteudo = {
        k: _jsonable(v)
        for k, v in sorted(row.items())
        if k not in {"row_hash", "first_seen_at", "last_changed_at"}
    }
    blob = json.dumps(conteudo, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def corta_texto(texto: str | None, limite: int) -> str:
    """Corta no fim de uma palavra (nunca no meio) e acrescenta reticências."""
    t = (texto or "").strip()
    if len(t) <= limite:
        return t
    corte = t[: limite - 1]
    if " " in corte[limite // 2 :]:
        corte = corte.rsplit(" ", 1)[0]
    return corte.rstrip(" ,;:-") + "…"


def pncp_url(row: dict[str, Any]) -> str | None:
    """Página pública do edital no PNCP (sempre existe, ao contrário do link de origem)."""
    cnpj, ano, seq = row.get("orgao_cnpj"), row.get("ano_compra"), row.get("sequencial_compra")
    if not (cnpj and ano and seq):
        return None
    return f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}"
