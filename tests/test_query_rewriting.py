import pytest
from unittest.mock import MagicMock, AsyncMock

from app.core.prompts import (
    QUERY_REWRITE_SYSTEM_PROMPT,
    build_query_rewrite_prompt,
    clean_rewritten_query,
)
from app.schemas.chat import ChatMessage, ChatRequest
from app.services.chat_service import ChatService, ChatSessionManager
from app.services.llm_client import LLMClient


def test_build_query_rewrite_prompt():
    """Valida a construção do prompt objetivo de reescrita de query com e sem histórico."""
    # Sem histórico
    prompt_sem_hist = build_query_rewrite_prompt(user_message="O que é progressão aritmética?")
    assert "O que é progressão aritmética?" in prompt_sem_hist
    assert "(Sem histórico prévio)" in prompt_sem_hist
    assert "NÃO responda à pergunta" in prompt_sem_hist

    # Com histórico
    history = [
        {"role": "user", "content": "Como calcular o volume de um cilindro?"},
        {"role": "assistant", "content": "O volume do cilindro é V = pi * r² * h."}
    ]
    prompt_com_hist = build_query_rewrite_prompt(
        user_message="E se a altura dobrar de tamanho?",
        history_messages=history
    )
    assert "cilindro" in prompt_com_hist
    assert "E se a altura dobrar de tamanho?" in prompt_com_hist
    assert "Consulta de busca reescrita:" in prompt_com_hist


def test_clean_rewritten_query():
    """Valida a limpeza e higienização robusta da resposta do LLM para a query."""
    fallback = "pergunta original do aluno"

    # Query limpa direta
    assert clean_rewritten_query("Fórmula do volume do cilindro", fallback) == "Fórmula do volume do cilindro"

    # Query com aspas
    assert clean_rewritten_query('"Área de figuras planas trapézio"', fallback) == "Área de figuras planas trapézio"

    # Query com prefixo 'Consulta de busca:' ou 'Query:'
    assert clean_rewritten_query("Consulta de busca: Teorema de Pitágoras no triângulo", fallback) == "Teorema de Pitágoras no triângulo"
    assert clean_rewritten_query("Query: Probabilidade condicional e eventos independentes", fallback) == "Probabilidade condicional e eventos independentes"
    assert clean_rewritten_query("Busca: Estatística média moda mediana", fallback) == "Estatística média moda mediana"

    # Query com bloco de pensamento (<pensamento> ou <think>)
    raw_with_thought = "<pensamento>O aluno quer saber a fórmula do trapézio.</pensamento>\nÁrea do trapézio na geometria plana"
    assert clean_rewritten_query(raw_with_thought, fallback) == "Área do trapézio na geometria plana"

    # Fallback em caso de saída vazia ou apenas espaços
    assert clean_rewritten_query("", fallback) == fallback
    assert clean_rewritten_query("   ", fallback) == fallback
    assert clean_rewritten_query(None, fallback) == fallback


def test_rewrite_query_bypasses_llm_when_no_history():
    """Garante que a primeira mensagem (sem histórico) não gere latência de chamada ao LLM."""
    mock_llm = MagicMock(spec=LLMClient)
    service = ChatService(llm_client=mock_llm)

    res = service.rewrite_query("Qual é o valor de pi?", history_msgs=[])
    assert res == "Qual é o valor de pi?"
    mock_llm.generate.assert_not_called()


def test_rewrite_query_calls_llm_with_history():
    """Valida chamada ao LLM para resolver anáfora quando há histórico prévio."""
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.generate.return_value = "Cálculo do volume do cilindro com altura dobrada"

    service = ChatService(llm_client=mock_llm)
    history = [
        ChatMessage(role="user", content="Como calcular o volume de um cilindro?"),
        ChatMessage(role="assistant", content="O volume é V = pi * r² * h.")
    ]

    rewritten = service.rewrite_query("E se a altura dobrar?", history_msgs=history)
    assert rewritten == "Cálculo do volume do cilindro com altura dobrada"
    mock_llm.generate.assert_called_once()
    called_prompt = mock_llm.generate.call_args.kwargs["prompt"]
    assert "cilindro" in called_prompt


def test_rewrite_query_fallback_on_llm_error():
    """Garante resiliência: se o LLM falhar, faz fallback transparente para a mensagem original."""
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.generate.side_effect = RuntimeError("Conexão com Ollama instável")

    service = ChatService(llm_client=mock_llm)
    history = [ChatMessage(role="user", content="Pergunta anterior")]

    res = service.rewrite_query("Pergunta com anáfora", history_msgs=history)
    assert res == "Pergunta com anáfora"


@pytest.mark.anyio
async def test_arewrite_query_async():
    """Valida a versão assíncrona da reescrita de query."""
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.agenerate = AsyncMock(return_value="Consulta assíncrona reescrita")

    service = ChatService(llm_client=mock_llm)
    history = [ChatMessage(role="user", content="Turno 1")]

    rewritten = await service.arewrite_query("Turno 2", history_msgs=history)
    assert rewritten == "Consulta assíncrona reescrita"
    mock_llm.agenerate.assert_called_once()


def test_chat_service_multiturn_uses_rewritten_query_for_vector_search():
    """
    Testa fluxo completo multiturno:
    - No turno 1, a busca no Pinecone usa a pergunta original.
    - No turno 2, a busca no Pinecone usa a query reescrita pelo LLM.
    """
    manager = ChatSessionManager()
    mock_vectorstore = MagicMock()
    mock_vectorstore.search.return_value = []

    mock_llm = MagicMock(spec=LLMClient)
    # Turno 1: gera resposta
    mock_llm.generate.side_effect = [
        "<pensamento>Explicando cilindro.</pensamento><resposta>Volume é pi*r²*h.</resposta>",
        # Turno 2: primeira chamada é a reescrita, segunda chamada é a resposta
        "Cálculo do volume do cilindro com altura multiplicada por dois",
        "<pensamento>Calculando nova altura.</pensamento><resposta>O volume dobra se a altura dobrar.</resposta>",
    ]

    service = ChatService(llm_client=mock_llm, vector_store=mock_vectorstore, manager=manager)

    # Turno 1
    req1 = ChatRequest(message="Como calcula o volume do cilindro?")
    resp1 = service.send_message(req1)
    assert resp1.rewritten_query == "Como calcula o volume do cilindro?"
    assert mock_vectorstore.search.call_args_list[0].kwargs["query"] == "Como calcula o volume do cilindro?"

    # Turno 2 (mesma sessão com histórico)
    req2 = ChatRequest(message="E se a altura dobrar?", session_id=resp1.session_id)
    resp2 = service.send_message(req2)
    assert resp2.rewritten_query == "Cálculo do volume do cilindro com altura multiplicada por dois"
    assert mock_vectorstore.search.call_args_list[1].kwargs["query"] == "Cálculo do volume do cilindro com altura multiplicada por dois"
