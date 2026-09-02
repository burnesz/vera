import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService, ChatSessionManager
from app.services.llm_client import LLMClient


client = TestClient(app)


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
    mock_llm.generate.return_value = "O Teorema de Pitágoras é fundamental para calcular a hipotenusa: a² + b² = c²."

    service = ChatService(llm_client=mock_llm, vector_store=mock_vectorstore, manager=manager)

    # Turno 1
    req1 = ChatRequest(message="Como calcular a hipotenusa de um triângulo?")
    resp1 = service.send_message(req1)

    assert resp1.session_id is not None
    assert len(resp1.context_chunks) == 1
    assert "hipotenusa" in resp1.reply

    # Verifica se histórico gravou o turno 1
    history = manager.get_history(resp1.session_id)
    assert len(history) == 2
    assert history[0].role == "user"
    assert history[1].role == "assistant"

    # Turno 2 (mesma sessão)
    mock_llm.generate.return_value = "Se os catetos são 3 e 4, temos c² = 9 + 16 = 25, logo c = 5."
    req2 = ChatRequest(message="E se os catetos medirem 3 e 4?", session_id=resp1.session_id)
    resp2 = service.send_message(req2)

    assert resp2.session_id == resp1.session_id
    history_after_t2 = manager.get_history(resp1.session_id)
    assert len(history_after_t2) == 4


@patch("app.services.chat_service.PineconeVectorStore")
@patch("app.services.chat_service.LLMClient")
def test_chat_api_endpoints(mock_llm_cls, mock_vs_cls):
    mock_llm = MagicMock()
    mock_llm.agenerate = AsyncMock(return_value="Olá! Eu sou a VERA, sua tutora de Matemática. Como posso te ajudar hoje?")
    mock_llm_cls.return_value = mock_llm

    mock_vs = MagicMock()
    mock_vs.search.return_value = []
    mock_vs_cls.return_value = mock_vs

    # 1. Envio de mensagem
    response = client.post(
        "/api/v1/chat",
        json={"message": "Olá VERA, pode me ajudar com trigonometria?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "session_id" in data
    session_id = data["session_id"]

    # 2. Consulta de histórico
    hist_resp = client.get(f"/api/v1/chat/history/{session_id}")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert hist_data["session_id"] == session_id
    assert hist_data["total_messages"] >= 2

    # 3. Limpeza de sessão
    del_resp = client.delete(f"/api/v1/chat/session/{session_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["cleared"] is True
