import logging
from typing import List, Dict, Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Serviço de geração de embeddings com intfloat/multilingual-e5-base (768 dimensões).
    Aplica as diretrizes do modelo E5 (prefixo 'passage:' para documentos e 'query:' para buscas).
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self._model = None

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
        """
        prefixed_texts = [f"passage: {t.strip()}" for t in texts]
        embeddings = self.model.encode(prefixed_texts, normalize_embeddings=True, show_progress_bar=False)
        if hasattr(embeddings, "tolist"):
            return embeddings.tolist()
        return embeddings

    def embed_query(self, query: str) -> List[float]:
        """
        Gera embedding para consulta de busca com o prefixo 'query: '.
        """
        prefixed_query = f"query: {query.strip()}"
        embedding = self.model.encode(prefixed_query, normalize_embeddings=True, show_progress_bar=False)
        if hasattr(embedding, "tolist"):
            return embedding.tolist()
        return embedding


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
        """
        if not chunks:
            logger.warning("Nenhum chunk fornecido para upsert.")
            return 0

        total_upserted = 0
        total_chunks = len(chunks)
        logger.info(f"Iniciando upsert de {total_chunks} chunks no namespace '{namespace}' (lotes de {batch_size})...")

        for i in range(0, total_chunks, batch_size):
            batch = chunks[i : i + batch_size]
            texts = [c["text"] for c in batch]
            embeddings = self.embedding_service.embed_documents(texts)

            vectors = []
            for item, emb in zip(batch, embeddings):
                metadata = dict(item.get("metadata", {}))
                metadata["text"] = item["text"]
                vectors.append({
                    "id": item["id"],
                    "values": emb,
                    "metadata": metadata
                })

            self.index.upsert(vectors=vectors, namespace=namespace)
            total_upserted += len(vectors)
            logger.info(f"Progresso: {total_upserted}/{total_chunks} vetores inseridos no namespace '{namespace}'.")

        return total_upserted

    def search(
        self,
        query: str,
        namespace: str = settings.NAMESPACE_MATERIAIS_DIDATICOS,
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Executa busca por similaridade de cosseno com suporte a filtros de metadados.
        """
        query_vector = self.embedding_service.embed_query(query)
        
        response = self.index.query(
            vector=query_vector,
            top_k=top_k,
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

        return results
