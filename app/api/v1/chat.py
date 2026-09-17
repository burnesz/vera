from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.db.models.user import User
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatHistoryResponse,
    ChatSessionListResponse,
    UpdateChatSessionRequest
)
from app.services.chat_service import ChatService
from app.services.llm_client import LLMConnectionError, LLMTimeoutError

router = APIRouter(prefix="/chat", tags=["Chatbot Especialista"])


@router.get(
    "/sessions",
    response_model=ChatSessionListResponse,
    status_code=status.HTTP_200_OK,
    summary="Lista as sessões de conversa do estudante"
)
async def list_chat_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> ChatSessionListResponse:
    """
    Retorna a lista de todas as conversas anteriores do usuário com a Tutora VERA,
    ordenadas cronologicamente da mais recente para a mais antiga.
    """
    service = ChatService(db=db, user_id=current_user.id)
    sessions = service.list_user_sessions(current_user.id)
    return ChatSessionListResponse(
        sessions=sessions,
        total=len(sessions)
    )


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Envia uma mensagem para a Tutora Especialista em Matemática (VERA)"
)
async def chat_with_vera(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> ChatResponse:
    """
    Canal de conversação interativa com a Tutora VERA com persistência relacional:
    - Suporte a múltiplos turnos de conversa via `session_id`.
    - Resgate em tempo real de conteúdos teóricos confiáveis no Pinecone (`materiais_didaticos`).
    - Raciocínio didático passo a passo com Chain-of-Thought (CoT) contextualizado para o ENEM.
    - Gravação automática no PostgreSQL para histórico contínuo do estudante.
    """
    service = ChatService(db=db, user_id=current_user.id)
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> ChatHistoryResponse:
    """
    Retorna a lista de mensagens trocadas em uma sessão específica do usuário.
    """
    service = ChatService(db=db, user_id=current_user.id)
    return service.get_session_history(session_id, user_id=current_user.id)


@router.delete(
    "/session/{session_id}",
    status_code=status.HTTP_200_OK,
    summary="Exclui uma sessão de conversa e seu histórico"
)
async def delete_chat_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Exclui permanentemente a conversa e todas as mensagens associadas do banco de dados.
    """
    service = ChatService(db=db, user_id=current_user.id)
    cleared = service.clear_session(session_id, user_id=current_user.id)
    return {
        "session_id": session_id,
        "cleared": cleared,
        "message": "Sessão excluída com sucesso." if cleared else "Sessão não encontrada."
    }


@router.patch(
    "/session/{session_id}",
    status_code=status.HTTP_200_OK,
    summary="Renomeia o título de uma conversa"
)
async def rename_chat_session(
    session_id: str,
    payload: UpdateChatSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Atualiza o título da sessão de conversa especificada.
    """
    service = ChatService(db=db, user_id=current_user.id)
    renamed = service.rename_session(session_id, payload.titulo, user_id=current_user.id)
    if not renamed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sessão não encontrada ou não pertence ao usuário."
        )
    return {
        "session_id": session_id,
        "titulo": payload.titulo.strip(),
        "success": True
    }
