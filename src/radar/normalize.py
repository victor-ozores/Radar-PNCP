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


# --------------------------------------------------------------------------- texto para leitura
# Estas regras existem também em site/src/lib/formatos.ts. Se mudar uma, mude a outra e os testes.

VALOR_MINIMO_CONFIAVEL = 1_000  # abaixo disto o valor costuma ser preenchimento simbólico (R$ 0,04)


def valor_confiavel(valor: float | None) -> float | None:
    """O valor, se der para confiar nele; senão ``None`` ("valor não informado")."""
    if valor is None or valor != valor or valor < VALOR_MINIMO_CONFIAVEL:  # != : NaN
        return None
    return valor


_ETIQUETA_DO_SISTEMA = re.compile(r"^\s*\[[^\]]{1,60}\]\s*[-–:]?\s*")


def limpa_objeto(objeto: str | None) -> str:
    """Tira do começo a etiqueta do sistema que publicou ("[Portal de Compras Públicas] - ")."""
    texto = (objeto or "").strip()
    return _ETIQUETA_DO_SISTEMA.sub("", texto, count=1).strip() or texto


_PALAVRAS_PEQUENAS = frozenset(
    [
        "a",
        "as",
        "o",
        "os",
        "e",
        "em",
        "de",
        "da",
        "das",
        "do",
        "dos",
        "na",
        "nas",
        "no",
        "nos",
        "para",
        "por",
        "com",
        "sem",
        "ao",
        "aos",
        "ou",
        "um",
        "uma",
        "pelo",
        "pela",
        "pelos",
        "pelas",
        "que",
        "à",
        "às",
    ]
)
_SIGLAS = frozenset(
    (  # noqa: SIM905
        "ubs upa cras creas caps cei cmei emei emef cbuq bdi nbr abnt srp pncp cnpj cpf ltda epp ete "
        "eta epi art rrt crea cau saae sabesp copasa sanepar cemig der dnit tjmg tjsp tjrj trf trt "
        "ufmg ufpr usp unesp unicamp ifsp ifmg ifpr fiocruz sus ses sms pmf led pvc pead pcmso ltcat "
        "embrapa sesc senai senac sebrae incra ibama utfpr ufrj uff ufv fnde pac avcb ee cep emeb "
        "uenp fnhis cefet cemei usf icb cer cpi sam cac utm saa mdic mesp deadm diap dehis decs "
        "deart fad sesa semop repi iftm dga secod pirf tre copom saaeb feq baep cope femib cejusc "
        "fema cro ufjf sesmg sema seduc sesp"
    ).split()
)
# Nomes de órgãos vêm sem acento na origem; só estas palavras, que se repetem muito, voltam acentuadas.
_ACENTOS = {
    "municipio": "município",
    "municipios": "municípios",
    "justica": "justiça",
    "saude": "saúde",
    "educacao": "educação",
    "agropecuaria": "agropecuária",
    "publico": "público",
    "publica": "pública",
    "publicos": "públicos",
    "publicas": "públicas",
    "fundacao": "fundação",
    "camara": "câmara",
    "consorcio": "consórcio",
    "consorcios": "consórcios",
    "ministerio": "ministério",
    "policia": "polícia",
    "seguranca": "segurança",
    "administracao": "administração",
    "assistencia": "assistência",
    "agencia": "agência",
    "ciencia": "ciência",
    "ciencias": "ciências",
    "regiao": "região",
    "orgao": "órgão",
    "agua": "água",
    "aguas": "águas",
    "habitacao": "habitação",
    "transito": "trânsito",
    "superintendencia": "superintendência",
    "servico": "serviço",
    "servicos": "serviços",
    "estancia": "estância",
    "turistica": "turística",
    "parana": "paraná",
    "sao": "são",
    "jose": "josé",
    "joao": "joão",
    "conceicao": "conceição",
    "goias": "goiás",
}
_PRONOMES_COLADOS = frozenset(
    ["se", "lhe", "lhes", "me", "te", "nos", "vos", "lo", "la", "los", "las"]
)
_SEM_VOGAL = re.compile(r"^[^aeiouáéíóúâêôãõ]+$", re.IGNORECASE)
_ROMANO = re.compile(r"^[IVX]{1,4}$")
_PALAVRA = re.compile(r"[^\W_]+")
# "DR.", "AV." e parecidos: abreviação com inicial maiúscula, não sigla.
_ABREVIACOES = frozenset(["dr", "dra", "sr", "sra", "av", "prof", "profa", "eng"])


def _tem_letra(palavra: str) -> bool:
    return any(c.isalpha() for c in palavra)


def _eh_maiuscula(palavra: str) -> bool:
    """Tem letra e nenhuma minúscula."""
    return _tem_letra(palavra) and palavra == palavra.upper()


def _trechos_gritando(palavras: list[re.Match[str]]) -> list[tuple[int, int]]:
    """Trechos de palavras seguidas só em maiúsculas (número no meio não interrompe): (primeira, última).

    Só conta como "gritando" quando é longo: 3 palavras e 12 letras. Sigla solta ("UBS") não é.
    """
    trechos: list[tuple[int, int]] = []
    i = 0
    while i < len(palavras):
        if not _eh_maiuscula(palavras[i].group(0)):
            i += 1
            continue
        j, ultima, maiusculas, letras = i, i, 0, 0
        while j < len(palavras) and (
            _eh_maiuscula(palavras[j].group(0)) or not _tem_letra(palavras[j].group(0))
        ):
            if _eh_maiuscula(palavras[j].group(0)):
                maiusculas += 1
                letras += sum(c.isalpha() for c in palavras[j].group(0))
                ultima = j
            j += 1
        if maiusculas >= 3 and letras >= 12:
            trechos.append((i, ultima))
        i = j
    return trechos


