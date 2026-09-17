import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.prompts import parse_cot_response
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService, ChatSessionManager
from app.services.llm_client import LLMClient


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.base import Base
from app.db.session import get_db

chat_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
ChatTestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=chat_test_engine)
Base.metadata.create_all(bind=chat_test_engine)


def override_chat_get_db():
    db = ChatTestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_chat_db_override():
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_chat_get_db
    yield
    if previous:
        app.dependency_overrides[get_db] = previous
    else:
        app.dependency_overrides.pop(get_db, None)


client = TestClient(app)



def test_parse_cot_response_with_tags():
    raw = """
<pensamento>
1. Entendimento: O estudante quer calcular a área de um círculo com raio r=4.
2. Cálculos: A = pi * r^2 = 16*pi.
3. Validação: Fórmula correta, sem pegadinhas.
4. Didática: Conectar com o formato de pizza.
</pensamento>
<resposta>
Para calcular a área do círculo, usamos a fórmula $A = \\pi r^2$. Com raio 4, temos $A = 16\\pi$.
</resposta>
"""
    thought, reply = parse_cot_response(raw)
    assert thought is not None
    assert "O estudante quer calcular a área" in thought
    assert "Validação: Fórmula correta" in thought
    assert "Para calcular a área do círculo" in reply
    assert "<resposta>" not in reply
    assert "<pensamento>" not in reply


def test_parse_cot_response_without_tags():
    raw = "Olá, a resposta direta é 42."
    thought, reply = parse_cot_response(raw)
    assert thought is None
    assert reply == "Olá, a resposta direta é 42."


def test_parse_cot_response_partial_tags():
    raw = "<pensamento>Calculando x + 2 = 5 -> x = 3</pensamento>\nO valor de x é 3."
    thought, reply = parse_cot_response(raw)
    assert thought == "Calculando x + 2 = 5 -> x = 3"
    assert reply == "O valor de x é 3."


def test_chat_session_manager():
    manager = ChatSessionManager(max_history_turns=4)
    session_id = manager.get_or_create_session()
    assert session_id.startswith("sess_")

    # Adiciona 5 mensagens para testar janela deslizante de 4
    for i in range(5):
        manager.add_message(session_id, role="user" if i % 2 == 0 else "assistant", content=f"Msg {i}")

    history = manager.get_history(session_id)
    assert len(history) == 4
    assert history[0].content == "Msg 1"
    assert history[-1].content == "Msg 4"

    cleared = manager.clear_session(session_id)
    assert cleared is True
    assert len(manager.get_history(session_id)) == 0


def test_chat_service_multiturn_flow():
    manager = ChatSessionManager()
    mock_vectorstore = MagicMock()
    mock_vectorstore.search.return_value = [
        {
            "id": "chunk_pitagoras_1",
            "text": "O teorema de Pitágoras estabelece que a² + b² = c² em qualquer triângulo retângulo.",
            "score": 0.92,
            "metadata": {"title": "Geometria Plana", "topic": "Triângulos"}
        }
    ]

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.generate.return_value = (
        "<pensamento>Identificado triângulo retângulo. Validando hipotenusa.</pensamento>\n"
        "<resposta>O Teorema de Pitágoras é fundamental para calcular a hipotenusa: a² + b² = c².</resposta>"
    )

    service = ChatService(llm_client=mock_llm, vector_store=mock_vectorstore, manager=manager)

    # Turno 1
    req1 = ChatRequest(message="Como calcular a hipotenusa de um triângulo?")
    resp1 = service.send_message(req1)

    assert resp1.session_id is not None
    assert len(resp1.context_chunks) == 1
    assert "hipotenusa" in resp1.reply
    assert resp1.thought is not None
    assert "Validando hipotenusa" in resp1.thought

    # Verifica se histórico gravou a resposta limpa (sem tags) no turno 1
    history = manager.get_history(resp1.session_id)
    assert len(history) == 2
    assert history[0].role == "user"
    assert history[1].role == "assistant"
    assert "<pensamento>" not in history[1].content
    assert history[1].thought is not None

    # Turno 2 (mesma sessão)
    mock_llm.generate.return_value = (
        "<pensamento>Catetos 3 e 4. 3² + 4² = 9 + 16 = 25. Raiz é 5.</pensamento>\n"
        "<resposta>Se os catetos são 3 e 4, temos c² = 9 + 16 = 25, logo c = 5.</resposta>"
    )
    req2 = ChatRequest(message="E se os catetos medirem 3 e 4?", session_id=resp1.session_id)
    resp2 = service.send_message(req2)

    assert resp2.session_id == resp1.session_id
    assert resp2.thought is not None
    assert "Catetos 3 e 4" in resp2.thought
    history_after_t2 = manager.get_history(resp1.session_id)
    assert len(history_after_t2) == 4


