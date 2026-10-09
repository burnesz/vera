"""
Schemas Pydantic para validação estrutural e transferência de dados de Questões Inéditas do ENEM.
Atende a RN-Q01 (validação estrutural de unicidade e formato) e RN-Q02 (schema JSON estrito).
"""

from typing import Dict, Optional, List, Any
import uuid
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict


class QuestaoEnunciadoSolverOutput(BaseModel):
    """
    Schema estruturado para a Fase 1 da geração Program-Aided (PoT):
    O modelo produz exclusivamente o enunciado e o código Python do solver.
    """
    enunciado: str = Field(
        ...,
        description="Texto contextualizado da questão com comando final inequívoco."
    )
    tabela_dados: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Se o problema envolver tabela de dados, coloque-a aqui como uma lista de dicionários (cada dicionário é uma linha)."
    )
    solver: str = Field(
        ...,
        description="Função Python def resolver() calculando a resposta exata ('correta') e 4 distratores plausíveis ('distratores')."
    )

    @field_validator("enunciado")
    @classmethod
    def validate_enunciado(cls, v: str) -> str:
        clean = v.strip()
        if len(clean) < 30:
            raise ValueError("O enunciado deve conter uma situação-problema completa (mínimo de 30 caracteres).")
        return clean

    @field_validator("solver")
    @classmethod
    def validate_solver(cls, v: str) -> str:
        clean = v.strip()
        if "def resolver" not in clean:
            raise ValueError("O código do solver deve definir obrigatoriamente a função 'def resolver()'.")
        return clean


class QuestaoJustificativaOutput(BaseModel):
    """
    Schema estruturado para a Fase 2 da geração Program-Aided (PoT):
    O modelo redige a justificativa pedagógica com gabarito já conhecido e fixado por código.
    """
    justificativa: str = Field(
        ...,
        description="Explicação pedagógica passo a passo comprovando o gabarito e apontando o erro nos distratores."
    )


class QuestaoAutoValidacaoOutput(BaseModel):
    """
    Schema para a Fase de Auto-Validação da questão inédita gerada.
    A LLM testa a questão, resolve e verifica problemas de ambiguidade ou sentido.
    """
    faz_sentido_semanticamente: bool = Field(..., description="A questão faz sentido no mundo real e tem coerência?")
    sem_ambiguidade: bool = Field(..., description="A questão está livre de ambiguidades e dupla interpretação?")
    informacao_suficiente: bool = Field(..., description="Todas as informações necessárias para resolver estão presentes no texto?")
    sem_erros_vazamentos: bool = Field(..., description="O texto está livre de erros de português e NÃO contém palavras como 'solver', 'python', 'código' ou 'variável'?")
    resposta_nas_alternativas: bool = Field(..., description="Ao resolver mentalmente, a resposta obtida se encontra entre as alternativas fornecidas?")
    justificativa_resolucao: str = Field(..., description="Sua resolução passo a passo detalhada e didática provando qual é a alternativa correta e o erro das outras.")
    feedback_correcao: Optional[str] = Field(None, description="Se qualquer validação acima for falsa, explique detalhadamente O QUE DEVE SER CORRIGIDO no enunciado ou código.")
    aprovada: bool = Field(..., description="True APENAS SE todas as 5 checagens booleanas acima forem True.")


class QuestaoIneditaLLMOutput(BaseModel):
    """
    Schema estrito para a saída estruturada do LLM Qwen 2.5 via Ollama (format='json').
    Representa a estrutura de um item inédito de Matemática no padrão ENEM.
    """
    enunciado: str = Field(
        ...,
        description="Texto-base contextualizado e comando da questão, no padrão do ENEM."
    )
    tabela_dados: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Se o problema envolver tabela de dados, coloque-a aqui como uma lista de dicionários (cada dicionário é uma linha)."
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
    habilidades_com_erro: List[str] = Field(default_factory=list, description="Lista de códigos das habilidades que falharam em todas as tentativas")
    itens: List[BatchPopulationItemResult]
