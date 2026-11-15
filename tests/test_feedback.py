import pytest
import uuid
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models
from app.db.base import Base
from app.db.session import get_db
from app.db.models.user import User
from app.db.models.habilidade import HabilidadeEnem
from app.db.models.questao_enem import QuestaoEnem
from app.db.models.simulado import Simulado, SimuladoItem
from app.db.models.submission import SimuladoTentativa, RespostaItem
from app.db.models.feedback import Feedback
from app.db.models.history import DesempenhoHabilidade
from app.main import app
from app.core.security import get_password_hash, create_access_token
from app.services.feedback_service import FeedbackService
from app.services import simulado_service
from app.schemas.simulado import RespostaItemInput

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_seed():
    db = TestingSessionLocal()
    # Cria Habilidades
    for i in range(1, 31):
        hab_code = f"H{str(i).zfill(2)}"
        comp = ((i - 1) // 5) + 1
        if comp > 7:
            comp = 7
        db.add(HabilidadeEnem(
            codigo=hab_code,
            competencia=comp,
            descricao=f"Descrição oficial para {hab_code}",
            eixo_tematico="Matemática e suas Tecnologias"
        ))

    # Cria Usuário Estudante
    user = User(
        id=uuid.uuid4(),
        email="estudante_feedback@vera.com",
        nome="Estudante Feedback",
        hashed_password=get_password_hash("senha123"),
        role="student",
        is_ativo=True,
    )
    db.add(user)

    # Cria Questão ENEM
    q = QuestaoEnem(
        id=uuid.uuid4(),
        ano=2023,
        habilidade_codigo="H03",
        co_item=99901,
        enunciado="Um comerciante comprou 50 unidades de um produto por R$ 20,00 cada. Qual é o valor do lucro obtido se vender cada uma por R$ 25,00?",
        alternativas={"A": "R$ 100", "B": "R$ 200", "C": "R$ 250", "D": "R$ 300", "E": "R$ 500"},
        gabarito="C",
        metadados={"justificativa": "Lucro unitário é 25 - 20 = 5. Multiplicando por 50 temos 250."}
    )
    db.add(q)
    db.commit()

    # Cria Simulado e SimuladoItem
    sim = Simulado(
        id=uuid.uuid4(),
        user_id=user.id,
        titulo="Simulado Teste Feedback",
        tipo="geral",
    )
    db.add(sim)
    db.flush()

    item = SimuladoItem(
        simulado_id=sim.id,
        ordem=1,
        origem_questao="enem",
        questao_enem_id=q.id,
    )
    db.add(item)
    db.commit()

    # Garante override das dependências para este módulo de teste
    from app.api.deps import get_current_active_user
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_active_user] = lambda: user

    yield {
        "user_id": user.id,
        "questao_id": q.id,
        "simulado_id": sim.id,
        "simulado_item_id": item.id,
    }

    app.dependency_overrides.pop(get_current_active_user, None)



def test_build_rag_query():
    service = FeedbackService()
    query = service.build_rag_query(
        "H03",
        "Um comerciante comprou mercadorias com 10% de desconto. Qual é o valor final a ser pago?"
    )
    assert len(query) > 10
    # Deve conter menção a termos conceituais
    assert "Qual é o valor final a ser pago?" in query


def test_submissao_simulado_atualiza_desempenho_habilidades(setup_seed):
    db = TestingSessionLocal()
    user_id = setup_seed["user_id"]
    simulado_id = setup_seed["simulado_id"]
    item_id = setup_seed["simulado_item_id"]
    questao_id = setup_seed["questao_id"]

    # Submete com alternativa incorreta "B" (gabarito é C)
    respostas = [
        RespostaItemInput(
            simulado_item_id=item_id,
            questao_id=questao_id,
            alternativa_marcada="B",
            alternativa_selecionada="B",
        )
    ]
    tentativa = simulado_service.submeter_tentativa_simulado(db, simulado_id, user_id, respostas)
    assert tentativa.status == "completed"
    assert tentativa.total_acertos == 0

    # Verifica se DesempenhoHabilidade foi criado e atualizado
    desemp = db.query(DesempenhoHabilidade).filter(
        DesempenhoHabilidade.user_id == user_id,
        DesempenhoHabilidade.habilidade_codigo == "H03",
    ).first()
    assert desemp is not None
    assert desemp.total_questoes == 1
    assert desemp.total_acertos == 0
    assert desemp.taxa_acerto == 0.0
    assert desemp.nivel_dominio == "critico"


