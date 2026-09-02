import pytest
from unittest.mock import patch, MagicMock
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
    client = LLMClient(
        endpoint_url="https://test-tunnel.ngrok-free.dev",
        api_key="secret-key-123"
    )
    headers = client.headers
    assert headers["X-API-Key"] == "secret-key-123"
    assert headers["Content-Type"] == "application/json"
    assert headers["ngrok-skip-browser-warning"] == "1"


@patch("httpx.Client")
def test_llm_client_health_check_success(mock_client_cls):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"status": "ok"}'
    mock_resp.json.return_value = {"status": "ok"}
    mock_client.get.return_value = mock_resp
    mock_client_cls.return_value.__enter__.return_value = mock_client

    client = LLMClient(endpoint_url="https://test-tunnel.ngrok-free.dev", api_key="secret")
    result = client.health_check()

    assert result["healthy"] is True
    assert result["status"] == "healthy"
    mock_client.get.assert_called_once_with(
        "https://test-tunnel.ngrok-free.dev/health",
        headers=client.headers
    )


@patch("httpx.Client")
def test_llm_client_generate_success(mock_client_cls):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "response": "Feedback detalhado sobre o erro da questão.",
        "session_id": "default"
    }
    mock_client.post.return_value = mock_resp
    mock_client_cls.return_value.__enter__.return_value = mock_client

    client = LLMClient(endpoint_url="https://test-tunnel.ngrok-free.dev", api_key="secret")
    result = client.generate(prompt="Teste de prompt")

    assert result == "Feedback detalhado sobre o erro da questão."
    mock_client.post.assert_called_once()


@patch("httpx.Client")
@patch("time.sleep")
def test_llm_client_retry_on_server_error(mock_sleep, mock_client_cls):
    mock_client = MagicMock()
    
    # 1ª tentativa: 502, 2ª tentativa: 200 sucesso
    mock_resp_502 = MagicMock()
    mock_resp_502.status_code = 502
    
    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {"response": "Recuperado após retry!"}

    mock_client.post.side_effect = [mock_resp_502, mock_resp_200]
    mock_client_cls.return_value.__enter__.return_value = mock_client

    client = LLMClient(
        endpoint_url="https://test-tunnel.ngrok-free.dev",
        api_key="secret",
        max_retries=2
    )
    result = client.generate(prompt="Teste retry")

    assert result == "Recuperado após retry!"
    assert mock_client.post.call_count == 2
    mock_sleep.assert_called_once()
