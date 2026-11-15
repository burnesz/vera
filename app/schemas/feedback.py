import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class FeedbackExplicacaoRequest(BaseModel):
    resposta_item_id: uuid.UUID = Field(..., description="ID da resposta do estudante no simulado")


class FeedbackExplicacaoResponse(BaseModel):
    id: uuid.UUID
    resposta_item_id: uuid.UUID
    habilidade_codigo: str
    alternativa_marcada: str
    gabarito_oficial: str
    feedback_content: str
    thought_scratchpad: Optional[str] = None
    context_chunks: List[Dict[str, Any]] = Field(default_factory=list)
    is_verified: bool = True
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
