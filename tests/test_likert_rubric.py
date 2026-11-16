"""Testes da rubrica Likert cega de feedback e tutoria (RN-AVAL01, RN-AVAL02)."""
import pytest

from evaluation import likert_rubric as lr


def _par(id_, fluxo, vera="Primeiro texto com explicação suficiente para não parecer cortado. 😊",
         base="Segundo texto com explicação suficiente para não parecer cortado."):
    insumo = ({"habilidade_codigo": "H01", "enunciado": "Enunciado", "alternativas": {"A": "1", "B": "2"},
               "gabarito": "A", "alternativa_marcada": "B"} if fluxo == "feedback"
              else {"historico": [{"role": "user", "content": "Oi"}], "mensagem": "E agora?"})
    return {"id": id_, "status": "ok", "insumo": insumo,
            "vera": {"conteudo": vera, "fontes": ["x.pdf"]}, "baseline": {"conteudo": base}}


PARES = {"feedback": [_par(f"F{i:02d}", "feedback") for i in range(1, 5)],
         "tutoria": [_par(f"T{i:02d}", "tutoria") for i in range(1, 5)]}


def test_caderno_cego_nao_revela_a_condicao_nem_as_fontes():
    itens = lr.sortear_caderno(PARES, semente=1)
    pagina = lr.montar_html(itens)
    assert len(itens) == 8
    assert {it["id_par"] for it in itens} == {"FB01", "FB02", "FB03", "FB04", "TU01", "TU02", "TU03", "TU04"}
    for termo in ("VERA", "baseline", "x.pdf", "F01", "T01"):
        assert termo not in pagina
    for it in itens:
        assert {it["resposta_1"], it["resposta_2"]} == {"vera", "baseline"}


def test_sorteio_e_reprodutivel_e_alterna_a_posicao_da_vera():
    a, b = lr.sortear_caderno(PARES, 2026), lr.sortear_caderno(PARES, 2026)
    assert lr.chave_json(a) == lr.chave_json(b)
    many = {"feedback": [_par(f"F{i:02d}", "feedback") for i in range(1, 41)]}
    posicoes = {it["resposta_1"] for it in lr.sortear_caderno(many, 3)}
    assert posicoes == {"vera", "baseline"}


def test_respostas_suspeitas_detecta_vazia_e_formula_aberta():
    pares = {"feedback": [_par("F01", "feedback", base="..."),
                          _par("F02", "feedback", vera="Calculando: $$ x = \\frac{4" + " texto" * 20)],
             "tutoria": PARES["tutoria"]}
    pares["tutoria"] = [_par("T01", "tutoria", vera="Continue revisando a definição de progressão e de estat")]
    assert lr.respostas_suspeitas(pares) == [("F01", "baseline"), ("F02", "vera"), ("T01", "vera")]


def test_desmascarar_converte_resposta_1_e_2_em_condicoes():
    chave = [{"id_par": "FB01", "fluxo": "feedback", "par_original": "F03", "resposta_1": "baseline",
              "resposta_2": "vera"}]
    linha = {"id_par": "FB01", "avaliador": "prof", "preferencia": "2",
             **{f"r1_{c}": "2" for c, _ in lr.CRITERIOS}, **{f"r2_{c}": "5" for c, _ in lr.CRITERIOS}}
    reg = lr.desmascarar(chave, lr.ler_ficha([linha]))[0]
    assert reg["vera"] == {c: 5 for c, _ in lr.CRITERIOS}
    assert reg["baseline"] == {c: 2 for c, _ in lr.CRITERIOS}
    assert reg["preferencia"] == "vera"


def test_ficha_rejeita_nota_fora_da_escala():
    with pytest.raises(ValueError):
        lr.ler_ficha([{"id_par": "FB01", "r1_correcao": "7"}])
