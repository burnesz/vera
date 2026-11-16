"""
Gera feedbacks e conversas da Tutora para as contas fictícias, pela API real da VERA (como um aluno faria).
Usa o LLM local (Qwen3 via Ollama). Cada resposta leva de 2 a 5 minutos; suba a API com LLM_TIMEOUT_SECONDS=1200,
pois algumas respostas passam de 5 minutos com o limite de 3.072 tokens. Pré-requisito: scripts/seed_alunos_ficticios.py.
Uso: python scripts/gerar_conteudo_demo.py
"""
import sys
import time
import httpx

API = "http://localhost:8000/api/v1"
SENHA = "aluno123"
TIMEOUT = httpx.Timeout(900.0, connect=10.0)

# Competências fracas de cada perfil -> habilidades preferidas para o feedback
PLANO = {
    "camila.nogueira": {"habs": ["H06", "H07", "H08", "H09"], "n_feedback": 2, "chat": []},
    "mariana.costa": {
        "habs": ["H07", "H08", "H09", "H10", "H11", "H12", "H13", "H14"], "n_feedback": 2,
        "chat": ["Como eu calculo o volume de um cilindro?",
                 "E se eu dobrar o raio, o volume também dobra?"],
    },
    "juliana.rocha": {
        "habs": ["H19", "H20", "H21", "H22", "H23", "H15", "H16", "H17", "H18"], "n_feedback": 2,
        "chat": ["O que é uma função afim?",
                 "Como eu descubro o coeficiente angular se tenho dois pontos do gráfico?"],
    },
}


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def main():
    with httpx.Client(timeout=TIMEOUT) as cli:
        for slug, plano in PLANO.items():
            email = f"{slug}@ficticio.vera"
            tok = cli.post(f"{API}/auth/login", data={"username": email, "password": SENHA}).json()["access_token"]
            h = {"Authorization": f"Bearer {tok}"}
            tentativas = cli.get(f"{API}/simulados/tentativas/me", headers=h).json()
            ultima = max(tentativas, key=lambda t: t["completed_at"] or "")
            itens = cli.get(f"{API}/simulados/tentativas/{ultima['tentativa_id']}", headers=h).json()["itens"]
            erradas = [i for i in itens if not i["is_correto"] and i["alternativa_selecionada"] and i["resposta_item_id"]]
            erradas.sort(key=lambda i: (i["habilidade_codigo"] not in plano["habs"], i["ordem"]))
            feitos = 0
            for item in erradas:
                if feitos >= plano["n_feedback"]:
                    break
                t0 = time.time()
                r = cli.post(f"{API}/feedback/explicar", headers=h, json={"resposta_item_id": item["resposta_item_id"]})
                log(f"[feedback] {slug} questão {item['ordem']} ({item['habilidade_codigo']}, marcou "
                    f"{item['alternativa_selecionada']}, gabarito {item['gabarito_oficial']}): HTTP {r.status_code} "
                    f"em {time.time() - t0:.0f}s")
                feitos += r.status_code == 200
            sessao = None
            for msg in plano["chat"]:
                t0 = time.time()
                r = cli.post(f"{API}/chat", headers=h, json={"message": msg, "session_id": sessao})
                ok = r.status_code == 200
                sessao = r.json().get("session_id") if ok else sessao
                log(f"[tutora] {slug}: '{msg}' -> HTTP {r.status_code} em {time.time() - t0:.0f}s"
                    + (f" | reescrita: {r.json().get('rewritten_query')}" if ok else f" | {r.text[:200]}"))
    log("Concluído.")


if __name__ == "__main__":
    sys.exit(main())