def esta_gritando(texto: str) -> bool:
    """Tem um trecho longo em MAIÚSCULAS (como muitos objetos e órgãos do PNCP)?"""
    return bool(_trechos_gritando(list(_PALAVRA.finditer(texto))))


def _suaviza_palavra(
    m: re.Match[str], primeira_do_trecho: bool, texto: str, restaura_acentos: bool
) -> str:
    palavra = m.group(0)
    if any(c.isdigit() for c in palavra):
        return palavra
    baixa, base = palavra.lower(), fold(palavra)
    if len(palavra) == 1:
        return (
            baixa if baixa in {"a", "e", "o", "à"} and not primeira_do_trecho else palavra.upper()
        )
    if m.start() > 0 and texto[m.start() - 1] == "-" and baixa in _PRONOMES_COLADOS:
        return baixa  # "refere-se", "dê-lhe"
    sigla = (
        base in _SIGLAS
        or _ROMANO.match(palavra)
        or (len(palavra) <= 5 and _SEM_VOGAL.match(palavra) and base not in _ABREVIACOES)
    )
    if sigla:
        return palavra.upper()
    if not primeira_do_trecho and baixa in _PALAVRAS_PEQUENAS:
        return baixa
    final = _ACENTOS.get(base, baixa) if restaura_acentos else baixa
    return final[:1].upper() + final[1:]


def suaviza_caixa(texto: str, restaura_acentos: bool = False) -> str:
    """O trecho em CAIXA ALTA vira "Caixa Alta Normal" (preposições em minúsculas, siglas mantidas).

    Só para ler na tela e no Telegram: o texto guardado não muda, o resto do texto também não, e
    texto que já está em caixa normal passa sem alteração.
    """
    palavras = list(_PALAVRA.finditer(texto))
    trechos = _trechos_gritando(palavras)
    if not trechos:
        return texto
    trocas = {
        k: _suaviza_palavra(palavras[k], k == de, texto, restaura_acentos)
        for de, ate in trechos
        for k in range(de, ate + 1)
    }
    return _aplica_trocas(texto, palavras, trocas)


def _aplica_trocas(texto: str, palavras: list[re.Match[str]], trocas: dict[int, str]) -> str:
    """Troca só as palavras indicadas; o que está entre elas (espaços, pontuação) fica como estava."""
    saida: list[str] = []
    cursor = 0
    for k, m in enumerate(palavras):
        if k in trocas:
            saida += [texto[cursor : m.start()], trocas[k]]
            cursor = m.end()
    return "".join(saida) + texto[cursor:]


def acerta_cidade(orgao: str, municipio: str | None) -> str:
    """Onde o nome do órgão cita a cidade, usa a grafia da cidade como o próprio edital a traz.

    O nome do órgão chega sem acento ("Município de Ibirite") e a cidade do mesmo edital vem certa
    ("Ibirité"). Só entram palavras que diferem no acento ou na caixa, então o sentido não muda.
    """
    cidade = [m.group(0) for m in _PALAVRA.finditer(municipio or "")]
    palavras = list(_PALAVRA.finditer(orgao))
    alvo = [fold(c) for c in cidade]
    trocas: dict[int, str] = {}
    i = 0
    while cidade and i + len(cidade) <= len(palavras):
        if [fold(p.group(0)) for p in palavras[i : i + len(cidade)]] == alvo:
            trocas.update({i + k: c for k, c in enumerate(cidade)})
            i += len(cidade)
        else:
            i += 1
    return _aplica_trocas(orgao, palavras, trocas) if trocas else orgao


def nome_do_orgao(orgao: str | None, municipio: str | None) -> str:
    """O órgão como se lê na tela e no Telegram: caixa normal, acentos das palavras comuns e da cidade."""
    return acerta_cidade(suaviza_caixa(orgao or "", restaura_acentos=True), municipio)


#: situacaoCompraId de um edital que o PNCP **excluiu** (HTTP 410 na consulta individual). Não vem da
#: API: é nosso, para tirar o edital das listas sem apagar a linha.
SITUACAO_EXCLUIDA = 99
SITUACAO_EXCLUIDA_NOME = "Excluída do PNCP"

_ID_PNCP = re.compile(r"^(\d{14})-\d+-(\d+)/(\d{4})$")


def partes_do_id(id_: str | None) -> tuple[str, int, int] | None:
    """``numeroControlePNCP`` -> (cnpj do órgão, ano, sequencial), como a consulta individual pede."""
    m = _ID_PNCP.match(id_ or "")
    return (m.group(1), int(m.group(3)), int(m.group(2))) if m else None


def numero_do_edital(row: dict[str, Any]) -> str:
    """Ex.: "12/2026". Alguns órgãos preenchem o campo com lixo ("12 | Processo 1161"): fica o começo.

    Sem número que preste, devolve texto vazio (quem usa não inventa um).
    """
    numero = re.split(r"[|;]", str(row.get("numero_compra") or ""))[0].strip()
    if not numero or len(numero) > 20:
        return ""
    ano = row.get("ano_compra")
    return numero + (f"/{ano}" if ano and "/" not in numero else "")


def pncp_url(row: dict[str, Any]) -> str | None:
    """Página pública do edital no PNCP (sempre existe, ao contrário do link de origem)."""
    cnpj, ano, seq = row.get("orgao_cnpj"), row.get("ano_compra"), row.get("sequencial_compra")
    if not (cnpj and ano and seq):
        return None
    return f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}"
