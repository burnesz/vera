"""
Rubrica Likert cega (RN-AVAL01, RN-AVAL02) para os pares de feedback e de tutoria (VERA × baseline zero-shot).

O especialista vê, para cada insumo, as duas respostas lado a lado como "Resposta 1" e "Resposta 2", numa ordem
sorteada por par, e dá uma nota de 1 a 5 em cada critério da Seção 3.1 de
docs/03-avaliacao-cientifica/baseline-e-metricas-tcc.md. Só o texto final (`conteudo`) é mostrado: o raciocínio
interno e as fontes ficam de fora, porque a baseline não tem fontes e isso revelaria a condição.

As questões inéditas são avaliadas no caderno do repositório questoes-ineditas-enem
(scripts/avaliacao_especialista/montar_caderno.py), com os critérios da Seção 3.2.

Funções puras, usadas por scripts/montar_caderno_especialista.py e scripts/analisar_caderno_especialista.py.
"""
import html
import json
import random
from typing import Dict, List, Optional, Tuple

CRITERIOS = [
    ("correcao", "Correção conceitual e matemática: não há erros de cálculo nem definições incorretas."),
    ("clareza", "Clareza e didática: a explicação passo a passo é fácil de acompanhar por um estudante do Ensino Médio."),
    ("linguagem", "Linguagem adequada ao contexto do ENEM: tom acolhedor, termos corretos e exemplos adequados."),
    ("fidelidade", "Ausência de informações incorretas ou inventadas (regras, fórmulas ou fatos falsos)."),
]
FLUXOS = {"feedback": ("FB", "Parte A — Explicação de questão errada"), "tutoria": ("TU", "Parte B — Tutora virtual")}
PREFERENCIAS = {"1", "2", "E"}

# Renderização de Markdown + LaTeX no navegador, com a mesma regra de `$` inline do frontend da VERA
# (frontend/src/components/MathText.tsx). Sem internet, o texto aparece cru (com quebras de linha).
_SCRIPT_RENDER = r"""
<script>
const NO_WORD = String.raw`(?:(?![A-Za-zÀ-ÿ]{2})[^\n$])`;
const INLINE_DOLLAR_SOURCE =
  String.raw`(?<![a-zA-Z\\])\$(?:(?!\s)[^\n$]+?(?<!\s)|\s[^\n$]*?[\\^_={][^\n$]*?|\s${NO_WORD}*?[^\s$]${NO_WORD}*?)\$(?!\d)`;
const MATH = new RegExp(String.raw`\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)|` + INLINE_DOLLAR_SOURCE, 'g');
const ABRE = String.fromCharCode(0xE000), FECHA = String.fromCharCode(0xE001);  // marcadores das fórmulas protegidas
const ESC = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
// markdown = true: texto das respostas (Markdown + fórmulas); false: alternativas (só fórmulas: "64." não vira lista)
function renderiza(el, markdown) {
  if (!window.katex || (markdown && !window.marked)) { el.classList.add('raw'); return; }
  const formulas = [];
  const protegido = el.textContent.replace(MATH, m => { formulas.push(m); return ABRE + (formulas.length - 1) + FECHA; });
  const base = markdown ? marked.parse(protegido, { breaks: true }) : ESC(protegido);
  el.innerHTML = base.replace(new RegExp(ABRE + '(\\d+)' + FECHA, 'g'), (_, i) => {
    const m = formulas[+i];
    const bloco = m.startsWith('$$') || m.startsWith('\\[');
    const corpo = m.startsWith('$$') || m.startsWith('\\') ? m.slice(2, -2) : m.slice(1, -1);
    try { return katex.renderToString(corpo.trim(), { displayMode: bloco, throwOnError: false }); }
    catch (e) { return m; }
  });
}
document.querySelectorAll('.md').forEach(el => renderiza(el, true));
document.querySelectorAll('.mt').forEach(el => renderiza(el, false));
</script>
"""

