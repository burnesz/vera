import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.db.models import (
    User,
    HabilidadeEnem,
    QuestaoEnem,
    QuestaoInedita,
    Simulado,
    SimuladoItem,
    SimuladoTentativa,
    RespostaItem,
    Feedback,
    DesempenhoHabilidade,
    ChatSession,
    ChatMessageModel,
)


@pytest.fixture(scope="function")
def db_session():
    """
    Configura um banco SQLite em memória isolado para testes rápidos e independentes de infraestrutura.
    """
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_create_user(db_session):
    student = User(nome="Aluno Teste", email="aluno@teste.com", role="student")
    admin = User(nome="Admin Teste", email="admin@teste.com", role="admin")
    db_session.add_all([student, admin])
    db_session.commit()

    saved_student = db_session.query(User).filter_by(email="aluno@teste.com").first()
    assert saved_student is not None
    assert saved_student.role == "student"
    assert saved_student.is_ativo is True
    assert isinstance(saved_student.id, uuid.UUID)

    saved_admin = db_session.query(User).filter_by(email="admin@teste.com").first()
    assert saved_admin is not None
    assert saved_admin.role == "admin"


def test_habilidade_and_questoes(db_session):
    hab = HabilidadeEnem(
        codigo="H21",
        competencia=5,
        descricao="Resolver situação-problema cuja modelagem envolva conhecimentos algébricos.",
        eixo_tematico="Álgebra e Funções"
    )
    db_session.add(hab)
    db_session.commit()

    # 1. Questão Histórica do ENEM (acervo CSV)
    q_enem = QuestaoEnem(
        ano=2021,
        habilidade_codigo="H21",
        enunciado="Uma fábrica de velas produz...",
        alternativas={
            "A": "10 velas",
            "B": "20 velas",
            "C": "30 velas",
            "D": "40 velas",
            "E": "50 velas"
        },
        gabarito="B"
    )
    db_session.add(q_enem)

    # 2. Questão Inédita (gerada por IA)
    q_inedita = QuestaoInedita(
        habilidade_codigo="H21",
        enunciado="Um produtor rural precisa determinar a quantidade de ração...",
        alternativas={
            "A": "15 kg",
            "B": "25 kg",
            "C": "35 kg",
            "D": "45 kg",
            "E": "55 kg"
        },
        gabarito="C",
        justificativa="A resolução se dá pela equação de 1º grau: 2x + 10 = 80...",
        thought_scratchpad="Modelagem linear básica para avaliar a H21.",
        is_validated=True
    )
    db_session.add(q_inedita)
    db_session.commit()

    saved_q_enem = db_session.query(QuestaoEnem).filter_by(habilidade_codigo="H21").first()
    assert saved_q_enem is not None
    assert saved_q_enem.ano == 2021
    assert saved_q_enem.alternativas["B"] == "20 velas"
    assert saved_q_enem.habilidade.competencia == 5

    saved_q_inedita = db_session.query(QuestaoInedita).filter_by(habilidade_codigo="H21").first()
    assert saved_q_inedita is not None
    assert saved_q_inedita.is_validated is True
    assert saved_q_inedita.gabarito == "C"


def test_simulado_with_hybrid_items(db_session):
    hab = HabilidadeEnem(
        codigo="H08",
        competencia=2,
        descricao="Resolver situação-problema que envolva conhecimentos geométricos de espaço e forma.",
        eixo_tematico="Geometria"
    )
    db_session.add(hab)
    db_session.commit()

    q_enem = QuestaoEnem(
        ano=2020,
        habilidade_codigo="H08",
        enunciado="Geometria ENEM 2020",
        alternativas={"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"},
        gabarito="A"
    )
    q_inedita = QuestaoInedita(
        habilidade_codigo="H08",
        enunciado="Geometria Inédita IA",
        alternativas={"A": "10", "B": "20", "C": "30", "D": "40", "E": "50"},
        gabarito="D",
        justificativa="Cálculo de volume do cilindro"
    )
    db_session.add_all([q_enem, q_inedita])
    db_session.commit()

    simulado = Simulado(
        titulo="Simulado Geometria Espacial",
        descricao="Treino focado na Habilidade H08",
        tipo="treino_habilidade"
    )
    db_session.add(simulado)
    db_session.commit()

    # Item 1: Questão do ENEM
    item1 = SimuladoItem(
        simulado_id=simulado.id,
        ordem=1,
        origem_questao="enem",
        questao_enem_id=q_enem.id
    )
    # Item 2: Questão Inédita
    item2 = SimuladoItem(
        simulado_id=simulado.id,
        ordem=2,
        origem_questao="inedita",
        questao_inedita_id=q_inedita.id
    )
    db_session.add_all([item1, item2])
    db_session.commit()

    loaded_simulado = db_session.get(Simulado, simulado.id)
    assert len(loaded_simulado.itens) == 2
    assert loaded_simulado.itens[0].origem_questao == "enem"
    assert loaded_simulado.itens[0].questao_enem.ano == 2020
    assert loaded_simulado.itens[1].origem_questao == "inedita"
    assert loaded_simulado.itens[1].questao_inedita.gabarito == "D"


