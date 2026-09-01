from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API Config
    PROJECT_NAME: str = "VERA API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # LLM Remote Serving (Colab + Tunnel) - RN-INF01
    LLM_ENDPOINT_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_TIMEOUT_SECONDS: float = 60.0

    # Vector Store (Pinecone)
    PINECONE_API_KEY: str = ""
    PINECONE_ENVIRONMENT: str = "us-east-1"
    PINECONE_INDEX_NAME: str = "vera-math-index"
    
    # Embeddings
    EMBEDDING_MODEL_NAME: str = "intfloat/multilingual-e5-base"
    EMBEDDING_DIMENSION: int = 768

    # Cloudflare R2 (S3-compatible Object Storage)
    R2_ENDPOINT_URL: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "vera"

    # Chunking Strategy (RN-CHUNK01, RN-CHUNK02)
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150

    # PostgreSQL Relational Database
    DATABASE_URL: Optional[str] = "postgresql://postgres:postgres@localhost:5432/vera_db"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "vera_db"
    POSTGRES_PORT: int = 5432

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