_ESTILO = """
<style>
  body { font-family: Georgia, serif, 'Noto Color Emoji'; max-width: 980px; margin: 24px auto; padding: 0 16px; color: #111; background: #fff; line-height: 1.5; }
  h1 { font-size: 1.5em; } h1.parte { margin-top: 40px; border-bottom: 2px solid #333; }
  h2 { font-size: 1.15em; border-bottom: 1px solid #999; padding-bottom: 4px; } h3 { font-size: 1em; margin: 0 0 6px; }
  .instrucoes { border: 1px solid #999; padding: 12px 16px; background: #f6f6f6; }
  .hab, .pedido { font-size: .92em; color: #333; } .pedido { font-style: italic; }
  .alts { list-style: none; padding-left: 0; } .alts p { display: inline; margin: 0; }
  .conversa { border-left: 3px solid #bbb; padding-left: 12px; } .fala.nova { font-weight: 600; }
  .respostas { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .resposta { border: 1px solid #999; padding: 10px 12px; overflow-x: auto; font-size: .93em; min-width: 0; }
  .md.raw { white-space: pre-wrap; }
  table { border-collapse: collapse; margin: 8px 0; } th, td { border: 1px solid #999; padding: 4px 8px; text-align: left; vertical-align: top; }
  .crit { width: 100%; font-size: .9em; } .crit th { font-weight: normal; background: #f0f0f0; }
  .box, .resp { white-space: nowrap; text-align: center; }
  .obs { min-height: 60px; border-bottom: 1px dotted #999; } .par { margin-bottom: 32px; }
  .katex-display { overflow-x: auto; overflow-y: hidden; }
  @media (max-width: 700px) { .respostas { grid-template-columns: 1fr; } }
  @media print {
    body { margin: 0; max-width: none; font-size: 10pt; line-height: 1.35; }
    .par, .instrucoes { page-break-after: always; } .par { margin: 0; } h1.parte { margin-top: 0; }
    p { margin: 4px 0; } th, td { padding: 2px 6px; } .crit { font-size: 8.5pt; margin: 4px 0; }
    .resposta { font-size: 9pt; padding: 6px 8px; } .obs { min-height: 50px; }
    .avaliacao { break-inside: avoid; }
  }
</style>
"""

_CDN = """
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Color+Emoji&display=swap">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"></script>
"""


def colunas_ficha() -> List[str]:
    return (["id_par", "avaliador"] + [f"r1_{c}" for c, _ in CRITERIOS] + [f"r2_{c}" for c, _ in CRITERIOS]
            + ["preferencia", "observacao"])


def sortear_caderno(pares: Dict[str, List[dict]], semente: int) -> List[dict]:
    """
    Embaralha os pares de cada fluxo e sorteia, para cada um, qual condição aparece como Resposta 1.
    Devolve itens {id_par, fluxo, par_original, resposta_1, resposta_2, insumo, textos}.
    """
    rng = random.Random(semente)
    itens = []
    for fluxo in FLUXOS:
        lista = sorted((p for p in pares.get(fluxo, []) if p.get("status", "ok") == "ok"), key=lambda p: p["id"])
        rng.shuffle(lista)
        prefixo = FLUXOS[fluxo][0]
        for n, p in enumerate(lista, 1):
            ordem = ["vera", "baseline"]
            rng.shuffle(ordem)
            itens.append({"id_par": f"{prefixo}{n:02d}", "fluxo": fluxo, "par_original": p["id"],
                          "resposta_1": ordem[0], "resposta_2": ordem[1], "insumo": p["insumo"],
                          "textos": [p[ordem[0]]["conteudo"], p[ordem[1]]["conteudo"]]})
    return itens


def respostas_suspeitas(pares: Dict[str, List[dict]]) -> List[Tuple[str, str]]:
    """
    (id, condição) com sinal de corte pelo teto de tokens: resposta vazia, fórmula em bloco sem fechar ($$ ímpar) ou
    texto que termina no meio de uma palavra ou conta (último caractere é letra, dígito ou operador).
    """
    suspeitas = []
    for lista in pares.values():
        for p in lista:
            for cond in ("vera", "baseline"):
                texto = ((p.get(cond) or {}).get("conteudo", "") or "").rstrip()
                fim = texto[-1:] if texto else ""
                meio = fim.isalnum() or fim in ",;:=+-\\{(^_"
                if len(texto.strip(" .…\n")) < 50 or texto.count("$$") % 2 or meio:
                    suspeitas.append((p["id"], cond))
    return suspeitas


_COMANDOS_SOLTOS = {"\\times": "×", "\\cdot": "·", "\\div": "÷", "\\%": "%"}


