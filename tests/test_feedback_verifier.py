import pytest

from app.services.feedback_verifier import build_correction_hint, verify_feedback

ALTERNATIVAS = {"A": "R$ 100", "B": "R$ 200", "C": "R$ 250", "D": "R$ 300", "E": "R$ 500"}


def _verify(texto, gabarito="C", marcada="B", alternativas=ALTERNATIVAS, hab="H03"):
    return verify_feedback(texto, gabarito, marcada, alternativas, hab)


@pytest.mark.parametrize("texto", [
    "Você se confundiu no lucro unitário. A resposta correta é a alternativa C, pois $(25-20) \\times 50$.",
    "Revise a habilidade H03. O gabarito é **C**: o lucro unitário vezes 50 unidades.",
    "Seu erro foi multiplicar o preço de venda. Calculando: $$Lucro = (25 - 20) \\times 50 = 250$$ reais.",
    "A letra (C) está correta: lucro unitário de R$ 5,00 em 50 unidades, totalizando o valor esperado.",
    "Você marcou a alternativa B, que não é a correta. O correto é calcular 5 por unidade e chegar em C) R$ 250.",
])
def test_feedback_consistente_aprovado(texto):
    resultado = _verify(texto)
    assert resultado.aprovado, resultado.detalhes
    assert resultado.violacoes == []


def test_feedback_vazio_reprovado():
    resultado = _verify("   curto  ")
    assert not resultado.aprovado
    assert resultado.violacoes == ["VAZIO"]


def test_marcada_apresentada_como_correta():
    resultado = _verify("Muito bem! A alternativa B é a correta, pois 20 vezes 10 dá 200 reais de lucro.")
    assert not resultado.aprovado
    assert "MARCADA_COMO_CORRETA" in resultado.violacoes


def test_outra_alternativa_apresentada_como_correta():
    resultado = _verify("A resposta correta é a alternativa D, já que o lucro total é de 300 reais nessa venda.")
    assert not resultado.aprovado
    assert "CORRETA_DIVERGENTE" in resultado.violacoes
    assert "GABARITO_AUSENTE" in resultado.violacoes


def test_gabarito_ausente():
    resultado = _verify("Você precisa revisar porcentagem e regra de três para resolver esse tipo de questão.")
    assert not resultado.aprovado
    assert resultado.violacoes == ["GABARITO_AUSENTE"]


def test_artigos_minusculos_nao_sao_confundidos_com_letras():
    # "é a" e "e" minúsculos não podem ser lidos como alternativas A/E.
    resultado = _verify(
        "A resposta correta é a que considera o lucro unitário e o total de 50 unidades, ou seja, 250 reais."
    )
    assert resultado.aprovado, resultado.detalhes


def test_habilidade_divergente():
    resultado = _verify("O gabarito é C. Recomendo revisar a habilidade H17 sobre funções afins e gráficos.")
    assert not resultado.aprovado
    assert resultado.violacoes == ["HABILIDADE_DIVERGENTE"]


def test_habilidade_sem_zero_a_esquerda_e_aceita():
    resultado = _verify("O gabarito é C. Recomendo revisar a habilidade H3 sobre operações com números racionais.")
    assert resultado.aprovado, resultado.detalhes


def test_numeros_formato_brasileiro():
    alternativas = {"A": "R$ 1.250,50", "B": "R$ 1.000,00", "C": "R$ 900,00", "D": "R$ 800,00", "E": "R$ 700,00"}
    resultado = _verify(
        "O valor total é obtido somando as parcelas: $1250.5$ reais, como mostra a resolução passo a passo.",
        gabarito="A",
        marcada="B",
        alternativas=alternativas,
    )
    assert resultado.aprovado, resultado.detalhes


def test_alternativa_textual_sem_numeros():
    alternativas = {
        "A": "Função quadrática", "B": "Função afim", "C": "Função exponencial",
        "D": "Função logarítmica", "E": "Função constante",
    }
    resultado = _verify(
        "O crescimento por um fator fixo a cada período caracteriza uma função exponencial, e não uma reta.",
        gabarito="C",
        marcada="B",
        alternativas=alternativas,
    )
    assert resultado.aprovado, resultado.detalhes


def test_dica_de_correcao_cita_gabarito_e_motivos():
    resultado = _verify("Muito bem! A alternativa B é a correta, pois 20 vezes 10 dá 200 reais de lucro.")
    dica = build_correction_hint(resultado, "C", "B", "H03")
    assert "alternativa C" in dica
    assert "alternativa B" in dica
    assert "H03" in dica
    assert resultado.detalhes[0] in dica
