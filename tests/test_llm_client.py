import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx

from app.services.llm_client import (
    LLMClient,
    LLMConnectionError,
    LLMTimeoutError,
    LLMResponseError
)


def test_llm_client_mock_mode():
    client = LLMClient(mock_mode=True)
    health = client.health_check()
    assert health["healthy"] is True
    assert health["status"] == "mock"

    response = client.generate(prompt="Qual é o ciclo trigonométrico?")
    assert "Diagnóstico" in response or "Identificação" in response
    assert len(response) > 50


def test_llm_client_headers():
    client = LLMClient(endpoint_url="http://localhost:11434")
    headers = client.headers
    assert headers["Content-Type"] == "application/json"


@patch("httpx.Client")
def test_llm_client_health_check_success(mock_client_cls):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"models": [{"name": "qwen2.5:7b-instruct-q4_K_M"}]}'
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {
        "models": [{"name": "qwen2.5:7b-instruct-q4_K_M"}]
    }
    mock_client.get.return_value = mock_resp
    mock_client_cls.return_value.__enter__.return_value = mock_client

    client = LLMClient(
        endpoint_url="http://localhost:11434",
        model_name="qwen2.5:7b-instruct-q4_K_M"
    )
    result = client.health_check()

    assert result["healthy"] is True
    assert result["status"] == "healthy"
    assert result["provider"] == "ollama"
    assert result["model"] == "qwen2.5:7b-instruct-q4_K_M"
    assert result["model_available"] is True
    mock_client.get.assert_called_once_with(
        "http://localhost:11434/api/tags",
        headers=client.headers
    )


@patch("httpx.Client")
def test_llm_client_health_check_model_missing(mock_client_cls):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"models": [{"name": "llama3:latest"}]}'
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {
        "models": [{"name": "llama3:latest"}]
    }
    mock_client.get.return_value = mock_resp
    mock_client_cls.return_value.__enter__.return_value = mock_client

    client = LLMClient(
        endpoint_url="http://localhost:11434",
        model_name="qwen2.5:7b-instruct-q4_K_M"
    )
    result = client.health_check()

    assert result["healthy"] is True
    assert result["model_available"] is False


@patch("httpx.Client")
def test_llm_client_health_check_server_error(mock_client_cls):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_client.get.return_value = mock_resp
    mock_client_cls.return_value.__enter__.return_value = mock_client

    client = LLMClient(endpoint_url="http://localhost:11434")
    result = client.health_check()

    assert result["healthy"] is False
    assert result["status"] == "unhealthy"


@patch("httpx.Client")
def test_llm_client_generate_success(mock_client_cls):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "qwen2.5:7b-instruct-q4_K_M",
        "response": "Feedback pedagógico sobre o erro da questão.",
        "done": True
    }
    mock_client.post.return_value = mock_resp
    mock_client_cls.return_value.__enter__.return_value = mock_client

    client = LLMClient(
        endpoint_url="http://localhost:11434",
        model_name="qwen2.5:7b-instruct-q4_K_M"
    )
    result = client.generate(prompt="Teste de prompt")

    assert result == "Feedback pedagógico sobre o erro da questão."
    mock_client.post.assert_called_once()
    args, kwargs = mock_client.post.call_args
    assert args[0] == "http://localhost:11434/api/generate"
    payload = kwargs["json"]
    assert payload["model"] == "qwen2.5:7b-instruct-q4_K_M"
    assert payload["prompt"] == "Teste de prompt"
    assert payload["stream"] is False
    assert "options" in payload
    assert payload["options"]["num_predict"] == 1024


