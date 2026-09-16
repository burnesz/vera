import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict


# --- Requisições de Criação de Simulado ---

class SimuladoCreateRequest(BaseModel):
    titulo: Optional[str] = Field(default="Simulado ENEM Matemática", max_length=255)
    descricao: Optional[str] = Field(default=None, max_length=1000)
    tipo: str = Field(default="diagnostico", description="'diagnostico' ou 'geral'")


# --- Resposta do Simulado para Realização da Prova (SEM Gabarito) ---

class QuestaoItemResponse(BaseModel):
    simulado_item_id: uuid.UUID
    ordem: int
    origem_questao: str  # 'enem' ou 'inedita'
    questao_id: uuid.UUID
    ano: Optional[int] = None
    habilidade_codigo: str
    enunciado: str
    alternativas: Dict[str, str]

    model_config = ConfigDict(from_attributes=True)


class SimuladoResponse(BaseModel):
    id: uuid.UUID
    titulo: str
    descricao: Optional[str] = None
    tipo: str
    total_itens: int
    itens: List[QuestaoItemResponse]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Submissão e Correção do Simulado ---

class RespostaItemInput(BaseModel):
    simulado_item_id: uuid.UUID
    alternativa_selecionada: str = Field(..., max_length=1, description="Letra 'A', 'B', 'C', 'D' ou 'E'")


class SimuladoSubmissaoRequest(BaseModel):
    respostas: List[RespostaItemInput]


class ItemCorrecaoResponse(BaseModel):
    ordem: int
    simulado_item_id: uuid.UUID
    questao_id: uuid.UUID
    habilidade_codigo: str
    alternativa_selecionada: Optional[str] = None
    gabarito_oficial: str
    is_correto: bool


class SimuladoResultadoResponse(BaseModel):
    tentativa_id: uuid.UUID
    simulado_id: uuid.UUID
    user_id: uuid.UUID
    status: str
    total_itens: int
    total_acertos: int
    score_percentual: float
    started_at: datetime
    completed_at: Optional[datetime] = None
    itens: List[ItemCorrecaoResponse]

    model_config = ConfigDict(from_attributes=True)
