import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.prompts import parse_cot_response
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService, ChatSessionManager
from app.services.llm_client import LLMClient


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
