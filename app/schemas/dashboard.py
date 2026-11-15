import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class HabilidadeProgressoItem(BaseModel):
    habilidade_codigo: str
    competencia: int
    descricao: str
    eixo_tematico: Optional[str] = None
    total_questoes: int
    total_acertos: int
    taxa_acerto: float = Field(..., description="Taxa de acerto de 0.0 a 1.0 (ou 0.0 se não houver tentativas)")
    nivel_dominio: str = Field(..., description="'critico', 'em_desenvolvimento' ou 'consolidado'")
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CompetenciaProgressoItem(BaseModel):
    competencia: int
    titulo: str
    descricao: str
    total_questoes: int
    total_acertos: int
    taxa_acerto: float
    nivel_dominio: str
    habilidades_total: int = 0
    habilidades_consolidadas: int = 0

    model_config = ConfigDict(from_attributes=True)


class TentativaResumoItem(BaseModel):
    tentativa_id: uuid.UUID
    simulado_id: uuid.UUID
    titulo: str
    total_itens: int
    total_acertos: int
    score_percentual: float
    started_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DashboardDesempenhoResponse(BaseModel):
    total_simulados: int
    total_questoes_respondidas: int
    total_acertos: int
    taxa_acerto_global: float
    total_habilidades_consolidadas: int
    total_habilidades_em_desenvolvimento: int
    total_habilidades_criticas: int
    competencias: List[CompetenciaProgressoItem]
    habilidades: List[HabilidadeProgressoItem]
    ultimas_tentativas: List[TentativaResumoItem]

    model_config = ConfigDict(from_attributes=True)
