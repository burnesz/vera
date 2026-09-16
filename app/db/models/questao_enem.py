import uuid
from datetime import datetime
from typing import Dict, Any, List, TYPE_CHECKING
from sqlalchemy import String, Integer, Text, ForeignKey, UUID, DateTime, func, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.habilidade import HabilidadeEnem
    from app.db.models.simulado import SimuladoItem
    from app.db.models.submission import RespostaItem

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class QuestaoEnem(Base):
    """
    Acervo histórico original de questões do ENEM (2009-2024) extraídas via arquivo CSV.
    Armazenadas de forma relacional pura no PostgreSQL.
    """
    __tablename__ = "questoes_enem"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    ano: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    habilidade_codigo: Mapped[str] = mapped_column(
        String(10),
        ForeignKey("habilidades_enem.codigo", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    enunciado: Mapped[str] = mapped_column(Text, nullable=False)
    alternativas: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    gabarito: Mapped[str] = mapped_column(String(1), nullable=False)  # 'A', 'B', 'C', 'D', 'E'
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relacionamentos
    habilidade: Mapped["HabilidadeEnem"] = relationship(
        "HabilidadeEnem",
        back_populates="questoes_enem"
    )
    simulado_itens: Mapped[List["SimuladoItem"]] = relationship(
        "SimuladoItem",
        back_populates="questao_enem"
    )
    respostas_itens: Mapped[List["RespostaItem"]] = relationship(
        "RespostaItem",
        back_populates="questao_enem"
    )

    def __repr__(self) -> str:
        return f"<QuestaoEnem(id={self.id}, ano={self.ano}, hab='{self.habilidade_codigo}', gab='{self.gabarito}')>"
