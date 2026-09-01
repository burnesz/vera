import argparse
import logging
import sys
import time
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.services.storage import R2StorageService
from app.pipeline.chunking import MaterialChunker
from app.services.vectorstore import PineconeVectorStore, EmbeddingService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("vera.pipeline.ingestion")


def run_materials_ingestion(
    prefix: str = "",
    batch_size: int = 50,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Executa o pipeline completo de ingestão dos materiais didáticos teóricos:
    1. Conecta ao Cloudflare R2 e lista os PDFs.
    2. Baixa cada PDF e executa parsing + chunking semântico.
    3. Gera embeddings com intfloat/multilingual-e5-base.
    4. Indexa os vetores no namespace 'materiais_didaticos' do Pinecone.
    """
    start_time = time.time()
    logger.info("=" * 70)
    logger.info("INICIANDO PIPELINE DE INGESTÃO DE MATERIAIS DIDÁTICOS (R2 -> PINECONE)")
    logger.info("=" * 70)

    # 1. Conexão com R2
    storage = R2StorageService()
    logger.info(f"Conectando ao bucket R2 '{storage.bucket_name}'...")
    pdf_files = storage.list_files(prefix=prefix, extension=".pdf")

    if not pdf_files:
        logger.warning("Nenhum arquivo PDF encontrado no bucket R2.")
        return {
            "status": "warning",
            "message": "Nenhum PDF encontrado.",
            "total_files": 0,
            "total_chunks": 0,
            "total_vectors_upserted": 0
        }

    logger.info(f"Total de {len(pdf_files)} materiais identificados no R2 para processamento.")

    # 2. Parsing e Chunking
    chunker = MaterialChunker()
    all_chunks: List[Dict[str, Any]] = []
    processed_files = 0
    failed_files = []

    for idx, file_info in enumerate(pdf_files, 1):
        file_key = file_info["key"]
        logger.info(f"[{idx}/{len(pdf_files)}] Baixando e processando: {file_key}...")

        try:
            pdf_bytes = storage.download_file_bytes(file_key)
            chunks = chunker.process_pdf_material(file_key, pdf_bytes)
            all_chunks.extend(chunks)
            processed_files += 1
            logger.info(f" -> OK: {len(chunks)} chunks gerados para '{file_key}'.")
        except Exception as e:
            logger.error(f" -> FALHA ao processar '{file_key}': {e}")
            failed_files.append({"file": file_key, "error": str(e)})

    total_chunks = len(all_chunks)
    logger.info(f"\nResumo da Extração: {processed_files} arquivos processados com sucesso, {total_chunks} chunks no total.")

    # 3. Vetorização e Indexação no Pinecone
    total_upserted = 0
    if dry_run:
        logger.info("[DRY-RUN ATIVO] Vetorização e envio ao Pinecone ignorados.")
    else:
        if all_chunks:
            logger.info(f"Iniciando vetorização e upsert de {total_chunks} itens no Pinecone...")
            vector_store = PineconeVectorStore()
            total_upserted = vector_store.upsert_chunks(
                chunks=all_chunks,
                namespace=settings.NAMESPACE_MATERIAIS_DIDATICOS,
                batch_size=batch_size
            )
            logger.info(f"Sucesso: {total_upserted} vetores indexados no namespace '{settings.NAMESPACE_MATERIAIS_DIDATICOS}'.")

    elapsed_time = time.time() - start_time
    logger.info("=" * 70)
    logger.info(f"PIPELINE CONCLUÍDO EM {elapsed_time:.2f}s")
    logger.info(f"Arquivos processados: {processed_files}/{len(pdf_files)}")
    logger.info(f"Total de chunks: {total_chunks}")
    logger.info(f"Vetores indexados no Pinecone: {total_upserted}")
    logger.info("=" * 70)

    return {
        "status": "success",
        "total_files": len(pdf_files),
        "processed_files": processed_files,
        "failed_files": failed_files,
        "total_chunks": total_chunks,
        "total_vectors_upserted": total_upserted,
        "elapsed_seconds": round(elapsed_time, 2)
    }


def main():
    parser = argparse.ArgumentParser(description="Pipeline de Ingestão de Materiais Didáticos VERA (R2 -> Pinecone)")
    parser.add_argument("--prefix", type=str, default="", help="Prefixo opcional de busca no bucket R2")
    parser.add_argument("--batch-size", type=int, default=50, help="Tamanho do lote de embeddings e upsert (padrão: 50)")
    parser.add_argument("--dry-run", action="store_true", help="Executa o parsing e chunking sem enviar ao Pinecone")
    parser.add_argument("--test-query", type=str, default=None, help="Executa uma busca teste no Pinecone após a ingestão")

    args = parser.parse_args()

    results = run_materials_ingestion(
        prefix=args.prefix,
        batch_size=args.batch_size,
        dry_run=args.dry_run
    )

    if args.test_query:
        logger.info(f"\nTestando consulta no Pinecone: '{args.test_query}'...")
        vs = PineconeVectorStore()
        search_res = vs.search(query=args.test_query, namespace=settings.NAMESPACE_MATERIAIS_DIDATICOS, top_k=3)
        for i, res in enumerate(search_res, 1):
            logger.info(f"\n[Resultado {i} - Score: {res['score']:.4f}]")
            logger.info(f"Documento: {res['metadata'].get('document_name')} | Tópico: {res['metadata'].get('topic')}")
            logger.info(f"Trecho: {res['text'][:250]}...")


if __name__ == "__main__":
    main()
