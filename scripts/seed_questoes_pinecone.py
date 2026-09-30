#!/usr/bin/env python3
"""
Script de Carga e Vetorização de Questões Históricas do ENEM no Pinecone.
Popula o namespace 'questoes_enem' no índice vetorial do Pinecone a partir do
arquivo CSV 'data/itens_prova_2009_2024_enriquecido.csv'.

Os vetores representam os enunciados das questões históricas (com modelo multilingual-e5-large),
e as alternativas, gabarito, habilidade e metadados da TRI são anexados como metadados.
"""

import os
import sys
import csv
import time
import json
import logging
import argparse
from typing import List, Dict, Any, Optional

# Adiciona o diretório raiz ao PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.services.vectorstore import PineconeVectorStore, EmbeddingService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("vera.seed_questoes_pinecone")


def parse_csv_questions(csv_path: str) -> List[Dict[str, Any]]:
    """
    Lê o CSV enriquecido do ENEM e retorna a lista de questões estruturadas para vetorização.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Arquivo CSV não encontrado: {csv_path}")

    items: List[Dict[str, Any]] = []

    def parse_float(val: Optional[str]) -> float:
        if not val or val.strip() == "":
            return 0.0
        try:
            return float(val.strip().replace(",", "."))
        except ValueError:
            return 0.0

    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for line_num, row in enumerate(reader, start=2):
            try:
                co_item = int(row["CO_ITEM"].strip())
                ano = int(row["ANO_APLICACAO"].strip())
                hab_num = int(row["CO_HABILIDADE"].strip())
                hab_code = f"H{hab_num:02d}"
                gabarito = row["TX_GABARITO"].strip().upper()
                enunciado = row["DESC_ENUNCIADO"].strip()

                if not enunciado:
                    logger.warning(f"Linha {line_num} (CO_ITEM={co_item}) sem enunciado. Ignorando.")
                    continue

                alt_a = row.get("DESC_ALTER_A", "").strip()
                alt_b = row.get("DESC_ALTER_B", "").strip()
                alt_c = row.get("DESC_ALTER_C", "").strip()
                alt_d = row.get("DESC_ALTER_D", "").strip()
                alt_e = row.get("DESC_ALTER_E", "").strip()

                co_posicao = int(row["CO_POSICAO"].strip()) if row.get("CO_POSICAO", "").strip().isdigit() else 0
                co_prova = int(row["CO_PROVA"].strip()) if row.get("CO_PROVA", "").strip().isdigit() else 0
                tx_cor = row.get("TX_COR", "").strip()
                tp_aplicacao = row.get("TP_APLICACAO", "").strip()
                ref_arquivo_pdf = row.get("REF_ARQUIVO_PDF", "").strip()
                in_item_imagem = int(row.get("IN_ITEM_IMAGEM", "0").strip()) if row.get("IN_ITEM_IMAGEM", "").strip().isdigit() else 0

                # Metadados estritamente compatíveis com tipos primitivos do Pinecone
                # (str, int, float, bool, List[str] - sem dicts aninhados)
                metadata = {
                    "co_item": co_item,
                    "ano": ano,
                    "habilidade_codigo": hab_code,
                    "gabarito": gabarito,
                    "alt_a": alt_a,
                    "alt_b": alt_b,
                    "alt_c": alt_c,
                    "alt_d": alt_d,
                    "alt_e": alt_e,
                    "co_posicao": co_posicao,
                    "co_prova": co_prova,
                    "tx_cor": tx_cor,
                    "tp_aplicacao": tp_aplicacao,
                    "ref_arquivo_pdf": ref_arquivo_pdf,
                    "in_item_imagem": in_item_imagem,
                    "tri_param_a": parse_float(row.get("NU_PARAM_A")),
                    "tri_param_b": parse_float(row.get("NU_PARAM_B")),
                    "tri_param_c": parse_float(row.get("NU_PARAM_C")),
                    "text": enunciado[:3000]
                }

                items.append({
                    "id": f"enem_{ano}_{co_item}",
                    "text": enunciado,
                    "metadata": metadata
                })

            except Exception as e:
                logger.warning(f"Erro na linha {line_num} (CO_ITEM={row.get('CO_ITEM')}): {e}")

    return items


def seed_questoes_pinecone(
    csv_path: str = "data/itens_prova_2009_2024_enriquecido.csv",
    namespace: str = settings.NAMESPACE_QUESTOES_ENEM,
    batch_size: int = 50,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Executa a carga e vetorização de questões históricas no namespace 'questoes_enem' do Pinecone.
    """
    start_time = time.time()
    logger.info("=" * 80)
    logger.info(f"CARGA DE QUESTÕES HISTÓRICAS DO ENEM NO PINECONE (Namespace: '{namespace}')")
    logger.info("=" * 80)

    # 1. Parsing do CSV
    logger.info(f"Lendo itens do CSV em: {csv_path}...")
    chunks = parse_csv_questions(csv_path)
    total_items = len(chunks)
    logger.info(f"Total de {total_items} questões históricas válidas extraídas com sucesso.")

    if total_items == 0:
        return {"status": "warning", "message": "Nenhum item válido encontrado no CSV.", "total_upserted": 0}

    # 2. Upsert no Pinecone
    total_upserted = 0
    if dry_run:
        logger.info("[DRY-RUN] Simulação concluída. Nenhum vetor enviado ao Pinecone.")
    else:
        logger.info(f"Iniciando vetorização (E5-large) e envio ao namespace '{namespace}' em lotes de {batch_size}...")
        vector_store = PineconeVectorStore()
        total_upserted = vector_store.upsert_chunks(
            chunks=chunks,
            namespace=namespace,
            batch_size=batch_size
        )
        logger.info(f"Sucesso: {total_upserted}/{total_items} vetores indexados no namespace '{namespace}'.")

    elapsed_time = time.time() - start_time
    logger.info("=" * 80)
    logger.info(f"CARGA CONCLUÍDA EM {elapsed_time:.2f}s | Vetores upserted: {total_upserted}")
    logger.info("=" * 80)

    return {
        "status": "success",
        "total_items": total_items,
        "total_upserted": total_upserted,
        "namespace": namespace,
        "elapsed_seconds": round(elapsed_time, 2)
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Indexador de Questões Históricas do ENEM no Pinecone (Namespace questoes_enem)"
    )
    parser.add_argument(
        "--csv-path",
        type=str,
        default="data/itens_prova_2009_2024_enriquecido.csv",
        help="Caminho do CSV de itens enriquecidos do ENEM."
    )
    parser.add_argument(
        "--namespace",
        type=str,
        default=settings.NAMESPACE_QUESTOES_ENEM,
        help="Nome do namespace no Pinecone (padrão: 'questoes_enem')."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Tamanho do lote para envio ao Pinecone (padrão: 50)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Executa a extração e validação dos dados sem enviar ao Pinecone."
    )
    parser.add_argument(
        "--test-query",
        type=str,
        default=None,
        help="Executa uma busca teste no namespace após a indexação."
    )
    parser.add_argument(
        "--test-habilidade",
        type=str,
        default=None,
        help="Testa o resgate top-3 para uma habilidade (ex: 'H01') usando a query do Claude."
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    res = seed_questoes_pinecone(
        csv_path=args.csv_path,
        namespace=args.namespace,
        batch_size=args.batch_size,
        dry_run=args.dry_run
    )

    if not args.dry_run and (args.test_query or args.test_habilidade):
        vs = PineconeVectorStore()

        query_text = args.test_query
        if args.test_habilidade:
            hab_target = args.test_habilidade.strip().upper()
            if not hab_target.startswith("H"):
                hab_target = f"H{int(hab_target):02d}"
            elif len(hab_target) == 2:
                hab_target = f"H0{hab_target[1]}"

            queries_file = "data/habilidades_queries.json"
            if os.path.exists(queries_file):
                with open(queries_file, "r", encoding="utf-8") as f:
                    queries_data = json.load(f)
                matched = next((item for item in queries_data if item.get("habilidade_codigo") == hab_target or item.get("habilidade") == hab_target), None)
                if matched:
                    query_text = matched.get("query")
                    logger.info(f"\n[TESTE HABILIDADE {hab_target}] Usando query expandida do Claude:\n'{query_text}'")

        if query_text:
            logger.info(f"\nTestando busca semântica no Pinecone (top 3) com a query:\n'{query_text}'...")
            results = vs.search(
                query=query_text,
                namespace=args.namespace,
                top_k=3
            )
            print("\n" + "=" * 80)
            print(f" RESULTADOS DA BUSCA SEMÂNTICA NO PINECONE (Top {len(results)})")
            print("=" * 80)
            for idx, r in enumerate(results, 1):
                meta = r.get("metadata", {})
                enunciado = meta.get("text", "")
                resumo = (enunciado[:120] + "...") if len(enunciado) > 120 else enunciado
                print(f"[{idx}] Score: {r['score']:.4f} | Ano: {meta.get('ano')} | CO_ITEM: {meta.get('co_item')} | Hab: {meta.get('habilidade_codigo')} | Gab: {meta.get('gabarito')}")
                print(f"    Enunciado: {resumo}")
                print(f"    Alt A: {meta.get('alt_a')[:60]}... | Alt B: {meta.get('alt_b')[:60]}...")
            print("=" * 80)
