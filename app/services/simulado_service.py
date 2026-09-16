import uuid
import random
import logging
from datetime import datetime, timezone
from collections import defaultdict
from typing import Dict, Any, List, Optional, Set
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select

from app.db.models.simulado import Simulado, SimuladoItem
from app.db.models.questao_enem import QuestaoEnem
from app.db.models.submission import SimuladoTentativa, RespostaItem
from app.schemas.simulado import RespostaItemInput

logger = logging.getLogger("vera.services.simulado")

# As 13 habilidades líderes com acervo farto (>= 15 questões) para a 2ª questão
HABILIDADES_TOP13 = [
    "H01", "H02", "H03", "H04", "H11", "H12", 
    "H16", "H17", "H18", "H19", "H21", "H28", "H29"
]

# As 6 habilidades empatadas com 14 questões (4 delas são sorteadas para a 2ª questão)
HABILIDADES_EMPATADAS_14 = [
    "H05", "H10", "H14", "H23", "H27", "H30"
]


def gerar_simulado_enem(
    db: Session,
    titulo: Optional[str] = None,
    tipo: str = "diagnostico",
    descricao: Optional[str] = None
) -> Simulado:
    """
    Gera um novo simulado de exatamente 45 questões seguindo amostragem estratificada:
    - Estágio 1: 1 questão de cada uma das 28 habilidades disponíveis.
    - Estágio 2: 17 questões complementares das habilidades de maior relevância no ENEM (13 líderes + 4 sorteadas das 6 empatadas).
    - Estágio 3: Embaralhamento com ordem 1 a 45.
    (Sem anti-repetição por estudante, garantindo consulta rápida, desacoplada e direta).
    """
    # 1. Carrega todas as questões históricas do banco agrupadas por habilidade
    todas_questoes = db.query(QuestaoEnem).all()
    if not todas_questoes:
        raise ValueError("Nenhuma questão histórica do ENEM encontrada no banco de dados.")

    questoes_por_hab: Dict[str, List[QuestaoEnem]] = defaultdict(list)
    for q in todas_questoes:
        questoes_por_hab[q.habilidade_codigo].append(q)

    habs_disponiveis = sorted(questoes_por_hab.keys())
    total_habs = len(habs_disponiveis)

    questoes_selecionadas: List[QuestaoEnem] = []
    ids_selecionados: Set[uuid.UUID] = set()

    # --- Estágio 1: Cobertura Base (1 por habilidade disponível) ---
    for hab in habs_disponiveis:
        escolhida = random.choice(questoes_por_hab[hab])
        questoes_selecionadas.append(escolhida)
        ids_selecionados.add(escolhida.id)

    # --- Estágio 2: Complemento Estratificado ENEM (17 vagas restantes) ---
    vagas_extras = 45 - total_habs  # Tipicamente 45 - 28 = 17 vagas
    if vagas_extras > 0:
        # Filtra habilidades top que de fato existem no banco
        top13_validas = [h for h in HABILIDADES_TOP13 if h in questoes_por_hab]
        empatadas_validas = [h for h in HABILIDADES_EMPATADAS_14 if h in questoes_por_hab]

        qtd_sorteio = min(len(empatadas_validas), max(0, vagas_extras - len(top13_validas)))
        empatadas_sorteadas = random.sample(empatadas_validas, k=qtd_sorteio) if empatadas_validas else []

        habs_segunda_questao = top13_validas + empatadas_sorteadas

        for hab in habs_segunda_questao[:vagas_extras]:
            candidatas = [q for q in questoes_por_hab[hab] if q.id not in ids_selecionados]
            if not candidatas:
                candidatas = questoes_por_hab[hab]  # Fallback de segurança

            escolhida = random.choice(candidatas)
            questoes_selecionadas.append(escolhida)
            ids_selecionados.add(escolhida.id)

    # --- Estágio 3: Embaralhamento final ---
    random.shuffle(questoes_selecionadas)

    # Criação do Simulado e seus SimuladoItens
    simulado = Simulado(
        titulo=titulo or "Simulado ENEM Matemática",
        descricao=descricao or f"Simulado de 45 questões estratificado no padrão ENEM cobrindo {total_habs} habilidades.",
        tipo=tipo
    )
    db.add(simulado)
    db.flush()

    for idx, q in enumerate(questoes_selecionadas, start=1):
        item = SimuladoItem(
            simulado_id=simulado.id,
            ordem=idx,
            origem_questao="enem",
            questao_enem_id=q.id
        )
        db.add(item)

    db.commit()
    db.refresh(simulado)

    logger.info(f"Simulado '{simulado.id}' gerado com sucesso ({len(questoes_selecionadas)} questões).")
    return simulado


