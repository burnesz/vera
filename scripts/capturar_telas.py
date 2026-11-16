"""
Capturas de tela da VERA para a monografia (Seção 6.1), em 16:9: janela de 1600 x 900 e escala 2x (3200 x 1800 px).

Pré-requisitos:
- API (porta 8000) e frontend Vite (porta 5173) no ar, com o banco populado;
- contas fictícias de scripts/seed_alunos_ficticios.py e conteúdo gerado por scripts/gerar_conteudo_demo.py
  (feedbacks e conversas da tutora, gerados pela própria plataforma);
- Playwright para Python e o Chromium dele (não fazem parte do requirements.txt):
  pip install playwright && python -m playwright install chromium

Uso:
    python scripts/capturar_telas.py [pasta de saída] [grupo ...]
    grupos: acesso painel simulado correcao tutora (padrão: todos); pasta padrão: docs/assets/capturas-tela
Os emojis usam a fonte Noto Color Emoji do Google Fonts (o Chromium do WSL não tem fonte de emoji).
"""
import os
import re
import sys

import httpx
from playwright.sync_api import sync_playwright

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "docs", "assets", "capturas-tela")
GRUPOS = set(sys.argv[2:]) or {"acesso", "painel", "simulado", "correcao", "tutora"}
BASE = "http://localhost:5173"
API = "http://localhost:8000/api/v1"
SENHA = "aluno123"
VIEW = {"width": 1600, "height": 900}
os.makedirs(OUT, exist_ok=True)

# Emojis: o Chromium do WSL não tem fonte de emoji; a Noto Color Emoji entra como último recurso da pilha de fontes.
EMOJI_JS = """async () => {
  if (!document.getElementById('emoji-font')) {
    const l = document.createElement('link'); l.id = 'emoji-font'; l.rel = 'stylesheet';
    l.href = 'https://fonts.googleapis.com/css2?family=Noto+Color+Emoji&display=block';
    document.head.appendChild(l);
    await new Promise(r => { l.onload = r; l.onerror = r; setTimeout(r, 5000); });
  }
  for (const e of document.querySelectorAll('body, body *')) {
    const f = getComputedStyle(e).fontFamily;
    if (f && !f.includes('Noto Color Emoji')) e.style.fontFamily = f + ", 'Noto Color Emoji'";
  }
  await document.fonts.ready;
}"""


def log(msg):
    print(msg, flush=True)


def shot(pg, nome):
    pg.wait_for_timeout(800)
    pg.evaluate(EMOJI_JS)
    pg.wait_for_timeout(700)
    pg.screenshot(path=f"{OUT}/{nome}.png")
    log(f"ok {nome}")


def topo_em(pg, loc, margem=90):
    """Rola a página (ou o contêiner com rolagem) para o elemento ficar no topo da janela, com uma margem."""
    loc.first.scroll_into_view_if_needed()
    pg.evaluate("""([e, m]) => {
      e.scrollIntoView({block: 'start'});
      let p = e.parentElement;
      while (p && !(p.scrollHeight > p.clientHeight + 5 && /(auto|scroll)/.test(getComputedStyle(p).overflowY))) p = p.parentElement;
      if (p) p.scrollTop -= m; else window.scrollBy(0, -m);
    }""", [loc.first.element_handle(), margem])
    pg.wait_for_timeout(500)


def topo(pg):
    pg.evaluate("() => { window.scrollTo(0, 0); document.querySelectorAll('*').forEach(e => { if (e.scrollTop) e.scrollTop = 0; }); }")
    pg.wait_for_timeout(400)


def rolar(pg, loc, dy):
    """Rola o contêiner do elemento (ou a página) dy pixels."""
    pg.evaluate("""([e, dy]) => {
      let p = e.parentElement;
      while (p && !(p.scrollHeight > p.clientHeight + 5 && /(auto|scroll)/.test(getComputedStyle(p).overflowY))) p = p.parentElement;
      if (p) p.scrollTop += dy; else window.scrollBy(0, dy);
    }""", [loc.first.element_handle(), dy])
    pg.wait_for_timeout(500)


