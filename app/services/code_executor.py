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

# Constantes numéricas matemáticas, geométricas, fracionárias e temporais permitidas no código
ALLOWED_NUMERIC_CONSTANTS: Set[float] = {
    0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 12.0, 15.0,
    24.0, 30.0, 60.0, 100.0, 180.0, 360.0, 365.0, 1000.0, 3600.0, 10000.0,
    0.5, 0.25, 0.75, 0.1, 0.01, 0.001, 3.14, 3.1415, 3.1416
}

# Mapeamento de numerais por extenso e termos quantitativos/temporais comuns em enunciados
PORTUGUESE_WORD_NUMBERS: Dict[str, List[float]] = {
    "um": [1.0], "uma": [1.0], "unico": [1.0], "unica": [1.0],
    "dois": [2.0], "duas": [2.0], "dobro": [2.0], "duplo": [2.0], "ambos": [2.0], "ambas": [2.0],
    "meio": [0.5, 2.0], "metade": [0.5, 2.0],
    "tres": [3.0], "triplo": [3.0], "terco": [3.0], "terca": [3.0],
    "quatro": [4.0], "quadruplo": [4.0], "quarto": [0.25, 4.0],
    "cinco": [5.0], "quinto": [0.2, 5.0],
    "seis": [6.0], "meia": [6.0, 0.5],
    "sete": [7.0], "oito": [8.0], "nove": [9.0], "dez": [10.0], "dezena": [10.0],
    "onze": [11.0], "doze": [12.0], "duzia": [12.0],
    "treze": [13.0], "quatorze": [14.0], "catorze": [14.0], "quinze": [15.0], "quinzena": [15.0],
    "dezesseis": [16.0], "dezessete": [17.0], "dezoito": [18.0], "dezenove": [19.0],
    "vinte": [20.0], "trinta": [30.0], "quarenta": [40.0], "cinquenta": [50.0],
    "sessenta": [60.0], "setenta": [70.0], "oitenta": [80.0], "noventa": [90.0],
    "cem": [100.0], "cento": [100.0], "centena": [100.0],
    "duzentos": [200.0], "duzentas": [200.0], "trezentos": [300.0], "trezentas": [300.0],
    "quatrocentos": [400.0], "quinhentos": [500.0], "seiscentos": [600.0],
    "setecentos": [700.0], "oitocentos": [800.0], "novecentos": [900.0],
    "mil": [1000.0], "milhao": [1000000.0], "milhoes": [1000000.0],
    "semana": [7.0], "semanas": [7.0], "semanal": [7.0], "semanalmente": [7.0],
    "mes": [30.0, 12.0], "meses": [30.0, 12.0], "mensal": [30.0, 12.0], "mensalmente": [30.0, 12.0],
    "bimestre": [2.0, 60.0], "bimestral": [2.0, 60.0],
    "trimestre": [3.0, 90.0], "trimestral": [3.0, 90.0],
    "semestre": [6.0, 180.0], "semestral": [6.0, 180.0],
    "ano": [12.0, 365.0], "anos": [12.0, 365.0], "anual": [12.0, 365.0], "anualmente": [12.0, 365.0],
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


def auto_heal_distractors(
    correta_val: Any,
    distratores_vals: List[Any]
) -> List[str]:
    """
    Auto-Healing Algorítmico Determinístico (Abordagem 1 / Decisão DSR):
    Quando a função resolver() retorna distratores com duplicatas entre si ou que
    colidem com a resposta correta, esta função recupera a questão em tempo de execução
    sem necessidade de nova inferência no LLM:
    1. Preserva a resposta correta e todos os distratores que já são únicos.
    2. Identifica os valores em colisão ou faltantes.
    3. Infere a escala e natureza dos dados (inteiros ou decimais, passo delta característico).
    4. Gera substitutos plausíveis baseados em erros cognitivos típicos do ENEM
       (progressão de escala, variações de delta, proporções clássicas, etc.).
    5. Retorna exatamente 4 strings formatadas de distratores, garantindo unicidade estrita
       em conjunto com a resposta correta (total de 5 opções mutuamente exclusivas).
    """
    correta_str = format_number(correta_val)
    seen: Set[str] = {correta_str}
    accepted: List[str] = []

    for d in distratores_vals:
        d_str = format_number(d)
        if d_str not in seen:
            seen.add(d_str)
            accepted.append(d_str)

    if len(accepted) == 4:
        return accepted

    # Tenta resolver numericamente via inferência da distribuição
    try:
        c_num = float(correta_val)
        all_nums: List[float] = [c_num]
        for d in distratores_vals:
            try:
                all_nums.append(float(d))
            except (ValueError, TypeError):
                pass

        is_int = c_num.is_integer() and all(n.is_integer() for n in all_nums)
        unique_floats = sorted(list(set(all_nums)))

        # Calcula passo delta característico da questão
        if len(unique_floats) >= 2:
            diffs = [
                unique_floats[i + 1] - unique_floats[i]
                for i in range(len(unique_floats) - 1)
                if unique_floats[i + 1] - unique_floats[i] > 1e-4
            ]
            delta = min(diffs) if diffs else 1.0
        else:
            base = abs(c_num) if abs(c_num) > 0 else 1.0
            delta = max(1.0, round(base * 0.2)) if is_int else round(base * 0.2, 2)
            if delta == 0:
                delta = 1.0

        if is_int and delta < 1.0:
            delta = 1.0

        min_val = min(unique_floats)
        max_val = max(unique_floats)
        all_non_negative = all(x >= 0 for x in unique_floats)

        candidates: List[float] = []

        # 1. Progressão por passos acima do máximo e abaixo do mínimo
        for k in range(1, 25):
            candidates.append(max_val + k * delta)
            cand_below = min_val - k * delta
            if not all_non_negative or cand_below >= 0:
                candidates.append(cand_below)

            # Passos em torno da resposta correta
            candidates.append(c_num + k * delta)
            cand_c_below = c_num - k * delta
            if not all_non_negative or cand_c_below >= 0:
                candidates.append(cand_c_below)

        # 2. Erros proporcionais e de escala clássicos do ENEM
        if c_num != 0:
            candidates.append(c_num * 2.0)
            candidates.append(c_num * 1.5)
            candidates.append(c_num * 0.5)
            if is_int:
                candidates.append(c_num + 1.0)
                if not all_non_negative or c_num - 1.0 >= 0:
                    candidates.append(c_num - 1.0)
                candidates.append(c_num + 2.0)
                if not all_non_negative or c_num - 2.0 >= 0:
                    candidates.append(c_num - 2.0)
            if abs(c_num) >= 10:
                candidates.append(c_num * 10.0)
                candidates.append(c_num / 10.0)

        for cand in candidates:
            if is_int:
                cand = round(cand)
            cand_str = format_number(cand)
            if cand_str not in seen:
                seen.add(cand_str)
                accepted.append(cand_str)
                if len(accepted) == 4:
                    break

    except (ValueError, TypeError):
        pass

    # Fallback seguro para strings ou valores não numéricos residuais
    suffix_idx = 1
    while len(accepted) < 4:
        cand_str = f"{correta_str} (Opção {suffix_idx})"
        if cand_str not in seen:
            seen.add(cand_str)
            accepted.append(cand_str)
        suffix_idx += 1

    return accepted


def _get_target_names(target: ast.AST) -> Set[str]:
    """Extrai nomes de variáveis atribuídas em um alvo de atribuição (Name, Tuple, List, Subscript)."""
    return {node.id for node in ast.walk(target) if isinstance(node, ast.Name)}


def _get_loaded_names(node: ast.AST) -> Set[str]:
    """Extrai identificadores de variáveis lidos (Load) em uma subárvore AST."""
    return {
        sub.id for sub in ast.walk(node)
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load)
    }


