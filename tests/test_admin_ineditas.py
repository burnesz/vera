"""Rotas de administrador do serviço de questões inéditas, com o serviço externo substituído."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401 — registra os modelos
from app.core.security import create_access_token
from app.db.base import Base
from app.db.models.habilidade import HabilidadeEnem
from app.db.models.questao_inedita import QuestaoInedita
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from app.services import questoes_api_client as servico
from scripts.seed_habilidades import HABILIDADES_MAT

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Sessao = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

ID_OK, ID_OK2, ID_REPROVADA = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())


def _questao(qid, hab="H01"):
    return {"id": qid, "habilidade_codigo": hab, "enunciado": "Quanto vale?\n\n| a | b |\n| --- | --- |\n| 1 | 2 |",
            "alternativas": {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"}, "gabarito": "B",
            "justificativa": "Soma direta.", "thought_scratchpad": "def resolver(): ..."}


LOTE = {"id": "lote-1", "status": "concluido", "total": 3, "feitos": 3, "aprovadas": 2, "pedidos": [
    {"n": 1, "habilidade": "H01", "status": "aprovada", "tentativas": 1, "questao": _questao(ID_OK)},
    {"n": 2, "habilidade": "H05", "status": "aprovada", "tentativas": 2, "questao": _questao(ID_OK2, "H05")},
    {"n": 3, "habilidade": "H01", "status": "reprovada", "tentativas": 5, "questao": None},
]}


def _db():
    db = Sessao()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def cabecalhos():
    db = Sessao()
    for h in HABILIDADES_MAT:
        db.add(HabilidadeEnem(codigo=h["codigo"], competencia=h["competencia"], descricao=h["descricao"],
                              eixo_tematico=h["eixo_tematico"]))
    admin = User(nome="Admin", email="admin@t.com", hashed_password="x", role="admin", is_ativo=True)
    aluno = User(nome="Aluno", email="aluno@t.com", hashed_password="x", role="student", is_ativo=True)
    db.add_all([admin, aluno])
    db.commit()
    tok = {u.role: {"Authorization": f"Bearer {create_access_token(subject=str(u.id), role=u.role)}"}
           for u in (admin, aluno)}
    db.close()
    return tok


@pytest.fixture
def cliente(monkeypatch, cabecalhos):
    anterior = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _db
    monkeypatch.setattr(servico, "consultar_lote", lambda lote_id: __import__("copy").deepcopy(LOTE))
    monkeypatch.setattr(servico, "criar_lote", lambda h, q, m: {"id": "lote-1", "total": len(h) * q})
    yield TestClient(app)
    if anterior:
        app.dependency_overrides[get_db] = anterior
    else:
        app.dependency_overrides.pop(get_db, None)


def test_estudante_nao_acessa(cliente, cabecalhos):
    assert cliente.get("/api/v1/admin/ineditas/lotes/lote-1", headers=cabecalhos["student"]).status_code == 403
    assert cliente.post("/api/v1/admin/ineditas/lotes", json={"habilidades": ["H01"]},
                        headers=cabecalhos["student"]).status_code == 403
    assert cliente.get("/api/v1/admin/ineditas/lotes/lote-1").status_code == 401


def test_admin_cria_e_consulta_lote(cliente, cabecalhos):
    r = cliente.post("/api/v1/admin/ineditas/lotes", json={"habilidades": ["H01", "H05"], "quantidade": 2},
                     headers=cabecalhos["admin"])
    assert r.status_code == 202 and r.json()["total"] == 4
    lote = cliente.get("/api/v1/admin/ineditas/lotes/lote-1", headers=cabecalhos["admin"]).json()
    assert lote["aprovadas"] == 2 and lote["pedidos"][0]["questao"]["no_acervo"] is False


def test_importa_aprovadas_sem_duplicar(cliente, cabecalhos):
    url = "/api/v1/admin/ineditas/importar"
    r = cliente.post(url, json={"lote_id": "lote-1", "questao_ids": [ID_OK, ID_OK2]}, headers=cabecalhos["admin"])
    assert r.status_code == 200 and set(r.json()["importadas"]) == {ID_OK, ID_OK2}
    db = Sessao()
    q = db.get(QuestaoInedita, uuid.UUID(ID_OK))
    assert q.is_validated and q.gabarito == "B" and q.alternativas["E"] == "5" and "| a | b |" in q.enunciado
    db.close()
    r2 = cliente.post(url, json={"lote_id": "lote-1", "questao_ids": [ID_OK]}, headers=cabecalhos["admin"])
    assert r2.json() == {"importadas": [], "ja_existiam": [ID_OK]}
    lote = cliente.get("/api/v1/admin/ineditas/lotes/lote-1", headers=cabecalhos["admin"]).json()
    assert lote["pedidos"][0]["questao"]["no_acervo"] is True


def test_recusa_questao_fora_do_lote_ou_reprovada(cliente, cabecalhos):
    r = cliente.post("/api/v1/admin/ineditas/importar", json={"lote_id": "lote-1", "questao_ids": [ID_REPROVADA]},
                     headers=cabecalhos["admin"])
    assert r.status_code == 409


def test_servico_fora_do_ar(cliente, cabecalhos, monkeypatch):
    def fora(*a, **k):
        raise servico.ServicoQuestoesIndisponivel("Serviço de questões indisponível.")
    monkeypatch.setattr(servico, "consultar_lote", fora)
    r = cliente.get("/api/v1/admin/ineditas/lotes/lote-1", headers=cabecalhos["admin"])
    assert r.status_code == 503 and "indisponível" in r.json()["detail"]


def test_erro_do_servico_e_repassado(cliente, cabecalhos, monkeypatch):
    def recusa(*a, **k):
        raise servico.ErroServicoQuestoes(409, "Já há um lote em andamento.")
    monkeypatch.setattr(servico, "criar_lote", recusa)
    r = cliente.post("/api/v1/admin/ineditas/lotes", json={"habilidades": "all"}, headers=cabecalhos["admin"])
    assert r.status_code == 409 and r.json()["detail"] == "Já há um lote em andamento."
