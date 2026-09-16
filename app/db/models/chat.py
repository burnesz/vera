import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from sqlalchemy import String, Text, ForeignKey, UUID, DateTime, func, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.user import User

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class ChatSession(Base, TimestampMixin):
    """
    Sessão persistente de conversa com a Tutora VERA.
    Permite multiturno contínuo e histórico perpétuo para o estudante.
    """
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # UUID string como session_id
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    titulo: Mapped[str] = mapped_column(String(255), default="Conversa com VERA", nullable=False)

    # Relacionamentos
    user: Mapped[Optional["User"]] = relationship("User", back_populates="chat_sessions")
    messages: Mapped[List["ChatMessageModel"]] = relationship(
        "ChatMessageModel",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessageModel.created_at"
    )

    def __repr__(self) -> str:
        return f"<ChatSession(id='{self.id}', titulo='{self.titulo}')>"


class ChatMessageModel(Base):
    """
    Mensagem individual persistida de uma sessão de tutoria inteligente.
    """
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    session_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    thought: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context_chunks: Mapped[List[Dict[str, Any]]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relacionamentos
    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")

    def __repr__(self) -> str:
        return f"<ChatMessageModel(id={self.id}, session_id='{self.session_id}', role='{self.role}')>"
