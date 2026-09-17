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
from app.db.models.questao_inedita import QuestaoInedita
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
    Popula as habilidades, questões históricas e questões inéditas de teste.
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

    # 2. Popula questões históricas para as 28 habilidades (todas exceto H06 e H20)
    habs_disponiveis = [f"H{i:02d}" for i in range(1, 31) if i not in (6, 20)]
    co_item_counter = 1000

    for hab_code in habs_disponiveis:
        for q_idx in range(1, 4):
            co_item_counter += 1
            db.add(QuestaoEnem(
                co_item=co_item_counter,
                ano=2020,
                habilidade_codigo=hab_code,
                enunciado=f"Enunciado da questão histórica {co_item_counter} da habilidade {hab_code}.",
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

    # 3. Popula questões inéditas para 10 habilidades (H01 a H10)
    for hab_code in [f"H{i:02d}" for i in range(1, 11)]:
        db.add(QuestaoInedita(
            id=uuid.uuid4(),
            habilidade_codigo=hab_code,
            enunciado=f"Enunciado da questão inédita gerada por IA da habilidade {hab_code}.",
            alternativas={
                "A": "Alternativa Inédita A",
                "B": "Alternativa Inédita B",
                "C": "Alternativa Inédita C",
                "D": "Alternativa Inédita D",
                "E": "Alternativa Inédita E",
            },
            gabarito="B",
            justificativa="Resolução demonstrando que a alternativa B é o gabarito.",
            is_validated=True
        ))
    db.commit()

    # 4. Usuário de teste
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
    token = create_access_token(subject=str(user.id), role=user.role)
    db.close()
    return {"Authorization": f"Bearer {token}"}


def test_gerar_simulado_service():
    """
    Testa geração do simulado híbrido na camada de serviço:
    - Exatamente 45 questões
    - 15% de inéditas (7 questões) e 85% de históricas (38 questões)
    - Ordens de 1 a 45 sequenciais
    """
    db = TestingSessionLocal()
    simulado = simulado_service.gerar_simulado_enem(
        db,
        titulo="Simulado Híbrido Unitário",
        tipo="diagnostico",
        proporcao_ineditas=0.15
    )

    assert simulado.id is not None
    assert len(simulado.itens) == 45

    # Valida sequência de ordens
    ordens = [item.ordem for item in simulado.itens]
    assert ordens == list(range(1, 46))

    # Valida cotas de 15% inéditas (7) e 85% históricas (38)
    ineditas_itens = [item for item in simulado.itens if item.origem_questao == "inedita"]
    historicas_itens = [item for item in simulado.itens if item.origem_questao == "enem"]

    assert len(ineditas_itens) == 7
    assert len(historicas_itens) == 38

    for item in ineditas_itens:
        assert item.questao_inedita_id is not None
        assert item.questao_enem_id is None
        assert item.questao_inedita is not None

    for item in historicas_itens:
        assert item.questao_enem_id is not None
        assert item.questao_inedita_id is None
        assert item.questao_enem is not None

    # Valida diversidade de habilidades
    habs_no_simulado = set(
        item.questao_enem.habilidade_codigo if item.origem_questao == "enem"
        else item.questao_inedita.habilidade_codigo
        for item in simulado.itens
    )
    assert len(habs_no_simulado) >= 28

    # Testa também fallback com 0% inéditas
    simulado_zero = simulado_service.gerar_simulado_enem(
        db,
        titulo="Simulado 100% ENEM",
        proporcao_ineditas=0.0
    )
    assert len(simulado_zero.itens) == 45
    assert sum(1 for i in simulado_zero.itens if i.origem_questao == "inedita") == 0
    assert sum(1 for i in simulado_zero.itens if i.origem_questao == "enem") == 45

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
    assert dados_simulado["total_ineditas"] == 7
    assert dados_simulado["total_enem"] == 38
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


def test_listar_simulados_pendentes_e_arquivados(auth_headers):
    """
    Testa a listagem segregada de simulados pendentes e arquivados (finalizados):
    - Simulado pendente: gerado mas sem tentativa finalizada.
    - Simulado finalizado: gerado e com tentativa submetida.
    - Consulta de resultado por simulado_id.
    """
    # 1. Gera Simulado A (não será submetido -> pendente)
    resp_a = client.post(
        "/api/v1/simulados/gerar",
        json={"titulo": "Simulado Pendente de Teste"},
        headers=auth_headers
    )
    assert resp_a.status_code == 201
    simulado_a_id = resp_a.json()["id"]

    # 2. Gera Simulado B (será submetido -> finalizado/arquivado)
    resp_b = client.post(
        "/api/v1/simulados/gerar",
        json={"titulo": "Simulado Finalizado de Teste"},
        headers=auth_headers
    )
    assert resp_b.status_code == 201
    simulado_b_id = resp_b.json()["id"]
    itens_b = resp_b.json()["itens"]

    # Submete Simulado B
    submissao_payload = [
        {"simulado_item_id": item["simulado_item_id"], "alternativa_selecionada": "B"}
        for item in itens_b
    ]
    resp_sub = client.post(
        f"/api/v1/simulados/{simulado_b_id}/submeter",
        json={"respostas": submissao_payload},
        headers=auth_headers
    )
    assert resp_sub.status_code == 200

    # 3. Lista simulados do usuário via GET /api/v1/simulados/
    resp_lista = client.get("/api/v1/simulados/", headers=auth_headers)
    assert resp_lista.status_code == 200
    simulados = resp_lista.json()
    assert len(simulados) >= 2

    # Localiza os simulados na lista
    sim_a = next((s for s in simulados if s["id"] == simulado_a_id), None)
    sim_b = next((s for s in simulados if s["id"] == simulado_b_id), None)

    assert sim_a is not None
    assert sim_a["titulo"] == "Simulado Pendente de Teste"
    assert sim_a["status"] == "pendente"
    assert sim_a["tentativa_id"] is None
    assert sim_a["completed_at"] is None

    assert sim_b is not None
    assert sim_b["titulo"] == "Simulado Finalizado de Teste"
    assert sim_b["status"] == "finalizado"
    assert sim_b["tentativa_id"] is not None
    assert sim_b["total_acertos"] == 45
    assert sim_b["score_percentual"] == 100.0
    assert sim_b["completed_at"] is not None

    # 4. Consulta resultado do Simulado B via rota /{simulado_id}/resultado
    resp_res_b = client.get(f"/api/v1/simulados/{simulado_b_id}/resultado", headers=auth_headers)
    assert resp_res_b.status_code == 200
    assert resp_res_b.json()["simulado_id"] == simulado_b_id
    assert resp_res_b.json()["total_acertos"] == 45

    # 5. Consulta resultado do Simulado A (deve retornar 404 pois ainda está pendente)
    resp_res_a = client.get(f"/api/v1/simulados/{simulado_a_id}/resultado", headers=auth_headers)
    assert resp_res_a.status_code == 404

