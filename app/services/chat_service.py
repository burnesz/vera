import time
import uuid
import logging
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.core.prompts import build_chat_prompt
from app.schemas.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatContextChunk,
    ChatHistoryResponse
)
from app.services.llm_client import LLMClient
from app.services.vectorstore import PineconeVectorStore

logger = logging.getLogger(__name__)


class ChatSessionManager:
    """
    Gerenciador de memória de sessões de conversação em memória (multiturno).
    Mantém o histórico de mensagens por sessão com suporte a janela deslizante.
    """

    def __init__(self, max_history_turns: int = 12):
        self._sessions: Dict[str, List[ChatMessage]] = {}
        self.max_history_turns = max_history_turns

    def get_or_create_session(self, session_id: Optional[str] = None) -> str:
        if not session_id or not session_id.strip():
            session_id = f"sess_{uuid.uuid4().hex[:10]}"
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        return session_id

    def add_message(self, session_id: str, role: str, content: str) -> ChatMessage:
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        
        msg = ChatMessage(role=role, content=content, timestamp=time.time())
        self._sessions[session_id].append(msg)

        # Aplica janela deslizante para limitar o tamanho do histórico
        if len(self._sessions[session_id]) > self.max_history_turns:
            self._sessions[session_id] = self._sessions[session_id][-self.max_history_turns:]

        return msg

    def get_history(self, session_id: str, limit: Optional[int] = None) -> List[ChatMessage]:
        messages = self._sessions.get(session_id, [])
        if limit and limit > 0:
            return messages[-limit:]
        return list(messages)

    def clear_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def session_exists(self, session_id: str) -> bool:
        return session_id in self._sessions


# Instância global do gerenciador de sessão para a aplicação
session_manager = ChatSessionManager()


class ChatService:
    """
    Serviço orquestrador do Chatbot RAG de Matemática:
    1. Recupera o histórico da sessão (memória multiturno).
    2. Resgata materiais didáticos relevantes no Pinecone (materiais_didaticos).
    3. Constrói o prompt estruturado com raciocínio Chain-of-Thought (CoT).
    4. Envia para o LLM remoto (Qwen 2.5) via gateway resiliente.
    5. Atualiza o histórico da conversa e retorna a resposta formatada.
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        vector_store: Optional[PineconeVectorStore] = None,
        manager: Optional[ChatSessionManager] = None
    ):
        self.llm_client = llm_client or LLMClient()
        self.vector_store = vector_store or PineconeVectorStore()
        self.session_manager = manager or session_manager

    def _retrieve_context(self, query: str, top_k: int = 3) -> List[ChatContextChunk]:
        """
        Executa busca semântica de trechos didáticos relevantes no Pinecone.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        logger.info(f"Chat RAG: buscando contexto no namespace '{settings.NAMESPACE_MATERIAIS_DIDATICOS}' (top_k={top_k})...")
        try:
            raw_results = self.vector_store.search(
                query=clean_query,
                namespace=settings.NAMESPACE_MATERIAIS_DIDATICOS,
                top_k=top_k
            )

            context_chunks = []
            for item in raw_results:
                meta = item.get("metadata", {})
                context_chunks.append(
                    ChatContextChunk(
                        id=str(item.get("id", "")),
                        title=meta.get("title", meta.get("document_name", "Material Didático")),
                        topic=meta.get("topic", ""),
                        text=item.get("text", ""),
                        score=round(float(item.get("score", 0.0)), 4),
                        page_number=meta.get("page_number"),
                        document_name=meta.get("document_name")
                    )
                )
            return context_chunks
        except Exception as e:
            logger.warning(f"Não foi possível resgatar contexto do Pinecone ({e}). Continuando sem chunks teóricos...")
            return []

    def send_message(self, request: ChatRequest) -> ChatResponse:
        """
        Processamento síncrono da mensagem do estudante.
        """
        start_time = time.time()
        session_id = self.session_manager.get_or_create_session(request.session_id)

        # 1. Recupera histórico recente da sessão
        history_msgs = self.session_manager.get_history(session_id, limit=8)

        # 2. Resgata contexto teórico no Pinecone
        context_chunks = self._retrieve_context(
            query=request.message,
            top_k=request.top_k_context
        )

        # 3. Monta o prompt CoT com histórico e materiais teóricos
        prompt = build_chat_prompt(
            user_message=request.message,
            history_messages=[m.model_dump() for m in history_msgs],
            context_chunks=[c.model_dump() for c in context_chunks]
        )

        # 4. Inferência via LLM
        reply_raw = self.llm_client.generate(prompt=prompt, session_id=session_id)
        elapsed_time = round(time.time() - start_time, 2)

        # 5. Registra mensagens no histórico da sessão
        self.session_manager.add_message(session_id=session_id, role="user", content=request.message)
        self.session_manager.add_message(session_id=session_id, role="assistant", content=reply_raw)

        return ChatResponse(
            reply=reply_raw,
            session_id=session_id,
            context_chunks=context_chunks,
            inference_time_seconds=elapsed_time
        )

    async def asend_message(self, request: ChatRequest) -> ChatResponse:
        """
        Processamento assíncrono da mensagem do estudante.
        """
        start_time = time.time()
        session_id = self.session_manager.get_or_create_session(request.session_id)

        # 1. Recupera histórico recente da sessão
        history_msgs = self.session_manager.get_history(session_id, limit=8)

        # 2. Resgata contexto teórico no Pinecone
        context_chunks = self._retrieve_context(
            query=request.message,
            top_k=request.top_k_context
        )

        # 3. Monta o prompt CoT com histórico e materiais teóricos
        prompt = build_chat_prompt(
            user_message=request.message,
            history_messages=[m.model_dump() for m in history_msgs],
            context_chunks=[c.model_dump() for c in context_chunks]
        )

        # 4. Inferência assíncrona via LLM
        reply_raw = await self.llm_client.agenerate(prompt=prompt, session_id=session_id)
        elapsed_time = round(time.time() - start_time, 2)

        # 5. Registra mensagens no histórico da sessão
        self.session_manager.add_message(session_id=session_id, role="user", content=request.message)
        self.session_manager.add_message(session_id=session_id, role="assistant", content=reply_raw)

        return ChatResponse(
            reply=reply_raw,
            session_id=session_id,
            context_chunks=context_chunks,
            inference_time_seconds=elapsed_time
        )

    def get_session_history(self, session_id: str) -> ChatHistoryResponse:
        """
        Retorna o histórico de mensagens de uma sessão.
        """
        messages = self.session_manager.get_history(session_id)
        return ChatHistoryResponse(
            session_id=session_id,
            messages=messages,
            total_messages=len(messages)
        )

    def clear_session(self, session_id: str) -> bool:
        """
        Limpa o histórico de uma sessão de conversa.
        """
        return self.session_manager.clear_session(session_id)
