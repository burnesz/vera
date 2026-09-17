import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Integer, Text, ForeignKey, UUID, DateTime, CheckConstraint, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User
    from app.db.models.questao_enem import QuestaoEnem
    from app.db.models.questao_inedita import QuestaoInedita
    from app.db.models.submission import SimuladoTentativa


class Simulado(Base):
    """
    Caderno de simulado para o estudante (diagnóstico, por habilidade ou geral).
    """
    __tablename__ = "simulados"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    descricao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tipo: Mapped[str] = mapped_column(String(50), default="diagnostico", nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relacionamentos
    usuario: Mapped[Optional["User"]] = relationship("User", back_populates="simulados")
    itens: Mapped[List["SimuladoItem"]] = relationship(
        "SimuladoItem",
        back_populates="simulado",
        cascade="all, delete-orphan",
        order_by="SimuladoItem.ordem"
    )
    tentativas: Mapped[List["SimuladoTentativa"]] = relationship(
        "SimuladoTentativa",
        back_populates="simulado",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Simulado(id={self.id}, titulo='{self.titulo}', tipo='{self.tipo}')>"


class SimuladoItem(Base):
    """
    Item componente de um simulado.
    Utiliza Exclusive Arc para associar ou a uma questão histórica oficial (`questoes_enem`)
    ou a uma questão inédita gerada (`questoes_ineditas`).
    """
    __tablename__ = "simulado_itens"
    __table_args__ = (
        CheckConstraint(
            "(origem_questao = 'enem' AND questao_enem_id IS NOT NULL AND questao_inedita_id IS NULL) OR "
            "(origem_questao = 'inedita' AND questao_inedita_id IS NOT NULL AND questao_enem_id IS NULL)",
            name="chk_simulado_item_origem"
        ),
        UniqueConstraint("simulado_id", "ordem", name="uq_simulado_item_ordem"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    simulado_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulados.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
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

    # Relacionamentos
    simulado: Mapped["Simulado"] = relationship("Simulado", back_populates="itens")
    questao_enem: Mapped[Optional["QuestaoEnem"]] = relationship(
        "QuestaoEnem",
        back_populates="simulado_itens"
    )
    questao_inedita: Mapped[Optional["QuestaoInedita"]] = relationship(
        "QuestaoInedita",
        back_populates="simulado_itens"
    )

    def __repr__(self) -> str:
        return f"<SimuladoItem(id={self.id}, simulado_id={self.simulado_id}, ordem={self.ordem}, origem='{self.origem_questao}')>"