def _limpa_enunciado(texto: str) -> str:
    """Enunciados do dataset histórico trazem comandos LaTeX soltos, fora de $...$ (ex.: 110 m \\times 75 m)."""
    if "$" in texto:
        return texto
    for comando, simbolo in _COMANDOS_SOLTOS.items():
        texto = texto.replace(comando, simbolo)
    return texto


def _insumo_html(item: dict) -> str:
    ins = item["insumo"]
    if item["fluxo"] == "feedback":
        alts = "".join(f"<li><b>{html.escape(l)})</b> <span class='mt'>{html.escape(str(v))}</span></li>"
                       for l, v in sorted(ins["alternativas"].items()))
        return (f"<p class='hab'><b>Habilidade {html.escape(ins['habilidade_codigo'])}:</b> "
                f"{html.escape(ins.get('habilidade_descricao', ''))} (ENEM {html.escape(str(ins.get('ano', '')))})</p>"
                f"<div class='md enunciado'>{html.escape(_limpa_enunciado(ins['enunciado']))}</div><ol class='alts'>{alts}</ol>"
                f"<p><b>Gabarito:</b> {html.escape(ins['gabarito'])} &nbsp;·&nbsp; "
                f"<b>Alternativa marcada pelo estudante:</b> {html.escape(ins['alternativa_marcada'])}</p>"
                "<p class='pedido'>O estudante errou a questão e pediu uma explicação. Explicações recebidas:</p>")
    falas = "".join(f"<p class='fala'><b>{'Estudante' if m['role'] == 'user' else 'Tutora'}:</b> "
                    f"{html.escape(m['content'])}</p>" for m in ins.get("historico", []))
    return (f"<div class='conversa'>{falas}<p class='fala nova'><b>Estudante:</b> {html.escape(ins['mensagem'])}</p>"
            "</div><p class='pedido'>Respostas da tutora à última mensagem do estudante:</p>")


def _grade_html() -> str:
    cab = "".join(f"<th class='box'>{n}</th>" for n in range(1, 6))
    linhas = ""
    for n, (_, texto) in enumerate(CRITERIOS, 1):
        for r in (1, 2):
            celulas = "".join(f"<td class='box'>☐ {v}</td>" for v in range(1, 6))
            rotulo = f"<td rowspan='2'>{n}. {html.escape(texto)}</td>" if r == 1 else ""
            linhas += f"<tr>{rotulo}<td class='resp'>Resposta {r}</td>{celulas}</tr>"
    return (f"<div class='avaliacao'><table class='crit'><thead><tr><th>Critério (1 = discordo totalmente, 5 = concordo totalmente)</th>"
            f"<th></th>{cab}</tr></thead><tbody>{linhas}</tbody></table>"
            "<table class='crit'><tbody><tr><td>Qual resposta é melhor no conjunto?</td>"
            "<td class='box'>☐ Resposta 1</td><td class='box'>☐ Resposta 2</td><td class='box'>☐ Empate</td>"
            "</tr></tbody></table><p class='obs'><b>Observações:</b></p></div>")


