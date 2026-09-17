import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict


# --- Requisições de Criação de Simulado ---

class SimuladoCreateRequest(BaseModel):
    titulo: Optional[str] = Field(default="Simulado ENEM Matemática", max_length=255)
    descricao: Optional[str] = Field(default=None, max_length=1000)
    tipo: str = Field(default="diagnostico", description="'diagnostico' ou 'geral'")
    proporcao_ineditas: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Proporção de questões inéditas no caderno (padrão: 0.15 = 15%)"
    )


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
    user_id: Optional[uuid.UUID] = None
    total_itens: int
    total_enem: Optional[int] = 0
    total_ineditas: Optional[int] = 0
    itens: List[QuestaoItemResponse]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Listagem e Resumo de Simulados (Hub) ---

class SimuladoResumoResponse(BaseModel):
    id: uuid.UUID
    titulo: str
    descricao: Optional[str] = None
    tipo: str
    total_itens: int
    created_at: datetime
    status: str  # 'pendente' ou 'finalizado'
    tentativa_id: Optional[uuid.UUID] = None
    total_acertos: Optional[int] = None
    score_percentual: Optional[float] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# --- Submissão e Correção do Simulado ---

class RespostaItemInput(BaseModel):
    simulado_item_id: Optional[uuid.UUID] = None
    questao_id: Optional[uuid.UUID] = None
    alternativa_selecionada: Optional[str] = Field(default=None, max_length=1, description="Letra 'A', 'B', 'C', 'D', 'E' ou 'X'")
    alternativa_marcada: Optional[str] = Field(default=None, max_length=1, description="Alias para alternativa_selecionada")

    model_config = ConfigDict(from_attributes=True)


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
