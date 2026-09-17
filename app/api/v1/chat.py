from fastapi import APIRouter, HTTPException, Depends, status
from app.api.deps import get_current_active_user
from app.db.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse, ChatHistoryResponse
from app.services.chat_service import ChatService
from app.services.llm_client import LLMConnectionError, LLMTimeoutError

router = APIRouter(prefix="/chat", tags=["Chatbot Especialista"])


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Envia uma mensagem para a Tutora Especialista em Matemática (VERA)"
)
async def chat_with_vera(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user)
) -> ChatResponse:
    """
    Canal de conversação interativa com a Tutora VERA:
    - Suporte a múltiplos turnos de conversa via `session_id`.
    - Resgate em tempo real de conteúdos teóricos confiáveis no Pinecone (`materiais_didaticos`).
    - Raciocínio didático passo a passo com Chain-of-Thought (CoT) contextualizado para o ENEM.
    - Exige autenticação de usuário ativo via token Bearer JWT.
    """
    service = ChatService()
    try:
        response = await service.asend_message(request)
        return response
    except LLMConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Serviço de LLM temporariamente indisponível. Verifique se o daemon do Ollama está ativo ({e})."
        )
    except LLMTimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Tempo limite esgotado ao aguardar a resposta da Tutora ({e})."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno ao processar a mensagem no Chat: {str(e)}"
        )


@router.get(
    "/history/{session_id}",
    response_model=ChatHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Recupera o histórico de mensagens de uma sessão de conversa"
)
async def get_chat_history(
    session_id: str,
    current_user: User = Depends(get_current_active_user)
) -> ChatHistoryResponse:
    """
    Retorna a lista de mensagens trocadas em uma sessão específica.
    """
    service = ChatService()
    return service.get_session_history(session_id)


@router.delete(
    "/session/{session_id}",
    status_code=status.HTTP_200_OK,
    summary="Limpa e reinicia o histórico de uma sessão de conversa"
)
async def clear_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Exclui o histórico acumulado de uma sessão.
    """
    service = ChatService()
    cleared = service.clear_session(session_id)
    return {
        "session_id": session_id,
        "cleared": cleared,
        "message": "Sessão reiniciada com sucesso." if cleared else "Sessão não encontrada ou já vazia."
    }
