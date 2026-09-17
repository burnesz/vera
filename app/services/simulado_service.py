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
from app.db.models.questao_inedita import QuestaoInedita
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
    descricao: Optional[str] = None,
    proporcao_ineditas: float = 0.15,
    user_id: Optional[uuid.UUID] = None
) -> Simulado:
    """
    Gera um novo simulado de exatamente 45 questões seguindo amostragem estratificada híbrida:
    - Cota de Inéditas: 15% (round(45 * 0.15) = 7 questões) resgatadas da tabela questoes_ineditas.
    - Cota de Históricas: 85% (38 questões) resgatadas da tabela questoes_enem.
    - Cobertura ampla das habilidades da Matriz do ENEM.
    - Complementação estratificada com base nas habilidades líderes de frequência histórica.
    - Embaralhamento aleatório (ordem 1 a 45).
    """
    total_desejado = 45
    alvo_ineditas = round(total_desejado * proporcao_ineditas)
    alvo_historicas = total_desejado - alvo_ineditas

    # 1. Carrega e seleciona a cota de Questões Inéditas
    itens_ineditos: List[QuestaoInedita] = []
    habs_com_inedita: Set[str] = set()

    if alvo_ineditas > 0:
        todas_ineditas = (
            db.query(QuestaoInedita)
            .filter(QuestaoInedita.is_validated == True)
            .all()
        )
        if todas_ineditas:
            ineditas_por_hab: Dict[str, List[QuestaoInedita]] = defaultdict(list)
            for q in todas_ineditas:
                ineditas_por_hab[q.habilidade_codigo].append(q)

            qtd_ineditas_a_selecionar = min(alvo_ineditas, len(ineditas_por_hab))
            habs_sorteadas = random.sample(list(ineditas_por_hab.keys()), k=qtd_ineditas_a_selecionar)

            for hab in habs_sorteadas:
                escolhida = random.choice(ineditas_por_hab[hab])
                itens_ineditos.append(escolhida)
                habs_com_inedita.add(hab)

            logger.info(
                f"Selecionadas {len(itens_ineditos)} questões inéditas de {alvo_ineditas} pretendidas "
                f"cobrindo as habilidades: {sorted(habs_com_inedita)}"
            )
        else:
            logger.warning("Nenhuma questão inédita validada encontrada no banco. O simulado usará 100% históricas.")

    # Ajusta a cota de históricas caso não haja inéditas suficientes
    vagas_historicas = total_desejado - len(itens_ineditos)

    # 2. Carrega e seleciona a cota de Questões Históricas (ENEM)
    todas_historicas = db.query(QuestaoEnem).all()
    if not todas_historicas:
        raise ValueError("Nenhuma questão histórica do ENEM encontrada no banco de dados.")

    historicas_por_hab: Dict[str, List[QuestaoEnem]] = defaultdict(list)
    for q in todas_historicas:
        historicas_por_hab[q.habilidade_codigo].append(q)

    habs_historicas_disponiveis = sorted(historicas_por_hab.keys())

    itens_historicos: List[QuestaoEnem] = []
    ids_historicos_selecionados: Set[uuid.UUID] = set()

    # --- Estágio 1 (Históricas): Cobertura das habilidades que ainda não receberam questão inédita ---
    habs_sem_questao = [h for h in habs_historicas_disponiveis if h not in habs_com_inedita]
    for hab in habs_sem_questao:
        if len(itens_historicos) >= vagas_historicas:
            break
        escolhida = random.choice(historicas_por_hab[hab])
        itens_historicos.append(escolhida)
        ids_historicos_selecionados.add(escolhida.id)

    # --- Estágio 2 (Históricas): Complemento com habilidades de maior relevância ENEM ---
    vagas_sobrando = vagas_historicas - len(itens_historicos)
    if vagas_sobrando > 0:
        top13_validas = [h for h in HABILIDADES_TOP13 if h in historicas_por_hab]
        empatadas_validas = [h for h in HABILIDADES_EMPATADAS_14 if h in historicas_por_hab]

        qtd_sorteio = min(len(empatadas_validas), max(0, vagas_sobrando - len(top13_validas)))
        empatadas_sorteadas = random.sample(empatadas_validas, k=qtd_sorteio) if empatadas_validas else []

        fila_prioritaria = top13_validas + empatadas_sorteadas

        # Se a fila prioritária não for suficiente, expande com outras habilidades disponíveis
        if len(fila_prioritaria) < vagas_sobrando:
            extras = [h for h in habs_historicas_disponiveis if h not in fila_prioritaria]
            random.shuffle(extras)
            fila_prioritaria.extend(extras)

        # Preenche as vagas restantes
        idx_fila = 0
        while len(itens_historicos) < vagas_historicas:
            hab = fila_prioritaria[idx_fila % len(fila_prioritaria)]
            idx_fila += 1

            candidatas = [q for q in historicas_por_hab[hab] if q.id not in ids_historicos_selecionados]
            if not candidatas:
                candidatas = historicas_por_hab[hab]  # Fallback se todas da habilidade já foram usadas

            escolhida = random.choice(candidatas)
            itens_historicos.append(escolhida)
            ids_historicos_selecionados.add(escolhida.id)

    # 3. Mesclagem e Embaralhamento de todas as 45 questões
    itens_completos: List[Dict[str, Any]] = (
        [{"origem": "inedita", "questao": q} for q in itens_ineditos] +
        [{"origem": "enem", "questao": q} for q in itens_historicos]
    )
    random.shuffle(itens_completos)

    # 4. Criação do Simulado e gravação dos SimuladoItens
    total_ineditas_geradas = len(itens_ineditos)
    total_historicas_geradas = len(itens_historicos)

    simulado = Simulado(
        user_id=user_id,
        titulo=titulo or "Simulado ENEM Matemática",
        descricao=descricao or (
            f"Simulado de 45 questões no padrão ENEM composto por {total_historicas_geradas} questões históricas (85%) "
            f"e {total_ineditas_geradas} questões inéditas geradas por IA (15%)."
        ),
        tipo=tipo
    )
    db.add(simulado)
    db.flush()

    for idx, item_data in enumerate(itens_completos, start=1):
        origem = item_data["origem"]
        q = item_data["questao"]

        if origem == "inedita":
            item = SimuladoItem(
                simulado_id=simulado.id,
                ordem=idx,
                origem_questao="inedita",
                questao_inedita_id=q.id
            )
        else:
            item = SimuladoItem(
                simulado_id=simulado.id,
                ordem=idx,
                origem_questao="enem",
                questao_enem_id=q.id
            )
        db.add(item)

    db.commit()
    db.refresh(simulado)

    logger.info(
        f"Simulado '{simulado.id}' gerado com sucesso: {len(itens_completos)} questões "
        f"({total_historicas_geradas} históricas ENEM + {total_ineditas_geradas} inéditas IA)."
    )
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


