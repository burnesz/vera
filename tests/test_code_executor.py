import pytest
from app.services.code_executor import (
    execute_solver_code,
    check_code_safety,
    validate_solver_consistency,
    assemble_alternatives_and_gabarito,
    format_number,
    sanitize_solver_code,
    auto_heal_distractors
)


def test_format_number():
    assert format_number(34) == "34"
    assert format_number(34.0) == "34"
    assert format_number(12.5) == "12,5"
    assert format_number(12.50) == "12,5"
    assert format_number(3.14) == "3,14"
    assert format_number("teste") == "teste"


def test_sanitize_solver_code():
    code_with_md = "```python\ndef resolver():\n    return {'correta': 1, 'distratores': [2, 3, 4, 5]}\n```"
    cleaned = sanitize_solver_code(code_with_md)
    assert cleaned.startswith("def resolver():")
    assert not cleaned.endswith("```")


def test_execute_solver_code_success():
    code = """
def resolver():
    preco = 50.0
    desc = 0.20
    final = preco * (1 - desc)
    d1 = preco * desc  # 10
    d2 = preco * 1.20  # 60
    d3 = preco + 10    # 60 (ajustando para 65)
    d4 = 35.0
    return {
        'correta': final,
        'distratores': [10.0, 60.0, 65.0, 35.0]
    }
"""
    result = execute_solver_code(code, timeout=3)
    assert "correta" in result
    assert result["correta"] == 40.0
    assert len(result["distratores"]) == 4


def test_check_code_safety_blocked_imports():
    code_os = "import os\ndef resolver():\n    return {'correta': 1, 'distratores': [2, 3, 4, 5]}"
    with pytest.raises(PermissionError, match="Import não permitido"):
        check_code_safety(code_os)

    code_sub = "from subprocess import run\ndef resolver():\n    return {'correta': 1, 'distratores': [2, 3, 4, 5]}"
    with pytest.raises(PermissionError, match="ImportFrom não permitido"):
        check_code_safety(code_sub)


def test_check_code_safety_blocked_calls():
    code_eval = "def resolver():\n    eval('2+2')\n    return {'correta': 4, 'distratores': [1, 2, 3, 5]}"
    with pytest.raises(PermissionError, match="Chamada de função não permitida"):
        check_code_safety(code_eval)

    code_open = "def resolver():\n    open('/etc/passwd')\n    return {'correta': 1, 'distratores': [2, 3, 4, 5]}"
    with pytest.raises(PermissionError, match="Chamada de função não permitida"):
        check_code_safety(code_open)


def test_execute_solver_code_timeout():
    code_infinite = """
def resolver():
    while True:
        pass
    return {'correta': 1, 'distratores': [2, 3, 4, 5]}
"""
    with pytest.raises(TimeoutError, match="tempo limite de execução"):
        execute_solver_code(code_infinite, timeout=1)


def test_validate_solver_consistency_valid():
    enunciado = (
        "Um reservatório com capacidade de 1.200 litros é abastecido a uma taxa de 40 litros por minuto, "
        "enquanto uma válvula esvazia a 10 litros por minuto. Qual o tempo necessário para enchê-lo?"
    )
    code = """
def resolver():
    capacidade = 1200
    entrada = 40
    saida = 10
    taxa = entrada - saida
    tempo = capacidade / taxa
    return {'correta': tempo, 'distratores': [30, 50, 60, 80]}
"""
    result = {'correta': 40.0, 'distratores': [30.0, 50.0, 60.0, 80.0]}
    formatted_vals = validate_solver_consistency(enunciado, code, result)
    assert len(formatted_vals) == 5
    assert formatted_vals[0] == "40"
    assert "30" in formatted_vals


def test_auto_heal_distractors_with_duplicates_and_correct_collision():
    # Caso 1: Colisão com a correta (10) e repetição de distratores (30 e 30)
    correta = 10
    distratores = [10, 20, 30, 30]
    healed = auto_heal_distractors(correta, distratores)
    assert len(healed) == 4
    # Todos devem ser distintos entre si e distintos da resposta correta ("10")
    all_5 = [format_number(correta)] + healed
    assert len(set(all_5)) == 5
    assert "10" not in healed
    assert "20" in healed
    assert "30" in healed


def test_auto_heal_distractors_float_values():
    # Caso 2: Valores decimais
    correta = 12.5
    distratores = [10.0, 12.5, 15.0, 15.0]
    healed = auto_heal_distractors(correta, distratores)
    assert len(healed) == 4
    all_5 = [format_number(correta)] + healed
    assert len(set(all_5)) == 5
    assert "12,5" not in healed


def test_validate_solver_consistency_auto_heals_duplicate_alternatives():
    enunciado = "Teste com 100 reais e taxa de 10%."
    code = "def resolver():\n    return {'correta': 10, 'distratores': [10, 20, 30, 40]}"
    result = {'correta': 10, 'distratores': [10, 20, 30, 40]}  # Duplicata: 10 e 10

    formatted_vals = validate_solver_consistency(enunciado, code, result)
    assert len(formatted_vals) == 5
    assert len(set(formatted_vals)) == 5
    assert formatted_vals[0] == "10"


def test_validate_solver_consistency_missing_nexo_fails():
    enunciado = "Um comerciante comprou 5 caixas por 20 reais cada."
    code = """
def resolver():
    qtd = 5
    unit = 20
    # Alucinação: 99 não consta no enunciado nem é constante neutra
    bonus = 99
    total = (qtd * unit) + bonus
    return {'correta': total, 'distratores': [100, 150, 180, 200]}
"""
    result = {'correta': 199, 'distratores': [100, 150, 180, 200]}

    with pytest.raises(ValueError, match="Números utilizados na lógica do solver ausentes"):
        validate_solver_consistency(enunciado, code, result)


def test_validate_solver_consistency_ignores_distractor_only_constants():
    """Constantes auxiliares usadas apenas nos distratores (ex: +15, *1.25, 999) não devem reprovar o nexo de 'correta'."""
    enunciado = (
        "Um reservatório com capacidade de 1.200 litros é abastecido a 40 litros por minuto, "
        "com saída de 10 litros por minuto. Qual o tempo para enchê-lo?"
    )
    code = """
def resolver():
    capacidade = 1200
    entrada = 40
    saida = 10
    taxa = entrada - saida
    tempo = capacidade / taxa
    d1 = capacidade / entrada
    d2 = tempo + 15
    d3 = tempo * 1.25
    d4 = 999
    return {'correta': tempo, 'distratores': [d1, d2, d3, d4]}
"""
    result = {'correta': 40.0, 'distratores': [30.0, 55.0, 50.0, 999.0]}
    formatted_vals = validate_solver_consistency(enunciado, code, result)
    assert formatted_vals[0] == "40"
    assert len(formatted_vals) == 5


def test_assemble_alternatives_and_gabarito():
    formatted_vals = ["40", "30", "50", "60", "80"]
    alternativas, gabarito = assemble_alternatives_and_gabarito(formatted_vals)

    assert set(alternativas.keys()) == {"A", "B", "C", "D", "E"}
    assert len(set(alternativas.values())) == 5
    assert gabarito in {"A", "B", "C", "D", "E"}
    assert alternativas[gabarito] == "40"
