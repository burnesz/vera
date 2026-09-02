from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "api_v1" in data


@patch("app.services.llm_client.httpx.AsyncClient")
def test_health_endpoint_healthy(mock_async_client_cls):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"status": "ok"}'
    mock_resp.json.return_value = {"status": "ok"}
    
    mock_async_client_cls.return_value.__aenter__.return_value = mock_client
    mock_client.get.return_value = mock_resp

    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "api" in data
    assert "llm_remote" in data
