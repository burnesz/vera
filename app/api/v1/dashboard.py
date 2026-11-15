from typing import List, Dict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.api.deps import get_db, get_current_active_user
from app.db.models.user import User
from app.db.models.habilidade import HabilidadeEnem
from app.db.models.history import DesempenhoHabilidade
from app.db.models.submission import SimuladoTentativa
from app.schemas.dashboard import (
    DashboardDesempenhoResponse,
    HabilidadeProgressoItem,
    CompetenciaProgressoItem,
    TentativaResumoItem,
)

router = APIRouter()

COMPETENCIAS_INFO: Dict[int, Dict[str, str]] = {
    1: {
        "titulo": "Números e Operações",
        "descricao": "Construir significados para os números naturais, inteiros, racionais e reais.",
    },
    2: {
        "titulo": "Geometria e Formas",
        "descricao": "Utilizar o conhecimento geométrico para a leitura e representação da realidade.",
    },
    3: {
        "titulo": "Grandezas e Medidas",
        "descricao": "Construir noções de grandezas e medidas para a solução de problemas do cotidiano.",
    },
    4: {
        "titulo": "Proporcionalidade",
        "descricao": "Construir noções de variação de grandezas e proporcionalidade em situações práticas.",
    },
    5: {
        "titulo": "Funções e Álgebra",
        "descricao": "Modelar e resolver problemas envolvendo funções e representações algébricas.",
    },
    6: {
        "titulo": "Estatística e Gráficos",
        "descricao": "Interpretar dados de tabelas e gráficos estatísticos para análise de tendências.",
    },
    7: {
        "titulo": "Probabilidade e Contagem",
        "descricao": "Calcular probabilidades e aplicar princípios de análise combinatória.",
    },
}


@router.get(
    "/desempenho",
    response_model=DashboardDesempenhoResponse,
    summary="Retorna o diagnóstico consolidado de proficiência do estudante no ENEM",
)
def obter_dashboard_desempenho(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retorna a consolidação estatística do estudante:
    - Métricas globais de simulados e acertos.
    - Diagnóstico de proficiência nas 7 Competências (C1 a C7).
    - Status de domínio nas 30 Habilidades (H01 a H30).
    - Histórico das últimas tentativas concluídas.
    """
    # 1. Busca todas as habilidades oficiais cadastradas
    habilidades_db = db.query(HabilidadeEnem).order_by(HabilidadeEnem.codigo.asc()).all()

    # 2. Busca o histórico de desempenho do estudante por habilidade
    desempenhos_db = (
        db.query(DesempenhoHabilidade)
        .filter(DesempenhoHabilidade.user_id == current_user.id)
        .all()
    )
    desempenho_map = {d.habilidade_codigo: d for d in desempenhos_db}

    # 3. Busca tentativas concluídas do usuário
    tentativas_concluidas = (
        db.query(SimuladoTentativa)
        .options(joinedload(SimuladoTentativa.simulado))
        .filter(
            SimuladoTentativa.user_id == current_user.id,
            SimuladoTentativa.status == "completed",
        )
        .order_by(SimuladoTentativa.completed_at.desc())
        .all()
    )

    total_simulados = len(tentativas_concluidas)
    total_questoes_respondidas = sum(t.total_itens for t in tentativas_concluidas)
    total_acertos = sum(t.total_acertos for t in tentativas_concluidas)
    taxa_global = (
        round((total_acertos / total_questoes_respondidas) * 100, 2)
        if total_questoes_respondidas > 0
        else 0.0
    )

    # 4. Mapeia cada uma das 30 habilidades
    habilidades_itens: List[HabilidadeProgressoItem] = []
    comp_acumulador: Dict[int, Dict[str, Any]] = {
        c: {"total_q": 0, "total_a": 0, "hab_count": 0, "hab_cons": 0}
        for c in range(1, 8)
    }

    total_consolidadas = 0
    total_desenvolvimento = 0
    total_criticas = 0

    for hab in habilidades_db:
        desemp = desempenho_map.get(hab.codigo)
        if desemp:
            t_questoes = desemp.total_questoes
            t_acertos = desemp.total_acertos
            taxa = desemp.taxa_acerto
            dominio = desemp.nivel_dominio
            up_at = desemp.updated_at
        else:
            t_questoes = 0
            t_acertos = 0
            taxa = 0.0
            dominio = "em_desenvolvimento"
            up_at = None

        if dominio == "consolidado":
            total_consolidadas += 1
        elif dominio == "critico":
            total_criticas += 1
        else:
            total_desenvolvimento += 1

        # Acumula na respectiva competência
        if hab.competencia in comp_acumulador:
            comp_acumulador[hab.competencia]["total_q"] += t_questoes
            comp_acumulador[hab.competencia]["total_a"] += t_acertos
            comp_acumulador[hab.competencia]["hab_count"] += 1
            if dominio == "consolidado":
                comp_acumulador[hab.competencia]["hab_cons"] += 1

        habilidades_itens.append(
            HabilidadeProgressoItem(
                habilidade_codigo=hab.codigo,
                competencia=hab.competencia,
                descricao=hab.descricao,
                eixo_tematico=hab.eixo_tematico,
                total_questoes=t_questoes,
                total_acertos=t_acertos,
                taxa_acerto=taxa,
                nivel_dominio=dominio,
                updated_at=up_at,
            )
        )

    # 5. Constrói a lista das 7 Competências
    competencias_itens: List[CompetenciaProgressoItem] = []
    for c in range(1, 8):
        c_stats = comp_acumulador[c]
        t_q = c_stats["total_q"]
        t_a = c_stats["total_a"]
        taxa_c = round((t_a / t_q), 3) if t_q > 0 else 0.0

        if t_q == 0:
            c_dominio = "em_desenvolvimento"
        elif taxa_c < 0.50:
            c_dominio = "critico"
        elif taxa_c < 0.75:
            c_dominio = "em_desenvolvimento"
        else:
            c_dominio = "consolidado"

        info = COMPETENCIAS_INFO.get(c, {"titulo": f"Competência {c}", "descricao": ""})
        competencias_itens.append(
            CompetenciaProgressoItem(
                competencia=c,
                titulo=info["titulo"],
                descricao=info["descricao"],
                total_questoes=t_q,
                total_acertos=t_a,
                taxa_acerto=taxa_c,
                nivel_dominio=c_dominio,
                habilidades_total=c_stats["hab_count"],
                habilidades_consolidadas=c_stats["hab_cons"],
            )
        )

    # 6. Prepara as últimas 5 tentativas concluídas
    ultimas_tentativas = [
        TentativaResumoItem(
            tentativa_id=t.id,
            simulado_id=t.simulado_id,
            titulo=t.simulado.titulo if t.simulado else "Simulado ENEM",
            total_itens=t.total_itens,
            total_acertos=t.total_acertos,
            score_percentual=t.score_percentual,
            started_at=t.started_at,
            completed_at=t.completed_at,
        )
        for t in tentativas_concluidas[:5]
    ]

    return DashboardDesempenhoResponse(
        total_simulados=total_simulados,
        total_questoes_respondidas=total_questoes_respondidas,
        total_acertos=total_acertos,
        taxa_acerto_global=taxa_global,
        total_habilidades_consolidadas=total_consolidadas,
        total_habilidades_em_desenvolvimento=total_desenvolvimento,
        total_habilidades_criticas=total_criticas,
        competencias=competencias_itens,
        habilidades=habilidades_itens,
        ultimas_tentativas=ultimas_tentativas,
    )
