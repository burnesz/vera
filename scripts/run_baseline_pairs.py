"""
Gera os pares de saídas (VERA × baseline zero-shot) para a avaliação cega por especialista (RN-AVAL01).

Para cada insumo, as duas condições usam o mesmo modelo e o mesmo prompt; a VERA tem RAG (e, no feedback, a
verificação contra o gabarito com nova tentativa), a baseline não (app/services/baseline_service.py).

- Feedback: questões históricas de Matemática do ENEM (só texto, sem H06/H20), uma por habilidade, com uma
  alternativa errada sorteada como resposta do estudante. Se a VERA recusar o feedback (RN-FB04), o insumo é
  registrado como recusado e o próximo candidato é usado, até completar --n pares.
- Tutoria: diálogos de 2 turnos de evaluation/data/rewriting_dialogs.json (histórico + nova mensagem).

Grava em evaluation/results/pares-especialista-<data>/: pares_feedback.jsonl, pares_tutoria.jsonl e
manifest.json. É retomável: com --retomar <pasta>, os insumos já gravados são pulados.

Uso:
    ./.venv/bin/python scripts/run_baseline_pairs.py [--n 10] [--semente 2026]
    ./.venv/bin/python scripts/run_baseline_pairs.py --retomar evaluation/results/pares-especialista-<data>
"""
import os
import sys
import csv
import json
import time
import random
import argparse
import datetime
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import httpx  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.schemas.chat import ChatRequest  # noqa: E402
from app.services.baseline_service import BaselineService  # noqa: E402
from app.services.chat_service import ChatService, ChatSessionManager  # noqa: E402
from app.services.feedback_service import FeedbackService, FeedbackVerificationError  # noqa: E402
from app.services.llm_client import cliente_tutoria  # noqa: E402
from app.services.vectorstore import PineconeVectorStore  # noqa: E402

CSV_ITENS = os.path.join(ROOT, "data", "itens_prova_2009_2024_llm_texto.csv")
HABILIDADES = os.path.join(ROOT, "data", "habilidades_queries.json")
DIALOGOS = os.path.join(ROOT, "evaluation", "data", "rewriting_dialogs.json")
DIR_RESULTADOS = os.path.join(ROOT, "evaluation", "results")
HABILIDADES_FORA = {"H06", "H20"}


