import pytest
import uuid
from datetime import timedelta
from fastapi import status, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.db.models.user import User
from app.main import app
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token
)
from app.api.deps import require_admin


# Configuração de banco de dados em memória isolado para os testes de API
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


def test_password_hashing_and_verification():
    """Valida o funcionamento das funções de hash bcrypt."""
    password = "SenhaForteENEM2026!"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("SenhaErrada!", hashed) is False


def test_jwt_token_generation_and_decoding():
    """Valida emissão e decodificação do JWT."""
    user_id = str(uuid.uuid4())
    token = create_access_token(subject=user_id, role="student", expires_delta=timedelta(minutes=15))

    payload = decode_access_token(token)
    assert payload["sub"] == user_id
    assert payload["role"] == "student"
    assert "exp" in payload
    assert payload["type"] == "access"


def test_register_user_success():
    """Testa o endpoint de registro de novos estudantes."""
    email = f"aluno_{uuid.uuid4().hex[:6]}@enem.com"
    payload = {
        "nome": "Rubens Pereira",
        "email": email,
        "password": "senhaSegura123",
        "role": "student"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == email
    assert data["nome"] == "Rubens Pereira"
    assert data["role"] == "student"
    assert data["is_ativo"] is True
    assert "password" not in data
    assert "hashed_password" not in data


def test_register_duplicate_email():
    """Testa a rejeição ao registrar usuário com email existente."""
    email = "duplicado@enem.com"
    payload = {
        "nome": "Usuário Um",
        "email": email,
        "password": "senhaSegura123",
        "role": "student"
    }
    r1 = client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == status.HTTP_201_CREATED

    # Segunda tentativa com o mesmo email
    r2 = client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == status.HTTP_400_BAD_REQUEST
    assert "Já existe um usuário" in r2.json()["detail"]


def test_login_oauth2_form_success_and_failure():
    """Testa o endpoint de login compatível com OAuth2PasswordRequestForm (Swagger)."""
    email = f"oauth_user_{uuid.uuid4().hex[:6]}@enem.com"
    password = "minhaSenha123"
    client.post("/api/v1/auth/register", json={
        "nome": "Aluno OAuth",
        "email": email,
        "password": password,
        "role": "student"
    })

    # 1. Login com sucesso
    response = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert response.status_code == status.HTTP_200_OK
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

    # 2. Login com senha errada
    resp_err = client.post("/api/v1/auth/login", data={"username": email, "password": "senhaIncorreta"})
    assert resp_err.status_code == status.HTTP_401_UNAUTHORIZED
    assert "E-mail ou senha incorretos" in resp_err.json()["detail"]


def test_login_json_success_and_failure():
    """Testa o endpoint de login via JSON (para consumo web)."""
    email = f"json_user_{uuid.uuid4().hex[:6]}@enem.com"
    password = "minhaSenha456"
    client.post("/api/v1/auth/register", json={
        "nome": "Aluno JSON",
        "email": email,
        "password": password,
        "role": "student"
    })

    # 1. Login com sucesso
    response = client.post("/api/v1/auth/login/json", json={"email": email, "password": password})
    assert response.status_code == status.HTTP_200_OK
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

    # 2. Login com senha errada
    resp_err = client.post("/api/v1/auth/login/json", json={"email": email, "password": "senhaIncorreta"})
    assert resp_err.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_me():
    """Testa acesso à rota protegida /auth/me."""
    email = f"me_user_{uuid.uuid4().hex[:6]}@enem.com"
    password = "senhaValida789"
    client.post("/api/v1/auth/register", json={
        "nome": "Aluno Perfil",
        "email": email,
        "password": password,
        "role": "student"
    })

    login_resp = client.post("/api/v1/auth/login/json", json={"email": email, "password": password})
    token = login_resp.json()["access_token"]

    # 1. Requisição com token válido
    headers = {"Authorization": f"Bearer {token}"}
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == status.HTTP_200_OK
    user_data = me_resp.json()
    assert user_data["email"] == email
    assert user_data["nome"] == "Aluno Perfil"

    # 2. Requisição sem token (401)
    unauth_resp = client.get("/api/v1/auth/me")
    assert unauth_resp.status_code == status.HTTP_401_UNAUTHORIZED

    # 3. Requisição com token corrompido (401)
    bad_token_resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer token_invalido_123"})
    assert bad_token_resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_require_admin_role_check():
    """Testa a dependência require_admin."""
    student_user = User(nome="Aluno", email="a@t.com", hashed_password="x", role="student", is_ativo=True)
    admin_user = User(nome="Admin", email="b@t.com", hashed_password="x", role="admin", is_ativo=True)

    # Admin deve passar com sucesso
    assert require_admin(admin_user).role == "admin"

    # Student deve levantar HTTP 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        require_admin(student_user)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