def _extract_numbers_from_ast_node(node: ast.AST) -> Set[float]:
    """Extrai literais numéricos (int/float, excluindo bool) de uma subárvore AST."""
    nums: Set[float] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, (int, float)) and not isinstance(sub.value, bool):
            nums.add(float(sub.value))
    return nums


def _extract_correta_code_numbers(code: str) -> Set[float]:
    """
    Extrai via AST apenas os literais numéricos que participam direta ou indiretamente
    do cálculo da resposta 'correta', ignorando números usados exclusivamente na construção
    dos 'distratores' (ex: d1 = correta + 50, d2 = correta * 1.5).
    """
    clean_code = sanitize_solver_code(code)
    try:
        tree = ast.parse(clean_code)
    except SyntaxError:
        code_before_return = clean_code.split("return")[0] if "return" in clean_code else clean_code
        code_no_comments = re.sub(r"#.*", "", code_before_return)
        return {float(n) for n in re.findall(r"\b\d+(?:\.\d+)?\b", code_no_comments)}

    # Localiza o dicionário de retorno contendo a chave 'correta'
    result_dicts: List[ast.Dict] = []
    correta_exprs: List[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == "correta" and v is not None:
                    result_dicts.append(node)
                    correta_exprs.append(v)

    if not correta_exprs:
        # Fallback se não encontrar dicionário literal com chave 'correta'
        return _extract_numbers_from_ast_node(tree)

    needed_vars: Set[str] = set()
    relevant_nodes: List[ast.AST] = []
    for expr in correta_exprs:
        needed_vars.update(_get_loaded_names(expr))
        if not isinstance(expr, ast.Constant):
            relevant_nodes.append(expr)

    # Coleta todas as instruções (statements) dentro da AST
    all_stmts: List[ast.stmt] = [n for n in ast.walk(tree) if isinstance(n, ast.stmt)]
    relevant_stmts: Set[ast.stmt] = set()

    # Ponto fixo: propaga dependências reversas a partir das variáveis usadas em 'correta'
    changed = True
    while changed:
        changed = False
        for stmt in all_stmts:
            if stmt in relevant_stmts:
                continue

            if isinstance(stmt, ast.Assign):
                # Ignora atribuição direta do próprio dicionário final {'correta': ..., 'distratores': ...}
                if stmt.value in result_dicts:
                    continue
                targets: Set[str] = set()
                for t in stmt.targets:
                    targets.update(_get_target_names(t))
                if targets & needed_vars:
                    relevant_stmts.add(stmt)
                    relevant_nodes.append(stmt.value)
                    needed_vars.update(_get_loaded_names(stmt.value))
                    for t in stmt.targets:
                        needed_vars.update(_get_loaded_names(t))
                    changed = True

            elif isinstance(stmt, ast.AugAssign):
                targets = _get_target_names(stmt.target)
                if targets & needed_vars:
                    relevant_stmts.add(stmt)
                    relevant_nodes.append(stmt.value)
                    needed_vars.update(_get_loaded_names(stmt.value))
                    needed_vars.update(_get_loaded_names(stmt.target))
                    changed = True

            elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
                if stmt.value in result_dicts:
                    continue
                targets = _get_target_names(stmt.target)
                if targets & needed_vars:
                    relevant_stmts.add(stmt)
                    relevant_nodes.append(stmt.value)
                    needed_vars.update(_get_loaded_names(stmt.value))
                    changed = True

            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                # Captura mutações de listas/dicionários relevantes (ex: valores.append(1200))
                func = stmt.value.func
                if isinstance(func, ast.Attribute):
                    owner_vars = _get_loaded_names(func.value)
                    if owner_vars & needed_vars:
                        relevant_stmts.add(stmt)
                        relevant_nodes.append(stmt.value)
                        needed_vars.update(_get_loaded_names(stmt.value))
                        changed = True

            elif isinstance(stmt, ast.For):
                target_vars = _get_target_names(stmt.target)
                body_relevant = any(child in relevant_stmts for child in ast.walk(stmt) if isinstance(child, ast.stmt) and child is not stmt)
                if (target_vars & needed_vars) or body_relevant:
                    relevant_stmts.add(stmt)
                    relevant_nodes.append(stmt.iter)
                    needed_vars.update(_get_loaded_names(stmt.iter))
                    changed = True

            elif isinstance(stmt, (ast.While, ast.If)):
                body_relevant = any(child in relevant_stmts for child in ast.walk(stmt) if isinstance(child, ast.stmt) and child is not stmt)
                if body_relevant:
                    relevant_stmts.add(stmt)
                    relevant_nodes.append(stmt.test)
                    needed_vars.update(_get_loaded_names(stmt.test))
                    changed = True

    code_floats: Set[float] = set()
    for node in relevant_nodes:
        code_floats.update(_extract_numbers_from_ast_node(node))
    return code_floats


def validate_solver_consistency(
    enunciado: str,
    code: str,
    result: Dict[str, Any]
) -> List[str]:
    """
    Valida a consistência matemática e o nexo entre o código do solver e o texto do enunciado:
    1. Unicidade estrita: o gabarito e os 4 distratores devem ser distintos (com Auto-Healing).
    2. Checagem de nexo numérico: todo número utilizado no cálculo da resposta 'correta' deve estar presente no enunciado.
    Retorna a lista de 5 valores formatados [correta, distrator1, distrator2, distrator3, distrator4].
    """
    correta_val = result["correta"]
    distratores_vals = result["distratores"]

    correta_str = format_number(correta_val)
    dist_strs = [format_number(d) for d in distratores_vals]
    all_values = [correta_str] + dist_strs

    # 1. Validação de Unicidade com Auto-Healing Algorítmico (Abordagem 1)
    if len(set(all_values)) != 5:
        logger.warning(
            f"Auto-Healing: Colisão de alternativas detectada no solver ({all_values}). "
            f"Acionando auto-cura algorítmica para garantir unicidade estrita..."
        )
        dist_strs = auto_heal_distractors(
            correta_val=correta_val,
            distratores_vals=distratores_vals
        )
        all_values = [correta_str] + dist_strs
        logger.info(f"Auto-Healing: Alternativas curadas com sucesso: {all_values}")

    if len(set(all_values)) != 5:
        duplicates = [v for v in all_values if all_values.count(v) > 1]
        raise ValueError(
            f"Alternativas duplicadas geradas pelo solver mesmo após auto-healing: {all_values}. Valores repetidos: {set(duplicates)}."
        )

    # 2. Checagem de Nexo Numérico (Groundedness) restrita ao cálculo da resposta 'correta' via AST
    code_floats = _extract_correta_code_numbers(code)

    # Extrai números presentes no enunciado com suporte a separador de milhar brasileiro,
    # numerais por extenso, complementos percentuais e conversões diretas de escala/geometria.
    base_enun_floats: Set[float] = set()

    # 1. Padrão de milhar brasileiro: ex 1.200 ou 1.200,50 (mesmo se colado a unidade/símbolo)
    for match in re.finditer(r"(?<!\d)\d{1,3}(?:\.\d{3})+(?:,\d+)?(?!\d)", enunciado):
        raw_val = match.group(0).replace(".", "").replace(",", ".")
        try:
            base_enun_floats.add(float(raw_val))
        except ValueError:
            pass

    # 2. Padrão decimal padrão ou inteiro simples: ex 34, 12.5, 12,5, 20m, 40kg
    raw_enun_matches = re.findall(r"(?<!\d)\d+(?:[\.,]\d+)?(?!\d)", enunciado)
    for n in raw_enun_matches:
        try:
            base_enun_floats.add(float(n.replace(",", ".")))
        except ValueError:
            pass

    # 3. Numerais por extenso e termos temporais/quantitativos em português
    import unicodedata
    norm_text = "".join(
        c for c in unicodedata.normalize("NFKD", enunciado.lower())
        if not unicodedata.combining(c)
    )
    words_in_enun = set(re.findall(r"\b[a-z]+\b", norm_text))
    for word in words_in_enun:
        if word in PORTUGUESE_WORD_NUMBERS:
            base_enun_floats.update(PORTUGUESE_WORD_NUMBERS[word])

    enun_floats: Set[float] = set(base_enun_floats)

    # 4. Derivações diretas de escala métrica (x10, x100, x1000, /10, /100, /1000) e geometria (raio=d/2, dobro=2x)
    for val in base_enun_floats:
        if val != 0:
            enun_floats.update({
                round(val * 10.0, 6),
                round(val * 100.0, 6),
                round(val * 1000.0, 6),
                round(val / 10.0, 6),
                round(val / 100.0, 6),
                round(val / 1000.0, 6),
                round(val / 2.0, 6),
                round(val * 2.0, 6),
            })

    # 5. Tratamento de porcentagens e seus complementos: ex '20%' -> 20, 0.2, 80, 0.8, 1.2
    for match in re.finditer(r"(\d+(?:[\.,]\d+)?)\s*%", enunciado):
        val_str = match.group(1).replace(",", ".")
        try:
            val_pct = float(val_str)
            dec_pct = round(val_pct / 100.0, 6)
            enun_floats.update({
                val_pct,
                dec_pct,
                round(100.0 - val_pct, 6),
                round(1.0 - dec_pct, 6),
                round(1.0 + dec_pct, 6),
            })
        except ValueError:
            pass

    allowed_all = enun_floats | ALLOWED_NUMERIC_CONSTANTS

    def _is_grounded(target: float) -> bool:
        if target in allowed_all:
            return True
        return any(abs(target - candidate) <= 1e-6 for candidate in allowed_all)

    # Identifica números no código que não constam no enunciado nem na lista de constantes permitidas
    missing_numbers = {n for n in code_floats if not _is_grounded(n)}

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
