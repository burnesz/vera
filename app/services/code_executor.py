"""
Módulo de execução segura e validação de solvers em código Python para geração de questões.
Atende à arquitetura Program-Aided Generation (PoT):
1. Execução isolada em subprocess com timeout estrito.
2. Bloqueio preventivo de módulos e funções sensíveis via AST.
3. Validação de nexo numérico entre o enunciado e o código do solver.
4. Unicidade estrita e montagem programática das alternativas (A a E) e gabarito.
"""

import ast
import json
import logging
import random
import re
import subprocess
import sys
from typing import Dict, Any, List, Tuple, Set, Optional

logger = logging.getLogger(__name__)

# Módulos e funções bloqueados por segurança na análise estática do solver
BLOCKED_MODULES = {
    "os", "sys", "subprocess", "socket", "shutil", "urllib", "requests",
    "http", "ftplib", "smtplib", "telnetlib", "pathlib", "posix", "nt",
    "pty", "commands", "builtin", "builtins", "_thread", "threading",
    "multiprocessing", "ctypes", "pickle", "shelve", "dbm", "sqlite3"
}

BLOCKED_CALLS = {
    "eval", "exec", "compile", "__import__", "open", "getattr", "setattr",
    "delattr", "input", "exit", "quit", "breakpoint"
}

# Constantes numéricas matemáticas, geométricas e temporais neutras permitidas no código
ALLOWED_NUMERIC_CONSTANTS: Set[float] = {
    float(i) for i in range(51)
} | {
    60.0, 70.0, 80.0, 90.0, 100.0, 180.0, 200.0, 360.0, 365.0, 500.0, 1000.0,
    0.01, 0.02, 0.05, 0.1, 0.2, 0.25, 0.5, 0.75, 0.8, 1.1, 1.2, 1.25, 1.5, 2.5,
    3.14, 3.1415, 3.1416
}


def sanitize_solver_code(code: str) -> str:
    """
    Remove marcações de código markdown (```python ... ```) e espaços em branco excessivos.
    """
    code = code.strip()
    match = re.search(r"```(?:python)?\s*(.*?)\s*```", code, re.DOTALL | re.IGNORECASE)
    if match:
        code = match.group(1).strip()
    return code


def check_code_safety(code: str) -> None:
    """
    Realiza inspeção estática da AST do código para bloquear operações e imports potencialmente inseguros.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"Erro de sintaxe no código Python do solver: {e}")

    for node in ast.walk(tree):
        # Bloqueia import de módulos restritos
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_pkg = alias.name.split(".")[0]
                if root_pkg in BLOCKED_MODULES:
                    raise PermissionError(f"Import não permitido no solver: '{alias.name}'")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_pkg = node.module.split(".")[0]
                if root_pkg in BLOCKED_MODULES:
                    raise PermissionError(f"ImportFrom não permitido no solver: '{node.module}'")
        # Bloqueia chamadas a funções perigosas
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BLOCKED_CALLS:
                raise PermissionError(f"Chamada de função não permitida no solver: '{node.func.id}()'")


def execute_solver_code(code: str, timeout: int = 5) -> Dict[str, Any]:
    """
    Executa a função resolver() em um processo filho isolado com timeout estrito.
    Retorna o dicionário com 'correta' e 'distratores'.
    """
    clean_code = sanitize_solver_code(code)
    check_code_safety(clean_code)

    if "def resolver" not in clean_code:
        raise ValueError("O código fornecido não define a função obrigatória 'def resolver()'.")

    # Script wrapper seguro para execução em processo isolado
    runner_script = f"""
import json
import math

{clean_code}

try:
    res = resolver()
    print("___RESULT_START___")
    print(json.dumps(res))
    print("___RESULT_END___")
except Exception as e:
    import sys
    sys.stderr.write(f"EXCECAO_SOLVER: {{type(e).__name__}}: {{str(e)}}")
    sys.exit(1)
