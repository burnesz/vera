from fastapi import APIRouter, HTTPException, status
from app.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.services.feedback_service import FeedbackService
from app.services.llm_client import LLMConnectionError, LLMTimeoutError

router = APIRouter(prefix="/feedback", tags=["Feedback Pedagógico"])


@router.post(
    "/generate",
    response_model=FeedbackResponse,
    status_code=status.HTTP_200_OK,
    summary="Gera feedback pedagógico personalizado com Chain-of-Thought (CoT)"
)
async def generate_pedagogical_feedback(request: FeedbackRequest) -> FeedbackResponse:
    """
    Executa o Pipeline RAG de Feedback Pedagógico Personalizado (5 Etapas):
    1. Recebe a questão e a alternativa assinalada pelo estudante.
    2. Identifica as necessidades conceituais da habilidade do ENEM.
    3. Resgata materiais didáticos teóricos relevantes no Pinecone.
    4. Gera feedback estruturado em Chain-of-Thought (CoT) via Qwen 2.5.
    5. Executa verificação automática de gabarito para prevenir alucinações (RN-FB01 / RN-FB02).
    """
    service = FeedbackService()
    try:
        response = await service.agenerate_feedback(request)
        return response
    except LLMConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Serviço de LLM temporariamente indisponível. Verifique o túnel remoto ({e})."
        )
    except LLMTimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Tempo limite esgotado ao gerar feedback com o modelo ({e})."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno ao processar feedback: {str(e)}"
        )
