"""
Baseline zero-shot para a avaliação do TCC (RN-AVAL01).

Usa o mesmo modelo (LLM_MODEL_TUTORIA, RN-INF07) e os mesmos prompts da VERA, mas sem recuperação no Pinecone (sem material didático),
sem reescrita de consulta e sem a verificação do feedback contra o gabarito (RN-FB04): uma única geração com o
conhecimento paramétrico do modelo. Assim, a comparação com a VERA isola a contribuição da arquitetura.
"""
import time
import logging
from typing import Any, Dict, List, Optional

from app.core.prompts import (
    VERA_QUESTION_FEEDBACK_SYSTEM_PROMPT,
    build_chat_prompt,
    build_question_feedback_prompt,
    parse_cot_response,
)
from app.services.llm_client import LLMClient, cliente_tutoria

logger = logging.getLogger("vera.services.baseline")

# Mesmas temperaturas dos fluxos da VERA (FeedbackService e ChatService)
TEMPERATURA_FEEDBACK = 0.3
TEMPERATURA_TUTORIA = 0.2


class BaselineService:
    """Feedback e tutoria em modalidade zero-shot (sem RAG e sem verificação)."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or cliente_tutoria()  # mesmo modelo da VERA (RN-INF07)

    def gerar_feedback(
        self,
        habilidade_codigo: str,
        habilidade_descricao: str,
        enunciado: str,
        alternativas: Dict[str, str],
        alternativa_marcada: str,
        gabarito: str,
    ) -> Dict[str, Any]:
        """Mesmo prompt do feedback da VERA, sem trechos recuperados e com uma única tentativa."""
        prompt = build_question_feedback_prompt(
            habilidade_codigo=habilidade_codigo,
            habilidade_descricao=habilidade_descricao,
            enunciado=enunciado,
            alternativas=alternativas,
            alternativa_marcada=alternativa_marcada.strip().upper(),
            gabarito_oficial=gabarito.strip().upper(),
            context_chunks=None,
        )
        messages = [
            {"role": "system", "content": VERA_QUESTION_FEEDBACK_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        inicio = time.time()
        bruto = self.llm_client.generate(messages, temperature=TEMPERATURA_FEEDBACK)
        pensamento, conteudo = parse_cot_response(bruto)
        return {
            "conteudo": conteudo or bruto.strip(),
            "pensamento": pensamento,
            "tempo_s": round(time.time() - inicio, 2),
        }

    def responder_tutoria(self, mensagem: str, historico: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Mesmo prompt da tutora da VERA, com o histórico da conversa, mas sem material recuperado."""
        prompt = build_chat_prompt(
            user_message=mensagem,
            history_messages=historico or [],
            context_chunks=[],
        )
        inicio = time.time()
        bruto = self.llm_client.generate(prompt=prompt, session_id=None, temperature=TEMPERATURA_TUTORIA)
        pensamento, conteudo = parse_cot_response(bruto)
        return {
            "conteudo": conteudo or bruto.strip(),
            "pensamento": pensamento,
            "tempo_s": round(time.time() - inicio, 2),
        }
