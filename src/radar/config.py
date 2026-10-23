"""Leitura e validação do config.yaml (perfil de interesse e parâmetros da ingestão)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Perfil(_Base):
    nome: str
    descricao: str = ""


class Ingestao(_Base):
    ufs: list[str] = Field(min_length=1)
    modalidades: list[int] = Field(min_length=1)
    lookback_dias: int = Field(default=3, ge=1, le=30)
    # Dias de alterações lidos na consulta por atualização (prorrogações, suspensões). Menor que o
    # lookback de publicação porque a consulta devolve ~4x mais linhas (toda alteração conta).
    lookback_atualizacao_dias: int = Field(default=2, ge=1, le=30)
    # Conferência semanal (modo `reconcile`): relê as propostas abertas até daqui a N dias e confere,
    # um a um no PNCP, os editais que o robô guarda como abertos mas a listagem não traz mais
    # (excluídos do PNCP, prazo prorrogado). `conferencias_max` limita as consultas por execução.
    reconciliacao_dias: int = Field(default=14, ge=1, le=60)
    conferencias_max: int = Field(default=150, ge=0, le=500)
    # "Prazos chegando" confere no PNCP cada edital antes de listá-lo (no máximo N consultas por dia)
    conferencias_alerta_max: int = Field(default=15, ge=0, le=50)
    # Todo dia confere no PNCP, um a um, os editais que combinam e vencem nos próximos N dias, do que
    # vence primeiro ao que vence depois, até `conferencias_urgentes_max` consultas. A lista do PNCP
    # demora horas para refletir uma exclusão ou prorrogação, e quem age num edital de amanhã não pode
    # ter o prazo errado. 0 desliga.
    conferencia_urgente_dias: int = Field(default=3, ge=0, le=14)
    conferencias_urgentes_max: int = Field(default=100, ge=0, le=300)
    tamanho_pagina: int = Field(default=50, ge=10, le=50)
    intervalo_minimo_s: float = Field(default=4.0, ge=1.0)
    backoff_429_s: list[float] = Field(default_factory=lambda: [30, 60, 120], min_length=1)
    max_tentativas_5xx: int = Field(default=4, ge=1, le=8)
    timeout_s: float = Field(default=60, gt=0)
    max_paginas_por_serie: int = Field(default=400, ge=1)

    @field_validator("ufs")
    @classmethod
    def _ufs(cls, v: list[str]) -> list[str]:
        out = [u.strip().upper() for u in v]
        bad = [u for u in out if len(u) != 2 or not u.isalpha()]
        if bad:
            raise ValueError(f"UF inválida: {bad}")
        return out

    @field_validator("modalidades")
    @classmethod
    def _modalidades(cls, v: list[int]) -> list[int]:
        bad = [m for m in v if not 1 <= m <= 13]
        if bad:
            raise ValueError(f"Código de modalidade fora de 1..13: {bad}")
        return v


class Filtros(_Base):
    valor_min: float = Field(default=0, ge=0)
    valor_max: float | None = None

    @model_validator(mode="after")
    def _faixa(self) -> Filtros:
        if self.valor_max is not None and self.valor_max < self.valor_min:
            raise ValueError("valor_max menor que valor_min")
        return self


class TermoCompra(_Base):
    """Um termo que indica compra ou locação, com as exceções que o tornam obra ou serviço."""

    termo: str
    # "fornecimento e instalação/aplicação de..." é serviço: o termo é ignorado se vier seguido de um destes
    servico_se_seguido_de: list[str] = Field(default_factory=list)
    # "fornecimento de materiais e mão de obra" é contrato de obra: o termo é ignorado se o texto traz um destes
    obra_se_texto_tem: list[str] = Field(default_factory=list)


class Compra(_Base):
    """Regra firme: texto cuja primeira palavra-núcleo é compra ou locação recebe nota zero.

    Uma penalidade não basta: três termos fortes ("construção", "reforma", "ampliação") somam +70
    e cobrem um -40. A regra olha o que o texto *pede primeiro*, não só o começo literal.
    """

    termos: list[TermoCompra] = Field(default_factory=list)
    abre_com: list[str] = Field(default_factory=list)  # ex.: "Materiais para manutenção..."
    # Se uma destas palavras vem ANTES do termo de compra, o texto é obra ("execução ... incluindo a aquisição")
    nucleos_de_obra: list[str] = Field(default_factory=list)


class ServicosIntelectuais(_Base):
    """Regra firme: consultoria, fiscalização e projeto são serviço de escritório, não obra.

    Uma construtora executa a obra; quem fiscaliza, gerencia ou projeta é outra empresa. O texto
    recebe nota zero quando um destes termos vem antes de qualquer palavra de obra, a menos que
    também peça execução (contratação integrada, "fornecimento e instalação"...).
    """

    termos: list[str] = Field(default_factory=list)  # ex.: "fiscaliza*", "elabora* d* projeto*"
    # Se o texto traz um destes, é projeto + execução e a regra não se aplica
    executa_se_texto_tem: list[str] = Field(default_factory=list)
    # "fase de execução", "fiscalização da execução": quem acompanha não executa. Estas palavras antes de
    # "execução" tiram essa "execução" da conta de `executa_se_texto_tem`.
    apoio_antes_de_execucao: list[str] = Field(default_factory=list)
    # Palavra de obra que aparece ANTES do termo: o texto é obra ("reforma ... com projeto executivo")
    nucleos_de_obra: list[str] = Field(default_factory=list)


class Score(_Base):
    termos_fortes: list[str] = Field(default_factory=list)
    termos_fracos: list[str] = Field(default_factory=list)
    termos_negativos: list[str] = Field(default_factory=list)
    # Como cada termo aparece para a pessoa no painel ("construcao" -> "construção")
    rotulos: dict[str, str] = Field(default_factory=dict)
    compra: Compra = Field(default_factory=Compra)
    servicos_intelectuais: ServicosIntelectuais = Field(default_factory=ServicosIntelectuais)
    peso_forte: int = 35
    teto_fortes: int = 70
    peso_fraco: int = 8
    teto_fracos: int = 16
    penalidade_negativo: int = 40
    peso_uf: dict[str, int] = Field(default_factory=dict)
    peso_modalidade: dict[int, int] = Field(default_factory=dict)
    bonus_valor_na_faixa: int = 15
    penalidade_valor_fora_faixa: int = 15

    @model_validator(mode="after")
    def _precisa_termos(self) -> Score:
        if not (self.termos_fortes or self.termos_fracos):
            raise ValueError("Defina ao menos um termo forte ou fraco no score")
        return self


class Alerta(_Base):
    score_minimo: int = Field(default=40, ge=0, le=100)
    top_n: int = Field(default=10, ge=1, le=30)
    dias_prazo_proximo: int = Field(default=7, ge=1, le=60)
    # "Prazos chegando" só lista o que ainda dá tempo de disputar: vence entre
    # `prazo_minimo_dias` e `dias_prazo_proximo` dias a partir da execução.
    prazo_minimo_dias: int = Field(default=2, ge=0, le=30)
    max_vencendo: int = Field(default=5, ge=0, le=20)
    enviar_quando_vazio: bool = True
    # Endereço do painel público: vira o link "Ver todos no painel" no alerta. Vazio = sem link.
    painel_url: str | None = None

    @field_validator("painel_url")
    @classmethod
    def _painel_url_valida(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        if v and not v.startswith("https://"):
            raise ValueError("painel_url deve começar com https://")
        return v or None

    @model_validator(mode="after")
    def _janela_de_prazo(self) -> Alerta:
        if self.prazo_minimo_dias >= self.dias_prazo_proximo:
            raise ValueError("prazo_minimo_dias deve ser menor que dias_prazo_proximo")
        return self


class Export(_Base):
    dias_historico: int = Field(default=90, ge=1)
    dias_apos_encerramento: int = Field(default=7, ge=0)


class Config(_Base):
    perfil: Perfil
    ingestao: Ingestao
    filtros: Filtros = Field(default_factory=Filtros)
    score: Score
    alerta: Alerta = Field(default_factory=Alerta)
    export: Export = Field(default_factory=Export)


def load_config(path: str | Path) -> Config:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return Config.model_validate(raw)
