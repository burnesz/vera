#!/usr/bin/env python3
"""
Experimento 1 — Qualidade da recuperação no namespace `materiais_didaticos` (RN-AVAL01).

Executa as 126 queries do gabarito (`evaluation/data/retrieval_gold.json`) em:
  - sistemas: e5_denso (produção), e5_rerank (E5 + bge-reranker-v2-m3), bm25 (baseline lexical)
  - cenários: fechado (filtro nos 63 PDFs ENEM_MAT_*) e completo (namespace inteiro)

Saída em `evaluation/results/<nome>-<data>/`: rankings brutos (runs/*.jsonl), métricas por
query (CSV), resumo com IC 95% (JSON e Markdown) e comparações pareadas.
Se o gabarito não estiver congelado, a pasta recebe o prefixo `piloto-`.

Exemplos:
    ./.venv/bin/python scripts/run_retrieval_eval.py --limit 5            # teste de fumaça
    ./.venv/bin/python scripts/run_retrieval_eval.py                      # rodada completa
    ./.venv/bin/python scripts/run_retrieval_eval.py --sistemas e5_denso,bm25 --cenarios fechado
    ./.venv/bin/python scripts/run_retrieval_eval.py --recalcular evaluation/results/<pasta>
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings  # noqa: E402
from evaluation import retrieval_experiment as rx  # noqa: E402

SYSTEMS = ("e5_denso", "e5_rerank", "bm25")
SCENARIOS = ("fechado", "completo")
# Hipóteses pré-registradas: o sistema de produção contra a baseline lexical e o reranker contra a produção.
PAIRS = [("e5_denso", "bm25"), ("e5_rerank", "e5_denso"), ("e5_rerank", "bm25")]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
for noisy in ("httpx", "urllib3", "sentence_transformers", "pinecone"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
logger = logging.getLogger("run_retrieval_eval")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sistemas", default=",".join(SYSTEMS))
    p.add_argument("--cenarios", default=",".join(SCENARIOS))
    p.add_argument("--limit", type=int, default=None, help="Usa só as N primeiras queries (teste de fumaça).")
    p.add_argument("--recalcular", metavar="PASTA", default=None,
                   help="Recalcula métricas a partir de runs/*.jsonl já salvos, sem consultar o Pinecone.")
    p.add_argument("--atualizar-corpus", action="store_true", help="Baixa de novo os chunks usados pelo BM25.")
    p.add_argument("--bootstrap", type=int, default=10_000, help="Reamostragens do bootstrap e da permutação.")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def main():
    args = parse_args()
    systems = [s for s in args.sistemas.split(",") if s]
    scenarios = [s for s in args.cenarios.split(",") if s]
    for s in systems:
        if s not in SYSTEMS:
            sys.exit(f"Sistema desconhecido: {s}. Opções: {SYSTEMS}")
    for c in scenarios:
        if c not in SCENARIOS:
            sys.exit(f"Cenário desconhecido: {c}. Opções: {SCENARIOS}")

    gold = rx.load_json(rx.GOLD_PATH)
    frozen = bool(gold.get("congelado"))
    if not frozen:
        logger.warning("Gabarito NÃO congelado: os resultados serão marcados como piloto (RN-AVAL02).")
    items = rx.gold_items(gold)
    if args.limit:
        items = items[:args.limit]
    counts = rx.chunk_counts(gold)
    namespace = settings.NAMESPACE_MATERIAIS_DIDATICOS

    if args.recalcular:
        run_dir = os.path.abspath(args.recalcular)
        manifest = rx.load_json(os.path.join(run_dir, "manifest.json"))
    else:
        run_dir = rx.new_run_dir("recuperacao" if not args.limit else "fumaca-recuperacao", frozen)
        manifest = {
            "experimento": "recuperacao_materiais_didaticos",
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "git_commit": rx.git_commit(),
            "gabarito_versao": gold.get("versao"),
            "gabarito_congelado": frozen,
            "gabarito_sha256": rx.file_sha256(rx.GOLD_PATH),
            "n_queries": len(items),
            "namespace": namespace,
            "indice_pinecone": settings.PINECONE_INDEX_NAME,
            "modelo_embeddings": settings.EMBEDDING_MODEL_NAME,
            "reranker": "BAAI/bge-reranker-v2-m3",
            "bm25": {"k1": 1.2, "b": 0.75, "tokenizacao": "minusculas, sem acentos, stopwords PT, sem stemming"},
            "profundidade_ranking": rx.CANDIDATE_DEPTH,
            "k_operacional": rx.OPERATIONAL_K,
            "sistemas": systems,
            "cenarios": scenarios,
            "bootstrap": args.bootstrap,
            "seed": args.seed,
        }

        manifest["ambiente_ao_iniciar"] = rx.environment_info()
        from app.services.vectorstore import PineconeVectorStore
        vs = PineconeVectorStore()
        try:
            ns = vs.index.describe_index_stats().namespaces[namespace]
            manifest["vetores_no_namespace"] = ns["vector_count"] if isinstance(ns, dict) else ns.vector_count
        except Exception as e:  # informativo; não deve interromper o experimento
            manifest["vetores_no_namespace"] = f"indisponivel ({e})"

        corpus_all = None
        if "bm25" in systems:
            corpus_all = rx.load_or_fetch_corpus(vs.index, namespace, refresh=args.atualizar_corpus)
            manifest["chunks_corpus_bm25_completo"] = len(corpus_all)

        gold_names = rx.gold_document_names(gold)
        gold_set = set(gold_names)
        for scenario in scenarios:
            filt = {"document_name": {"$in": gold_names}} if scenario == "fechado" else None
            for system in systems:
                logger.info(f"Cenário '{scenario}' — sistema '{system}' — {len(items)} queries")
                if system == "e5_denso":
                    fn = rx.make_dense_retriever(vs, namespace, filt)
                elif system == "e5_rerank":
                    fn = rx.make_rerank_retriever(vs, namespace, filt)
                else:
                    corpus = [c for c in corpus_all if scenario == "completo" or c["document_name"] in gold_set]
                    manifest[f"chunks_corpus_bm25_{scenario}"] = len(corpus)
                    fn = rx.make_bm25_retriever(corpus)
                records = rx.run_system(fn, items)
                rx.save_jsonl(os.path.join(run_dir, "runs", f"{scenario}__{system}.jsonl"), records)

        manifest["ambiente_ao_final"] = rx.environment_info()
        manifest["dispositivo_embeddings"] = vs.embedding_service.device
        with open(os.path.join(run_dir, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2)

    analyze(run_dir, manifest, items, counts, scenarios, systems, args)


def analyze(run_dir, manifest, items, counts, scenarios, systems, args):
    rows_all, summaries, comparisons = [], {}, {}
    breakdowns = {"tipo de query": {}, "eixo temático": {}, "tamanho do documento": {}}
    for scenario in scenarios:
        rows_by_system = {}
        for system in systems:
            path = os.path.join(run_dir, "runs", f"{scenario}__{system}.jsonl")
            if not os.path.exists(path):
                logger.warning(f"Rodada ausente: {path}")
                continue
            rows = rx.per_query_metrics(rx.load_jsonl(path), items, counts)
            label = f"{scenario}/{system}"
            rows_by_system[system] = rows
            summaries[label] = rx.summarize(rows, n_resamples=args.bootstrap, seed=args.seed)
            breakdowns["tipo de query"][label] = rx.summarize_by(rows, "tipo")
            breakdowns["eixo temático"][label] = rx.summarize_by(rows, "eixo")
            breakdowns["tamanho do documento"][label] = rx.summarize_by(rows, "tamanho")
            rows_all += [{"cenario": scenario, "sistema": system, **r} for r in rows]
        pairs = [p for p in PAIRS if p[0] in rows_by_system and p[1] in rows_by_system]
        if pairs:
            comparisons[f"cenário {scenario}"] = rx.compare_systems(
                rows_by_system, pairs=pairs, n_resamples=args.bootstrap, seed=args.seed)

    rx.write_csv(os.path.join(run_dir, "metricas_por_query.csv"), rows_all)
    with open(os.path.join(run_dir, "resumo.json"), "w", encoding="utf-8") as fh:
        json.dump({"resumo": summaries, "recortes": breakdowns, "comparacoes": comparisons},
                  fh, ensure_ascii=False, indent=2)
    report = rx.ExperimentReport("Experimento 1 — Recuperação em materiais_didaticos",
                                 manifest, summaries, breakdowns, comparisons)
    with open(os.path.join(run_dir, "relatorio.md"), "w", encoding="utf-8") as fh:
        fh.write(report.to_markdown())
    print(report.to_markdown())
    print(f"\nResultados salvos em: {run_dir}")


if __name__ == "__main__":
    main()