import uuid
from app.api.deps import get_current_active_user
from app.db.models.user import User


def test_chat_endpoints_require_authentication():
    """Garante que as rotas de chat rejeitam requisições sem token JWT com HTTP 401."""
    # 1. Envio de mensagem sem auth
    r_post = client.post("/api/v1/chat", json={"message": "Pergunta sem autenticação"})
    assert r_post.status_code == 401

    # 2. Histórico sem auth
    r_get = client.get("/api/v1/chat/history/qualquer_sessao")
    assert r_get.status_code == 401

    # 3. Limpeza de sessão sem auth
    r_del = client.delete("/api/v1/chat/session/qualquer_sessao")
    assert r_del.status_code == 401


@patch("app.services.chat_service.PineconeVectorStore")
@patch("app.services.chat_service.LLMClient")
def test_chat_api_endpoints(mock_llm_cls, mock_vs_cls):
    mock_llm = MagicMock()
    mock_llm.agenerate = AsyncMock(
        return_value="<pensamento>Saudação inicial ao estudante.</pensamento>\n<resposta>Olá! Eu sou a VERA, sua tutora de Matemática. Como posso te ajudar hoje?</resposta>"
    )
    mock_llm_cls.return_value = mock_llm

    mock_vs = MagicMock()
    mock_vs.search.return_value = []
    mock_vs_cls.return_value = mock_vs

    mock_user = User(
        id=uuid.uuid4(),
        nome="Estudante Teste",
        email="estudante_chat@enem.com",
        hashed_password="hashed_pw",
        role="student",
        is_ativo=True
    )
    app.dependency_overrides[get_current_active_user] = lambda: mock_user

    try:
        # 1. Envio de mensagem autenticada
        response = client.post(
            "/api/v1/chat",
            json={"message": "Olá VERA, pode me ajudar com trigonometria?"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert "thought" in data
        assert data["thought"] == "Saudação inicial ao estudante."
        assert "Olá! Eu sou a VERA" in data["reply"]
        assert "session_id" in data
        session_id = data["session_id"]

        # 2. Consulta de histórico autenticada
        hist_resp = client.get(f"/api/v1/chat/history/{session_id}")
        assert hist_resp.status_code == 200
        hist_data = hist_resp.json()
        assert hist_data["session_id"] == session_id
        assert hist_data["total_messages"] >= 2
        assert hist_data["messages"][-1]["thought"] == "Saudação inicial ao estudante."

        # 3. Limpeza de sessão autenticada
        del_resp = client.delete(f"/api/v1/chat/session/{session_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["cleared"] is True
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)


@patch("app.services.chat_service.PineconeVectorStore")
@patch("app.services.chat_service.LLMClient")
def test_chat_sessions_listing_and_rename(mock_llm_cls, mock_vs_cls):
    """Testa a listagem de sessões, persistência com usuário no banco e renomeação."""
    mock_llm = MagicMock()
    mock_llm.agenerate = AsyncMock(
        return_value="<pensamento>Explicando Pitágoras.</pensamento>\n<resposta>O Teorema de Pitágoras é a² + b² = c².</resposta>"
    )
    mock_llm_cls.return_value = mock_llm

    mock_vs = MagicMock()
    mock_vs.search.return_value = []
    mock_vs_cls.return_value = mock_vs

    db = ChatTestingSessionLocal()
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        nome="Estudante Persistente",
        email=f"persistente_{user_id.hex[:6]}@enem.com",
        hashed_password="pw",
        role="student",
        is_ativo=True
    )
    db.add(user)
    db.commit()

    app.dependency_overrides[get_current_active_user] = lambda: user

    try:
        # Envia primeira mensagem
        r1 = client.post(
            "/api/v1/chat",
            json={"message": "Como aplicar Pitágoras em triângulos?"}
        )
        assert r1.status_code == 200
        s_id = r1.json()["session_id"]

        # Lista sessões do usuário
        r_list = client.get("/api/v1/chat/sessions")
        assert r_list.status_code == 200
        data_list = r_list.json()
        assert data_list["total"] >= 1
        found = [s for s in data_list["sessions"] if s["id"] == s_id]
        assert len(found) == 1
        assert "Pitágoras" in found[0]["titulo"]
        assert found[0]["total_messages"] == 2

        # Renomeia sessão
        r_rename = client.patch(
            f"/api/v1/chat/session/{s_id}",
            json={"titulo": "Estudo de Geometria: Pitágoras"}
        )
        assert r_rename.status_code == 200
        assert r_rename.json()["titulo"] == "Estudo de Geometria: Pitágoras"

        # Consulta histórico com novo título
        r_hist = client.get(f"/api/v1/chat/history/{s_id}")
        assert r_hist.status_code == 200
        assert r_hist.json()["titulo"] == "Estudo de Geometria: Pitágoras"

        # Exclui a sessão
        r_del = client.delete(f"/api/v1/chat/session/{s_id}")
        assert r_del.status_code == 200

        # Confirma que sessão não aparece mais na listagem
        r_list_after = client.get("/api/v1/chat/sessions")
        assert not any(s["id"] == s_id for s in r_list_after.json()["sessions"])
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)
        db.delete(user)
        db.commit()
        db.close()


