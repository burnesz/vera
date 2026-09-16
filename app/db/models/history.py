import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, Integer, Float, ForeignKey, UUID, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User
    from app.db.models.habilidade import HabilidadeEnem


class DesempenhoHabilidade(Base):
    """
    Agregação contínua de desempenho do estudante por habilidade oficial do ENEM.
    Alimenta o Dashboard Pedagógico e direciona a geração de novas questões de treino.
    """
    __tablename__ = "desempenho_habilidades"
    __table_args__ = (
        UniqueConstraint("user_id", "habilidade_codigo", name="uq_user_habilidade_desempenho"),
    )

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
    habilidade_codigo: Mapped[str] = mapped_column(
        String(10),
        ForeignKey("habilidades_enem.codigo", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    total_questoes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_acertos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    taxa_acerto: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    nivel_dominio: Mapped[str] = mapped_column(
        String(20),
        default="em_desenvolvimento",
        nullable=False
    )  # 'critico', 'em_desenvolvimento', 'consolidado'
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relacionamentos
    user: Mapped["User"] = relationship("User", back_populates="desempenho_habilidades")
    habilidade: Mapped["HabilidadeEnem"] = relationship("HabilidadeEnem", back_populates="desempenhos")

    def __repr__(self) -> str:
        return (
            f"<DesempenhoHabilidade(user_id={self.user_id}, hab='{self.habilidade_codigo}', "
            f"taxa={self.taxa_acerto:.2f}, dominio='{self.nivel_dominio}')>"
        )
