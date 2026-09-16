import pytest
import uuid
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
from app.main import app
from app.core.security import get_password_hash, create_access_token
from app.services import simulado_service
from app.schemas.simulado import RespostaItemInput, SimuladoSubmissaoRequest
from scripts.seed_habilidades import HABILIDADES_MAT

# Banco SQLite em memória para os testes
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


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_database_data():
    """
    Popula as habilidades e questões de teste para as 28 habilidades disponíveis.
    """
    db = TestingSessionLocal()
    # 1. Habilidades
    for hab in HABILIDADES_MAT:
        db.add(HabilidadeEnem(
            codigo=hab["codigo"],
            competencia=hab["competencia"],
            descricao=hab["descricao"],
            eixo_tematico=hab["eixo_tematico"]
        ))
    db.commit()

    # 2. Popula questões para as 28 habilidades (todas exceto H06 e H20)
    # Colocamos pelo menos 3 questões por habilidade para permitir o sorteio da 1ª e da 2ª questão
    habs_disponiveis = [f"H{i:02d}" for i in range(1, 31) if i not in (6, 20)]
    co_item_counter = 1000

    for hab_code in habs_disponiveis:
        for q_idx in range(1, 4):
            co_item_counter += 1
            db.add(QuestaoEnem(
                co_item=co_item_counter,
                ano=2020,
                habilidade_codigo=hab_code,
                enunciado=f"Enunciado da questão {co_item_counter} da habilidade {hab_code}.",
                alternativas={
                    "A": "Alternativa A",
                    "B": "Alternativa B",
                    "C": "Alternativa C",
                    "D": "Alternativa D",
                    "E": "Alternativa E",
                },
                gabarito="B",
                metadados={"tri": {"param_b": 1.2}}
            ))
    db.commit()

    # 3. Usuário de teste
    test_user = User(
        id=uuid.uuid4(),
        nome="Estudante Simulado",
        email="estudante.simulado@teste.com",
        hashed_password=get_password_hash("senha123"),
        role="student",
        is_ativo=True
    )
    db.add(test_user)
    db.commit()
    db.close()


@pytest.fixture
def auth_headers():
    db = TestingSessionLocal()
    user = db.query(User).filter_by(email="estudante.simulado@teste.com").first()
    token = create_access_token({"sub": str(user.id), "role": user.role})
    db.close()
    return {"Authorization": f"Bearer {token}"}


def test_gerar_simulado_service():
    """
    Testa geração do simulado na camada de serviço:
    - Exatamente 45 questões
    - 28 habilidades contempladas
    - Ordens de 1 a 45 sequenciais
    """
    db = TestingSessionLocal()
    simulado = simulado_service.gerar_simulado_enem(db, titulo="Simulado Unitário", tipo="diagnostico")

    assert simulado.id is not None
    assert len(simulado.itens) == 45

    # Valida sequência de ordens
    ordens = [item.ordem for item in simulado.itens]
    assert ordens == list(range(1, 46))

    # Valida que todas as 28 habilidades disponíveis foram contempladas
    habs_no_simulado = set(item.questao_enem.habilidade_codigo for item in simulado.itens)
    assert len(habs_no_simulado) == 28
    assert "H06" not in habs_no_simulado
    assert "H20" not in habs_no_simulado

    db.close()


def test_submeter_tentativa_service():
    """
    Testa a correção e persistência de tentativa de simulado.
    """
    db = TestingSessionLocal()
    user = db.query(User).filter_by(email="estudante.simulado@teste.com").first()
    simulado = simulado_service.gerar_simulado_enem(db, titulo="Simulado para Submissão")

    # Responde as primeiras 10 questões como 'B' (gabarito correto) e as outras 35 como 'A' (incorreto)
    respostas_input = []
    for item in simulado.itens:
        alternativa = "B" if item.ordem <= 10 else "A"
        respostas_input.append(
            RespostaItemInput(
                simulado_item_id=item.id,
                alternativa_selecionada=alternativa
            )
        )

    tentativa = simulado_service.submeter_tentativa_simulado(
        db=db,
        simulado_id=simulado.id,
        user_id=user.id,
        respostas_input=respostas_input
    )

    assert tentativa.total_itens == 45
    assert tentativa.total_acertos == 10
    assert tentativa.score_percentual == round((10 / 45) * 100, 2)
    assert tentativa.status == "completed"
    assert tentativa.completed_at is not None
    assert len(tentativa.respostas) == 45

    db.close()


def test_api_simulado_completo(auth_headers):
    """
    Testa o fluxo completo via API:
    1. POST /api/v1/simulados/gerar (Gera simulado, valida sem gabarito)
    2. GET /api/v1/simulados/{id} (Consulta simulado para resolução)
    3. POST /api/v1/simulados/{id}/submeter (Submete e calcula nota)
    4. GET /api/v1/simulados/tentativas/{tentativa_id} (Recupera resultado)
    """
    # 1. Gerar Simulado
    resp_gerar = client.post(
        "/api/v1/simulados/gerar",
        json={"titulo": "Simulado API Teste", "tipo": "diagnostico"},
        headers=auth_headers
    )
    assert resp_gerar.status_code == 201
    dados_simulado = resp_gerar.json()
    assert dados_simulado["total_itens"] == 45
    assert len(dados_simulado["itens"]) == 45
    simulado_id = dados_simulado["id"]

    # Valida que o gabarito NÃO é exposto na resposta da prova
    for item in dados_simulado["itens"]:
        assert "gabarito" not in item
        assert "gabarito_oficial" not in item
        assert item["enunciado"] is not None
        assert "A" in item["alternativas"]

    # 2. Obter Simulado por ID
    resp_obter = client.get(f"/api/v1/simulados/{simulado_id}", headers=auth_headers)
    assert resp_obter.status_code == 200
    assert resp_obter.json()["id"] == simulado_id
    assert len(resp_obter.json()["itens"]) == 45

    # 3. Submeter Simulado
    # Marca tudo como 'B' (todas as questões de teste têm gabarito 'B', portanto acertará 45/45)
    respostas_payload = [
        {"simulado_item_id": item["simulado_item_id"], "alternativa_selecionada": "B"}
        for item in dados_simulado["itens"]
    ]

    resp_submeter = client.post(
        f"/api/v1/simulados/{simulado_id}/submeter",
        json={"respostas": respostas_payload},
        headers=auth_headers
    )
    assert resp_submeter.status_code == 200
    resultado = resp_submeter.json()
    assert resultado["simulado_id"] == simulado_id
    assert resultado["total_itens"] == 45
    assert resultado["total_acertos"] == 45
    assert resultado["score_percentual"] == 100.0
    assert len(resultado["itens"]) == 45
    tentativa_id = resultado["tentativa_id"]

    # Agora o gabarito oficial DEVE estar presente no relatório de correção
    for item in resultado["itens"]:
        assert item["gabarito_oficial"] == "B"
        assert item["alternativa_selecionada"] == "B"
        assert item["is_correto"] is True

    # 4. Consultar Tentativa
    resp_tentativa = client.get(f"/api/v1/simulados/tentativas/{tentativa_id}", headers=auth_headers)
    assert resp_tentativa.status_code == 200
    tentativa_dados = resp_tentativa.json()
    assert tentativa_dados["tentativa_id"] == tentativa_id
    assert tentativa_dados["total_acertos"] == 45