"""

    try:
        proc = subprocess.run(
            [sys.executable, "-c", runner_script],
            capture_output=True,
            text=True,
            timeout=timeout
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"O solver excedeu o tempo limite de execução ({timeout}s). Possível loop infinito.")

    if proc.returncode != 0:
        err_msg = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"Falha na execução do solver: {err_msg[:400]}")

    stdout = proc.stdout
    start_tag = "___RESULT_START___"
    end_tag = "___RESULT_END___"

    if start_tag not in stdout or end_tag not in stdout:
        raise ValueError(f"Saída do solver não formatada corretamente. Stdout: {stdout[:300]}")

    start_idx = stdout.find(start_tag) + len(start_tag)
    end_idx = stdout.find(end_tag)
    raw_json = stdout[start_idx:end_idx].strip()

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Não foi possível decodificar o JSON retornado por resolver(): {e}. Raw: {raw_json}")

    if not isinstance(data, dict):
        raise ValueError(f"O retorno de resolver() deve ser um dicionário. Obtido: {type(data).__name__}")

    if "correta" not in data or "distratores" not in data:
        raise ValueError("O dicionário retornado por resolver() deve conter as chaves 'correta' e 'distratores'.")

    if not isinstance(data["distratores"], (list, tuple)) or len(data["distratores"]) != 4:
        raise ValueError(f"A chave 'distratores' deve conter exatamente 4 valores. Encontrado: {len(data.get('distratores', []))}")

    return data


def format_number(val: Any) -> str:
    """
    Formata valores numéricos para apresentação limpa em português:
    - Inteiros: '34'
    - Decimais: '12,5' ou '3,75' (máximo 2 casas decimais, cortando zeros finais)
    """
    try:
        num = float(val)
    except (ValueError, TypeError):
        return str(val).strip()

    if num.is_integer():
        return str(int(num))

    # Formata com até 2 casas decimais, remove zeros à direita e substitui ponto por vírgula
    formatted = f"{num:.2f}".rstrip("0").rstrip(".")
    return formatted.replace(".", ",")


def validate_solver_consistency(
    enunciado: str,
    code: str,
    result: Dict[str, Any]
) -> List[str]:
    """
    Valida a consistência matemática e o nexo entre o código do solver e o texto do enunciado:
    1. Unicidade estrita: o gabarito e os 4 distratores devem ser distintos.
    2. Checagem de nexo numérico: todo número utilizado no código antes do return deve estar presente no enunciado.
    Retorna a lista de 5 valores formatados [correta, distrator1, distrator2, distrator3, distrator4].
    """
    correta_val = result["correta"]
    distratores_vals = result["distratores"]

    correta_str = format_number(correta_val)
    dist_strs = [format_number(d) for d in distratores_vals]
    all_values = [correta_str] + dist_strs

    # 1. Validação de Unicidade
    if len(set(all_values)) != 5:
        duplicates = [v for v in all_values if all_values.count(v) > 1]
        raise ValueError(
            f"Alternativas duplicadas geradas pelo solver: {all_values}. Valores repetidos: {set(duplicates)}."
        )

    # 2. Checagem de Nexo Numérico (Groundedness)
    # Extrai o corpo do código antes do 'return' e remove comentários
    code_before_return = code.split("return")[0] if "return" in code else code
    code_no_comments = re.sub(r"#.*", "", code_before_return)

    # Extrai todos os números literais no código
    raw_code_nums = re.findall(r"\b\d+(?:\.\d+)?\b", code_no_comments)
    code_floats: Set[float] = set()
    for n in raw_code_nums:
        try:
            code_floats.add(float(n))
        except ValueError:
            pass

    # Extrai números presentes no enunciado com suporte a separador de milhar brasileiro (1.200 ou 1.200,50)
    enun_floats: Set[float] = set()

    # 1. Padrão de milhar brasileiro: ex 1.200 ou 1.200,50
    for match in re.finditer(r"\b\d{1,3}(?:\.\d{3})+(?:,\d+)?\b", enunciado):
        raw_val = match.group(0).replace(".", "").replace(",", ".")
        try:
            enun_floats.add(float(raw_val))
        except ValueError:
            pass

    # 2. Padrão decimal padrão ou inteiro simples: ex 34, 12.5, 12,5
    raw_enun_matches = re.findall(r"\b\d+(?:[\.,]\d+)?\b", enunciado)
    for n in raw_enun_matches:
        try:
            enun_floats.add(float(n.replace(",", ".")))
        except ValueError:
            pass

    # 3. Tratamento de porcentagens: ex '2%' ou '15%' -> adiciona também 0.02 e 0.15
    for match in re.finditer(r"(\d+(?:[\.,]\d+)?)\s*%", enunciado):
        val_str = match.group(1).replace(",", ".")
        try:
            val_pct = float(val_str)
            enun_floats.add(round(val_pct / 100.0, 6))
        except ValueError:
            pass

    # Identifica números no código que não constam no enunciado nem na lista de constantes neutras
    missing_numbers = {
        n for n in code_floats
        if n not in enun_floats and n not in ALLOWED_NUMERIC_CONSTANTS
    }

    if missing_numbers:
        missing_fmt = sorted([int(x) if x.is_integer() else x for x in missing_numbers])
        raise ValueError(
            f"Números utilizados na lógica do solver ausentes no enunciado da questão: {missing_fmt}. "
            f"O enunciado e o solver devem utilizar os mesmos dados numéricos."
        )

    return all_values


def assemble_alternatives_and_gabarito(
    formatted_values: List[str]
) -> Tuple[Dict[str, str], str]:
    """
    Embaralha de forma aleatória a resposta correta e os 4 distratores,
    atribuindo as letras A a E e determinando o gabarito oficial com garantia matemática.
    """
    correta = formatted_values[0]
    shuffled = list(formatted_values)
    random.shuffle(shuffled)

    letras = ["A", "B", "C", "D", "E"]
    alternativas = {letra: valor for letra, valor in zip(letras, shuffled)}
    gabarito = letras[shuffled.index(correta)]

    return alternativas, gabarito