def test_gerar_feedback_com_mock_llm_e_cache(setup_seed):
    db = TestingSessionLocal()
    user_id = setup_seed["user_id"]

    # Pega a resposta do item salva
    resposta = db.query(RespostaItem).first()
    assert resposta is not None

    mock_llm = MagicMock()
    mock_llm.generate.return_value = (
        "<pensamento>\n"
        "O aluno marcou B porque calculou 20 * 10 em vez de (25-20)*50.\n"
        "</pensamento>\n"
        "<resposta>\n"
        "Você errou ao esquecer de calcular a diferença unitária.\n"
        "O cálculo correto é: $$Lucro = (25 - 20) \\times 50 = 250$$\n"
        "Recomendo revisar o conceito de lucro e margem de contribuição na habilidade H03.\n"
        "</resposta>"
    )

    mock_vectorstore = MagicMock()
    mock_vectorstore.search.return_value = [
        {"id": "doc-1", "metadata": {"title": "Apostila Matemática", "topic": "Matemática Financeira"}, "text": "Lucro é receita menos custo."}
    ]

    service = FeedbackService(llm_client=mock_llm, vector_store=mock_vectorstore)

    # 1. Primeira chamada: gera e persiste
    feedback = service.gerar_ou_obter_feedback_item(db, resposta.id, user_id)
    assert feedback is not None
    assert feedback.resposta_item_id == resposta.id
    assert "O cálculo correto é:" in feedback.feedback_content
    assert feedback.thought_scratchpad is not None
    assert "O aluno marcou B" in feedback.thought_scratchpad
    assert mock_llm.generate.call_count == 1

    # 2. Segunda chamada: deve retornar do cache (sem chamar LLM novamente)
    feedback_cached = service.gerar_ou_obter_feedback_item(db, resposta.id, user_id)
    assert feedback_cached.id == feedback.id
    assert mock_llm.generate.call_count == 1  # Mantém 1, provando cache instantâneo


def test_api_dashboard_desempenho(setup_seed):
    user_id = setup_seed["user_id"]
    token = create_access_token(subject=str(user_id))

    response = client.get(
        "/api/v1/dashboard/desempenho",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_simulados"] >= 1
    assert "competencias" in data
    assert len(data["competencias"]) == 7
    assert "habilidades" in data
    assert len(data["habilidades"]) == 30
    assert "ultimas_tentativas" in data
    assert len(data["ultimas_tentativas"]) >= 1


def test_api_feedback_endpoints(setup_seed):
    db = TestingSessionLocal()
    user_id = setup_seed["user_id"]
    token = create_access_token(subject=str(user_id))
    resposta = db.query(RespostaItem).first()

    # Consulta feedback existente via GET
    res_get = client.get(
        f"/api/v1/feedback/{resposta.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_get.status_code == 200
    data_get = res_get.json()
    assert data_get["resposta_item_id"] == str(resposta.id)
    assert data_get["alternativa_marcada"] == "B"
    assert data_get["gabarito_oficial"] == "C"


def test_api_listar_minhas_tentativas(setup_seed):
    user_id = setup_seed["user_id"]
    token = create_access_token(subject=str(user_id))

    response = client.get(
        "/api/v1/simulados/tentativas/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    tentativas = response.json()
    assert len(tentativas) >= 1
    assert "score_percentual" in tentativas[0]
    assert "total_acertos" in tentativas[0]
