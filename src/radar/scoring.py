"""Score de relevância por regras (determinístico e explicável).

Cada edital recebe uma nota de 0 a 100 e a lista de motivos que levou a ela. As regras e
os pesos vêm do ``config.yaml``; este módulo só aplica.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from radar.config import Config
from radar.normalize import fold

#: situacaoCompraId do PNCP: 2 revogada, 3 anulada, 4 suspensa
SITUACOES_INATIVAS = {2, 3, 4}
_NOMES_INATIVOS = ("revogad", "anulad", "suspens")

#: "mão de obra" aparece em quase todo contrato de serviços (limpeza, vigilância...) e não
#: indica obra de engenharia; sai do texto antes de comparar com os termos do perfil.
_MAO_DE_OBRA = re.compile(r"\bmao[\s-]+de[\s-]+obra\b")


def _term_regex(term: str) -> str:
    partes = []
    for tok in fold(term).split(" "):
        if tok.endswith("*"):
            partes.append(re.escape(tok[:-1]) + r"\w*")
        else:
            partes.append(re.escape(tok))
    return r"\s+".join(partes)


def compile_term(term: str) -> re.Pattern[str]:
    """``obra*`` casa com obra/obras; frases com espaço casam palavra a palavra."""
    return re.compile(r"\b" + _term_regex(term) + r"\b")


#: Tudo o que pode vir antes do verbo de compra sem mudar o sentido: "[Portal de Compras
#: Públicas] -", "SRP", "Registro de preços para a futura e eventual", "Contratação para a".
_ABERTURA = (
    r"^(?:\[[^\]]*\]\s*-?\s*)?(?:srp\s+)?"
    r"(?:registro\s+de\s+precos?\s*(?:para|visando|objetivando)?\s*)?"
    r"(?:a\s+)?(?:futura\s+e\s+eventual\s+)?(?:contratacao\s+)?(?:para\s+)?(?:a\s+)?"
)


def compile_abertura(termos: list[str]) -> re.Pattern[str] | None:
    """Casa quando o objeto *abre* com um dos termos (ex.: "Registro de preços para aquisição")."""
    if not termos:
        return None
    alternativas = "|".join(_term_regex(t) for t in termos)
    return re.compile(_ABERTURA + r"(?:" + alternativas + r")\b")


@dataclass
class ScoreResult:
    score: int
    relevante: bool
    motivos: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


class Scorer:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        s = cfg.score
        self._fortes = [(t, compile_term(t)) for t in s.termos_fortes]
        self._fracos = [(t, compile_term(t)) for t in s.termos_fracos]
        self._negativos = [(t, compile_term(t)) for t in s.termos_negativos]
        self._compra = compile_abertura(s.abre_com_exclusao)

    def score(self, row: dict[str, Any], agora: datetime) -> ScoreResult:
        s = self.cfg.score
        motivos: list[str] = []
        flags: list[str] = []

        if self._inativo(row):
            return ScoreResult(
                0, False, ["situação inativa (revogada/anulada/suspensa)"], ["inativo"]
            )

        fim = row.get("data_encerramento_proposta")
        if isinstance(fim, datetime) and fim < agora:
            return ScoreResult(0, False, ["prazo de propostas encerrado"], ["encerrado"])

        texto = _MAO_DE_OBRA.sub(" ", fold(row.get("objeto")))
        if self._compra and self._compra.search(texto):
            # Compra de produto: uma penalidade não basta, pois três termos fortes ("construção",
            # "reforma", "ampliação") somam +70 e cobrem os -40 (visto em produção, 20/10/2026).
            return ScoreResult(
                0,
                False,
                ["compra de material: o objeto abre com aquisição/fornecimento"],
                ["compra"],
            )
        fortes = [t for t, p in self._fortes if p.search(texto)]
        fracos = [t for t, p in self._fracos if p.search(texto)]
        negativos = [t for t, p in self._negativos if p.search(texto)]

        if not fortes and not fracos:
            return ScoreResult(0, False, ["nenhum termo do perfil no objeto"], flags)

        total = 0
        if fortes:
            pts = min(len(fortes) * s.peso_forte, s.teto_fortes)
            total += pts
            motivos.append(f"+{pts} termos fortes: {', '.join(fortes)}")
        if fracos:
            pts = min(len(fracos) * s.peso_fraco, s.teto_fracos)
            total += pts
            motivos.append(f"+{pts} termos fracos: {', '.join(fracos)}")
        if negativos:
            total -= s.penalidade_negativo
            motivos.append(f"-{s.penalidade_negativo} termos de exclusão: {', '.join(negativos)}")

        pts_uf = s.peso_uf.get(str(row.get("uf") or "").upper(), 0)
        if pts_uf:
            total += pts_uf
            motivos.append(f"+{pts_uf} UF {row.get('uf')}")
        pts_mod = s.peso_modalidade.get(row.get("modalidade_id") or 0, 0)
        if pts_mod:
            total += pts_mod
            motivos.append(f"+{pts_mod} modalidade {row.get('modalidade_nome')}")

        valor = row.get("valor_estimado")
        if not valor:  # None ou 0: orçamento sigiloso ou não informado
            flags.append("valor_nao_informado")
        else:
            f = self.cfg.filtros
            if valor >= f.valor_min and (f.valor_max is None or valor <= f.valor_max):
                total += s.bonus_valor_na_faixa
                motivos.append(f"+{s.bonus_valor_na_faixa} valor na faixa")
            else:
                total -= s.penalidade_valor_fora_faixa
                motivos.append(f"-{s.penalidade_valor_fora_faixa} valor fora da faixa")
                flags.append("valor_fora_da_faixa")

        total = max(0, min(100, total))
        return ScoreResult(total, total >= self.cfg.alerta.score_minimo, motivos, flags)

    @staticmethod
    def _inativo(row: dict[str, Any]) -> bool:
        if row.get("situacao_id") in SITUACOES_INATIVAS:
            return True
        nome = fold(row.get("situacao_nome"))
        return any(n in nome for n in _NOMES_INATIVOS)
