import time
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """
    Representação de uma mensagem individual no histórico de conversação.
    """
    role: Literal["user", "assistant", "system"] = Field(..., description="Papel do remetente da mensagem")
    content: str = Field(..., description="Conteúdo textual da mensagem")
    thought: Optional[str] = Field(
        default=None,
        description="Raciocínio interno e validação matemática passo a passo (Chain-of-Thought Scratchpad), se houver"
    )
    timestamp: float = Field(default_factory=time.time, description="Timestamp Unix da criação da mensagem")


class ChatContextChunk(BaseModel):
    """
    Trecho de material didático confiável resgatado do Pinecone para embasar a resposta da tutora.
    """
    id: str = Field(..., description="Identificador único do chunk no Pinecone")
    title: str = Field(..., description="Título do documento ou tópico didático")
    topic: str = Field(default="", description="Tópico matemático associado")
    text: str = Field(..., description="Conteúdo teórico do trecho")
    score: float = Field(..., description="Score de similaridade de cosseno com a pergunta")
    page_number: Optional[int] = Field(default=None, description="Número da página no documento original")
    document_name: Optional[str] = Field(default=None, description="Nome do arquivo PDF de origem")


class ChatRequest(BaseModel):
    """
    Requisição de envio de mensagem para o Chatbot especialista em Matemática.
    """
    message: str = Field(..., min_length=1, description="Pergunta ou mensagem enviada pelo estudante")
    session_id: Optional[str] = Field(
        default=None,
        description="Identificador único da sessão de conversa para manter memória de contexto multiturno. Se omitido, uma nova sessão será criada."
    )
    top_k_context: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Quantidade de trechos didáticos para resgate no Pinecone"
    )


class ChatResponse(BaseModel):
    """
    Resposta retornada pelo Chatbot especialista com raciocínio pedagógico e fontes consultadas.
    """
    reply: str = Field(..., description="Resposta didática formatada em Markdown gerada pela tutora VERA")
    thought: Optional[str] = Field(
        default=None,
        description="Raciocínio interno e validação matemática passo a passo da Tutora (Chain-of-Thought Scratchpad)"
    )
    session_id: str = Field(..., description="Identificador da sessão da conversa")
    context_chunks: List[ChatContextChunk] = Field(
        default_factory=list,
        description="Trechos teóricos resgatados do Pinecone que fundamentaram a resposta"
    )
    inference_time_seconds: float = Field(..., description="Tempo de inferência e processamento em segundos")


class ChatHistoryResponse(BaseModel):
    """
    Histórico completo de mensagens de uma sessão de conversa.
    """
    session_id: str = Field(..., description="Identificador da sessão")
    messages: List[ChatMessage] = Field(default_factory=list, description="Lista de mensagens da sessão")
    total_messages: int = Field(..., description="Quantidade total de mensagens na sessão")
