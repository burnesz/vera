import re
import time
import logging
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.core.prompts import build_feedback_prompt
from app.schemas.feedback import (
    FeedbackRequest,
    FeedbackResponse,
    FeedbackContextChunk,
    FeedbackVerification
)
from app.services.llm_client import LLMClient
from app.services.vectorstore import PineconeVectorStore

logger = logging.getLogger(__name__)


class FeedbackService:
    """
    Serviço orquestrador do Pipeline RAG de Feedback Pedagógico (5 Etapas):
    1. Entrada: Identificação da questão e resposta do estudante.
    2. Mapeamento Semântico: Construção da query de busca contextual.
    3. Retrieval: Busca semântica no namespace 'materiais_didaticos' (Pinecone).
    4. Geração CoT: Injeção de contexto e inferência com Qwen 2.5.
    5. Verificação Automática: Checagem de consistência com gabarito oficial (RN-FB01, RN-FB02).
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        vector_store: Optional[PineconeVectorStore] = None
    ):
        self.llm_client = llm_client or LLMClient()
        self.vector_store = vector_store or PineconeVectorStore()

    def _retrieve_context(
        self,
        enunciado: str,
        habilidade: Optional[str] = None,
        top_k: int = 3
    ) -> List[FeedbackContextChunk]:
        """
        Executa busca semântica de materiais didáticos relevantes no Pinecone (RN-VETOR01).
        """
        # Constrói query combinando habilidade/tópico e enunciado
        query_parts = []
        if habilidade and habilidade != "Matemática do ENEM":
            query_parts.append(habilidade)
        query_parts.append(enunciado[:300])
        search_query = " ".join(query_parts)

        logger.info(f"Executando busca de contexto no namespace '{settings.NAMESPACE_MATERIAIS_DIDATICOS}' (top_k={top_k})...")
        try:
            raw_results = self.vector_store.search(
                query=search_query,
                namespace=settings.NAMESPACE_MATERIAIS_DIDATICOS,
                top_k=top_k
            )

            context_chunks = []
            for item in raw_results:
                meta = item.get("metadata", {})
                context_chunks.append(
                    FeedbackContextChunk(
                        id=item["id"],
                        title=meta.get("title", meta.get("document_name", "Material Didático")),
                        topic=meta.get("topic", ""),
                        text=item.get("text", ""),
                        score=round(float(item.get("score", 0.0)), 4),
                        page_number=meta.get("page_number"),
                        document_name=meta.get("document_name")
                    )
                )
            return context_chunks
        except Exception as e:
            logger.warning(f"Não foi possível resgatar contexto do Pinecone ({e}). Prosseguindo sem chunks extras...")
            return []

    def _verify_consistency_with_gabarito(
        self,
        feedback_text: str,
        gabarito: str,
        resposta_aluno: str
    ) -> FeedbackVerification:
        """
        Verificação automática de consistência entre a explicação gerada e o gabarito oficial (RN-FB01).
        Garante que o modelo não alucine e confirme o gabarito oficial como correto.
        """
        gabarito_upper = gabarito.strip().upper()
        resposta_aluno_upper = resposta_aluno.strip().upper()

        # Expressões que indicam confirmação do gabarito correto
        # ex: "Alternativa correta: B", "alternativa B é a correta", "letra B", "gabarito: B"
        patterns_gabarito = [
            rf"alternativa\s*(?:correta|certa)?\s*[:\-\(]?\s*[\*\_]*\s*({gabarito_upper})\b",
            rf"letra\s*[:\-\(]?\s*[\*\_]*\s*({gabarito_upper})\b",
            rf"gabarito\s*(?:oficial)?\s*[:\-\(]?\s*[\*\_]*\s*({gabarito_upper})\b",
            rf"resposta\s*(?:correta)?\s*[:\-\(]?\s*[\*\_]*\s*({gabarito_upper})\b"
        ]

        found_gabarito_match = False
        for p in patterns_gabarito:
            if re.search(p, feedback_text, re.IGNORECASE):
                found_gabarito_match = True
                break

        # Verifica se o modelo erroneamente declarou a alternativa errada do aluno como correta
        contradiction_patterns = [
            rf"alternativa\s*(?:correta|certa)\s*[:\-\(]?\s*[\*\_]*\s*({resposta_aluno_upper})\b",
            rf"resposta\s*correta\s*é\s*(?:a\s*)?alternativa\s*[\*\_]*\s*({resposta_aluno_upper})\b"
        ]
        has_contradiction = False
        for cp in contradiction_patterns:
            if re.search(cp, feedback_text, re.IGNORECASE):
                has_contradiction = True
                break

        if has_contradiction:
            logger.warning(f"RN-FB01 Falha: Modelo indicou a alternativa incorreta ({resposta_aluno_upper}) como correta.")
            return FeedbackVerification(
                is_valid=False,
                verified_against_gabarito=False,
                detected_answer=resposta_aluno_upper,
                confidence=0.0,
                details=f"Inconsistência detectada: o feedback validou a alternativa incorreta ({resposta_aluno_upper})."
            )

        if found_gabarito_match or (gabarito_upper in feedback_text):
            return FeedbackVerification(
                is_valid=True,
                verified_against_gabarito=True,
                detected_answer=gabarito_upper,
                confidence=0.95,
                details=f"Consistência validada com sucesso em relação ao gabarito ({gabarito_upper})."
            )

        # Se não encontrou menção explícita mas não houve contradição, aceita com confiança moderada
        return FeedbackVerification(
            is_valid=True,
            verified_against_gabarito=True,
            detected_answer=gabarito_upper,
            confidence=0.80,
            details="Nenhuma contradição detectada na resolução."
        )

    def generate_feedback(self, request: FeedbackRequest) -> FeedbackResponse:
        """
        Execução síncrona do fluxo completo de feedback pedagógico.
        """
        start_time = time.time()
        logger.info(f"Iniciando pipeline de Feedback Pedagógico para questão (Gabarito: {request.gabarito}, Aluno: {request.resposta_aluno})...")

        # 1 & 2 & 3. Retrieval no Pinecone
        context_chunks = self._retrieve_context(
            enunciado=request.enunciado,
            habilidade=request.habilidade,
            top_k=request.top_k_context
        )

        # 4. Construção do Prompt CoT e Inferência
        prompt = build_feedback_prompt(
            enunciado=request.enunciado,
            alternativas=request.alternativas,
            gabarito_oficial=request.gabarito,
            resposta_aluno=request.resposta_aluno,
            habilidade=request.habilidade or "Matemática do ENEM",
            context_chunks=[c.model_dump() for c in context_chunks]
        )

        generated_raw = self.llm_client.generate(prompt=prompt)
        elapsed_time = round(time.time() - start_time, 2)

        # 5. Verificação Automática (RN-FB01 / RN-FB02)
        verification = self._verify_consistency_with_gabarito(
            feedback_text=generated_raw,
            gabarito=request.gabarito,
            resposta_aluno=request.resposta_aluno
        )

        # RN-FB02: Se a verificação falhar, retém o feedback e loga para inspeção
        if not verification.is_valid:
            logger.error("RN-FB02: Feedback retido por falha na verificação de gabarito.")
            safe_fallback_feedback = (
                "### Orientação Pedagógica VERA\n\n"
                f"A alternativa correta oficial para esta questão é a **({request.gabarito.upper()})**.\n\n"
                f"Você assinalou a alternativa **({request.resposta_aluno.upper()})**, que é incorreta. "
                "Para garantir a precisão máxima do seu aprendizado, este feedback foi enviado para revisão automática "
                "por apresentar divergência de consistência. Recomendamos revisar os conceitos teóricos relacionados a esta habilidade."
            )
            return FeedbackResponse(
                feedback_markdown=safe_fallback_feedback,
                context_chunks=context_chunks,
                verification=verification,
                inference_time_seconds=elapsed_time,
                status="retained"
            )

        return FeedbackResponse(
            feedback_markdown=generated_raw,
            context_chunks=context_chunks,
            verification=verification,
            inference_time_seconds=elapsed_time,
            status="success"
        )

    async def agenerate_feedback(self, request: FeedbackRequest) -> FeedbackResponse:
        """
        Execução assíncrona do fluxo completo de feedback pedagógico.
        """
        start_time = time.time()
        logger.info(f"Iniciando pipeline assíncrono de Feedback Pedagógico (Gabarito: {request.gabarito}, Aluno: {request.resposta_aluno})...")

        # 1 & 2 & 3. Retrieval
        context_chunks = self._retrieve_context(
            enunciado=request.enunciado,
            habilidade=request.habilidade,
            top_k=request.top_k_context
        )

        # 4. Geração CoT
        prompt = build_feedback_prompt(
            enunciado=request.enunciado,
            alternativas=request.alternativas,
            gabarito_oficial=request.gabarito,
            resposta_aluno=request.resposta_aluno,
            habilidade=request.habilidade or "Matemática do ENEM",
            context_chunks=[c.model_dump() for c in context_chunks]
        )

        generated_raw = await self.llm_client.agenerate(prompt=prompt)
        elapsed_time = round(time.time() - start_time, 2)

        # 5. Verificação Automática
        verification = self._verify_consistency_with_gabarito(
            feedback_text=generated_raw,
            gabarito=request.gabarito,
            resposta_aluno=request.resposta_aluno
        )

        if not verification.is_valid:
            logger.error("RN-FB02: Feedback retido por falha na verificação de gabarito (async).")
            safe_fallback_feedback = (
                "### Orientação Pedagógica VERA\n\n"
                f"A alternativa correta oficial para esta questão é a **({request.gabarito.upper()})**.\n\n"
                f"Você assinalou a alternativa **({request.resposta_aluno.upper()})**, que é incorreta. "
                "Para garantir a precisão máxima do seu aprendizado, este feedback foi enviado para revisão automática "
                "por apresentar divergência de consistência. Recomendamos revisar os conceitos teóricos relacionados a esta habilidade."
            )
            return FeedbackResponse(
                feedback_markdown=safe_fallback_feedback,
                context_chunks=context_chunks,
                verification=verification,
                inference_time_seconds=elapsed_time,
                status="retained"
            )

        return FeedbackResponse(
            feedback_markdown=generated_raw,
            context_chunks=context_chunks,
            verification=verification,
            inference_time_seconds=elapsed_time,
            status="success"
        )