def obter_simulado_com_questoes(db: Session, simulado_id: uuid.UUID) -> Optional[Simulado]:
    """
    Recupera um simulado ordenado por ordem dos itens com as questões associadas carregadas.
    """
    return (
        db.query(Simulado)
        .options(
            joinedload(Simulado.itens).joinedload(SimuladoItem.questao_enem),
            joinedload(Simulado.itens).joinedload(SimuladoItem.questao_inedita),
        )
        .filter(Simulado.id == simulado_id)
        .first()
    )


def submeter_tentativa_simulado(
    db: Session,
    simulado_id: uuid.UUID,
    user_id: uuid.UUID,
    respostas_input: List[RespostaItemInput]
) -> SimuladoTentativa:
    """
    Valida e calcula o resultado da submissão do estudante para um simulado.
    Salva a SimuladoTentativa e cada RespostaItem no banco.
    """
    simulado = obter_simulado_com_questoes(db, simulado_id)
    if not simulado:
        raise ValueError(f"Simulado não encontrado para o ID: {simulado_id}")

    # Indexa as respostas do aluno por simulado_item_id
    respostas_map: Dict[uuid.UUID, str] = {
        r.simulado_item_id: r.alternativa_selecionada.strip().upper()
        for r in respostas_input
    }

    total_itens = len(simulado.itens)
    total_acertos = 0
    now = datetime.now(timezone.utc)

    tentativa = SimuladoTentativa(
        user_id=user_id,
        simulado_id=simulado.id,
        status="completed",
        total_itens=total_itens,
        total_acertos=0,
        score_percentual=0.0,
        completed_at=now
    )
    db.add(tentativa)
    db.flush()

    for item in simulado.itens:
        alternativa_marcada = respostas_map.get(item.id, "X")  # 'X' indica item não respondido/em branco
        
        # Obtém gabarito da questão histórica ou inédita
        if item.origem_questao == "enem" and item.questao_enem:
            gabarito = item.questao_enem.gabarito.strip().upper()
        elif item.origem_questao == "inedita" and item.questao_inedita:
            gabarito = item.questao_inedita.gabarito.strip().upper()
        else:
            gabarito = ""

        is_correta = (alternativa_marcada == gabarito) if alternativa_marcada != "X" else False
        if is_correta:
            total_acertos += 1

        resposta_db = RespostaItem(
            tentativa_id=tentativa.id,
            origem_questao=item.origem_questao,
            questao_enem_id=item.questao_enem_id,
            questao_inedita_id=item.questao_inedita_id,
            alternativa_marcada=alternativa_marcada,
            is_correta=is_correta
        )
        db.add(resposta_db)

    tentativa.total_acertos = total_acertos
    tentativa.score_percentual = round((total_acertos / total_itens) * 100, 2) if total_itens > 0 else 0.0

    db.commit()
    db.refresh(tentativa)
    logger.info(f"Tentativa '{tentativa.id}' submetida: {total_acertos}/{total_itens} acertos ({tentativa.score_percentual}%).")
    return tentativa


def obter_tentativa_com_itens(db: Session, tentativa_id: uuid.UUID) -> Optional[SimuladoTentativa]:
    """
    Recupera uma tentativa com simulado, itens e respostas carregados.
    """
    return (
        db.query(SimuladoTentativa)
        .options(
            joinedload(SimuladoTentativa.simulado).joinedload(Simulado.itens).joinedload(SimuladoItem.questao_enem),
            joinedload(SimuladoTentativa.simulado).joinedload(Simulado.itens).joinedload(SimuladoItem.questao_inedita),
            joinedload(SimuladoTentativa.respostas)
        )
        .filter(SimuladoTentativa.id == tentativa_id)
        .first()
    )
