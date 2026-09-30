#!/usr/bin/env python3
"""
CLI de Busca Semântica no Pinecone para o projeto VERA.
Permite consultar os namespaces 'materiais_didaticos' e 'questoes_enem'
retornando os trechos e metadados na íntegra (sem truncamento).

Exemplos de uso:
    ./.venv/bin/python scripts/search_pinecone.py "teorema de pitágoras no triângulo retângulo"
    ./.venv/bin/python scripts/search_pinecone.py "probabilidade condicional" --namespace materiais_didaticos --top-k 5
    ./.venv/bin/python scripts/search_pinecone.py "progressão aritmética" --namespace questoes_enem --top-k 2
    ./.venv/bin/python scripts/search_pinecone.py "geometria plana" --json
"""

import os
import sys
import json
import argparse
from typing import List, Dict, Any

# Adiciona a raiz do projeto ao sys.path para importar app.*
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.services.vectorstore import PineconeVectorStore


def format_text_box(title: str, content: str, width: int = 80) -> str:
    border = "-" * width
    return f"{border}\n{title.upper()}\n{border}\n{content}\n{border}"


def main():
    parser = argparse.ArgumentParser(
        description="Consulta vetorial no Pinecone retornando trechos e metadados na íntegra."
    )
    parser.add_argument(
        "query",
        type=str,
        nargs="?",
        default=None,
        help="Texto da consulta semântica (ex: 'função afim e taxa de variação')"
    )
    parser.add_argument(
        "-q", "--query-param",
        dest="query_flag",
        type=str,
        default=None,
        help="Texto alternativo para consulta via flag (-q / --query-param)"
    )
    parser.add_argument(
        "-n", "--namespace",
        type=str,
        default=settings.NAMESPACE_MATERIAIS_DIDATICOS,
        help=f"Namespace do Pinecone a ser consultado (ex: '{settings.NAMESPACE_MATERIAIS_DIDATICOS}', 'materiais_didaticos_v2', '{settings.NAMESPACE_QUESTOES_ENEM}')"
    )
    parser.add_argument(
        "-k", "--top-k",
        type=int,
        default=4,
        help="Quantidade de resultados a retornar (padrão: 4)"
    )
    parser.add_argument(
        "--rerank",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Ativa ou desativa o re-ranqueamento com BAAI/bge-reranker-v2-m3 (padrão: ativo)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Retorna a saída formatada em JSON bruto na saída padrão."
    )

    args = parser.parse_args()

    search_query = args.query or args.query_flag
    if not search_query or not search_query.strip():
        parser.error("A consulta (query) é obrigatória. Exemplo: ./.venv/bin/python scripts/search_pinecone.py 'sua pergunta'")

    search_query = search_query.strip()

    if not args.json:
        print("=" * 80)
        print(f"🔍 BUSCA SEMÂNTICA NO PINECONE")
        print(f"• Query:      \"{search_query}\"")
        print(f"• Namespace:  {args.namespace}")
        print(f"• Top-K:      {args.top_k}")
        print(f"• Rerank:     {'Ativo (BAAI/bge-reranker-v2-m3)' if args.rerank else 'Desativado (cosseno puro)'}")
        print("=" * 80)
        print("Carregando modelo de embeddings e consultando índice...")

    try:
        vs = PineconeVectorStore()
        results = vs.search(
            query=search_query,
            namespace=args.namespace,
            top_k=args.top_k,
            rerank=args.rerank,
            rerank_top_k=args.top_k
        )
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}, ensure_ascii=False, indent=2))
        else:
            print(f"\n❌ Erro ao consultar o Pinecone: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    if not results:
        print("\n⚠️  Nenhum resultado encontrado para a consulta informada.")
        return

    print(f"\n✅ {len(results)} resultado(s) recuperado(s):\n")

    for idx, item in enumerate(results, 1):
        meta = item.get("metadata", {})
        score = item.get("score", 0.0)
        doc_id = item.get("id", "N/A")
        full_text = item.get("text", "") or meta.get("text", "")

        score_label = f"Score Rerank: {score:.4f} (Original Pinecone: {item.get('original_score', 0.0):.4f})" if item.get("reranked") else f"Score de Similaridade: {score:.4f}"

        print("=" * 80)
        print(f"📌 RESULTADO {idx}/{len(results)} — {score_label} (ID: {doc_id})")
        print("=" * 80)

        # Metadados específicos do namespace
        if args.namespace == settings.NAMESPACE_MATERIAIS_DIDATICOS:
            doc_name = meta.get("document_name") or meta.get("document") or "N/A"
            title = meta.get("title") or "N/A"
            topic = meta.get("topic") or "N/A"
            page = meta.get("page_number") or meta.get("page") or "N/A"

            print(f"• Documento:  {doc_name}")
            print(f"• Título:     {title}")
            print(f"• Tópico:     {topic}")
            print(f"• Página:     {page}")
            print("\n--- [TRECHO DIDÁTICO NA ÍNTEGRA] ---")
            print(full_text.strip() if full_text else "(Texto vazio)")

        elif args.namespace == settings.NAMESPACE_QUESTOES_ENEM:
            ano = meta.get("ano", "N/A")
            co_item = meta.get("co_item", "N/A")
            hab = meta.get("habilidade_codigo", "N/A")
            gabarito = meta.get("gabarito", "N/A")

            print(f"• Edição ENEM:   {ano}")
            print(f"• Código Item:   {co_item}")
            print(f"• Habilidade:    {hab}")
            print(f"• Gabarito:      {gabarito}")
            print("\n--- [ENUNCIADO DA QUESTÃO NA ÍNTEGRA] ---")
            print(full_text.strip() if full_text else "(Enunciado vazio)")

            # Se houver alternativas nos metadados
            alt_a = meta.get("alt_a")
            if alt_a:
                print("\n--- [ALTERNATIVAS] ---")
                for letter in ["a", "b", "c", "d", "e"]:
                    alt_val = meta.get(f"alt_{letter}", "")
                    mark = " [CORRETA]" if letter.upper() == str(gabarito).upper() else ""
                    print(f"  {letter.upper()}) {alt_val}{mark}")

        else:
            print("Metadados:", json.dumps(meta, ensure_ascii=False, indent=2))
            print("\n--- [TEXTO NA ÍNTEGRA] ---")
            print(full_text.strip())

        print("\n")


if __name__ == "__main__":
    main()
