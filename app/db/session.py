from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings

# Engine com pool_pre_ping para reconectar automaticamente em caso de queda temporária da conexão
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=False
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db() -> Generator[Session, None, None]:
    """
    Dependência FastAPI para gerenciamento de sessões do banco de dados.
    Garante fechamento seguro da sessão após a conclusão da requisição.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