def montar_html(itens: List[dict], titulo: str = "Avaliação de explicações de Matemática") -> str:
    secoes, fluxo_atual = [], None
    for it in itens:
        if it["fluxo"] != fluxo_atual:
            fluxo_atual = it["fluxo"]
            secoes.append(f"<h1 class='parte'>{html.escape(FLUXOS[fluxo_atual][1])}</h1>")
        respostas = "".join(f"<div class='resposta'><h3>Resposta {n}</h3><div class='md'>{html.escape(t)}</div></div>"
                            for n, t in enumerate(it["textos"], 1))
        secoes.append(f"<section class='par'><h2>{it['id_par']}</h2>{_insumo_html(it)}"
                      f"<div class='respostas'>{respostas}</div>{_grade_html()}</section>")
    criterios = "".join(f"<li>{html.escape(t)}</li>" for _, t in CRITERIOS)
    n_fb = sum(it["fluxo"] == "feedback" for it in itens)
    n_tu = len(itens) - n_fb
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(titulo)}</title>{_CDN}{_ESTILO}</head><body>
<h1>{html.escape(titulo)}</h1>
<div class="instrucoes">
  <p>Este caderno tem {len(itens)} situações: na Parte A, {n_fb} explicações para uma questão do ENEM que o
  estudante errou; na Parte B, {n_tu} respostas de uma tutora virtual a perguntas de estudantes. Em cada situação há
  duas respostas, <b>Resposta 1</b> e <b>Resposta 2</b>, produzidas por processos diferentes.</p>
  <p><b>Para cada situação:</b></p>
  <ol>
    <li>Leia a questão (ou a conversa) e as duas respostas.</li>
    <li>Dê, para cada resposta, uma nota de <b>1</b> (discordo totalmente) a <b>5</b> (concordo totalmente) em cada
      afirmação: <ul>{criterios}</ul></li>
    <li>Indique qual resposta é melhor no conjunto, ou se há empate.</li>
    <li>Se quiser, escreva uma observação, principalmente quando der nota 1 ou 2.</li>
  </ol>
  <p>As respostas também podem ser registradas na planilha <code>ficha_respostas_explicacoes.csv</code>: uma linha
  por situação, notas de 1 a 5 nas colunas <code>r1_*</code> (Resposta 1) e <code>r2_*</code> (Resposta 2) e
  <b>1</b>, <b>2</b> ou <b>E</b> (empate) na coluna <code>preferencia</code>.</p>
</div>
{''.join(secoes)}
{_SCRIPT_RENDER}
</body></html>"""


def ler_ficha(linhas: List[dict], arquivo: str = "ficha") -> Dict[str, Dict[str, dict]]:
    """{id_par: {avaliador: {'r1': {crit: nota}, 'r2': {...}, 'preferencia': '1'|'2'|'E'|None}}}."""
    out: Dict[str, Dict[str, dict]] = {}
    for linha in linhas:
        id_par = (linha.get("id_par") or "").strip()
        if not id_par:
            continue
        avaliador = (linha.get("avaliador") or "").strip() or arquivo
        reg: dict = {"r1": {}, "r2": {}, "preferencia": None}
        for r in ("r1", "r2"):
            for c, _ in CRITERIOS:
                v = (linha.get(f"{r}_{c}") or "").strip()
                if v:
                    if v not in {"1", "2", "3", "4", "5"}:
                        raise ValueError(f"{arquivo}, {id_par}: nota '{v}' em {r}_{c} (use 1 a 5)")
                    reg[r][c] = int(v)
        pref = (linha.get("preferencia") or "").strip().upper()
        if pref:
            if pref not in PREFERENCIAS:
                raise ValueError(f"{arquivo}, {id_par}: preferência '{pref}' (use 1, 2 ou E)")
            reg["preferencia"] = pref
        if reg["r1"] or reg["r2"] or reg["preferencia"]:
            out.setdefault(id_par, {})[avaliador] = reg
    return out


def desmascarar(chave: List[dict], fichas: Dict[str, Dict[str, dict]]) -> List[dict]:
    """
    Converte Resposta 1/2 em VERA/baseline com a chave. Uma linha por (par, avaliador):
    {id_par, fluxo, par_original, avaliador, vera: {crit: nota}, baseline: {...}, preferencia}, em que preferencia é
    'vera', 'baseline', 'empate' ou None.
    """
    por_id = {k["id_par"]: k for k in chave}
    registros = []
    for id_par, por_avaliador in fichas.items():
        if id_par not in por_id:
            raise ValueError(f"Par {id_par} não está na chave.")
        k = por_id[id_par]
        cond = {"r1": k["resposta_1"], "r2": k["resposta_2"]}
        for avaliador, reg in por_avaliador.items():
            pref: Optional[str] = None
            if reg["preferencia"] == "E":
                pref = "empate"
            elif reg["preferencia"]:
                pref = cond[f"r{reg['preferencia']}"]
            registros.append({"id_par": id_par, "fluxo": k["fluxo"], "par_original": k["par_original"],
                              "avaliador": avaliador, cond["r1"]: reg["r1"], cond["r2"]: reg["r2"],
                              "preferencia": pref})
    return registros


def chave_json(itens: List[dict]) -> str:
    return json.dumps([{k: it[k] for k in ("id_par", "fluxo", "par_original", "resposta_1", "resposta_2")}
                       for it in itens], ensure_ascii=False, indent=2)
