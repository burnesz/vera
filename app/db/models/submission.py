import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, UUID, DateTime, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User
    from app.db.models.simulado import Simulado
    from app.db.models.questao_enem import QuestaoEnem
    from app.db.models.questao_inedita import QuestaoInedita
    from app.db.models.feedback import Feedback


class SimuladoTentativa(Base):
    """
    Registro da tentativa de execução de um simulado pelo estudante.
    """
    __tablename__ = "simulado_tentativas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    simulado_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulados.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="in_progress", nullable=False)
    total_itens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_acertos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    score_percentual: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relacionamentos
    user: Mapped["User"] = relationship("User", back_populates="tentativas")
    simulado: Mapped["Simulado"] = relationship("Simulado", back_populates="tentativas")
    respostas: Mapped[List["RespostaItem"]] = relationship(
        "RespostaItem",
        back_populates="tentativa",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<SimuladoTentativa(id={self.id}, user_id={self.user_id}, status='{self.status}')>"


class RespostaItem(Base):
    """
    Resposta fornecida pelo estudante para um item do simulado.
    Utiliza Exclusive Arc para associar à questão histórica ou à inédita.
    """
    __tablename__ = "respostas_itens"
    __table_args__ = (
        CheckConstraint(
            "(origem_questao = 'enem' AND questao_enem_id IS NOT NULL AND questao_inedita_id IS NULL) OR "
            "(origem_questao = 'inedita' AND questao_inedita_id IS NOT NULL AND questao_enem_id IS NULL)",
            name="chk_resposta_item_origem"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    tentativa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulado_tentativas.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    origem_questao: Mapped[str] = mapped_column(String(20), nullable=False)  # 'enem' ou 'inedita'
    questao_enem_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questoes_enem.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    questao_inedita_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questoes_ineditas.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    alternativa_marcada: Mapped[str] = mapped_column(String(1), nullable=False)
    is_correta: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relacionamentos
    tentativa: Mapped["SimuladoTentativa"] = relationship("SimuladoTentativa", back_populates="respostas")
    questao_enem: Mapped[Optional["QuestaoEnem"]] = relationship(
        "QuestaoEnem",
        back_populates="respostas_itens"
    )
    questao_inedita: Mapped[Optional["QuestaoInedita"]] = relationship(
        "QuestaoInedita",
        back_populates="respostas_itens"
    )
    feedback: Mapped[Optional["Feedback"]] = relationship(
        "Feedback",
        back_populates="resposta_item",
        uselist=False,
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<RespostaItem(id={self.id}, tentativa_id={self.tentativa_id}, correta={self.is_correta})>"
