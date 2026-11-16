"""Testes da baseline zero-shot (RN-AVAL01): mesmos prompts da VERA, sem RAG e sem verificação."""
from unittest.mock import MagicMock

from app.services.baseline_service import BaselineService
from app.services.feedback_service import FeedbackService
from app.services.llm_client import LLMClient

RESPOSTA = "A alternativa correta é a C: 5 cadernos custam R$ 20, pois cada um custa R$ 4."
RESPOSTA_COT = f"<pensamento>raciocínio interno</pensamento><resposta>{RESPOSTA}</resposta>"

ITEM = dict(
    habilidade_codigo="H03",
    habilidade_descricao="Resolver situação-problema envolvendo conhecimentos numéricos.",
    enunciado="Uma loja vende 3 cadernos por R$ 12. Quanto custam 5 cadernos?",
    alternativas={"A": "15", "B": "18", "C": "20", "D": "24", "E": "36"},
    alternativa_marcada="b",
    gabarito="c",
)


def test_feedback_baseline_usa_o_prompt_da_vera_sem_material_recuperado():
    llm = MagicMock(spec=LLMClient)
    llm.generate.return_value = RESPOSTA_COT
    resultado = BaselineService(llm_client=llm).gerar_feedback(**ITEM)

    assert llm.generate.call_count == 1  # uma única tentativa, sem a verificação RN-FB04
    mensagens = llm.generate.call_args.args[0]
    sistema, usuario = mensagens[0]["content"], mensagens[1]["content"]
    assert sistema.startswith("Você é VERA")
    assert "CONTEÚDO TEÓRICO DIDÁTICO DE APOIO" not in usuario
    assert "Alternativa B" in usuario and "Alternativa C" in usuario
    assert llm.generate.call_args.kwargs["temperature"] == 0.3
    assert resultado["conteudo"] == RESPOSTA
    assert resultado["pensamento"] == "raciocínio interno"


def test_feedback_da_vera_e_da_baseline_partem_do_mesmo_prompt_exceto_o_rag():
    """O prompt da VERA só difere do da baseline pelo bloco de material recuperado."""
    llm_vera, llm_base = MagicMock(spec=LLMClient), MagicMock(spec=LLMClient)
    llm_vera.generate.return_value = llm_base.generate.return_value = RESPOSTA_COT
    vector_store = MagicMock()
    vector_store.search.return_value = [{"id": "1", "text": "Regra de três simples.", "score": 0.9,
                                         "metadata": {"title": "Proporção"}}]
    vera = FeedbackService(llm_client=llm_vera, vector_store=vector_store)
    vera.gerar_feedback_verificado(
        **{k: v for k, v in ITEM.items() if k not in ("alternativa_marcada", "gabarito")},
        alternativa_marcada="B", gabarito="C",
    )
    BaselineService(llm_client=llm_base).gerar_feedback(**ITEM)

    prompt_vera = llm_vera.generate.call_args_list[0].args[0][1]["content"]
    prompt_base = llm_base.generate.call_args.args[0][1]["content"]
    assert "Regra de três simples." in prompt_vera
    bloco_rag = prompt_vera[prompt_vera.index("\n\nCONTEÚDO TEÓRICO"):prompt_vera.index("HABILIDADE DO ENEM")]
    assert prompt_vera.replace(bloco_rag, "\n") == prompt_base


def test_tutoria_baseline_mantem_o_historico_e_nao_recupera_material():
    llm = MagicMock(spec=LLMClient)
    llm.generate.return_value = RESPOSTA_COT
    historico = [{"role": "user", "content": "Como calculo o volume de um cilindro?"},
                 {"role": "assistant", "content": "V = área da base vezes a altura."}]
    resultado = BaselineService(llm_client=llm).responder_tutoria("E a área total dele?", historico)

    prompt = llm.generate.call_args.kwargs["prompt"]
    assert "Nenhum material didático complementar resgatado" in prompt
    assert "Como calculo o volume de um cilindro?" in prompt and "E a área total dele?" in prompt
    assert llm.generate.call_args.kwargs["temperature"] == 0.2
    assert llm.generate.call_count == 1  # sem a chamada de reescrita de consulta
    assert resultado["conteudo"] == RESPOSTA
