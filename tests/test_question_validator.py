import pytest
from app.services.question_validator import validate_questao_inedita, extract_json_from_text


def test_extract_json_from_text():
    # Caso 1: JSON com bloco markdown
    raw_md = 'Aqui está a questão:\n```json\n{"enunciado": "Teste", "gabarito": "A"}\n```\nEspero que ajude!'
    extracted = extract_json_from_text(raw_md)
    assert extracted == '{"enunciado": "Teste", "gabarito": "A"}'

    # Caso 2: JSON puro
    raw_pure = '{"enunciado": "Teste", "gabarito": "B"}'
    assert extract_json_from_text(raw_pure) == raw_pure


def test_validate_questao_inedita_valid():
    valid_payload = {
        "thought_scratchpad": "Planejando questão sobre proporcionalidade direta.",
        "enunciado": "Um estudante deseja calcular o consumo total de combustível para uma viagem de 480 km, sabendo que o carro consome 1 litro a cada 12 km rodados. Qual a quantidade necessária em litros?",
        "alternativas": {
            "A": "30 litros.",
            "B": "35 litros.",
            "C": "40 litros.",
            "D": "45 litros.",
            "E": "50 litros."
        },
        "gabarito": "C",
        "justificativa": "Dividindo 480 por 12, obtemos 40 litros. Portanto, alternativa C."
    }

    is_valid, error, item = validate_questao_inedita(valid_payload)
    assert is_valid is True
    assert error is None
    assert item is not None
    assert item.gabarito == "C"
    assert len(item.alternativas) == 5


def test_validate_questao_inedita_duplicate_alternatives_fails():
    """Valida cumprimento estrito de RN-Q01: ausência de alternativas duplicadas."""
    payload_com_duplicata = {
        "enunciado": "Em uma fábrica de calçados, a produção diária foi mapeada e a gerência precisa calcular a média aritmética dos pares produzidos.",
        "alternativas": {
            "A": "150 pares.",
            "B": "150 pares.",  # DUPLICATA!
            "C": "200 pares.",
            "D": "250 pares.",
            "E": "300 pares."
        },
        "gabarito": "C",
        "justificativa": "A média calculada é 200."
    }

    is_valid, error, item = validate_questao_inedita(payload_com_duplicata)
    assert is_valid is False
    assert item is None
    assert "RN-Q01 violada" in error or "duplicados" in error


def test_validate_questao_inedita_invalid_gabarito():
    payload_gabarito_invalido = {
        "enunciado": "Em um parque da cidade, uma pista de corrida circular tem raio de 50 metros. Um corredor completa 10 voltas na pista.",
        "alternativas": {
            "A": "1 000 m.",
            "B": "2 000 m.",
            "C": "3 140 m.",
            "D": "4 000 m.",
            "E": "5 000 m."
        },
        "gabarito": "F",  # Inválido! Deve ser A-E
        "justificativa": "Resolução..."
    }

    is_valid, error, item = validate_questao_inedita(payload_gabarito_invalido)
    assert is_valid is False
    assert "Gabarito deve ser exatamente uma das letras A, B, C, D ou E" in error


def test_validate_questao_inedita_missing_alternative():
    payload_faltando_alt = {
        "enunciado": "Uma caixa d'água no formato de paralelepípedo reto retângulo tem dimensões 2 m x 3 m x 1,5 m. O volume em metros cúbicos é:",
        "alternativas": {
            "A": "6 m³.",
            "B": "7 m³.",
            "C": "8 m³.",
            "D": "9 m³."
            # Falta E!
        },
        "gabarito": "D",
        "justificativa": "Volume = 2 * 3 * 1.5 = 9."
    }

    is_valid, error, item = validate_questao_inedita(payload_faltando_alt)
    assert is_valid is False
    assert "exatamente as chaves A, B, C, D, E" in error


def test_validate_questao_inedita_anti_plagiarism():
    exemplo_historico = {
        "enunciado": "O medidor de energia elétrica das residências, conhecido por relógio de luz, é constituído de quatro pequenos relógios dispostos lado a lado.",
        "alternativas": {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"},
        "gabarito": "A"
    }

    payload_copiado = {
        "enunciado": "O medidor de energia elétrica das residências, conhecido por relógio de luz, é constituído de quatro pequenos relógios dispostos lado a lado com ponteiros.",
        "alternativas": {"A": "10", "B": "20", "C": "30", "D": "40", "E": "50"},
        "gabarito": "A",
        "justificativa": "Mesma questão copiada."
    }

    is_valid, error, item = validate_questao_inedita(payload_copiado, few_shot_exemplos=[exemplo_historico])
    assert is_valid is False
    assert "excessivamente similar" in error or "ineditismo" in error