@patch("httpx.Client")
@patch("time.sleep")
def test_llm_client_retry_on_server_error(mock_sleep, mock_client_cls):
    mock_client = MagicMock()
    
    # 1ª tentativa: 502, 2ª tentativa: 200 sucesso
    mock_resp_502 = MagicMock()
    mock_resp_502.status_code = 502
    
    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {
        "model": "qwen2.5:7b-instruct-q4_K_M",
        "response": "Recuperado após retry!",
        "done": True
    }

    mock_client.post.side_effect = [mock_resp_502, mock_resp_200]
    mock_client_cls.return_value.__enter__.return_value = mock_client

    client = LLMClient(
        endpoint_url="http://localhost:11434",
        max_retries=2
    )
    result = client.generate(prompt="Teste retry")

    assert result == "Recuperado após retry!"
    assert mock_client.post.call_count == 2
    mock_sleep.assert_called_once()


@pytest.mark.anyio
@patch("httpx.AsyncClient")
async def test_llm_client_agenerate_success(mock_async_client_cls):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "qwen2.5:7b-instruct-q4_K_M",
        "response": "Resposta assíncrona do Ollama.",
        "done": True
    }
    mock_async_client_cls.return_value.__aenter__.return_value = mock_client
    mock_client.post = AsyncMock(return_value=mock_resp)

    client = LLMClient(
        endpoint_url="http://localhost:11434",
        model_name="qwen2.5:7b-instruct-q4_K_M"
    )
    result = await client.agenerate(prompt="Pergunta assíncrona")

    assert result == "Resposta assíncrona do Ollama."
    mock_client.post.assert_called_once()
    args, kwargs = mock_client.post.call_args
    assert args[0] == "http://localhost:11434/api/generate"
    assert kwargs["json"]["model"] == "qwen2.5:7b-instruct-q4_K_M"


@pytest.mark.anyio
@patch("httpx.AsyncClient")
async def test_llm_client_ahealth_check_success(mock_async_client_cls):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"models": [{"name": "qwen2.5:7b-instruct-q4_K_M"}]}'
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {
        "models": [{"name": "qwen2.5:7b-instruct-q4_K_M"}]
    }
    mock_async_client_cls.return_value.__aenter__.return_value = mock_client
    mock_client.get = AsyncMock(return_value=mock_resp)

    client = LLMClient(
        endpoint_url="http://localhost:11434",
        model_name="qwen2.5:7b-instruct-q4_K_M"
    )
    result = await client.ahealth_check()

    assert result["healthy"] is True
    assert result["status"] == "healthy"
    assert result["model_available"] is True
    mock_client.get.assert_called_once_with(
        "http://localhost:11434/api/tags",
        headers=client.headers
    )


def test_lista_de_mensagens_vira_system_e_prompt_no_api_generate():
    """O /api/generate do Ollama só aceita texto em 'prompt' (uma lista dava HTTP 400 no feedback)."""
    from app.services.llm_client import LLMClient

    _, payload = LLMClient(model_name="m")._build_payload_and_url(
        prompt=[{"role": "system", "content": "Você é VERA."}, {"role": "user", "content": "Explique o erro."}]
    )
    assert payload["system"] == "Você é VERA."
    assert payload["prompt"] == "Explique o erro."
    assert "think" not in payload


def test_think_vai_no_payload_quando_definido():
    from app.services.llm_client import LLMClient

    _, payload = LLMClient(model_name="qwen3:8b-q4_K_M", think=False)._build_payload_and_url(prompt="oi")
    assert payload["think"] is False and payload["prompt"] == "oi" and "system" not in payload


def test_feedback_tutora_e_baseline_usam_o_modelo_da_tutoria():
    """RN-INF07: feedback, tutora e baseline usam LLM_MODEL_TUTORIA com LLM_THINK_TUTORIA."""
    from unittest.mock import MagicMock
    from app.core.config import settings
    from app.services.baseline_service import BaselineService
    from app.services.chat_service import ChatService
    from app.services.feedback_service import FeedbackService

    for servico in (FeedbackService(vector_store=MagicMock()), ChatService(vector_store=MagicMock()), BaselineService()):
        assert servico.llm_client.model_name == settings.LLM_MODEL_TUTORIA
        assert servico.llm_client.think == settings.LLM_THINK_TUTORIA
