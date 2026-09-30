import pytest
import uuid
import json
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models
from app.db.base import Base
from app.db.models.habilidade import HabilidadeEnem
from app.db.models.questao_enem import QuestaoEnem
from app.db.models.questao_inedita import QuestaoInedita
from app.services.llm_client import LLMClient
from app.services.vectorstore import PineconeVectorStore
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
            descricao="Reconhecer, no contexto social, diferentes significados e representações dos números e operações.",
            eixo_tematico="Números e Operações"
        )
        db.merge(hab)

        q1 = QuestaoEnem(
            id=uuid.uuid4(),
            ano=2021,
            habilidade_codigo="H01",
            enunciado="Enunciado da questão histórica 1 sobre leitura de medidores...",
            alternativas={"A": "10", "B": "20", "C": "30", "D": "40", "E": "50"},
            gabarito="B"
        )
        q2 = QuestaoEnem(
            id=uuid.uuid4(),
            ano=2022,
            habilidade_codigo="H01",
            enunciado="Enunciado da questão histórica 2 sobre operações básicas...",
            alternativas={"A": "100", "B": "200", "C": "300", "D": "400", "E": "500"},
            gabarito="D"
        )
        db.add(q1)
        db.add(q2)
        db.commit()
    finally:
        db.close()


def test_retrieve_few_shot_examples():
    db = TestingSessionLocal()
    try:
        mock_vs = MagicMock(spec=PineconeVectorStore)
        service = QuestionService(vector_store=mock_vs)
        exemplos = service.retrieve_few_shot_examples(db, "H01", k=2)
        assert len(exemplos) == 2
        for ex in exemplos:
            assert ex.habilidade_codigo == "H01"
            assert ex.gabarito in ["A", "B", "C", "D", "E"]
    finally:
        db.close()


def test_generate_single_questao_inedita_pot_success():
    """Valida o pipeline PoT completo de duas fases (Solver + Justificativa)."""
    db = TestingSessionLocal()
    try:
        mock_llm = MagicMock(spec=LLMClient)
        mock_vs = MagicMock(spec=PineconeVectorStore)
        mock_vs.search.return_value = []

        # Fase 1: Enunciado e Solver
        resp_fase1 = json.dumps({
            "enunciado": "Um reservatório com capacidade de 1.200 litros é abastecido a 40 litros por minuto com saída simultânea de 10 litros por minuto. Qual o tempo em minutos para enchê-lo?",
            "solver": "def resolver():\n    capacidade = 1200\n    entrada = 40\n    saida = 10\n    taxa = entrada - saida\n    tempo = capacidade / taxa\n    return {'correta': tempo, 'distratores': [30, 50, 60, 80]}"
        })

        # Fase 2: Justificativa
        resp_fase2 = json.dumps({
            "justificativa": "A taxa líquida é 40 - 10 = 30 L/min. Dividindo 1200 por 30, obtemos 40 minutos."
        })

        mock_llm.generate.side_effect = [resp_fase1, resp_fase2]

        service = QuestionService(llm_client=mock_llm, vector_store=mock_vs)
        questao = service.generate_single_questao_inedita(
            db=db,
            habilidade_codigo="H01",
            num_few_shot=2,
            max_attempts=2,
            use_pot=True
        )

        assert questao is not None
        assert questao.habilidade_codigo == "H01"
        assert questao.is_validated is True
        assert len(questao.alternativas) == 5
        # O gabarito matemático comprovado é 40
        assert questao.alternativas[questao.gabarito] == "40"
        assert "def resolver" in questao.thought_scratchpad
        assert "taxa líquida" in questao.justificativa
        assert mock_llm.generate.call_count == 2
    finally:
        db.close()


