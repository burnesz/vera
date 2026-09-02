from typing import Dict, Any
from fastapi import APIRouter, status
from app.core.config import settings
from app.services.llm_client import LLMClient

router = APIRouter(tags=["Health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> Dict[str, Any]:
    """
    Verificação abrangente do estado de saúde dos componentes do sistema VERA:
    - Status da API FastAPI
    - Status e latência do servidor LLM remoto (Colab + túnel ngrok - RN-INF02)
    - Configurações de serviços
    """
    llm_client = LLMClient()
    llm_health = await llm_client.ahealth_check()

    overall_status = "ok" if llm_health.get("healthy") else "degraded"

    return {
        "status": overall_status,
        "api": {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "status": "online"
        },
        "llm_remote": llm_health,
        "vector_store": {
            "index_name": settings.PINECONE_INDEX_NAME,
            "environment": settings.PINECONE_ENVIRONMENT,
            "namespace_materials": settings.NAMESPACE_MATERIAIS_DIDATICOS
        }
    }
