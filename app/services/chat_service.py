import time
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings
from app.core.prompts import build_chat_prompt, parse_cot_response
from app.db.models.chat import ChatSession, ChatMessageModel
from app.schemas.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatContextChunk,
    ChatHistoryResponse,
    ChatSessionSummary,
)
from app.services.llm_client import LLMClient
from app.services.vectorstore import PineconeVectorStore

logger = logging.getLogger(__name__)


def generate_session_title(first_message: str, max_length: int = 40) -> str:
    """
    Gera um título representativo e legível para a conversa a partir da primeira pergunta.
    """
    clean = first_message.strip().replace("\n", " ")
    if len(clean) <= max_length:
        return clean
    return clean[:max_length].rstrip() + "..."


class ChatSessionManager:
    """
    Gerenciador de memória volátil em RAM para sessões de conversação (fallback e testes desacoplados).
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

    def add_message(self, session_id: str, role: str, content: str, thought: Optional[str] = None) -> ChatMessage:
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        
        msg = ChatMessage(role=role, content=content, thought=thought, timestamp=time.time())
        self._sessions[session_id].append(msg)

        # Aplica janela deslizante para limitar o tamanho do histórico em RAM
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


# Instância global do gerenciador de sessão em memória
session_manager = ChatSessionManager()


class ChatService:
    """
    Serviço orquestrador do Chatbot RAG de Matemática com Persistência Relacional:
    1. Recupera ou cria sessão no PostgreSQL (chat_sessions) vinculada ao estudante.
    2. Resgata histórico de turnos anteriores para montagem de contexto multiturno.
    3. Resgata materiais didáticos relevantes no Pinecone (namespace materiais_didaticos).
    4. Constrói o prompt estruturado com raciocínio Chain-of-Thought (CoT).
    5. Executa inferência com o modelo local Qwen 2.5 via Ollama com resiliência e retry.
    6. Separa o raciocínio interno (<pensamento>) da resposta didática (<resposta>).
    7. Persiste a pergunta e a resposta com metadados no banco de dados relacional.
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        vector_store: Optional[PineconeVectorStore] = None,
        manager: Optional[ChatSessionManager] = None,
        db: Optional[Session] = None,
        user_id: Optional[uuid.UUID] = None,
    ):
        self.llm_client = llm_client or LLMClient()
        self.vector_store = vector_store or PineconeVectorStore()
        self.session_manager = manager or session_manager
        self.db = db
        self.user_id = user_id

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

    def _get_or_create_db_session(self, session_id: Optional[str], initial_message: str) -> str:
        """
        Garante a existência da sessão no PostgreSQL se houver conexão ativa com o banco.
        """
        if not session_id or not session_id.strip():
            session_id = f"sess_{uuid.uuid4().hex[:12]}"

        if self.db:
            existing = self.db.query(ChatSession).filter(ChatSession.id == session_id).first()
            
            # Valida se o user_id existe no banco para respeitar a Foreign Key
            valid_user_id = None
            if self.user_id:
                from app.db.models.user import User
                user_exists = self.db.query(User).filter(User.id == self.user_id).first()
                if user_exists:
                    valid_user_id = self.user_id

            if not existing:
                title = generate_session_title(initial_message)
                new_session = ChatSession(
                    id=session_id,
                    user_id=valid_user_id,
                    titulo=title
                )
                self.db.add(new_session)
                self.db.flush()
            else:
                if valid_user_id and not existing.user_id:
                    existing.user_id = valid_user_id
                existing.updated_at = func.now()
                self.db.flush()

        return session_id

    def _get_history_for_prompt(self, session_id: str, limit: int = 8) -> List[ChatMessage]:
        """
        Recupera os turnos recentes para compor o contexto da conversa para o LLM.
        Prioriza o PostgreSQL; caso ausente, recorre à memória RAM.
        """
        if self.db:
            db_msgs = (
                self.db.query(ChatMessageModel)
                .filter(ChatMessageModel.session_id == session_id)
                .order_by(ChatMessageModel.created_at.desc())
                .limit(limit)
                .all()
            )
            if db_msgs:
                db_msgs.reverse()
                return [
                    ChatMessage(
                        id=str(m.id),
                        role=m.role,  # type: ignore
                        content=m.content,
                        thought=m.thought,
                        timestamp=m.created_at.timestamp() if m.created_at else time.time(),
                        created_at=m.created_at,
                    )
                    for m in db_msgs
                ]

        return self.session_manager.get_history(session_id, limit=limit)

    def _save_interaction_to_db(
        self,
        session_id: str,
        user_message: str,
        clean_reply: str,
        thought: Optional[str],
        context_chunks: List[ChatContextChunk]
    ) -> None:
        """
        Persiste tanto a mensagem do usuário quanto a réplica didática da tutora no banco.
        """
        if not self.db:
            return

        try:
            # Mensagem do Estudante
            user_model = ChatMessageModel(
                session_id=session_id,
                role="user",
                content=user_message,
                context_chunks=[]
            )
            self.db.add(user_model)

            # Mensagem da Tutora VERA
            assistant_model = ChatMessageModel(
                session_id=session_id,
                role="assistant",
                content=clean_reply,
                thought=thought,
                context_chunks=[c.model_dump() for c in context_chunks]
            )
            self.db.add(assistant_model)

            # Atualiza updated_at da sessão
            session = self.db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if session:
                session.updated_at = func.now()

            self.db.commit()
        except Exception as e:
            logger.error(f"Falha ao persistir mensagens de chat no PostgreSQL: {e}")
            self.db.rollback()

    def send_message(self, request: ChatRequest) -> ChatResponse:
        """
        Processamento síncrono da mensagem do estudante com persistência.
        """
        start_time = time.time()
        session_id = self._get_or_create_db_session(request.session_id, request.message)
        self.session_manager.get_or_create_session(session_id)

        # 1. Recupera histórico recente
        history_msgs = self._get_history_for_prompt(session_id, limit=8)

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
        reply_raw = self.llm_client.generate(prompt=prompt, session_id=None)
        elapsed_time = round(time.time() - start_time, 2)

        # 5. Separa raciocínio (thought) da resposta didática final
        thought, clean_reply = parse_cot_response(reply_raw)

        # 6. Grava em banco de dados e memória volátil
        self._save_interaction_to_db(
            session_id=session_id,
            user_message=request.message,
            clean_reply=clean_reply,
            thought=thought,
            context_chunks=context_chunks
        )
        self.session_manager.add_message(session_id=session_id, role="user", content=request.message)
        self.session_manager.add_message(session_id=session_id, role="assistant", content=clean_reply, thought=thought)

        return ChatResponse(
            reply=clean_reply,
            thought=thought,
            session_id=session_id,
            context_chunks=context_chunks,
            inference_time_seconds=elapsed_time
        )

    async def asend_message(self, request: ChatRequest) -> ChatResponse:
        """
        Processamento assíncrono da mensagem do estudante com persistência.
        """
        start_time = time.time()
        session_id = self._get_or_create_db_session(request.session_id, request.message)
        self.session_manager.get_or_create_session(session_id)

        # 1. Recupera histórico recente
        history_msgs = self._get_history_for_prompt(session_id, limit=8)

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
        reply_raw = await self.llm_client.agenerate(prompt=prompt, session_id=None)
        elapsed_time = round(time.time() - start_time, 2)

        # 5. Separa raciocínio (thought) da resposta didática final
        thought, clean_reply = parse_cot_response(reply_raw)

        # 6. Grava em banco de dados e memória volátil
        self._save_interaction_to_db(
            session_id=session_id,
            user_message=request.message,
            clean_reply=clean_reply,
            thought=thought,
            context_chunks=context_chunks
        )
        self.session_manager.add_message(session_id=session_id, role="user", content=request.message)
        self.session_manager.add_message(session_id=session_id, role="assistant", content=clean_reply, thought=thought)

        return ChatResponse(
            reply=clean_reply,
            thought=thought,
            session_id=session_id,
            context_chunks=context_chunks,
            inference_time_seconds=elapsed_time
        )

    def list_user_sessions(self, user_id: uuid.UUID) -> List[ChatSessionSummary]:
        """
        Lista todas as sessões de conversa do estudante ordenadas da mais recente para a mais antiga.
        """
        if not self.db:
            return []

        sessions_with_count = (
            self.db.query(
                ChatSession,
                func.count(ChatMessageModel.id).label("total_messages")
            )
            .outerjoin(ChatMessageModel, ChatSession.id == ChatMessageModel.session_id)
            .filter(ChatSession.user_id == user_id)
            .group_by(ChatSession.id)
            .order_by(ChatSession.updated_at.desc())
            .all()
        )

        return [
            ChatSessionSummary(
                id=s.id,
                titulo=s.titulo,
                created_at=s.created_at,
                updated_at=s.updated_at,
                total_messages=count
            )
            for s, count in sessions_with_count
        ]

    def get_session_history(self, session_id: str, user_id: Optional[uuid.UUID] = None) -> ChatHistoryResponse:
        """
        Retorna o histórico completo de mensagens de uma sessão persistida.
        """
        if self.db:
            session = self.db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if session:
                # Se a sessão tem dono, garante que apenas ele ou admin pode ler
                if user_id and session.user_id and session.user_id != user_id:
                    return ChatHistoryResponse(
                        session_id=session_id,
                        titulo=session.titulo,
                        messages=[],
                        total_messages=0
                    )

                msgs = (
                    self.db.query(ChatMessageModel)
                    .filter(ChatMessageModel.session_id == session_id)
                    .order_by(ChatMessageModel.created_at.asc())
                    .all()
                )

                formatted = [
                    ChatMessage(
                        id=str(m.id),
                        role=m.role,  # type: ignore
                        content=m.content,
                        thought=m.thought,
                        timestamp=m.created_at.timestamp() if m.created_at else time.time(),
                        created_at=m.created_at,
                        context_chunks=m.context_chunks or []
                    )
                    for m in msgs
                ]

                return ChatHistoryResponse(
                    session_id=session_id,
                    titulo=session.titulo,
                    messages=formatted,
                    total_messages=len(formatted)
                )

        messages = self.session_manager.get_history(session_id)
        return ChatHistoryResponse(
            session_id=session_id,
            titulo=None,
            messages=messages,
            total_messages=len(messages)
        )

    def clear_session(self, session_id: str, user_id: Optional[uuid.UUID] = None) -> bool:
        """
        Exclui o histórico de uma sessão no banco de dados e na memória RAM.
        """
        cleared = False
        if self.db:
            session = self.db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if session:
                if not user_id or not session.user_id or session.user_id == user_id:
                    self.db.delete(session)
                    self.db.commit()
                    cleared = True

        if self.session_manager.clear_session(session_id):
            cleared = True

        return cleared

    def rename_session(self, session_id: str, new_title: str, user_id: Optional[uuid.UUID] = None) -> bool:
        """
        Atualiza o título de uma sessão de conversa do usuário.
        """
        if not self.db:
            return False

        session = self.db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            return False

        if user_id and session.user_id and session.user_id != user_id:
            return False

        session.titulo = new_title.strip()
        session.updated_at = func.now()
        self.db.commit()
        return True
