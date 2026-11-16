#!/usr/bin/env python3
"""
Validação do gabarito por um segundo avaliador (concordância inter-anotadores).

Fluxo (pooling no estilo TREC):
  1. `exportar`: monta o pool de pares (query, PDF) = documentos do gabarito + os PDFs mais bem
     ranqueados pelos sistemas na rodada piloto. A planilha sai embaralhada e SEM o grau do
     gabarito, para julgamento cego.
  2. O segundo avaliador preenche a coluna `grau` com 0, 1 ou 2 (critérios na nota de avaliação).
  3. `calcular`: kappa de Cohen (simples e ponderado linear) entre o gabarito e o avaliador,
     matriz de confusão, divergências e possíveis relevantes ausentes do gabarito.

Exemplos:
    ./.venv/bin/python scripts/relevance_agreement.py exportar --rodada evaluation/results/piloto-recuperacao-<data>
    ./.venv/bin/python scripts/relevance_agreement.py calcular --anotacao evaluation/data/anotacao/pool_avaliador2.csv
"""

import argparse
import csv
import glob
import os
import random
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from evaluation import quantitative as q  # noqa: E402
from evaluation import retrieval_experiment as rx  # noqa: E402

DEFAULT_DIR = os.path.join(rx.ROOT, "evaluation", "data", "anotacao")


def top_documents(ranking, n):
    seen = []
    for h in ranking:
        name = h["document_name"]
        if name not in seen:
            seen.append(name)
        if len(seen) == n:
            break
    return seen


def exportar(args):
    gold = rx.load_json(rx.GOLD_PATH)
    docs = {d["document_name"]: d for d in gold["documentos"]}
    pool = {qq["id"]: set(qq["relevantes"]) for qq in gold["queries"]}
    run_files = sorted(glob.glob(os.path.join(args.rodada, "runs", "*.jsonl")))
    if not run_files:
        sys.exit(f"Nenhuma rodada encontrada em {args.rodada}/runs")
    for path in run_files:
        for rec in rx.load_jsonl(path):
            # Só PDFs do corpus julgado; chunks dos livros TEO_* etc. ficam como não julgados.
            pool[rec["id"]].update(d for d in top_documents(rec["ranking"], args.top) if d in docs)

    queries = {qq["id"]: qq for qq in gold["queries"]}
    rows = [{"query_id": qid, "query": queries[qid]["query"], "documento": d,
             "artigo_wikipedia": docs[d]["artigo_wikipedia"], "grau": ""}
            for qid, ds in pool.items() for d in sorted(ds)]
    random.Random(args.seed).shuffle(rows)
    for i, r in enumerate(rows, 1):
        r["par_id"] = f"P{i:04d}"
    os.makedirs(os.path.dirname(args.saida), exist_ok=True)
    with open(args.saida, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["par_id", "query_id", "query", "documento", "artigo_wikipedia", "grau"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} pares exportados para {args.saida} ({len(run_files)} rodadas no pool, top-{args.top}).")


def calcular(args):
    gold = rx.load_json(rx.GOLD_PATH)
    rel = {qq["id"]: qq["relevantes"] for qq in gold["queries"]}
    with open(args.anotacao, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    a_gold, a_ann, missing, diverg = [], [], [], []
    for r in rows:
        if r["grau"].strip() == "":
            missing.append(r["par_id"])
            continue
        g_ann = int(r["grau"])
        if g_ann not in (0, 1, 2):
            sys.exit(f"Grau inválido em {r['par_id']}: {g_ann}")
        g_gold = int(rel[r["query_id"]].get(r["documento"], 0))
        a_gold.append(g_gold)
        a_ann.append(g_ann)
        if g_gold != g_ann:
            diverg.append({**r, "grau_gabarito": g_gold})
    if missing:
        print(f"AVISO: {len(missing)} pares sem grau foram ignorados.")
    if not a_gold:
        sys.exit("Nenhum par anotado.")

    k = q.cohen_kappa(a_gold, a_ann)
    kw = q.cohen_kappa(a_gold, a_ann, weights="linear")
    agree = sum(1 for x, y in zip(a_gold, a_ann) if x == y) / len(a_gold)
    print(f"Pares anotados: {len(a_gold)}")
    print(f"Concordância observada: {100 * agree:.1f}%")
    print(f"Kappa de Cohen: {k:.3f}")
    print(f"Kappa ponderado linear: {kw:.3f}")
    print("\nMatriz de confusão (linhas = gabarito, colunas = avaliador):")
    print("      0     1     2")
    for gg in (0, 1, 2):
        print(f"{gg}  " + " ".join(f"{sum(1 for x, y in zip(a_gold, a_ann) if x == gg and y == aa):5d}" for aa in (0, 1, 2)))

    out = os.path.splitext(args.anotacao)[0] + "_divergencias.csv"
    if diverg:
        rx.write_csv(out, diverg)
        novos = sum(1 for d in diverg if d["grau_gabarito"] == 0)
        print(f"\n{len(diverg)} divergências salvas em {out} ({novos} possíveis relevantes ausentes do gabarito).")
        print("Resolva as divergências por consenso, atualize o gabarito e só então congele (RN-AVAL02).")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("exportar")
    e.add_argument("--rodada", required=True, help="Pasta de uma rodada de run_retrieval_eval.py")
    e.add_argument("--top", type=int, default=5, help="PDFs distintos do topo de cada rodada a incluir no pool")
    e.add_argument("--saida", default=os.path.join(DEFAULT_DIR, "pool.csv"))
    e.add_argument("--seed", type=int, default=42)
    c = sub.add_parser("calcular")
    c.add_argument("--anotacao", required=True, help="CSV do pool com a coluna 'grau' preenchida")
    args = p.parse_args()
    exportar(args) if args.cmd == "exportar" else calcular(args)


if __name__ == "__main__":
    main()