def ler_jsonl(caminho):
    if not os.path.exists(caminho):
        return []
    with open(caminho, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def gravar_jsonl(caminho, registro):
    with open(caminho, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def candidatos_feedback(rng):
    """Uma lista embaralhada de questões, com habilidades distintas primeiro (rodízio)."""
    descricoes = {h["habilidade_codigo"]: h["descricao_original"] for h in json.load(open(HABILIDADES, encoding="utf-8"))}
    with open(CSV_ITENS, encoding="utf-8-sig") as f:
        linhas = [r for r in csv.DictReader(f, delimiter=";")
                  if r["SG_AREA"] == "MT" and r["IN_ITEM_IMAGEM"] == "0" and r["IN_ITEM_ABAN"] == "0"]
    por_hab, vistos = {}, set()
    for r in linhas:
        hab = f"H{int(float(r['CO_HABILIDADE'])):02d}"
        alts = {l: r[f"DESC_ALTER_{l}"].strip() for l in "ABCDE"}
        if hab in HABILIDADES_FORA or r["CO_ITEM"] in vistos or not r["DESC_ENUNCIADO"].strip() or not all(alts.values()):
            continue
        vistos.add(r["CO_ITEM"])
        por_hab.setdefault(hab, []).append({
            "co_item": r["CO_ITEM"], "ano": r["ANO_APLICACAO"], "habilidade_codigo": hab,
            "habilidade_descricao": descricoes.get(hab, f"Habilidade {hab}"),
            "enunciado": r["DESC_ENUNCIADO"].strip(), "alternativas": alts, "gabarito": r["TX_GABARITO"].strip().upper(),
        })
    for lista in por_hab.values():
        rng.shuffle(lista)
    habs = sorted(por_hab)
    rng.shuffle(habs)
    fila = []
    while any(por_hab.values()):
        for h in habs:
            if por_hab[h]:
                item = por_hab[h].pop()
                erradas = [l for l in "ABCDE" if l != item["gabarito"]]
                item["alternativa_marcada"] = rng.choice(erradas)
                fila.append(item)
    return fila


def manifest(pasta, args, modelo):
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    except Exception:
        commit = ""
    try:
        ollama = httpx.get(f"{settings.LLM_ENDPOINT_URL.rstrip('/')}/api/version", timeout=10).json().get("version", "")
    except Exception:
        ollama = ""
    dados = {
        "criado_em": datetime.datetime.now().isoformat(timespec="seconds"), "commit_vera": commit,
        "modelo": modelo, "ollama_versao": ollama, "endpoint": settings.LLM_ENDPOINT_URL,
        "n_pares_por_fluxo": args.n, "semente": args.semente, "top_k_contexto": 3,
        "max_tokens": settings.LLM_MAX_TOKENS_TUTORIA, "num_ctx": settings.LLM_NUM_CTX,
        "timeout_s": settings.LLM_TIMEOUT_SECONDS,
        "condicoes": {
            "vera": "FeedbackService.gerar_feedback_verificado (RAG + verificação RN-FB04) e ChatService.send_message "
                    "(reescrita + RAG)",
            "baseline": "BaselineService: mesmos prompts, sem RAG, sem reescrita e sem verificação",
        },
    }
    with open(os.path.join(pasta, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Gera os pares VERA × baseline para o especialista.")
    parser.add_argument("--n", type=int, default=10, help="Pares por fluxo.")
    parser.add_argument("--semente", type=int, default=2026)
    parser.add_argument("--retomar", default=None, help="Pasta de uma rodada anterior, para continuar.")
    args = parser.parse_args()

    pasta = args.retomar or os.path.join(DIR_RESULTADOS, f"pares-especialista-{time.strftime('%Y%m%d-%H%M%S')}")
    os.makedirs(pasta, exist_ok=True)
    arq_fb, arq_tut = os.path.join(pasta, "pares_feedback.jsonl"), os.path.join(pasta, "pares_tutoria.jsonl")
    llm = cliente_tutoria()  # o mesmo modelo nas duas condições (RN-INF07)
    if not args.retomar:
        manifest(pasta, args, f"{llm.model_name} (think={llm.think})")

    vector_store = PineconeVectorStore()
    feedback_vera = FeedbackService(llm_client=llm, vector_store=vector_store)
    baseline = BaselineService(llm_client=llm)

    # ---------------- Feedback ----------------
    feitos = ler_jsonl(arq_fb)
    ja_vistos = {r["insumo"]["co_item"] for r in feitos}
    aceitos = sum(1 for r in feitos if r["status"] == "ok")
    for item in candidatos_feedback(random.Random(args.semente)):
        if aceitos >= args.n:
            break
        if item["co_item"] in ja_vistos:
            continue
        entrada = {k: item[k] for k in ("habilidade_codigo", "habilidade_descricao", "enunciado", "alternativas",
                                        "alternativa_marcada", "gabarito")}
        inicio = time.time()
        try:
            vera = feedback_vera.gerar_feedback_verificado(**entrada)
            saida_vera = {"conteudo": vera["conteudo"], "pensamento": vera["pensamento"],
                          "tentativas": len(vera["verificacoes"]), "tempo_s": round(time.time() - inicio, 2),
                          "fontes": [c.get("document_name") or c.get("title") for c in vera["context_chunks"]]}
            status = "ok"
        except FeedbackVerificationError as e:
            saida_vera = {"recusado": str(e), "tempo_s": round(time.time() - inicio, 2)}
            status = "vera_recusou"
        saida_base = baseline.gerar_feedback(**entrada) if status == "ok" else None
        gravar_jsonl(arq_fb, {"id": f"F{aceitos + 1:02d}" if status == "ok" else None, "status": status,
                              "insumo": item, "vera": saida_vera, "baseline": saida_base})
        aceitos += status == "ok"
        print(f"[feedback] {item['habilidade_codigo']} item {item['co_item']}: {status} "
              f"(VERA {saida_vera['tempo_s']}s{'' if not saida_base else f', baseline {saida_base['tempo_s']}s'}) "
              f"| {aceitos}/{args.n}", flush=True)

    # ---------------- Tutoria ----------------
    dialogos = json.load(open(DIALOGOS, encoding="utf-8"))["dialogos"]
    random.Random(args.semente).shuffle(dialogos)
    feitos = {r["insumo"]["id"] for r in ler_jsonl(arq_tut)}
    for n, dialogo in enumerate(dialogos[:args.n], start=1):
        if dialogo["id"] in feitos:
            continue
        manager = ChatSessionManager()  # sessão isolada, só em memória (sem banco)
        sessao = manager.get_or_create_session(f"aval_{dialogo['id']}")
        for msg in dialogo["historico"]:
            manager.add_message(sessao, msg["role"], msg["content"])
        chat = ChatService(llm_client=llm, vector_store=vector_store, manager=manager, db=None)
        inicio = time.time()
        resp = chat.send_message(ChatRequest(message=dialogo["mensagem"], session_id=sessao))
        saida_vera = {"conteudo": resp.reply, "pensamento": resp.thought, "consulta_reescrita": resp.rewritten_query,
                      "fontes": [c.document_name or c.title for c in resp.context_chunks],
                      "tempo_s": round(time.time() - inicio, 2)}
        saida_base = baseline.responder_tutoria(dialogo["mensagem"], dialogo["historico"])
        gravar_jsonl(arq_tut, {"id": f"T{n:02d}", "insumo": {k: dialogo[k] for k in ("id", "historico", "mensagem")},
                               "vera": saida_vera, "baseline": saida_base})
        print(f"[tutoria] {dialogo['id']}: VERA {saida_vera['tempo_s']}s, baseline {saida_base['tempo_s']}s "
              f"| {n}/{args.n}", flush=True)

    print(f"Pares gravados em {os.path.relpath(pasta, ROOT)}", flush=True)


if __name__ == "__main__":
    main()
