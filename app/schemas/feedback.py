from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class FeedbackRequest(BaseModel):
    """
    Schema de requisição para geração de feedback pedagógico personalizado.
    """
    question_id: Optional[str] = Field(default=None, description="ID único ou identificador da questão")
    enunciado: str = Field(..., min_length=10, description="Texto do enunciado da questão do ENEM")
    alternativas: Dict[str, str] = Field(
        ...,
        description="Mapeamento das alternativas de A a E, ex: {'A': '...', 'B': '...'}"
    )
    gabarito: str = Field(..., description="Letra da alternativa correta (A, B, C, D ou E)")
    resposta_aluno: str = Field(..., description="Letra da alternativa assinalada pelo estudante")
    habilidade: Optional[str] = Field(default="Matemática do ENEM", description="Código ou descrição da habilidade da Matriz INEP")
    top_k_context: int = Field(default=3, ge=1, le=10, description="Quantidade de trechos didáticos para resgate no Pinecone")

    @field_validator("gabarito", "resposta_aluno")
    @classmethod
    def validate_alternative_letter(cls, v: str) -> str:
        clean = v.strip().upper()
        if clean not in ["A", "B", "C", "D", "E"]:
            raise ValueError(f"Alternativa inválida: '{v}'. Deve ser uma letra entre A e E.")
        return clean

    @field_validator("alternativas")
    @classmethod
    def validate_alternativas_dict(cls, v: Dict[str, str]) -> Dict[str, str]:
        if len(v) < 2:
            raise ValueError("A questão deve conter pelo menos 2 alternativas.")
        normalized = {k.strip().upper(): str(val).strip() for k, val in v.items()}
        return normalized


class FeedbackContextChunk(BaseModel):
    """
    Trecho de material didático resgatado do Pinecone para compor o contexto do RAG.
    """
    id: str
    title: str
    topic: str
    text: str
    score: float
    page_number: Optional[int] = None
    document_name: Optional[str] = None


class FeedbackVerification(BaseModel):
    """
    Resultado da validação automática de consistência entre o feedback gerado e o gabarito oficial (RN-FB01 / RN-FB02).
    """
    is_valid: bool = Field(..., description="Se o feedback foi aprovado na verificação de consistência")
    verified_against_gabarito: bool = Field(..., description="Se a alternativa do gabarito foi confirmada na resolução")
    detected_answer: Optional[str] = Field(default=None, description="Alternativa identificada como correta pelo modelo")
    confidence: float = Field(default=1.0, description="Nível de confiança da verificação")
    details: str = Field(default="", description="Detalhes ou logs do processo de verificação")


class FeedbackResponse(BaseModel):
    """
    Resposta estruturada contendo o feedback pedagógico gerado, contexto utilizado e validação.
    """
    feedback_markdown: str = Field(..., description="Feedback didático formatado em Markdown com seções CoT")
    context_chunks: List[FeedbackContextChunk] = Field(default_factory=list, description="Materiais didáticos que embasaram a resposta")
    verification: FeedbackVerification = Field(..., description="Resultado do guardrail de verificação de consistência")
    inference_time_seconds: float = Field(..., description="Tempo de processamento e inferência em segundos")
    status: str = Field(default="success", description="Status da operação: success, retained, error")