@patch("app.services.chat_service.PineconeVectorStore")
@patch("app.services.chat_service.LLMClient")
def test_chat_user_isolation(mock_llm_cls, mock_vs_cls):
    """Garante isolamento estrito entre usuários: Estudante A não acessa conversas de Estudante B."""
    mock_llm = MagicMock()
    mock_llm.agenerate = AsyncMock(return_value="<pensamento>Segredo.</pensamento>\n<resposta>Resposta privada.</resposta>")
    mock_llm_cls.return_value = mock_llm

    mock_vs = MagicMock()
    mock_vs.search.return_value = []
    mock_vs_cls.return_value = mock_vs

    db = ChatTestingSessionLocal()

    u1 = User(id=uuid.uuid4(), nome="Aluno A", email=f"aluno_a_{uuid.uuid4().hex[:6]}@enem.com", hashed_password="pw", role="student", is_ativo=True)
    u2 = User(id=uuid.uuid4(), nome="Aluno B", email=f"aluno_b_{uuid.uuid4().hex[:6]}@enem.com", hashed_password="pw", role="student", is_ativo=True)
    db.add_all([u1, u2])
    db.commit()

    try:
        # Aluno A cria sessão
        app.dependency_overrides[get_current_active_user] = lambda: u1
        r_a = client.post("/api/v1/chat", json={"message": "Pergunta do Aluno A"})
        assert r_a.status_code == 200
        sess_a_id = r_a.json()["session_id"]

        # Aluno B lista sessões -> Não deve conter sess_a_id
        app.dependency_overrides[get_current_active_user] = lambda: u2
        r_b_list = client.get("/api/v1/chat/sessions")
        assert r_b_list.status_code == 200
        assert not any(s["id"] == sess_a_id for s in r_b_list.json()["sessions"])

        # Aluno B tenta acessar histórico da sessão do Aluno A -> deve retornar vazio
        r_b_hist = client.get(f"/api/v1/chat/history/{sess_a_id}")
        assert r_b_hist.status_code == 200
        assert r_b_hist.json()["total_messages"] == 0

        # Aluno B tenta renomear sessão do Aluno A -> 404
        r_b_ren = client.patch(f"/api/v1/chat/session/{sess_a_id}", json={"titulo": "Hackeado"})
        assert r_b_ren.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)
        db.delete(u1)
        db.delete(u2)
        db.commit()
        db.close()


