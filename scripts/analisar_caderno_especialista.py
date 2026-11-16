"""
Análise das fichas preenchidas do caderno de feedback e tutoria (montar_caderno_especialista.py).

Para cada fluxo: média da VERA e da baseline em cada critério, diferença, teste de Wilcoxon pareado (por par, com
a média dos avaliadores), preferência geral e a regra RN-AVAL01 (VERA >= baseline em todos os critérios).
Grava <rodada>/caderno/resultados_especialista.md.

Uso:
    ./.venv/bin/python scripts/analisar_caderno_especialista.py <rodada> ficha_prof1.csv [ficha_prof2.csv ...]
"""
import os
import sys
import csv
import json
import argparse
from statistics import mean
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from evaluation import likert_rubric as lr  # noqa: E402


def fmt(x, casas=2):
    return f"{x:.{casas}f}".replace(".", ",")


def wilcoxon_p(x, y):
    if len(x) < 2 or all(a == b for a, b in zip(x, y)):
        return None
    from scipy.stats import wilcoxon
    return float(wilcoxon(x, y, zero_method="zsplit").pvalue)


def tabela_fluxo(fluxo, registros):
    por_par = defaultdict(list)
    for r in registros:
        if r["fluxo"] == fluxo:
            por_par[r["par_original"]].append(r)
    titulo = lr.FLUXOS[fluxo][1].split("— ")[-1]
    linhas = [f"## {titulo} ({len(por_par)} pares avaliados)", "",
              "| Critério | VERA (média) | Baseline (média) | Diferença | p (Wilcoxon) | VERA ≥ baseline? |",
              "|---|---|---|---|---|---|"]
    aceita = bool(por_par)
    for c, _ in lr.CRITERIOS:
        x, y = [], []
        for regs in por_par.values():
            v = [r["vera"][c] for r in regs if c in r.get("vera", {})]
            b = [r["baseline"][c] for r in regs if c in r.get("baseline", {})]
            if v and b:
                x.append(mean(v))
                y.append(mean(b))
        if not x:
            linhas.append(f"| {c} | — | — | — | — | — |")
            aceita = False
            continue
        p = wilcoxon_p(x, y)
        ok = mean(x) >= mean(y)
        aceita &= ok
        linhas.append(f"| {c} | {fmt(mean(x))} | {fmt(mean(y))} | {'+' if mean(x) >= mean(y) else ''}"
                      f"{fmt(mean(x) - mean(y))} | {'—' if p is None else fmt(p, 3)} | {'sim' if ok else '**não**'} |")
    prefs = [r["preferencia"] for regs in por_par.values() for r in regs if r["preferencia"]]
    if prefs:
        cont = {k: sum(p == k for p in prefs) for k in ("vera", "baseline", "empate")}
        linhas += ["", f"**Preferência** ({len(prefs)} julgamentos): VERA {cont['vera']}, baseline {cont['baseline']}, "
                   f"empate {cont['empate']}."]
    linhas += ["", f"**RN-AVAL01** (VERA ≥ baseline na média de todos os critérios): "
               f"{'atendida' if aceita else 'não atendida'}.", ""]
    return linhas


def main():
    parser = argparse.ArgumentParser(description="Analisa as fichas do caderno de feedback e tutoria.")
    parser.add_argument("rodada")
    parser.add_argument("fichas", nargs="+")
    args = parser.parse_args()

    pasta = os.path.join(args.rodada, "caderno")
    with open(os.path.join(pasta, "chave_caderno.json"), encoding="utf-8") as f:
        chave = json.load(f)
    fichas = {}
    for n, caminho in enumerate(args.fichas, 1):
        with open(caminho, encoding="utf-8-sig", newline="") as f:
            lidas = lr.ler_ficha(list(csv.DictReader(f, delimiter=";")), arquivo=f"avaliador{n}")
        for id_par, por_av in lidas.items():
            fichas.setdefault(id_par, {}).update(por_av)
    registros = lr.desmascarar(chave, fichas)
    avaliadores = sorted({r["avaliador"] for r in registros})

    linhas = ["# Avaliação por especialista: feedback e tutoria (VERA × baseline zero-shot)", "",
              f"Rodada `{os.path.basename(os.path.normpath(args.rodada))}`; avaliadores: {', '.join(avaliadores)}. "
              "Com mais de um avaliador, cada par usa a média das notas. Wilcoxon pareado bicaudal "
              "(`zero_method=zsplit`).", ""]
    for fluxo in lr.FLUXOS:
        linhas += tabela_fluxo(fluxo, registros)
    saida = os.path.join(pasta, "resultados_especialista.md")
    with open(saida, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))
    print("\n".join(linhas))
    print(f"Gravado em {os.path.relpath(saida, ROOT)}")


if __name__ == "__main__":
    main()
