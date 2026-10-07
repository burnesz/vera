#!/usr/bin/env python3
"""
clean_tiny_chunks.py — Limpeza cirúrgica de fragmentos residuais (< 15 palavras) no Pinecone.
Varre o namespace 'materiais_didaticos' e deleta vetores com textos minúsculos/inúteis.
"""

import os
import sys
import logging
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from pinecone import Pinecone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vera.clean_chunks")


def clean_tiny_chunks(namespace: str = settings.NAMESPACE_MATERIAIS_DIDATICOS, min_words: int = 15, dry_run: bool = False):
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    index = pc.Index(settings.PINECONE_INDEX_NAME)

    logger.info(f"Iniciando varredura no namespace '{namespace}' (limiar: < {min_words} palavras, dry_run={dry_run})...")

    ids_to_delete = []
    scanned = 0

    for res in index.list(namespace=namespace):
        vec_ids = [v.id for v in res.vectors] if hasattr(res, 'vectors') else list(res)
        for i in range(0, len(vec_ids), 100):
            sub = vec_ids[i:i+100]
            f = index.fetch(ids=sub, namespace=namespace)
            scanned += len(f.vectors)
            for vid, vec in f.vectors.items():
                meta = vec.metadata or {}
                text = (meta.get("text") or "").strip()
                words = text.split()
                if len(words) < min_words:
                    ids_to_delete.append((vid, len(words), text, meta.get("document_name")))

    logger.info(f"Varredura concluída. {scanned} vetores analisados.")
    logger.info(f"Encontrados {len(ids_to_delete)} fragmentos minúsculos (< {min_words} palavras).")

    for vid, w_count, text, doc in ids_to_delete:
        logger.info(f"  - [{vid}] ({doc}) {w_count} palavras: {text!r}")

    if not dry_run and ids_to_delete:
        del_ids = [x[0] for x in ids_to_delete]
        for i in range(0, len(del_ids), 100):
            batch = del_ids[i:i+100]
            index.delete(ids=batch, namespace=namespace)
        logger.info(f"Sucesso: {len(del_ids)} vetores minúsculos deletados do Pinecone!")
    elif dry_run:
        logger.info("Modo dry-run: nenhum vetor foi excluído.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Limpeza de chunks minúsculos no Pinecone")
    parser.add_argument("--namespace", default=settings.NAMESPACE_MATERIAIS_DIDATICOS)
    parser.add_argument("--min-words", type=int, default=15)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    clean_tiny_chunks(namespace=args.namespace, min_words=args.min_words, dry_run=args.dry_run)
