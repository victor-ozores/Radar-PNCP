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


class Score(_Base):
    termos_fortes: list[str] = Field(default_factory=list)
    termos_fracos: list[str] = Field(default_factory=list)
    termos_negativos: list[str] = Field(default_factory=list)
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
    max_vencendo: int = Field(default=5, ge=0, le=20)
    enviar_quando_vazio: bool = True


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