def listar_simulados_usuario(db: Session, user_id: uuid.UUID) -> List[Dict[str, Any]]:
    """
    Lista todos os simulados pertencentes a um determinado usuário, ordenados pelo mais recente.
    Identifica para cada um se está pendente (em andamento) ou finalizado (com tentativa concluída).
    """
    simulados = (
        db.query(Simulado)
        .options(
            joinedload(Simulado.itens),
            joinedload(Simulado.tentativas),
        )
        .filter(Simulado.user_id == user_id)
        .order_by(Simulado.created_at.desc())
        .all()
    )

    resultado = []
    for sim in simulados:
        # Verifica se há tentativa concluída
        tentativas_concluidas = [
            t for t in sim.tentativas if t.status == "completed"
        ]
        # Pega a mais recente se houver
        ultima_tentativa = None
        if tentativas_concluidas:
            ultima_tentativa = max(
                tentativas_concluidas,
                key=lambda t: t.completed_at or t.started_at
            )

        status_simulado = "finalizado" if ultima_tentativa else "pendente"

        resultado.append({
            "id": sim.id,
            "titulo": sim.titulo,
            "descricao": sim.descricao,
            "tipo": sim.tipo,
            "total_itens": len(sim.itens),
            "created_at": sim.created_at,
            "status": status_simulado,
            "tentativa_id": ultima_tentativa.id if ultima_tentativa else None,
            "total_acertos": ultima_tentativa.total_acertos if ultima_tentativa else None,
            "score_percentual": ultima_tentativa.score_percentual if ultima_tentativa else None,
            "completed_at": ultima_tentativa.completed_at if ultima_tentativa else None,
        })

    return resultado


def obter_resultado_simulado_por_id(db: Session, simulado_id: uuid.UUID, user_id: uuid.UUID) -> Optional[SimuladoTentativa]:
    """
    Recupera a tentativa concluída mais recente de um simulado específico para um usuário.
    """
    return (
        db.query(SimuladoTentativa)
        .options(
            joinedload(SimuladoTentativa.simulado).joinedload(Simulado.itens).joinedload(SimuladoItem.questao_enem),
            joinedload(SimuladoTentativa.simulado).joinedload(Simulado.itens).joinedload(SimuladoItem.questao_inedita),
            joinedload(SimuladoTentativa.respostas),
        )
        .filter(
            SimuladoTentativa.simulado_id == simulado_id,
            SimuladoTentativa.user_id == user_id,
            SimuladoTentativa.status == "completed"
        )
        .order_by(SimuladoTentativa.completed_at.desc())
        .first()
    )