def login(pg, email, entrar=True):
    pg.goto(BASE + "/login")
    pg.fill("input[placeholder='seu.email@exemplo.com']", email)
    pg.fill("input[type=password]", SENHA)
    if entrar:
        pg.click("button[type=submit]")
        pg.wait_for_url(re.compile(r"/$|/home"), timeout=15000)
        pg.wait_for_timeout(2500)


def contexto(b):
    return b.new_context(viewport=VIEW, device_scale_factor=2, locale="pt-BR")


def itens_mariana():
    with httpx.Client(timeout=30) as cli:
        tok = cli.post(f"{API}/auth/login", data={"username": "mariana.costa@ficticio.vera", "password": SENHA}).json()
        h = {"Authorization": f"Bearer {tok['access_token']}"}
        tent = max(cli.get(f"{API}/simulados/tentativas/me", headers=h).json(), key=lambda t: t["completed_at"] or "")
        itens = cli.get(f"{API}/simulados/tentativas/{tent['tentativa_id']}", headers=h).json()["itens"]
        erradas = [i for i in itens if not i["is_correto"] and i["alternativa_selecionada"] and i["resposta_item_id"]]
        com = [i for i in erradas if cli.get(f"{API}/feedback/{i['resposta_item_id']}", headers=h).status_code == 200]
        sem = [i for i in erradas if i not in com]
        return com, sem


def ir_para_questao(pg, ordem):
    pg.get_by_role("button", name=str(ordem), exact=True).first.click()
    pg.wait_for_timeout(3000)


