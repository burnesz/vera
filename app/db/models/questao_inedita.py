import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from sqlalchemy import String, Text, ForeignKey, UUID, DateTime, Boolean, func, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.habilidade import HabilidadeEnem
    from app.db.models.simulado import SimuladoItem
    from app.db.models.submission import RespostaItem

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class QuestaoInedita(Base):
    """
    Questões inéditas de treino geradas pelo modelo LLM (Qwen2.5) para cobrir lacunas
    de aprendizagem do estudante nas habilidades do ENEM.
    """
    __tablename__ = "questoes_ineditas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    habilidade_codigo: Mapped[str] = mapped_column(
        String(10),
        ForeignKey("habilidades_enem.codigo", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    enunciado: Mapped[str] = mapped_column(Text, nullable=False)
    alternativas: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    gabarito: Mapped[str] = mapped_column(String(1), nullable=False)
    justificativa: Mapped[str] = mapped_column(Text, nullable=False)
    thought_scratchpad: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_validated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relacionamentos
    habilidade: Mapped["HabilidadeEnem"] = relationship(
        "HabilidadeEnem",
        back_populates="questoes_ineditas"
    )
    simulado_itens: Mapped[List["SimuladoItem"]] = relationship(
        "SimuladoItem",
        back_populates="questao_inedita"
    )
    respostas_itens: Mapped[List["RespostaItem"]] = relationship(
        "RespostaItem",
        back_populates="questao_inedita"
    )

    def __repr__(self) -> str:
        return f"<QuestaoInedita(id={self.id}, hab='{self.habilidade_codigo}', valid={self.is_validated})>"
