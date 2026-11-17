"""Capturas 16:9 da tela de administração de questões inéditas (23 e 24), no padrão de scripts/capturar_telas.py.

Uso: python scripts/capturar_telas_admin.py <senha do admin> <id do lote> <pasta> [H03,H12,H24] [H24]
"""
import sys
from playwright.sync_api import sync_playwright

senha, lote_id, pasta = sys.argv[1], sys.argv[2], sys.argv[3]
habs = sys.argv[4].split(",") if len(sys.argv) > 4 else []
BASE = "http://localhost:5173"
EMOJI = ("var l=document.createElement('link');l.rel='stylesheet';"
         "l.href='https://fonts.googleapis.com/css2?family=Noto+Color+Emoji&display=swap';document.head.appendChild(l);")

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1600, "height": 900}, device_scale_factor=2, locale="pt-BR")
    pg = ctx.new_page()
    pg.goto(BASE + "/login")
    pg.fill("input[placeholder='seu.email@exemplo.com']", "admin@vera.com")
    pg.fill("input[type=password]", senha)
    pg.click("button[type=submit]")
    pg.wait_for_timeout(3000)
    pg.evaluate(f"localStorage.setItem('vera_admin_lote_ineditas','{lote_id}')")
    pg.goto(BASE + "/admin-ineditas")
    pg.evaluate(EMOJI)
    pg.wait_for_timeout(3000)
    for h in habs:  # mostra no formulário as habilidades do lote exibido
        pg.locator(f"label:has-text('{h}') input[type=checkbox]").first.check()
    pg.evaluate("window.scrollTo(0, 0)")
    pg.wait_for_timeout(500)
    pg.screenshot(path=f"{pasta}/23_admin_ineditas_lote.png")

    alvo = sys.argv[5] if len(sys.argv) > 5 else ''  # habilidade da questão aberta na revisão
    pg.locator(f"section:has-text('Questões aprovadas') button.btn-ghost:has-text('{alvo}')").first.click()
    pg.wait_for_timeout(1200)
    sec = pg.locator("section:has-text('Questões aprovadas')")
    y = sec.evaluate("e => e.getBoundingClientRect().top + window.scrollY")
    pg.evaluate(f"window.scrollTo(0, {y} - 80)")
    pg.wait_for_timeout(600)
    pg.screenshot(path=f"{pasta}/24_admin_ineditas_revisao.png")
    print("largura:", pg.evaluate("document.documentElement.scrollWidth"))
    b.close()
