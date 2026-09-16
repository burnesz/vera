from functools import lru_cache
from typing import Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API Config
    PROJECT_NAME: str = "VERA API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # JWT Authentication
    JWT_SECRET_KEY: str = "vera-jwt-secret-key-dev-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 horas

    # LLM Remote Serving (Colab + Tunnel) - RN-INF01
    LLM_ENDPOINT_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_TIMEOUT_SECONDS: float = 60.0
    LLM_MAX_TOKENS: int = 1024

    # Vector Store (Pinecone)
    PINECONE_API_KEY: str = ""
    PINECONE_ENVIRONMENT: str = "us-east-1"
    PINECONE_INDEX_NAME: str = "vera-math-index"
    
    # Embeddings
    EMBEDDING_MODEL_NAME: str = "intfloat/multilingual-e5-large"
    EMBEDDING_DIMENSION: int = 1024

    # Cloudflare R2 (S3-compatible Object Storage)
    R2_ENDPOINT_URL: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "vera"

    # Chunking Strategy (RN-CHUNK01, RN-CHUNK02)
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150

    # PostgreSQL Relational Database
    DATABASE_URL: Optional[str] = None
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "vera_db"
    POSTGRES_PORT: int = 5432

    @model_validator(mode="after")
    def assemble_database_url(self) -> "Settings":
        """
        Monta a DATABASE_URL dinamicamente caso não tenha sido fornecida explicitamente.
        Garante fonte única da verdade com as variáveis POSTGRES_*.
        """
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        return self

    # Namespaces Pinecone (RN-VETOR01)
    NAMESPACE_MATERIAIS_DIDATICOS: str = "materiais_didaticos"
    NAMESPACE_QUESTOES_HISTORICAS: str = "questoes_historicas"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
