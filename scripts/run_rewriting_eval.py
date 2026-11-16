#!/usr/bin/env python3
"""
Experimento 2 — Efeito do Query Rewriting (RN-CHAT01) na recuperação do Chat RAG.

Para cada diálogo de 2 turnos de `evaluation/data/rewriting_dialogs.json`, compara três consultas:
  - sem_reescrita: a mensagem de seguimento crua (ex.: "E a área total dele, como faço?")
  - com_reescrita: a mensagem reescrita pelo LLM via ChatService.rewrite_query (produção)
  - oraculo:       a consulta autocontida escrita à mão (limite superior)

A busca é a de produção (E5 denso, top-K). Exige o Ollama ativo (não usa mock_mode).

Exemplos:
    ./.venv/bin/python scripts/run_rewriting_eval.py
    ./.venv/bin/python scripts/run_rewriting_eval.py --cenario completo
    ./.venv/bin/python scripts/run_rewriting_eval.py --recalcular evaluation/results/<pasta>
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings  # noqa: E402
from evaluation import retrieval_experiment as rx  # noqa: E402

CONDITIONS = ("sem_reescrita", "com_reescrita", "oraculo")
PAIRS = [("com_reescrita", "sem_reescrita"), ("oraculo", "com_reescrita")]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
for noisy in ("httpx", "urllib3", "sentence_transformers", "pinecone"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
logger = logging.getLogger("run_rewriting_eval")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cenario", choices=("fechado", "completo"), default="fechado")
    p.add_argument("--recalcular", metavar="PASTA", default=None)
    p.add_argument("--limit", type=int, default=None, help="Usa só os N primeiros diálogos (teste de fumaça).")
    p.add_argument("--bootstrap", type=int, default=10_000)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def dialog_items(dialogs, gold, queries_by_condition):
    docs = {d["document_name"]: d for d in gold["documentos"]}
    items = {}
    for cond in CONDITIONS:
        items[cond] = [{
            "id": d["id"],
            "query": queries_by_condition[cond][d["id"]],
            "relevantes": rx.expand_with_segments(d["relevantes"], gold),
            "topico_alvo": d["topico_alvo"],
            "eixo": docs[d["topico_alvo"]]["eixo_tematico"],
        } for d in dialogs]
    return items


def main():
    args = parse_args()
    gold = rx.load_json(rx.GOLD_PATH)
    data = rx.load_json(rx.DIALOGS_PATH)
    dialogs = data["dialogos"][:args.limit] if args.limit else data["dialogos"]
    counts = rx.chunk_counts(gold)
    frozen = bool(gold.get("congelado")) and bool(data.get("congelado"))
    namespace = settings.NAMESPACE_MATERIAIS_DIDATICOS

    if args.recalcular:
        run_dir = os.path.abspath(args.recalcular)
        manifest = rx.load_json(os.path.join(run_dir, "manifest.json"))
        rewrites = {r["id"]: r for r in rx.load_jsonl(os.path.join(run_dir, "reescritas.jsonl"))}
    else:
        from app.schemas.chat import ChatMessage
        from app.services.chat_service import ChatService
        from app.services.llm_client import cliente_tutoria
        from app.services.vectorstore import PineconeVectorStore

        llm = cliente_tutoria()  # o mesmo modelo da tutora em produção (RN-INF07)
        health = llm.health_check()
        if not health.get("healthy") or health.get("status") == "mock":
            sys.exit(f"Ollama indisponível ({health.get('message', health.get('status'))}). "
                     "Este experimento exige o LLM real.")
        if not health.get("model_available", True):
            sys.exit(f"Modelo '{llm.model_name}' não encontrado no Ollama.")

        vs = PineconeVectorStore()
        chat = ChatService(llm_client=llm, vector_store=vs)
        run_dir = rx.new_run_dir("fumaca-reescrita" if args.limit else "reescrita", frozen)
        manifest = {
            "experimento": "query_rewriting",
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "git_commit": rx.git_commit(),
            "gabarito_versao": gold.get("versao"),
            "gabarito_congelado": frozen,
            "gabarito_sha256": rx.file_sha256(rx.GOLD_PATH),
            "dialogos_sha256": rx.file_sha256(rx.DIALOGS_PATH),
            "n_dialogos": len(dialogs),
            "cenario": args.cenario,
            "modelo_llm": llm.model_name,
            "modelo_embeddings": settings.EMBEDDING_MODEL_NAME,
            "sistema_busca": "e5_denso",
            "bootstrap": args.bootstrap,
            "seed": args.seed,
        }

        rewrites = {}
        for d in dialogs:
            history = [ChatMessage(role=m["role"], content=m["content"]) for m in d["historico"]]
            t0 = time.perf_counter()
            rewritten = chat.rewrite_query(d["mensagem"], history)
            rewrites[d["id"]] = {"id": d["id"], "mensagem": d["mensagem"], "reescrita": rewritten,
                                 "latencia_reescrita_ms": round((time.perf_counter() - t0) * 1000, 2)}
            logger.info(f"{d['id']}: '{d['mensagem']}' -> '{rewritten}'")
        rx.save_jsonl(os.path.join(run_dir, "reescritas.jsonl"), rewrites.values())

        filt = {"document_name": {"$in": rx.gold_document_names(gold)}} if args.cenario == "fechado" else None
        retrieve = rx.make_dense_retriever(vs, namespace, filt)
        queries = {
            "sem_reescrita": {d["id"]: d["mensagem"] for d in dialogs},
            "com_reescrita": {d["id"]: rewrites[d["id"]]["reescrita"] for d in dialogs},
            "oraculo": {d["id"]: d["consulta_oraculo"] for d in dialogs},
        }
        items = dialog_items(dialogs, gold, queries)
        for cond in CONDITIONS:
            logger.info(f"Condição '{cond}'")
            rx.save_jsonl(os.path.join(run_dir, "runs", f"{cond}.jsonl"), rx.run_system(retrieve, items[cond]))
        manifest["ambiente_ao_final"] = rx.environment_info()
        with open(os.path.join(run_dir, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2)

    queries = {
        "sem_reescrita": {d["id"]: d["mensagem"] for d in dialogs},
        "com_reescrita": {d["id"]: rewrites[d["id"]]["reescrita"] for d in dialogs},
        "oraculo": {d["id"]: d["consulta_oraculo"] for d in dialogs},
    }
    items = dialog_items(dialogs, gold, queries)
    rows_by_cond, summaries = {}, {}
    segments = rx.segment_index(gold)
    # No cenário fechado as apostilas não podem ser recuperadas: só os julgamentos por documento.
    fechado = manifest.get("cenario", args.cenario) == "fechado"
    for cond in CONDITIONS:
        cond_items = rx.without_segments(items[cond], segments) if fechado else items[cond]
        rows = rx.per_query_metrics(rx.load_jsonl(os.path.join(run_dir, "runs", f"{cond}.jsonl")), cond_items,
                                    counts, segments)
        rows_by_cond[cond] = rows
        summaries[cond] = rx.summarize(rows, n_resamples=args.bootstrap, seed=args.seed)
    comparisons = {"query rewriting": rx.compare_systems(
        rows_by_cond, pairs=PAIRS, n_resamples=args.bootstrap, seed=args.seed)}

    rx.write_csv(os.path.join(run_dir, "metricas_por_query.csv"),
                 [{"condicao": c, **r} for c, rows in rows_by_cond.items() for r in rows])
    with open(os.path.join(run_dir, "resumo.json"), "w", encoding="utf-8") as fh:
        json.dump({"resumo": summaries, "comparacoes": comparisons}, fh, ensure_ascii=False, indent=2)
    report = rx.ExperimentReport("Experimento 2 — Query Rewriting no Chat RAG", manifest, summaries, {}, comparisons)
    md = report.to_markdown()
    md += "\n## Reescritas produzidas pelo LLM\n\n| Diálogo | Mensagem | Reescrita |\n|---|---|---|\n"
    md += "\n".join(f"| {r['id']} | {r['mensagem']} | {r['reescrita']} |" for r in rewrites.values()) + "\n"
    with open(os.path.join(run_dir, "relatorio.md"), "w", encoding="utf-8") as fh:
        fh.write(md)
    print(md)
    print(f"\nResultados salvos em: {run_dir}")


if __name__ == "__main__":
    main()
