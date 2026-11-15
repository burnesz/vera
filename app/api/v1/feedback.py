import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_active_user
from app.db.models.user import User
from app.schemas.feedback import FeedbackExplicacaoRequest, FeedbackExplicacaoResponse
from app.services.feedback_service import FeedbackVerificationError, feedback_service

router = APIRouter()


@router.post(
    "/explicar",
    response_model=FeedbackExplicacaoResponse,
    status_code=status.HTTP_200_OK,
    summary="Gera ou obtém o feedback explicativo da Tutora VERA para um erro em questão de simulado",
)
def solicitar_feedback_questao(
    body: FeedbackExplicacaoRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Aciona a Tutora VERA para gerar uma explicação pedagógica contextualizada sobre o erro do aluno.
    Caso o feedback já tenha sido gerado anteriormente, retorna imediatamente do cache relacional (0ms).
    """
    try:
        feedback = feedback_service.gerar_ou_obter_feedback_item(
            db=db,
            resposta_item_id=body.resposta_item_id,
            user_id=current_user.id,
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except FeedbackVerificationError as e:
        # RN-FB04: feedback reprovado na verificação contra o gabarito não é exibido.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{e} Tente solicitar a explicação novamente.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar feedback com a Tutora VERA: {e}",
        )

    # Identifica a habilidade e as letras a partir da resposta_item vinculada
    resp = feedback.resposta_item
    q = resp.questao_enem if resp.origem_questao == "enem" else resp.questao_inedita
    hab_cod = q.habilidade_codigo if q else ""
    gab = q.gabarito if q else ""

    return FeedbackExplicacaoResponse(
        id=feedback.id,
        resposta_item_id=feedback.resposta_item_id,
        habilidade_codigo=hab_cod,
        alternativa_marcada=resp.alternativa_marcada or "X",
        gabarito_oficial=gab,
        feedback_content=feedback.feedback_content,
        thought_scratchpad=feedback.thought_scratchpad,
        context_chunks=feedback.context_chunks or [],
        is_verified=feedback.is_verified,
        created_at=feedback.created_at,
    )


@router.get(
    "/{resposta_item_id}",
    response_model=FeedbackExplicacaoResponse,
    summary="Consulta feedback existente previamente gerado para um item de resposta",
)
def obter_feedback_item(
    resposta_item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Verifica se a Tutora VERA já gerou feedback para este item e retorna o conteúdo persistido.
    """
    try:
        feedback = feedback_service.obter_feedback_existente(
            db=db,
            resposta_item_id=resposta_item_id,
            user_id=current_user.id,
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )

    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum feedback encontrado para esta resposta.",
        )

    resp = feedback.resposta_item
    q = resp.questao_enem if resp.origem_questao == "enem" else resp.questao_inedita
    hab_cod = q.habilidade_codigo if q else ""
    gab = q.gabarito if q else ""

    return FeedbackExplicacaoResponse(
        id=feedback.id,
        resposta_item_id=feedback.resposta_item_id,
        habilidade_codigo=hab_cod,
        alternativa_marcada=resp.alternativa_marcada or "X",
        gabarito_oficial=gab,
        feedback_content=feedback.feedback_content,
        thought_scratchpad=feedback.thought_scratchpad,
        context_chunks=feedback.context_chunks or [],
        is_verified=feedback.is_verified,
        created_at=feedback.created_at,
    )
