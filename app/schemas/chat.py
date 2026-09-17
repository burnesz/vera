import time
from datetime import datetime
from typing import List, Optional, Literal, Any
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """
    Representação de uma mensagem individual no histórico de conversação.
    """
    id: Optional[str] = Field(default=None, description="Identificador único da mensagem no banco de dados")
    role: Literal["user", "assistant", "system"] = Field(..., description="Papel do remetente da mensagem")
    content: str = Field(..., description="Conteúdo textual da mensagem")
    thought: Optional[str] = Field(
        default=None,
        description="Raciocínio interno e validação matemática passo a passo (Chain-of-Thought Scratchpad), se houver"
    )
    timestamp: float = Field(default_factory=time.time, description="Timestamp Unix da criação da mensagem")
    created_at: Optional[datetime] = Field(default=None, description="Data/hora formatada de criação")
    context_chunks: List[Any] = Field(default_factory=list, description="Chunks teóricos vinculados à resposta")


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
    titulo: Optional[str] = Field(default=None, description="Título da conversa")
    messages: List[ChatMessage] = Field(default_factory=list, description="Lista de mensagens da sessão")
    total_messages: int = Field(..., description="Quantidade total de mensagens na sessão")


class ChatSessionSummary(BaseModel):
    """
    Resumo de uma sessão de conversa para listagem no painel lateral.
    """
    id: str = Field(..., description="Identificador único da sessão")
    titulo: str = Field(..., description="Título da conversa")
    created_at: datetime = Field(..., description="Data/hora de criação")
    updated_at: datetime = Field(..., description="Data/hora da última mensagem")
    total_messages: int = Field(default=0, description="Quantidade total de mensagens na sessão")


class ChatSessionListResponse(BaseModel):
    """
    Lista de conversas do usuário.
    """
    sessions: List[ChatSessionSummary] = Field(default_factory=list, description="Lista de sessões de conversa do estudante")
    total: int = Field(..., description="Total de sessões encontradas")


class UpdateChatSessionRequest(BaseModel):
    """
    Requisição para renomear uma sessão de conversa.
    """
    titulo: str = Field(..., min_length=1, max_length=255, description="Novo título da conversa")

