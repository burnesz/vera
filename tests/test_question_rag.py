import pytest
import uuid
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.habilidade import HabilidadeEnem
from app.db.models.questao_enem import QuestaoEnem
from app.services.question_service import QuestionService

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    db = TestingSessionLocal()
    try:
        hab = HabilidadeEnem(
            codigo="H01",
            competencia=1,
            descricao="Reconhecer, no contexto social, diferentes significados dos números.",
            eixo_tematico="Números e Operações"
        )
        db.merge(hab)

        q1 = QuestaoEnem(
            id=uuid.uuid4(),
            ano=2021,
            habilidade_codigo="H01",
            enunciado="Enunciado da questão histórica 1...",
            alternativas={"A": "10", "B": "20", "C": "30", "D": "40", "E": "50"},
            gabarito="B"
        )
        db.merge(q1)
        db.commit()
    finally:
        db.close()


def test_habilidades_queries_loaded():
    """Valida se o catálogo de 30 habilidades com as queries do Claude é carregado corretamente."""
    service = QuestionService(queries_path="data/habilidades_queries.json")
    mapping = service._habilidades_queries
    
    assert len(mapping) >= 30
    assert "H01" in mapping
    assert "H30" in mapping
    assert "query" in mapping["H01"]
    assert len(mapping["H01"]["query"]) > 20


def test_retrieve_rag_few_shot_pinecone_success():
    """Valida resgate semântico de exemplos RAG no namespace 'questoes_enem' do Pinecone."""
    mock_vector_store = MagicMock()
    mock_vector_store.search.return_value = [
        {
            "id": "enem_2023_101",
            "score": 0.88,
            "text": "Enunciado questão 1",
            "metadata": {
                "ano": 2023,
                "co_item": 101,
                "habilidade_codigo": "H01",
                "gabarito": "A",
                "alt_a": "Opção A",
                "alt_b": "Opção B",
                "alt_c": "Opção C",
                "alt_d": "Opção D",
                "alt_e": "Opção E",
                "text": "Enunciado questão 1"
            }
        },
        {
            "id": "enem_2022_102",
            "score": 0.84,
            "text": "Enunciado questão 2",
            "metadata": {
                "ano": 2022,
                "co_item": 102,
                "habilidade_codigo": "H01",
                "gabarito": "C",
                "alt_a": "Opção 1",
                "alt_b": "Opção 2",
                "alt_c": "Opção 3",
                "alt_d": "Opção 4",
                "alt_e": "Opção 5",
                "text": "Enunciado questão 2"
            }
        },
        {
            "id": "enem_2021_103",
            "score": 0.81,
            "text": "Enunciado questão 3",
            "metadata": {
                "ano": 2021,
                "co_item": 103,
                "habilidade_codigo": "H02",
                "gabarito": "E",
                "alt_a": "Alt 1",
                "alt_b": "Alt 2",
                "alt_c": "Alt 3",
                "alt_d": "Alt 4",
                "alt_e": "Alt 5",
                "text": "Enunciado questão 3"
            }
        }
    ]

    service = QuestionService(vector_store=mock_vector_store)
    examples = service.retrieve_rag_few_shot_examples(habilidade_codigo="H01", k=3)

    assert len(examples) == 3
    assert examples[0]["ano"] == 2023
    assert examples[0]["gabarito"] == "A"
    assert examples[0]["alternativas"]["A"] == "Opção A"
    assert examples[0]["score"] == 0.88
    mock_vector_store.search.assert_called_once()


def test_retrieve_rag_few_shot_fallback():
    """Valida o mecanismo de fallback determinístico no banco relacional caso o Pinecone falhe."""
    mock_vector_store = MagicMock()
    mock_vector_store.search.side_effect = Exception("Conexão Pinecone timeout")

    service = QuestionService(vector_store=mock_vector_store)
    db = TestingSessionLocal()
    try:
        examples = service.retrieve_rag_few_shot_examples(habilidade_codigo="H01", k=2, db=db)
        assert len(examples) == 1
        assert examples[0]["gabarito"] == "B"
        assert examples[0]["score"] == 1.0
    finally:
        db.close()
