import logging
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.core.sanitizer import sanitize_utf8_string, sanitize_metadata

import os
import torch

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Serviço de geração de embeddings com intfloat/multilingual-e5-large (1024 dimensões).
    Aplica as diretrizes do modelo E5 (prefixo 'passage:' para documentos e 'query:' para buscas).
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self._model = None
        # Otimiza o paralelismo em CPUs para maior vazão de inferência
        num_threads = os.cpu_count() or 4
        torch.set_num_threads(num_threads)

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Carregando modelo de embeddings '{self.model_name}'...")
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Gera embeddings para passagens de documentos com o prefixo 'passage: '.
        Sanitiza strings para UTF-8 válido e trata falhas de forma resiliente.
        """
        sanitized_texts = []
        for t in texts:
            clean = sanitize_utf8_string(t)
            sanitized_texts.append(f"passage: {clean}" if clean else "passage: ")

        try:
            embeddings = self.model.encode(sanitized_texts, normalize_embeddings=True, show_progress_bar=False)
            if hasattr(embeddings, "tolist"):
                return embeddings.tolist()
            return embeddings
        except Exception as e:
            logger.warning(f"Falha ao codificar lote de embeddings ({e}). Processando item a item de contingência...")
            results = []
            for text_item in sanitized_texts:
                try:
                    emb = self.model.encode([text_item], normalize_embeddings=True, show_progress_bar=False)
                    results.append(emb[0].tolist() if hasattr(emb[0], "tolist") else emb[0])
                except Exception as inner_e:
                    logger.error(f"Ignorando texto corrompido que falhou no tokenizer: {inner_e}")
                    results.append([0.0] * settings.EMBEDDING_DIMENSION)
            return results

    def embed_query(self, query: str) -> List[float]:
        """
        Gera embedding para consulta de busca com o prefixo 'query: '.
        """
        clean_query = sanitize_utf8_string(query)
        prefixed_query = f"query: {clean_query}"
        embedding = self.model.encode(prefixed_query, normalize_embeddings=True, show_progress_bar=False)
        if hasattr(embedding, "tolist"):
            return embedding.tolist()
        return embedding


_cross_encoder_model = None


def get_cross_encoder(model_name: str = "BAAI/bge-reranker-v2-m3"):
    """
    Carrega e mantém em cache singleton o modelo CrossEncoder para reranking.
    Garante carregamento único na aplicação.
    """
    global _cross_encoder_model
    if _cross_encoder_model is None:
        from sentence_transformers import CrossEncoder
        logger.info(f"Carregando modelo CrossEncoder '{model_name}' (singleton)...")
        _cross_encoder_model = CrossEncoder(model_name)
    return _cross_encoder_model


class PineconeVectorStore:
    """
    Cliente para gerenciamento e busca no índice Pinecone com suporte aos namespaces:
    - 'materiais_didaticos' (RN-VETOR01)
    - 'questoes_historicas' (RN-VETOR01)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        index_name: Optional[str] = None,
        embedding_service: Optional[EmbeddingService] = None
    ):
        self.api_key = api_key or settings.PINECONE_API_KEY
        self.index_name = index_name or settings.PINECONE_INDEX_NAME
        self.embedding_service = embedding_service or EmbeddingService()
        self._pc = None
        self._index = None

    @property
    def pc(self):
        if self._pc is None:
            if not self.api_key or self.api_key == "seu_pinecone_api_key":
                raise ValueError("PINECONE_API_KEY não configurada ou inválida no .env")
            from pinecone import Pinecone
            self._pc = Pinecone(api_key=self.api_key)
        return self._pc

    @property
    def index(self):
        if self._index is None:
            from pinecone import ServerlessSpec
            existing_indexes = [idx["name"] for idx in self.pc.list_indexes()]
            if self.index_name not in existing_indexes:
                logger.info(f"Índice '{self.index_name}' não encontrado. Criando índice Pinecone...")
                self.pc.create_index(
                    name=self.index_name,
                    dimension=settings.EMBEDDING_DIMENSION,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region=settings.PINECONE_ENVIRONMENT)
                )
            self._index = self.pc.Index(self.index_name)
        return self._index

    def upsert_chunks(
        self,
        chunks: List[Dict[str, Any]],
        namespace: str = settings.NAMESPACE_MATERIAIS_DIDATICOS,
        batch_size: int = 50
    ) -> int:
        """
        Gera embeddings e faz o upsert dos chunks no Pinecone em lotes.
        Sanitiza rigorosamente IDs, textos e metadados contra caracteres surrogates
        e bytes nulos, evitando erros de serialização no orjson do Pinecone.
        """
        if not chunks:
            logger.warning("Nenhum chunk fornecido para upsert.")
            return 0

        total_upserted = 0
        total_chunks = len(chunks)
        logger.info(f"Iniciando upsert de {total_chunks} chunks no namespace '{namespace}' (lotes de {batch_size})...")

        for i in range(0, total_chunks, batch_size):
            batch = chunks[i : i + batch_size]
            valid_batch = []
            for c in batch:
                if not c or not c.get("text"):
                    continue
                clean_text = sanitize_utf8_string(c["text"])
                if clean_text:
                    valid_batch.append((c, clean_text))

            if not valid_batch:
                continue

            texts = [item[1] for item in valid_batch]
            embeddings = self.embedding_service.embed_documents(texts)

            vectors = []
            for (item, clean_text), emb in zip(valid_batch, embeddings):
                metadata = sanitize_metadata(dict(item.get("metadata", {})))
                metadata["text"] = clean_text[:3000]
                vector_id = sanitize_utf8_string(str(item.get("id", "")))
                vectors.append({
                    "id": vector_id,
                    "values": emb,
                    "metadata": metadata
                })

            self.index.upsert(vectors=vectors, namespace=namespace)
            total_upserted += len(vectors)
            logger.info(f"Progresso: {total_upserted}/{total_chunks} vetores inseridos no namespace '{namespace}'.")

        return total_upserted

    def clear_namespace(self, namespace: str) -> None:
        """
        Remove todos os vetores de um namespace específico no Pinecone.
        """
        logger.info(f"Limpando todos os vetores do namespace '{namespace}'...")
        try:
            self.index.delete(delete_all=True, namespace=namespace)
            logger.info(f"Namespace '{namespace}' limpo com sucesso no Pinecone.")
        except Exception as e:
            logger.error(f"Erro ao limpar namespace '{namespace}': {e}")
            raise

    def search(
        self,
        query: str,
        namespace: str = settings.NAMESPACE_MATERIAIS_DIDATICOS,
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
        rerank: bool = False,
        rerank_top_k: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Executa busca por similaridade de cosseno com suporte a filtros de metadados.
        Se rerank=True, busca os top_k=25 candidatos iniciais no Pinecone, aplica
        o CrossEncoder BAAI/bge-reranker-v2-m3 e devolve os top 4 mais aderentes.
        """
        query_vector = self.embedding_service.embed_query(query)
        
        # Se rerank for solicitado, busca top_k=25 candidatos no Pinecone
        pinecone_k = 25 if rerank else top_k

        response = self.index.query(
            vector=query_vector,
            top_k=pinecone_k,
            namespace=namespace,
            filter=filter_dict,
            include_metadata=True
        )

        results = []
        for match in response.get("matches", []):
            results.append({
                "id": match["id"],
                "score": match.get("score", 0.0),
                "text": match.get("metadata", {}).get("text", ""),
                "metadata": match.get("metadata", {})
            })

        # Re-ranqueamento neural com CrossEncoder
        if rerank and results:
            cross_encoder = get_cross_encoder()
            pairs = [[query, r.get("text", "")] for r in results]
            rerank_scores = cross_encoder.predict(pairs)

            for r, score_val in zip(results, rerank_scores):
                r["original_score"] = r["score"]
                r["score"] = float(score_val)
                r["reranked"] = True

            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:rerank_top_k]

        return results
