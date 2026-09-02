import pytest
from unittest.mock import MagicMock, patch

from app.schemas.feedback import FeedbackRequest
from app.services.feedback_service import FeedbackService
from app.services.llm_client import LLMClient


@pytest.fixture
def sample_feedback_request():
    return FeedbackRequest(
        question_id="enem_2022_mat_q140",
        enunciado=(
            "Um arquiteto deseja calcular a altura de um edifício utilizando a sombra projetada no solo. "
            "Sabendo que o ângulo de elevação do Sol é de 30° e o comprimento da sombra é de 60 metros, "
            "qual é a altura aproximada do edifício? (Considere tg 30° = 0,58)"
        ),
        alternativas={
            "A": "15,4 m",
            "B": "34,8 m",
            "C": "60,0 m",
            "D": "103,4 m",
            "E": "120,0 m"
        },
        gabarito="B",
        resposta_aluno="D",
        habilidade="H19 - Resolver situação-problema que envolva conhecimentos de trigonometria",
        top_k_context=2
    )


def test_feedback_service_flow_success(sample_feedback_request):
    mock_vectorstore = MagicMock()
    mock_vectorstore.search.return_value = [
        {
            "id": "chunk_trig_1",
            "text": "A tangente de um ângulo é a razão entre o cateto oposto e o cateto adjacente: tg(θ) = oposto / adjacente.",
            "score": 0.89,
            "metadata": {"title": "Razões Trigonométricas", "topic": "Trigonometria"}
        }
    ]

    mock_llm_client = MagicMock(spec=LLMClient)
    mock_llm_client.generate.return_value = (
        "### 1. Diagnóstico da Habilidade e Conceito\n"
        "A questão avalia a habilidade H19 e conceitos de trigonometria no triângulo retângulo.\n\n"
        "### 2. Análise do Erro (Distrator Escolhido)\n"
        "O estudante assinalou a alternativa (D) provavelmente porque dividiu o adjacente pela tangente (60 / 0,58 ≈ 103,4) "
        "ao invés de multiplicar.\n\n"
        "### 3. Resolução Passo a Passo (Chain-of-Thought)\n"
        "Sabemos que tg 30° = h / 60 => h = 60 * 0,58 = 34,8 metros. Portanto, a **alternativa correta: B**.\n\n"
        "### 4. Dica e Plano de Ação\n"
        "Revise as relações no triângulo retângulo prestando atenção no isolamento das variáveis na equação."
    )

    service = FeedbackService(llm_client=mock_llm_client, vector_store=mock_vectorstore)
    response = service.generate_feedback(sample_feedback_request)

    assert response.status == "success"
    assert response.verification.is_valid is True
    assert response.verification.verified_against_gabarito is True
    assert response.verification.detected_answer == "B"
    assert len(response.context_chunks) == 1
    assert response.context_chunks[0].id == "chunk_trig_1"
    assert "34,8" in response.feedback_markdown

    mock_vectorstore.search.assert_called_once()
    mock_llm_client.generate.assert_called_once()


def test_feedback_service_guardrail_rejection_rn_fb01(sample_feedback_request):
    """
    Testa se o guardrail retém a resposta quando o modelo alucina e valida a resposta errada do aluno (RN-FB01 / RN-FB02).
    """
    mock_vectorstore = MagicMock()
    mock_vectorstore.search.return_value = []

    mock_llm_client = MagicMock(spec=LLMClient)
    # Modelo alucinando que a resposta correta é a D (que era a marcada pelo aluno)
    mock_llm_client.generate.return_value = (
        "O cálculo resultou em 103,4 m. Portanto, a resposta correta é a alternativa D."
    )

    service = FeedbackService(llm_client=mock_llm_client, vector_store=mock_vectorstore)
    response = service.generate_feedback(sample_feedback_request)

    assert response.status == "retained"
    assert response.verification.is_valid is False
    assert "revisão automática" in response.feedback_markdown
    assert "(B)" in response.feedback_markdown