def test_submission_and_feedback_flow(db_session):
    # Setup
    user = User(nome="Aluno Teste", email="aluno_simulado@teste.com")
    hab = HabilidadeEnem(
        codigo="H12",
        competencia=3,
        descricao="Resolver situação-problema que envolva medidas de grandezas.",
        eixo_tematico="Grandezas e Medidas"
    )
    db_session.add_all([user, hab])
    db_session.commit()

    q_enem = QuestaoEnem(
        ano=2019,
        habilidade_codigo="H12",
        enunciado="Questão de escala e conversão de unidades",
        alternativas={"A": "100", "B": "200", "C": "300", "D": "400", "E": "500"},
        gabarito="C"
    )
    simulado = Simulado(titulo="Simulado de Medidas")
    db_session.add_all([q_enem, simulado])
    db_session.commit()

    # Tentativa do aluno
    tentativa = SimuladoTentativa(
        user_id=user.id,
        simulado_id=simulado.id,
        status="completed",
        total_itens=1,
        total_acertos=0,
        score_percentual=0.0
    )
    db_session.add(tentativa)
    db_session.commit()

    # Resposta errada do estudante (marcou 'A', gabarito era 'C')
    resposta = RespostaItem(
        tentativa_id=tentativa.id,
        origem_questao="enem",
        questao_enem_id=q_enem.id,
        alternativa_marcada="A",
        is_correta=False
    )
    db_session.add(resposta)
    db_session.commit()

    # Geração do Feedback Pedagógico RAG
    fb = Feedback(
        resposta_item_id=resposta.id,
        feedback_content="Você errou na conversão de cm³ para litros. Observe que 1 litro equivale a 1.000 cm³...",
        thought_scratchpad="O estudante cometeu um erro de conversão de grandezas lineares para cúbicas.",
        context_chunks=[{
            "id": "mat_grandezas_p10_c1",
            "title": "Conversão de Unidades",
            "text": "1 m³ = 1000 litros. 1 dm³ = 1 litro."
        }],
        is_verified=True
    )
    db_session.add(fb)

    # Atualização do Desempenho por Habilidade
    desempenho = DesempenhoHabilidade(
        user_id=user.id,
        habilidade_codigo="H12",
        total_questoes=1,
        total_acertos=0,
        taxa_acerto=0.0,
        nivel_dominio="critico"
    )
    db_session.add(desempenho)
    db_session.commit()

    # Asserções
    loaded_resposta = db_session.get(RespostaItem, resposta.id)
    assert loaded_resposta.is_correta is False
    assert loaded_resposta.feedback is not None
    assert "conversão" in loaded_resposta.feedback.feedback_content
    assert len(loaded_resposta.feedback.context_chunks) == 1

    loaded_desempenho = db_session.query(DesempenhoHabilidade).filter_by(
        user_id=user.id,
        habilidade_codigo="H12"
    ).first()
    assert loaded_desempenho.nivel_dominio == "critico"
    assert loaded_desempenho.taxa_acerto == 0.0


def test_chat_persistence(db_session):
    user = User(nome="Aluno Chat", email="chat@teste.com")
    db_session.add(user)
    db_session.commit()

    session_id = "session_test_123"
    chat_sess = ChatSession(id=session_id, user_id=user.id, titulo="Dúvidas sobre Trigonometria")
    db_session.add(chat_sess)
    db_session.commit()

    msg1 = ChatMessageModel(
        session_id=session_id,
        role="user",
        content="Como funciona o ciclo trigonométrico?"
    )
    msg2 = ChatMessageModel(
        session_id=session_id,
        role="assistant",
        content="O ciclo trigonométrico é uma circunferência de raio unitário (R=1)...",
        thought="Explicar conceitos de seno e cosseno nos quadrantes.",
        context_chunks=[{"title": "Ciclo Trigonométrico", "text": "Raio unitário centrado na origem."}]
    )
    db_session.add_all([msg1, msg2])
    db_session.commit()

    loaded_chat = db_session.get(ChatSession, session_id)
    assert loaded_chat is not None
    assert len(loaded_chat.messages) == 2
    assert loaded_chat.messages[0].role == "user"
    assert loaded_chat.messages[1].role == "assistant"
    assert loaded_chat.user.nome == "Aluno Chat"
