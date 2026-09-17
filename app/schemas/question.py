"""
Schemas Pydantic para validação estrutural e transferência de dados de Questões Inéditas do ENEM.
Atende a RN-Q01 (validação estrutural de unicidade e formato) e RN-Q02 (schema JSON estrito).
"""

from typing import Dict, Optional, List, Any
import uuid
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict


class QuestaoIneditaLLMOutput(BaseModel):
    """
    Schema estrito para a saída estruturada do LLM Qwen 2.5 via Ollama (format='json').
    Representa a estrutura de um item inédito de Matemática no padrão ENEM.
    """
    enunciado: str = Field(
        ...,
        description="Texto-base contextualizado e comando da questão, no padrão do ENEM."
    )
    alternativas: Dict[str, str] = Field(
        ...,
        description="Dicionário com exatamente 5 alternativas identificadas pelas chaves 'A', 'B', 'C', 'D' e 'E'."
    )
    gabarito: str = Field(
        ...,
        description="Letra da alternativa correta única ('A', 'B', 'C', 'D' ou 'E')."
    )
    justificativa: str = Field(
        ...,
        description="Resolução detalhada passo a passo e justificativa do porquê dos distratores estarem incorretos."
    )
    thought_scratchpad: Optional[str] = Field(
        None,
        description="Raciocínio Chain-of-Thought interno percorrido pelo modelo durante o planejamento do item."
    )

    @field_validator("gabarito")
    @classmethod
    def validate_gabarito(cls, v: str) -> str:
        clean_v = v.strip().upper()
        if clean_v not in {"A", "B", "C", "D", "E"}:
            raise ValueError(f"Gabarito deve ser exatamente uma das letras A, B, C, D ou E. Recebido: '{v}'")
        return clean_v

    @field_validator("alternativas")
    @classmethod
    def validate_alternativas(cls, v: Dict[str, str]) -> Dict[str, str]:
        expected_keys = {"A", "B", "C", "D", "E"}
        normalized_keys = {k.strip().upper(): str(val).strip() for k, val in v.items()}
        
        if set(normalized_keys.keys()) != expected_keys:
            raise ValueError(
                f"As alternativas devem conter exatamente as chaves A, B, C, D, E. "
                f"Chaves recebidas: {sorted(list(normalized_keys.keys()))}"
            )

        for letter, text in normalized_keys.items():
            if not text:
                raise ValueError(f"O texto da alternativa '{letter}' não pode ser vazio.")

        # RN-Q01: Ausência de alternativas duplicadas
        vals = [text.strip().lower() for text in normalized_keys.values()]
        if len(set(vals)) != len(vals):
            raise ValueError("RN-Q01 violada: foram encontradas alternativas com textos idênticos/duplicados.")

        return normalized_keys

    @field_validator("enunciado")
    @classmethod
    def validate_enunciado(cls, v: str) -> str:
        clean = v.strip()
        if len(clean) < 40:
            raise ValueError(f"Enunciado muito curto ({len(clean)} caracteres) para o padrão contextualizado do ENEM.")
        return clean


class QuestaoIneditaBase(BaseModel):
    habilidade_codigo: str = Field(..., description="Código da Habilidade da Matriz de Referência (ex: 'H01')")
    enunciado: str = Field(..., description="Enunciado completo da questão")
    alternativas: Dict[str, str] = Field(..., description="Dicionário com as alternativas A, B, C, D, E")
    gabarito: str = Field(..., description="Letra do gabarito oficial ('A' a 'E')")
    justificativa: str = Field(..., description="Justificativa da resposta e resolução")
    thought_scratchpad: Optional[str] = None
    is_validated: bool = True


class QuestaoIneditaCreate(QuestaoIneditaBase):
    pass


class QuestaoIneditaResponse(QuestaoIneditaBase):
    id: uuid.UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class QuestaoGenerateRequest(BaseModel):
    habilidade_codigo: str = Field(
        ...,
        description="Código da habilidade da Matriz do ENEM para gerar o item (ex: 'H01')"
    )
    num_few_shot_examples: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Quantidade de itens reais de treino do PostgreSQL a injetar no prompt (padrão 2)"
    )


class BatchPopulationRequest(BaseModel):
    habilidades: Optional[List[str]] = Field(
        None,
        description="Lista de códigos de habilidades específicas (ex: ['H01', 'H02']). Se omitido, processa todas as 30."
    )
    count_per_habilidade: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Número de questões inéditas a gerar por habilidade (padrão 1)"
    )
    num_few_shot_examples: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Número de exemplos históricos few-shot a usar no prompt"
    )


class BatchPopulationItemResult(BaseModel):
    habilidade_codigo: str
    questao_id: Optional[uuid.UUID] = None
    success: bool
    attempts: int
    error: Optional[str] = None
    elapsed_seconds: float


class BatchPopulationSummary(BaseModel):
    total_habilidades_processadas: int
    total_sucesso: int
    total_falhas: int
    tempo_total_segundos: float
    itens: List[BatchPopulationItemResult]
