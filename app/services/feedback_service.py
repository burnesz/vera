import os
import json
import uuid
import re
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.prompts import (
    VERA_QUESTION_FEEDBACK_SYSTEM_PROMPT,
    build_question_feedback_prompt,
    parse_cot_response,
)
from app.db.models.submission import RespostaItem, SimuladoTentativa
from app.db.models.feedback import Feedback
from app.db.models.habilidade import HabilidadeEnem
from app.services.feedback_verifier import (
    FeedbackVerification,
    build_correction_hint,
    verify_feedback,
)
from app.services.llm_client import LLMClient
from app.services.vectorstore import PineconeVectorStore

logger = logging.getLogger("vera.services.feedback")

# Tentativas totais de geração antes de recusar o feedback (RN-FB04).
MAX_FEEDBACK_ATTEMPTS = 3


class FeedbackVerificationError(RuntimeError):
    """
    Nenhuma tentativa de geração passou na verificação automática contra o gabarito (RN-FB04).
    O feedback reprovado não é persistido nem exibido ao estudante.
    """

    def __init__(self, message: str, verificacoes: List[FeedbackVerification]):
        super().__init__(message)
        self.verificacoes = verificacoes


class FeedbackService:
    """
    Serviço pedagógico para geração e consulta de feedbacks analíticos por item de simulado.
    Combina RAG sobre teoria matemática (Pinecone) com raciocínio Chain-of-Thought (CoT)
    para explicar acolhedoramente o erro do estudante e orientar seus estudos.
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        vector_store: Optional[PineconeVectorStore] = None,
        queries_path: str = "data/habilidades_queries.json",
    ):
        self.llm_client = llm_client or LLMClient(model_name=settings.LLM_MODEL_TUTORIA, think=settings.LLM_THINK_TUTORIA)  # RN-INF07
        self.vector_store = vector_store or PineconeVectorStore()
        self.queries_path = queries_path
        self._canonical_queries_cache: Optional[Dict[str, str]] = None

    def _load_canonical_queries(self) -> Dict[str, str]:
        """
        Carrega o dicionário de queries conceituais canônicas para as 30 habilidades do ENEM.
        """
        if self._canonical_queries_cache is not None:
            return self._canonical_queries_cache

        cache: Dict[str, str] = {}
        if os.path.exists(self.queries_path):
            try:
                with open(self.queries_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        hab = item.get("habilidade_codigo") or item.get("habilidade")
                        q = item.get("query")
                        if hab and q:
                            clean_hab = hab.replace("H", "").zfill(2)
                            cache[f"H{clean_hab}"] = q
            except Exception as e:
                logger.warning(f"Erro ao carregar queries canônicas de {self.queries_path}: {e}")

        self._canonical_queries_cache = cache
        return cache

    def _extract_final_command(self, enunciado: str) -> str:
        """
        Extrai o comando matemático final do enunciado (última pergunta/frase).
        """
        if not enunciado:
            return ""
        # Divide por pontuação final (. ? !)
        sentences = re.split(r"(?<=[.?!])\s+", enunciado.strip())
        if sentences:
            # Pega as últimas 1 ou 2 frases que costumam conter o comando efetivo
            return " ".join(sentences[-2:]).strip()
        return enunciado.strip()

    def build_rag_query(self, habilidade_codigo: str, enunciado: str) -> str:
        """
        Constrói a query RAG determinística combinando a essência da habilidade com o comando do item.
        """
        canonical_map = self._load_canonical_queries()
        canonical_query = canonical_map.get(habilidade_codigo, "")
        final_cmd = self._extract_final_command(enunciado)

        if canonical_query and final_cmd:
            return f"{canonical_query} {final_cmd}".strip()
        elif canonical_query:
            return canonical_query
        return final_cmd or f"Habilidade {habilidade_codigo} Matemática ENEM"

    def _retrieve_context(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Recupera trechos conceituais relevantes do namespace de materiais didáticos no Pinecone.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        logger.info(f"Feedback RAG: consultando '{settings.NAMESPACE_MATERIAIS_DIDATICOS}' (top_k={top_k})...")
        try:
            raw_results = self.vector_store.search(
                query=clean_query,
                namespace=settings.NAMESPACE_MATERIAIS_DIDATICOS,
                top_k=top_k,
            )
            context_chunks: List[Dict[str, Any]] = []
            for item in raw_results:
                meta = item.get("metadata", {})
                context_chunks.append({
                    "id": str(item.get("id", "")),
                    "title": meta.get("title") or meta.get("document_name") or "Material Didático",
                    "topic": meta.get("topic", ""),
                    "text": item.get("text", ""),
                    "score": round(float(item.get("score", 0.0)), 4),
                    "document_name": meta.get("document_name"),
                })
            return context_chunks
        except Exception as e:
            logger.warning(f"Não foi possível resgatar contexto do Pinecone para feedback ({e}). Continuando sem chunks teóricos...")
            return []

    def obter_feedback_existente(
        self,
        db: Session,
        resposta_item_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[Feedback]:
        """
        Retorna o feedback persistido caso já exista (cache instantâneo de 0ms).
        """
        resposta = (
            db.query(RespostaItem)
            .options(joinedload(RespostaItem.tentativa))
            .filter(RespostaItem.id == resposta_item_id)
            .first()
        )
        if not resposta:
            return None

        # Validação de segurança: apenas o estudante dono da tentativa pode acessar
        if resposta.tentativa.user_id != user_id:
            raise PermissionError("Acesso não autorizado ao item desta tentativa.")

        return db.query(Feedback).filter(Feedback.resposta_item_id == resposta_item_id).first()

    def gerar_ou_obter_feedback_item(
        self,
        db: Session,
        resposta_item_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Feedback:
        """
        Gera ou recupera o feedback da Tutora VERA para uma resposta do estudante.
        """
        # 1. Verifica cache no banco
        existente = self.obter_feedback_existente(db, resposta_item_id, user_id)
        if existente:
            logger.info(f"Feedback para resposta '{resposta_item_id}' retornado do cache relacional (0ms).")
            return existente

        # 2. Carrega a resposta com suas relações
        resposta = (
            db.query(RespostaItem)
            .options(
                joinedload(RespostaItem.tentativa),
                joinedload(RespostaItem.questao_enem),
                joinedload(RespostaItem.questao_inedita),
            )
            .filter(RespostaItem.id == resposta_item_id)
            .first()
        )
        if not resposta:
            raise ValueError(f"Resposta com ID '{resposta_item_id}' não encontrada.")

        if resposta.tentativa.user_id != user_id:
            raise PermissionError("Acesso não autorizado ao item desta tentativa.")

        # 3. Extrai dados da questão
        if resposta.origem_questao == "enem" and resposta.questao_enem:
            q = resposta.questao_enem
            enunciado = q.enunciado
            alternativas = q.alternativas or {}
            gabarito = q.gabarito.strip().upper()
            hab_cod = q.habilidade_codigo
        elif resposta.origem_questao == "inedita" and resposta.questao_inedita:
            q = resposta.questao_inedita
            enunciado = q.enunciado
            alternativas = q.alternativas or {}
            gabarito = q.gabarito.strip().upper()
            hab_cod = q.habilidade_codigo
        else:
            raise ValueError("Item de simulado sem questão associada.")

        # Obtém descrição da habilidade
        hab_obj = db.query(HabilidadeEnem).filter(HabilidadeEnem.codigo == hab_cod).first()
        hab_desc = hab_obj.descricao if hab_obj else f"Habilidade {hab_cod}"

        marcada = (resposta.alternativa_marcada or "X").strip().upper()

        # 4 a 6. RAG, inferência e verificação contra o gabarito (RN-FB04)
        gerado = self.gerar_feedback_verificado(
            habilidade_codigo=hab_cod,
            habilidade_descricao=hab_desc,
            enunciado=enunciado,
            alternativas=alternativas,
            alternativa_marcada=marcada,
            gabarito=gabarito,
        )

        # 7. Salva na tabela feedbacks do PostgreSQL
        feedback = Feedback(
            resposta_item_id=resposta.id,
            feedback_content=gerado["conteudo"],
            thought_scratchpad=gerado["pensamento"],
            context_chunks=gerado["context_chunks"],
            is_verified=True,
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)

        logger.info(f"Feedback '{feedback.id}' gerado e persistido com sucesso para resposta '{resposta.id}'.")
        return feedback

    def gerar_feedback_verificado(
        self,
        habilidade_codigo: str,
        habilidade_descricao: str,
        enunciado: str,
        alternativas: Dict[str, str],
        alternativa_marcada: str,
        gabarito: str,
    ) -> Dict[str, Any]:
        """
        Gera o feedback de um item sem acessar o banco: RAG no Pinecone, inferência com CoT e verificação
        contra o gabarito com Stateless Retry (RN-FB04). Levanta FeedbackVerificationError se nenhuma
        tentativa for aprovada. Retorna o conteúdo, o raciocínio, os trechos recuperados e as verificações.
        """
        hab_cod, hab_desc, marcada = habilidade_codigo, habilidade_descricao, alternativa_marcada

        # 4. Busca contexto RAG determinístico no Pinecone
        rag_query = self.build_rag_query(hab_cod, enunciado)
        context_chunks = self._retrieve_context(rag_query, top_k=3)

        # 5. Monta prompt e dispara inferência no LLM
        prompt = build_question_feedback_prompt(
            habilidade_codigo=hab_cod,
            habilidade_descricao=hab_desc,
            enunciado=enunciado,
            alternativas=alternativas,
            alternativa_marcada=marcada,
            gabarito_oficial=gabarito,
            context_chunks=context_chunks,
        )

        # 6. Inferência + pós-processamento: verificação contra gabarito e Matriz (RN-FB04).
        # Cada nova tentativa reconstrói o prompt do zero (Stateless Retry), anexando a
        # instrução corretiva derivada das violações da tentativa anterior.
        verificacoes: List[FeedbackVerification] = []
        thought: Optional[str] = None
        clean_reply = ""
        correction_hint = ""
        for attempt in range(1, MAX_FEEDBACK_ATTEMPTS + 1):
            messages = [
                {"role": "system", "content": VERA_QUESTION_FEEDBACK_SYSTEM_PROMPT},
                {"role": "user", "content": prompt + correction_hint},
            ]

            logger.info(
                f"Disparando geração de feedback pedagógico no LLM para {hab_cod} "
                f"(marcada='{marcada}', gabarito='{gabarito}', tentativa {attempt}/{MAX_FEEDBACK_ATTEMPTS})..."
            )
            raw_reply = self.llm_client.generate(messages, temperature=0.3)

            thought, clean_reply = parse_cot_response(raw_reply)
            if not clean_reply:
                clean_reply = raw_reply.strip()

            verificacao = verify_feedback(
                content=clean_reply,
                gabarito=gabarito,
                alternativa_marcada=marcada,
                alternativas=alternativas,
                habilidade_codigo=hab_cod,
            )
            verificacoes.append(verificacao)
            if verificacao.aprovado:
                logger.info(f"Feedback aprovado na verificação automática (tentativa {attempt}/{MAX_FEEDBACK_ATTEMPTS}).")
                break

            logger.warning(
                f"Feedback reprovado na verificação automática (tentativa {attempt}/{MAX_FEEDBACK_ATTEMPTS}): "
                f"{verificacao.violacoes} — {verificacao.detalhes}"
            )
            correction_hint = build_correction_hint(verificacao, gabarito, marcada, hab_cod)
        else:
            raise FeedbackVerificationError(
                f"A explicação gerada não passou na verificação automática contra o gabarito após "
                f"{MAX_FEEDBACK_ATTEMPTS} tentativas.",
                verificacoes,
            )

        return {
            "conteudo": clean_reply,
            "pensamento": thought,
            "context_chunks": context_chunks,
            "verificacoes": verificacoes,
        }


# Instância singleton padrão do serviço
feedback_service = FeedbackService()