def main():
    com_fb, sem_fb = itens_mariana()
    log(f"Mariana: com feedback {[i['ordem'] for i in com_fb]}; erradas sem feedback {[i['ordem'] for i in sem_fb][:5]}")
    with sync_playwright() as p:
        b = p.chromium.launch()

        if "acesso" in GRUPOS:
            ctx = contexto(b)
            pg = ctx.new_page()
            pg.goto(BASE + "/")
            shot(pg, "01_inicio")
            login(pg, "mariana.costa@ficticio.vera", entrar=False)
            shot(pg, "02_login")
            ctx.close()

        if "painel" in GRUPOS:
            ctx = contexto(b)
            pg = ctx.new_page()
            login(pg, "mariana.costa@ficticio.vera")
            shot(pg, "03_painel_resumo")
            topo_em(pg, pg.get_by_role("heading", name=re.compile("Proficiência nas 7 Competências")), 130)
            shot(pg, "04_painel_competencias")
            pg.get_by_role("button", name=re.compile(r"^Críticas")).click()
            topo_em(pg, pg.get_by_role("heading", name=re.compile("Matriz de Habilidades")), 130)
            shot(pg, "05_painel_habilidades_criticas")
            ctx.close()

        if "simulado" in GRUPOS:
            ctx = contexto(b)
            pg = ctx.new_page()
            login(pg, "mariana.costa@ficticio.vera")
            pg.goto(BASE + "/simulado")
            pg.get_by_role("button", name=re.compile(r"^Finalizados")).click()
            shot(pg, "06_meus_simulados")
            pg.get_by_role("button", name="Gerar Novo Simulado").first.click()
            shot(pg, "07_gerar_simulado")
            ctx.close()

            ctx = contexto(b)
            pg = ctx.new_page()
            login(pg, "lucas.ferreira@ficticio.vera")
            pg.goto(BASE + "/simulado")
            pg.wait_for_timeout(1500)
            pg.get_by_role("button", name=re.compile(r"Iniciar Simulado|Continuar")).first.click()
            pg.wait_for_timeout(2000)
            ir_para_questao(pg, 1)
            shot(pg, "08_caderno_prova")
            for n in range(1, 6):
                pg.get_by_role("button", name=re.compile(r"^B\s")).first.click()
                if n == 3:
                    pg.get_by_role("button", name="Revisar Depois").click()
                pg.get_by_role("button", name="Próxima").first.click()
                pg.wait_for_timeout(300)
            topo(pg)
            shot(pg, "09_caderno_grade")
            pg.get_by_role("button", name="Entregar Simulado").first.click()
            shot(pg, "10_entrega_confirmacao")
            ctx.close()

        if "correcao" in GRUPOS:
            ctx = contexto(b)
            pg = ctx.new_page()
            login(pg, "mariana.costa@ficticio.vera")
            pg.goto(BASE + "/simulado")
            pg.get_by_role("button", name=re.compile(r"^Finalizados")).click()
            pg.get_by_role("button", name="Ver Gabarito & Desempenho").first.click()
            pg.wait_for_timeout(2000)
            shot(pg, "11_relatorio_desempenho")
            pg.get_by_role("button", name=re.compile(r"Gabarito Rápido")).click()
            pg.wait_for_timeout(800)
            topo_em(pg, pg.get_by_text(re.compile(r"Gabarito Geral dos 45 Itens")), 130)
            shot(pg, "12_gabarito_rapido")
            pg.get_by_role("button", name=re.compile(r"Revisão Detalhada")).click()
            if sem_fb:
                ir_para_questao(pg, sem_fb[0]["ordem"])
                topo_em(pg, pg.get_by_text(re.compile(r"^Questão \d+ de 45$")), 130)
                shot(pg, "13_questao_errada")
                topo_em(pg, pg.get_by_text(re.compile(r"Quer entender exatamente")), 420)
                rolar(pg, pg.get_by_text(re.compile(r"Quer entender exatamente")), 200)
                shot(pg, "14_questao_errada_convite")
            if com_fb:
                ir_para_questao(pg, com_fb[0]["ordem"])
                cartao = pg.get_by_text(re.compile(r"Explicação Pedagógica da Tutora VERA"))
                topo_em(pg, cartao, 130)
                shot(pg, "15_feedback_vera_inicio")
                rolar(pg, cartao, 700)
                shot(pg, "16_feedback_vera_continuacao")
                rotulo = pg.get_by_text(re.compile(r"Ver Raciocínio Interno da Tutora"))
                rotulo.first.click()
                pg.wait_for_timeout(800)
                topo_em(pg, cartao, 130)
                shot(pg, "17_feedback_raciocinio")
            ctx.close()

        if "tutora" in GRUPOS:
            ctx = contexto(b)
            pg = ctx.new_page()
            login(pg, "mariana.costa@ficticio.vera")
            pg.goto(BASE + "/chat")
            pg.wait_for_timeout(2000)
            shot(pg, "18_tutora_inicio")
            pg.get_by_text(re.compile(r"cilindro", re.I)).first.click()
            pg.wait_for_timeout(3000)
            pergunta1 = pg.get_by_text(re.compile(r"Como eu calculo o volume de um cilindro"))
            topo_em(pg, pergunta1.last, 30)
            shot(pg, "19_tutora_conversa_1")
            pergunta2 = pg.get_by_text(re.compile(r"E se eu dobrar o raio"))
            topo_em(pg, pergunta2.last, 30)
            shot(pg, "20_tutora_conversa_2")
            fontes = pg.get_by_text(re.compile(r"Fontes teóricas"))
            if fontes.count():
                topo_em(pg, fontes.last, 560)
                shot(pg, "21_tutora_fontes")
            raciocinio = pg.get_by_text(re.compile(r"Raciocínio Pedagógico"))
            if raciocinio.count():
                raciocinio.last.click()
                pg.wait_for_timeout(800)
                topo_em(pg, raciocinio.last, 40)
                shot(pg, "22_tutora_raciocinio")
            ctx.close()
        b.close()


if __name__ == "__main__":
    main()
