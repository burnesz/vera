import uuid
from typing import List, TYPE_CHECKING
from sqlalchemy import String, Boolean, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.submission import SimuladoTentativa
    from app.db.models.history import DesempenhoHabilidade
    from app.db.models.chat import ChatSession


class User(Base, TimestampMixin):
    """
    Representação dos usuários da plataforma VERA.
    Suporta distinção de papéis: 'student' (estudante) e 'admin' (administrador).
    """
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="student", nullable=False)
    is_ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relacionamentos
    tentativas: Mapped[List["SimuladoTentativa"]] = relationship(
        "SimuladoTentativa",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    desempenho_habilidades: Mapped[List["DesempenhoHabilidade"]] = relationship(
        "DesempenhoHabilidade",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    chat_sessions: Mapped[List["ChatSession"]] = relationship(
        "ChatSession",
        back_populates="user"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"
