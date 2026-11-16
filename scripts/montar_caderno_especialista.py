"""
Monta o caderno cego de feedback e tutoria para o especialista (evaluation/likert_rubric.py), a partir de uma rodada
de scripts/run_baseline_pairs.py.

Grava em <rodada>/caderno/:
    caderno_explicacoes.html            o caderno (abre no navegador e imprime; precisa de internet para as fórmulas)
    ficha_respostas_explicacoes.csv     a planilha das notas (abre no Excel)
    chave_caderno.json                  qual condição é a Resposta 1 e a Resposta 2 de cada par (NÃO entregar)

Recusa a rodada se houver resposta vazia ou com fórmula sem fechar (sinal de corte pelo teto de tokens), a menos
que se passe --aceitar-suspeitas.

Uso:
    ./.venv/bin/python scripts/montar_caderno_especialista.py evaluation/results/pares-especialista-<data>
"""
import os
import sys
import csv
import json
import argparse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from evaluation import likert_rubric as lr  # noqa: E402


def ler_jsonl(caminho):
    with open(caminho, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    parser = argparse.ArgumentParser(description="Monta o caderno cego de feedback e tutoria.")
    parser.add_argument("rodada", help="pasta evaluation/results/pares-especialista-<data>")
    parser.add_argument("--semente", type=int, default=2026)
    parser.add_argument("--aceitar-suspeitas", action="store_true")
    args = parser.parse_args()

    pares = {"feedback": ler_jsonl(os.path.join(args.rodada, "pares_feedback.jsonl")),
             "tutoria": ler_jsonl(os.path.join(args.rodada, "pares_tutoria.jsonl"))}
    suspeitas = lr.respostas_suspeitas(pares)
    if suspeitas and not args.aceitar_suspeitas:
        sys.exit(f"Respostas vazias ou cortadas: {suspeitas}. Confira a rodada ou use --aceitar-suspeitas.")

    itens = lr.sortear_caderno(pares, args.semente)
    saida = os.path.join(args.rodada, "caderno")
    os.makedirs(saida, exist_ok=True)
    with open(os.path.join(saida, "caderno_explicacoes.html"), "w", encoding="utf-8") as f:
        f.write(lr.montar_html(itens))
    with open(os.path.join(saida, "chave_caderno.json"), "w", encoding="utf-8") as f:
        f.write(lr.chave_json(itens))
    with open(os.path.join(saida, "ficha_respostas_explicacoes.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        colunas = lr.colunas_ficha()
        w.writerow(colunas)
        for it in itens:
            w.writerow([it["id_par"]] + [""] * (len(colunas) - 1))

    n_vera_1 = sum(it["resposta_1"] == "vera" for it in itens)
    print(f"{len(itens)} pares no caderno; a VERA é a Resposta 1 em {n_vera_1} deles.")
    print(f"Arquivos em {os.path.relpath(saida, ROOT)}/")


if __name__ == "__main__":
    main()
