import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from sqlalchemy import Text, ForeignKey, UUID, DateTime, Boolean, func, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.submission import RespostaItem

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class Feedback(Base):
    """
    Feedback pedagógico personalizado gerado pelo LLM para auxiliar o estudante
    na superação de um erro em um item específico do simulado (RN-FB01, RN-FB02).
    """
    __tablename__ = "feedbacks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    resposta_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("respostas_itens.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    feedback_content: Mapped[str] = mapped_column(Text, nullable=False)
    thought_scratchpad: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context_chunks: Mapped[List[Dict[str, Any]]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relacionamentos
    resposta_item: Mapped["RespostaItem"] = relationship(
        "RespostaItem",
        back_populates="feedback"
    )

    def __repr__(self) -> str:
        return f"<Feedback(id={self.id}, resposta_id={self.resposta_item_id}, verified={self.is_verified})>"
