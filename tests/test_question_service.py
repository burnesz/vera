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
        # Cadastra habilidade H01
        hab = HabilidadeEnem(
            codigo="H01",
            competencia=1,
            descricao="Reconhecer, no contexto social, diferentes significados e representações dos números e operações.",
            eixo_tematico="Números e Operações"
        )
        db.merge(hab)

        # Cadastra 2 questões históricas do ENEM para H01
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
        service = QuestionService()
        exemplos = service.retrieve_few_shot_examples(db, "H01", k=2)
        assert len(exemplos) == 2
        for ex in exemplos:
            assert ex.habilidade_codigo == "H01"
            assert ex.gabarito in ["A", "B", "C", "D", "E"]
    finally:
        db.close()


def test_generate_single_questao_inedita_success():
    db = TestingSessionLocal()
    try:
        mock_llm = MagicMock(spec=LLMClient)
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

        service = QuestionService(llm_client=mock_llm)
        questao = service.generate_single_questao_inedita(
            db=db,
            habilidade_codigo="H01",
            num_few_shot=2,
            max_attempts=2
        )

        assert questao is not None
        assert questao.habilidade_codigo == "H01"
        assert questao.gabarito == "B"
        assert questao.is_validated is True
        assert len(questao.alternativas) == 5

        # Verifica persistência no banco
        do_banco = db.get(QuestaoInedita, questao.id)
        assert do_banco is not None
        assert do_banco.enunciado == questao.enunciado
    finally:
        db.close()


def test_generate_single_questao_inedita_retry_on_invalid():
    """Testa se o serviço tenta novamente quando o LLM gera saída inválida na 1ª tentativa."""
    db = TestingSessionLocal()
    try:
        mock_llm = MagicMock(spec=LLMClient)

        # 1ª resposta com alternativas duplicadas (falha RN-Q01)
        resp_invalida = json.dumps({
            "enunciado": "Enunciado de teste qualquer para validação...",
            "alternativas": {"A": "10", "B": "10", "C": "20", "D": "30", "E": "40"},
            "gabarito": "C",
            "justificativa": "..."
        })

        # 2ª resposta válida
        resp_valida = json.dumps({
            "enunciado": "Um veículo percorre uma distância de 360 quilômetros com velocidade constante de 90 km/h. O tempo de viagem em horas é:",
            "alternativas": {"A": "2 horas.", "B": "3 horas.", "C": "4 horas.", "D": "5 horas.", "E": "6 horas."},
            "gabarito": "C",
            "justificativa": "360 / 90 = 4 horas."
        })

        mock_llm.generate.side_effect = [resp_invalida, resp_valida]

        service = QuestionService(llm_client=mock_llm)
        questao = service.generate_single_questao_inedita(
            db=db,
            habilidade_codigo="H01",
            max_attempts=2
        )

        assert questao is not None
        assert questao.gabarito == "C"
        assert mock_llm.generate.call_count == 2
    finally:
        db.close()


def test_generate_batch_success():
    db = TestingSessionLocal()
    try:
        mock_llm = MagicMock(spec=LLMClient)
        mock_output = json.dumps({
            "enunciado": "Um investidor aplicou um capital de R$ 5.000,00 a juros simples de 2% ao mês durante 6 meses. Qual o montante final?",
            "alternativas": {
                "A": "R$ 5.200,00.",
                "B": "R$ 5.400,00.",
                "C": "R$ 5.600,00.",
                "D": "R$ 5.800,00.",
                "E": "R$ 6.000,00."
            },
            "gabarito": "C",
            "justificativa": "Juros = 5000 * 0.02 * 6 = 600. Montante = 5600."
        })
        mock_llm.generate.return_value = mock_output

        service = QuestionService(llm_client=mock_llm)
        summary = service.generate_batch(
            db=db,
            habilidades=["H01"],
            count_per_habilidade=1
        )

        assert summary.total_habilidades_processadas == 1
        assert summary.total_sucesso == 1
        assert summary.total_falhas == 0
        assert len(summary.itens) == 1
        assert summary.itens[0].success is True
    finally:
        db.close()
