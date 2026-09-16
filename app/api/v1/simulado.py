import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_active_user
from app.db.models.user import User
from app.schemas.simulado import (
    SimuladoCreateRequest,
    SimuladoResponse,
    QuestaoItemResponse,
    SimuladoSubmissaoRequest,
    SimuladoResultadoResponse,
    ItemCorrecaoResponse,
)
from app.services import simulado_service

router = APIRouter()


@router.post(
    "/gerar",
    response_model=SimuladoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Gera um novo simulado de 45 questões no padrão ENEM",
    description=(
        "Gera e persiste um caderno de simulado de 45 questões com amostragem estratificada: "
        "28 questões base (cobrindo 100% das habilidades textuais disponíveis) e 17 questões complementares "
        "distribuídas nas habilidades de maior peso do ENEM. Os gabaritos são omitidos nesta resposta."
    ),
)
def gerar_simulado(
    body: SimuladoCreateRequest = SimuladoCreateRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        simulado = simulado_service.gerar_simulado_enem(
            db=db,
            titulo=body.titulo,
            tipo=body.tipo,
            descricao=body.descricao
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    itens_response = []
    for item in simulado.itens:
        if item.origem_questao == "enem" and item.questao_enem:
            q = item.questao_enem
            itens_response.append(
                QuestaoItemResponse(
                    simulado_item_id=item.id,
                    ordem=item.ordem,
                    origem_questao=item.origem_questao,
                    questao_id=q.id,
                    ano=q.ano,
                    habilidade_codigo=q.habilidade_codigo,
                    enunciado=q.enunciado,
                    alternativas=q.alternativas,
                )
            )
        elif item.origem_questao == "inedita" and item.questao_inedita:
            q = item.questao_inedita
            itens_response.append(
                QuestaoItemResponse(
                    simulado_item_id=item.id,
                    ordem=item.ordem,
                    origem_questao=item.origem_questao,
                    questao_id=q.id,
                    ano=None,
                    habilidade_codigo=q.habilidade_codigo,
                    enunciado=q.enunciado,
                    alternativas=q.alternativas,
                )
            )

    return SimuladoResponse(
        id=simulado.id,
        titulo=simulado.titulo,
        descricao=simulado.descricao,
        tipo=simulado.tipo,
        total_itens=len(itens_response),
        itens=itens_response,
        created_at=simulado.created_at,
    )


@router.get(
    "/{simulado_id}",
    response_model=SimuladoResponse,
    summary="Recupera um simulado montado para realização (SEM gabarito)",
)
def obter_simulado(
    simulado_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    simulado = simulado_service.obter_simulado_com_questoes(db, simulado_id)
    if not simulado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulado não encontrado."
        )

    itens_response = []
    for item in sorted(simulado.itens, key=lambda x: x.ordem):
        if item.origem_questao == "enem" and item.questao_enem:
            q = item.questao_enem
            itens_response.append(
                QuestaoItemResponse(
                    simulado_item_id=item.id,
                    ordem=item.ordem,
                    origem_questao=item.origem_questao,
                    questao_id=q.id,
                    ano=q.ano,
                    habilidade_codigo=q.habilidade_codigo,
                    enunciado=q.enunciado,
                    alternativas=q.alternativas,
                )
            )
        elif item.origem_questao == "inedita" and item.questao_inedita:
            q = item.questao_inedita
            itens_response.append(
                QuestaoItemResponse(
                    simulado_item_id=item.id,
                    ordem=item.ordem,
                    origem_questao=item.origem_questao,
                    questao_id=q.id,
                    ano=None,
                    habilidade_codigo=q.habilidade_codigo,
                    enunciado=q.enunciado,
                    alternativas=q.alternativas,
                )
            )

    return SimuladoResponse(
        id=simulado.id,
        titulo=simulado.titulo,
        descricao=simulado.descricao,
        tipo=simulado.tipo,
        total_itens=len(itens_response),
        itens=itens_response,
        created_at=simulado.created_at,
    )


@router.post(
    "/{simulado_id}/submeter",
    response_model=SimuladoResultadoResponse,
    summary="Submete as respostas de um simulado, calcula score e revela gabarito",
)
def submeter_simulado(
    simulado_id: uuid.UUID,
    payload: SimuladoSubmissaoRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        tentativa = simulado_service.submeter_tentativa_simulado(
            db=db,
            simulado_id=simulado_id,
            user_id=current_user.id,
            respostas_input=payload.respostas
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    return formatar_resultado_tentativa(tentativa)


@router.get(
    "/tentativas/{tentativa_id}",
    response_model=SimuladoResultadoResponse,
    summary="Consulta o resultado de uma tentativa realizada",
)
def obter_tentativa(
    tentativa_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    tentativa = simulado_service.obter_tentativa_com_itens(db, tentativa_id)
    if not tentativa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tentativa de simulado não encontrada."
        )

    # Garante que o estudante só visualiza suas próprias tentativas (a não ser que seja admin)
    if tentativa.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso não autorizado a esta tentativa."
        )

    return formatar_resultado_tentativa(tentativa)


def formatar_resultado_tentativa(tentativa) -> SimuladoResultadoResponse:
    """
    Função auxiliar para montar o payload de resultado e conferência de gabarito.
    """
    simulado = tentativa.simulado
    # Mapa de respostas salvas
    mapa_respostas = {}
    for resp in tentativa.respostas:
        mapa_respostas[resp.questao_enem_id or resp.questao_inedita_id] = resp

    itens_correcao: List[ItemCorrecaoResponse] = []
    for item in sorted(simulado.itens, key=lambda x: x.ordem):
        q_id = item.questao_enem_id or item.questao_inedita_id
        resposta_dada = mapa_respostas.get(q_id)

        if item.origem_questao == "enem" and item.questao_enem:
            gabarito = item.questao_enem.gabarito
            hab = item.questao_enem.habilidade_codigo
        elif item.origem_questao == "inedita" and item.questao_inedita:
            gabarito = item.questao_inedita.gabarito
            hab = item.questao_inedita.habilidade_codigo
        else:
            gabarito = ""
            hab = ""

        marcada = resposta_dada.alternativa_marcada if resposta_dada else None
        is_correto = resposta_dada.is_correta if resposta_dada else False

        itens_correcao.append(
            ItemCorrecaoResponse(
                ordem=item.ordem,
                simulado_item_id=item.id,
                questao_id=q_id,
                habilidade_codigo=hab,
                alternativa_selecionada=marcada if marcada != "X" else None,
                gabarito_oficial=gabarito,
                is_correto=is_correto,
            )
        )

    return SimuladoResultadoResponse(
        tentativa_id=tentativa.id,
        simulado_id=tentativa.simulado_id,
        user_id=tentativa.user_id,
        status=tentativa.status,
        total_itens=tentativa.total_itens,
        total_acertos=tentativa.total_acertos,
        score_percentual=tentativa.score_percentual,
        started_at=tentativa.started_at,
        completed_at=tentativa.completed_at,
        itens=itens_correcao,
    )
