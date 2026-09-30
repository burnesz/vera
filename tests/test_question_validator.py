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


def test_validate_questao_inedita_sanitizes_corrupted_latex():
    """Valida se o validador repara form feed residual e comandos LaTeX corrompidos."""
    raw_corrupted_json = (
        '{\n'
        '  "thought_scratchpad": "Etapa 1: V(x) = 50 - \\frac{1}{4}x^2",\n'
        '  "enunciado": "Em uma loja, o valor unitário é V(x) = 50 - \\x0crac{1}{4}x^2. Calcule para x=4.",\n'
        '  "alternativas": {\n'
        '    "A": "46",\n'
        '    "B": "48",\n'
        '    "C": "50",\n'
        '    "D": "52",\n'
        '    "E": "54"\n'
        '  },\n'
        '  "gabarito": "A",\n'
        '  "justificativa": "Para x=4, V(4) = 50 - 4 = 46. Alternativa A."\n'
        '}'
    )

    is_valid, error, item = validate_questao_inedita(raw_corrupted_json)
    assert is_valid is True
    assert item is not None
    # Garante que \x0crac foi restaurado para \frac
    assert "\\frac" in item.enunciado or r"\frac" in item.enunciado
    assert "\x0c" not in item.enunciado


def test_validate_questao_inedita_rejects_shortcut_reasoning():
    """Valida se o validador rejeita questão onde o comando pede valor total mas o gabarito é o unitário."""
    payload_shortcut = {
        "thought_scratchpad": "Calculando: V(8) = 34. Total: 8 * 34 = 272.",
        "enunciado": "Uma loja vende camisas cujo valor unitário com desconto é dado por V(x). Qual será o valor total pago por 8 camisas?",
        "alternativas": {
            "A": "34",  # Erro! 34 é o valor unitário, não o total pedido
            "B": "50",
            "C": "272",
            "D": "300",
            "E": "350"
        },
        "gabarito": "A",  # Erro! Gabarito deveria ser C (272)
        "justificativa": "Calculamos V(8) = 34. Logo a alternativa A está correta."
    }

    is_valid, error, item = validate_questao_inedita(payload_shortcut)
    assert is_valid is False
    assert item is None
    assert "Shortcut Reasoning" in error or "Inconsistência semântica" in error