def test_generate_single_questao_inedita_pot_retry_on_solver_error():
    """Valida se o pipeline PoT captura o erro de execução do solver e re-tenta com feedback."""
    db = TestingSessionLocal()
    try:
        mock_llm = MagicMock(spec=LLMClient)
        mock_vs = MagicMock(spec=PineconeVectorStore)
        mock_vs.search.return_value = []

        # 1ª tentativa Fase 1: Solver com divisão por zero
        resp_fase1_erro = json.dumps({
            "enunciado": "Um motorista calcula a velocidade em uma viagem de 100 km com tempo 0 horas.",
            "solver": "def resolver():\n    dist = 100\n    t = 0\n    v = dist / t\n    return {'correta': v, 'distratores': [10, 20, 30, 40]}"
        })

        # 2ª tentativa Fase 1: Solver corrigido
        resp_fase1_ok = json.dumps({
            "enunciado": "Um motorista calcula a velocidade em uma viagem de 100 km com tempo de 2 horas. Qual a velocidade média em km/h?",
            "solver": "def resolver():\n    dist = 100\n    t = 2\n    v = dist / t\n    return {'correta': v, 'distratores': [30, 40, 60, 70]}"
        })

        # Fase 2 da 2ª tentativa: Justificativa
        resp_fase2 = json.dumps({
            "justificativa": "A velocidade média é 100 / 2 = 50 km/h."
        })

        mock_llm.generate.side_effect = [resp_fase1_erro, resp_fase1_ok, resp_fase2]

        service = QuestionService(llm_client=mock_llm, vector_store=mock_vs)
        questao = service.generate_single_questao_inedita(
            db=db,
            habilidade_codigo="H01",
            max_attempts=3,
            use_pot=True
        )

        assert questao is not None
        assert questao.alternativas[questao.gabarito] == "50"
        assert mock_llm.generate.call_count == 3
    finally:
        db.close()


def test_generate_single_questao_inedita_traditional_fallback():
    """Valida geração tradicional (use_pot=False) ou recebimento de alternativas prontas."""
    db = TestingSessionLocal()
    try:
        mock_llm = MagicMock(spec=LLMClient)
        mock_vs = MagicMock(spec=PineconeVectorStore)
        mock_vs.search.return_value = []

        mock_output = {
            "thought_scratchpad": "Passo a passo da geração de questão inédita.",
            "enunciado": "Em uma loja de informática, o preço de um computador sofreu um desconto de 15% na semana da tecnologia. Sabendo que o preço original era de R$ 2.400,00, qual é o valor final pago pelo cliente?",
            "alternativas": {
                "A": "R$ 1.980,00.",
                "B": "R$ 2.040,00.",
                "C": "R$ 2.100,00.",
                "D": "R$ 2.160,00.",
                "E": "R$ 2.240,00."
            },
            "gabarito": "B",
            "justificativa": "15% de 2400 é 360. Subtraindo 360 de 2400, obtemos R$ 2.040,00 (Alternativa B)."
        }
        mock_llm.generate.return_value = json.dumps(mock_output)

        service = QuestionService(llm_client=mock_llm, vector_store=mock_vs)
        questao = service.generate_single_questao_inedita(
            db=db,
            habilidade_codigo="H01",
            num_few_shot=2,
            max_attempts=2,
            use_pot=False
        )

        assert questao is not None
        assert questao.habilidade_codigo == "H01"
        assert questao.gabarito == "B"
        assert questao.is_validated is True
        assert len(questao.alternativas) == 5
    finally:
        db.close()


def test_generate_batch_success():
    db = TestingSessionLocal()
    try:
        mock_llm = MagicMock(spec=LLMClient)
        mock_vs = MagicMock(spec=PineconeVectorStore)
        mock_vs.search.return_value = []

        resp_pot = json.dumps({
            "enunciado": "Um investidor aplicou um capital de 5000 reais a uma taxa mensal de 2% durante 6 meses sob juros simples. Qual o montante final em reais?",
            "solver": "def resolver():\n    c = 5000\n    i = 0.02\n    t = 6\n    j = c * i * t\n    m = c + j\n    return {'correta': m, 'distratores': [5200, 5400, 5800, 6000]}"
        })
        resp_just = json.dumps({
            "justificativa": "Juros = 5000 * 0.02 * 6 = 600. Montante = 5000 + 600 = 5600 reais."
        })
        mock_llm.generate.side_effect = [resp_pot, resp_just]

        service = QuestionService(llm_client=mock_llm, vector_store=mock_vs)
        summary = service.generate_batch(
            db=db,
            habilidades=["H01"],
            count_per_habilidade=1,
            use_pot=True
        )

        assert summary.total_habilidades_processadas == 1
        assert summary.total_sucesso == 1
        assert summary.total_falhas == 0
        assert len(summary.itens) == 1
        assert summary.itens[0].success is True
    finally:
        db.close()
