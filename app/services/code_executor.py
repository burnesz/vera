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
    0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 10.0, 12.0, 24.0, 60.0, 100.0, 180.0, 360.0, 1000.0,
    0.5, 0.1, 0.01, 3.14, 3.1415, 3.1416
}

# Mapeamento de numerais por extenso e termos quantitativos/fracionários em português para nexo numérico
_WORDS_TO_NUMBERS: Dict[str, float] = {
    "zero": 0.0,
    "um": 1.0, "uma": 1.0, "unico": 1.0, "único": 1.0, "unica": 1.0, "única": 1.0,
    "dois": 2.0, "duas": 2.0, "ambos": 2.0, "ambas": 2.0, "par": 2.0, "dobro": 2.0, "duplo": 2.0, "bimestre": 2.0, "bimestral": 2.0,
    "tres": 3.0, "três": 3.0, "triplo": 3.0, "trimestre": 3.0, "trimestral": 3.0,
    "quatro": 4.0, "quadruplo": 4.0, "quádruplo": 4.0, "quadrimestre": 4.0,
    "cinco": 5.0, "quintuplo": 5.0, "quíntuplo": 5.0,
    "seis": 6.0, "semestre": 6.0, "semestral": 6.0, "meia": 6.0,
    "sete": 7.0,
    "oito": 8.0,
    "nove": 9.0,
    "dez": 10.0, "dezena": 10.0, "decada": 10.0, "década": 10.0,
    "onze": 11.0,
    "doze": 12.0, "duzia": 12.0, "dúzia": 12.0,
    "treze": 13.0,
    "quatorze": 14.0, "catorze": 14.0,
    "quinze": 15.0, "quinzena": 15.0,
    "dezesseis": 16.0,
    "dezessete": 17.0,
    "dezoito": 18.0,
    "dezenove": 19.0,
    "vinte": 20.0,
    "trinta": 30.0,
    "quarenta": 40.0,
    "cinquenta": 50.0,
    "sessenta": 60.0,
    "setenta": 70.0,
    "oitenta": 80.0,
    "noventa": 90.0,
    "cem": 100.0, "cento": 100.0, "centena": 100.0,
    "duzentos": 200.0, "duzentas": 200.0,
    "trezentos": 300.0, "trezentas": 300.0,
    "quatrocentos": 400.0, "quatrocentas": 400.0,
    "quinhentos": 500.0, "quinhentas": 500.0,
    "seiscentos": 600.0, "seiscentas": 600.0,
    "setecentos": 700.0, "setecentas": 700.0,
    "oitocentos": 800.0, "oitocentas": 800.0,
    "novecentos": 900.0, "novecentas": 900.0,
    "mil": 1000.0,
    "meio": 0.5, "metade": 0.5,
    "terco": 3.0, "terço": 3.0, "terca": 3.0, "terça": 3.0,
    "quarto": 4.0, "quarta": 4.0,
    "quinto": 5.0, "quinta": 5.0,
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


import builtins

ALLOWED_BUILTINS: Set[str] = set(dir(builtins)) | {"math", "json", "resolver"}


def _extract_store_names(node: ast.AST) -> Set[str]:
    """Extrai todos os identificadores atribuídos (ctx=Store) em um nó de destino da AST."""
    names: Set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
            names.add(sub.id)
    return names


def _check_expr_free_vars(node: Optional[ast.AST], bound: Set[str]) -> Optional[str]:
    """
    Inspeciona recursivamente uma expressão AST buscando nomes livres (ast.Name com ctx=Load)
    não presentes em `bound`, respeitando o escopo local de comprehensions e lambdas.
    """
    if node is None:
        return None

    if isinstance(node, ast.Name):
        if isinstance(node.ctx, ast.Load) and node.id not in bound:
            return node.id
        return None

    if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
        comp_bound = set(bound)
        for gen in node.generators:
            free = _check_expr_free_vars(gen.iter, comp_bound)
            if free:
                return free
            comp_bound.update(_extract_store_names(gen.target))
            for if_clause in gen.ifs:
                free = _check_expr_free_vars(if_clause, comp_bound)
                if free:
                    return free
        if isinstance(node, ast.DictComp):
            free = _check_expr_free_vars(node.key, comp_bound)
            if free:
                return free
            return _check_expr_free_vars(node.value, comp_bound)
        return _check_expr_free_vars(node.elt, comp_bound)

    if isinstance(node, ast.Lambda):
        lam_bound = set(bound)
        for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
            lam_bound.add(arg.arg)
        if node.args.vararg:
            lam_bound.add(node.args.vararg.arg)
        if node.args.kwarg:
            lam_bound.add(node.args.kwarg.arg)
        return _check_expr_free_vars(node.body, lam_bound)

    if isinstance(node, ast.NamedExpr):
        free = _check_expr_free_vars(node.value, bound)
        if free:
            return free
        bound.update(_extract_store_names(node.target))
        return None

    for child in ast.iter_child_nodes(node):
        free = _check_expr_free_vars(child, bound)
        if free:
            return free
    return None


def _check_stmts_free_vars(stmts: List[ast.stmt], bound: Set[str]) -> Optional[str]:
    """Percorre sequencialmente uma lista de statements AST verificando variáveis livres."""
    for stmt in stmts:
        if isinstance(stmt, ast.Assign):
            free = _check_expr_free_vars(stmt.value, bound)
            if free:
                return free
            for target in stmt.targets:
                # Se for indexação/atributo (ex: lista[i] = 1), verifica Loads no target
                if not isinstance(target, ast.Name):
                    for child in ast.iter_child_nodes(target):
                        free = _check_expr_free_vars(child, bound)
                        if free:
                            return free
                bound.update(_extract_store_names(target))
        elif isinstance(stmt, ast.AnnAssign):
            if stmt.value:
                free = _check_expr_free_vars(stmt.value, bound)
                if free:
                    return free
            bound.update(_extract_store_names(stmt.target))
        elif isinstance(stmt, ast.AugAssign):
            if isinstance(stmt.target, ast.Name) and stmt.target.id not in bound:
                return stmt.target.id
            free = _check_expr_free_vars(stmt.target, bound)
            if free:
                return free
            free = _check_expr_free_vars(stmt.value, bound)
            if free:
                return free
        elif isinstance(stmt, (ast.For, ast.AsyncFor)):
            free = _check_expr_free_vars(stmt.iter, bound)
            if free:
                return free
            bound.update(_extract_store_names(stmt.target))
            free = _check_stmts_free_vars(stmt.body, bound)
            if free:
                return free
            free = _check_stmts_free_vars(stmt.orelse, bound)
            if free:
                return free
        elif isinstance(stmt, (ast.While, ast.If)):
            free = _check_expr_free_vars(stmt.test, bound)
            if free:
                return free
            free = _check_stmts_free_vars(stmt.body, bound)
            if free:
                return free
            free = _check_stmts_free_vars(stmt.orelse, bound)
            if free:
                return free
        elif isinstance(stmt, ast.Import):
            for alias in stmt.names:
                bound.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(stmt, ast.ImportFrom):
            for alias in stmt.names:
                bound.add(alias.asname or alias.name)
        elif isinstance(stmt, ast.FunctionDef):
            bound.add(stmt.name)
            fn_bound = set(bound)
            for arg in stmt.args.posonlyargs + stmt.args.args + stmt.args.kwonlyargs:
                fn_bound.add(arg.arg)
            if stmt.args.vararg:
                fn_bound.add(stmt.args.vararg.arg)
            if stmt.args.kwarg:
                fn_bound.add(stmt.args.kwarg.arg)
            free = _check_stmts_free_vars(stmt.body, fn_bound)
            if free:
                return free
        else:
            for child in ast.iter_child_nodes(stmt):
                free = _check_expr_free_vars(child, bound)
                if free:
                    return free
    return None


def check_free_variables(tree: ast.Module) -> None:
    """
    Gate estático (0ms): detecta nomes livres (ex.: `tabela_dados` ou variáveis externas)
    dentro do módulo e de `resolver()` antes de iniciar qualquer subprocesso.
    """
    bound: Set[str] = set(ALLOWED_BUILTINS)
    free = _check_stmts_free_vars(tree.body, bound)
    if free:
        raise ValueError(
            f"Variável externa/livre '{free}' não definida: "
            f"declare os valores como variáveis dentro de resolver(); não use variáveis externas"
        )


def check_code_safety(code: str) -> ast.Module:
    """
    Realiza inspeção estática (0ms) da AST do código para:
    1. Classificar erros de sintaxe (`SyntaxError`).
    2. Bloquear operações e imports potencialmente inseguros.
    3. Detectar variáveis livres / externas não declaradas dentro de `resolver()`.
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

    check_free_variables(tree)
    return tree


def _normalize_five_distractors(correta_val: Any, distratores_vals: List[Any]) -> List[Any]:
    """
    Quando o solver retorna 5 itens na lista 'distratores' (ex.: incluiu o próprio gabarito
    junto com os 4 distratores), verifica se 1 deles é igual ao gabarito (ou duplicado) e
    o descarta para reaproveitar os 4 distratores legítimos.
    """
    if len(distratores_vals) != 5:
        return list(distratores_vals)

    correta_str = format_number(correta_val)
    filtered: List[Any] = []
    removed_one = False
    for d in distratores_vals:
        if not removed_one and format_number(d) == correta_str:
            removed_one = True
            continue
        filtered.append(d)

    if len(filtered) == 4:
        logger.info("Solver retornou 5 distratores com 1 igual à correta; descartado o duplicado do gabarito para reutilizar os 4 distratores.")
        return filtered

    # Caso nenhum seja igual à correta, remove a primeira duplicata interna (se houver) ou mantém os 4 primeiros distintos
    dedup: List[Any] = []
    seen_strs: Set[str] = set()
    for d in distratores_vals:
        d_str = format_number(d)
        if d_str not in seen_strs:
            seen_strs.add(d_str)
            dedup.append(d)
    if len(dedup) >= 4:
        return dedup[:4]

    return list(distratores_vals)[:4]


class _ResolverLocalsTransformer(ast.NodeTransformer):
    """
    Transforma a função top-level `def resolver()` para retornar seu escopo local (`locals()`),
    preservando qualquer retorno explícito em `__explicit_return__` para retrocompatibilidade.
    """

    def __init__(self) -> None:
        super().__init__()
        self._in_resolver = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        if node.name == "resolver" and not self._in_resolver:
            self._in_resolver = True
            new_body = []
            for stmt in node.body:
                visited = self.visit(stmt)
                if isinstance(visited, list):
                    new_body.extend(visited)
                elif visited is not None:
                    new_body.append(visited)
            # Garante retorno de locals() ao final da função resolver()
            ret_locals = ast.Return(
                value=ast.Call(
                    func=ast.Name(id="locals", ctx=ast.Load()),
                    args=[],
                    keywords=[]
                )
            )
            new_body.append(ret_locals)
            node.body = new_body
            self._in_resolver = False
            return node
        # Não transforma funções auxiliares internas
        return node

    def visit_Return(self, node: ast.Return) -> Any:
        if not self._in_resolver:
            return node
        assign_ret = ast.Assign(
            targets=[ast.Name(id="__explicit_return__", ctx=ast.Store())],
            value=node.value if node.value is not None else ast.Constant(value=None)
        )
        ret_locals = ast.Return(
            value=ast.Call(
                func=ast.Name(id="locals", ctx=ast.Load()),
                args=[],
                keywords=[]
            )
        )
        return [assign_ret, ret_locals]


def _instrument_resolver_ast(clean_code: str) -> str:
    """Instrumenta a AST de resolver() para devolver locals() ao executor."""
    tree = ast.parse(clean_code)
    has_resolver = any(
        isinstance(node, ast.FunctionDef) and node.name == "resolver"
        for node in tree.body
    )
    if not has_resolver:
        raise ValueError("O código fornecido não define a função obrigatória 'def resolver()'.")
    transformer = _ResolverLocalsTransformer()
    tree = transformer.visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def execute_solver_code(code: str, timeout: int = 5) -> Dict[str, Any]:
    """
    Executa a função resolver() em um processo filho isolado com timeout estrito.
    Coleta `correta` e variáveis `erro_*` do escopo local (ou retorno explícito legado),
    deduplica distratores e retorna o dicionário com 'correta' e 'distratores'.
    """
    clean_code = sanitize_solver_code(code)
    check_code_safety(clean_code)

    if "def resolver" not in clean_code:
        raise ValueError("O código fornecido não define a função obrigatória 'def resolver()'.")

    instrumented_code = _instrument_resolver_ast(clean_code)

    # Script wrapper seguro para execução em processo isolado
    runner_script = f"""
import json
import math
import types

{instrumented_code}

def _is_serializable_val(val):
    if val is None or isinstance(val, (bool, types.ModuleType, types.FunctionType, type)):
        return False
    return isinstance(val, (int, float, str, list, tuple, dict))

try:
    scope = resolver()
    if not isinstance(scope, dict):
        raise ValueError(f"Escopo inválido retornado por resolver(): {{type(scope).__name__}}")

    erro_vals = [
        v for k, v in scope.items()
        if k.startswith("erro_") and _is_serializable_val(v)
    ]

    if "correta" in scope and erro_vals:
        res = {{
            "correta": scope["correta"],
            "distratores": erro_vals,
            "_raw_erros_count": len(erro_vals)
        }}
    elif "__explicit_return__" in scope and isinstance(scope["__explicit_return__"], dict):
        explicit = scope["__explicit_return__"]
        raw_d = explicit.get("distratores")
        res = {{
            "correta": explicit.get("correta"),
            "distratores": list(raw_d) if isinstance(raw_d, (list, tuple)) else raw_d,
            "_raw_erros_count": len(raw_d) if isinstance(raw_d, (list, tuple)) else 0
        }}
        if "correta" not in explicit or "distratores" not in explicit:
            res = explicit
    elif "correta" in scope:
        res = {{
            "correta": scope["correta"],
            "distratores": erro_vals,
            "_raw_erros_count": len(erro_vals)
        }}
    else:
        raise ValueError("O dicionário retornado por resolver() deve conter as chaves 'correta' e 'distratores' (ou definir 'correta' e variáveis 'erro_*').")

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

    if not isinstance(data["distratores"], (list, tuple)):
        raise ValueError("A chave 'distratores' deve ser uma lista ou tupla.")

    raw_distratores = list(data["distratores"])
    raw_count = data.pop("_raw_erros_count", len(raw_distratores))

    if raw_count < 3:
        raise ValueError(
            f"Distratores insuficientes no solver: defina pelo menos 3 variáveis 'erro_*' (encontrado: {raw_count})."
        )

    # Deduplica distratores preservando a ordem e filtrando colisões com 'correta'
    correta_str = format_number(data["correta"])
    unique_distractors: List[Any] = []
    seen_strs: Set[str] = {correta_str}
    for d in raw_distratores:
        d_str = format_number(d)
        if d_str not in seen_strs:
            seen_strs.add(d_str)
            unique_distractors.append(d)

    if len(unique_distractors) < 3:
        num_collisions = max(4 - len(unique_distractors), raw_count - len(unique_distractors))
        raise ValueError(
            f"Colisão excessiva de alternativas no solver ({num_collisions} colisões). "
            f"O solver deve produzir pelo menos 3 distratores únicos distintos do gabarito."
        )

    # Com 4 ou mais distratores distintos, usa 4; com 3, mantém os 3 para o auto_heal completar o 4º
    data["distratores"] = unique_distractors[:4]

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


def validate_solver_consistency(
    enunciado: str,
    code: str,
    result: Dict[str, Any]
) -> List[str]:
    """
    Valida a consistência matemática e o nexo entre o código do solver e o texto do enunciado:
    1. Se vierem 5 distratores, verifica se 1 é igual ao gabarito e o descarta para reutilizar 4.
    2. Unicidade estrita: o gabarito e os 4 distratores devem ser distintos (com Auto-Healing limitado a 1 colisão).
    3. Checagem de nexo numérico: todo número utilizado no código antes do return deve estar presente no enunciado
       (em algarismos ou por extenso).
    Retorna a lista de 5 valores formatados [correta, distrator1, distrator2, distrator3, distrator4].
    """
    correta_val = result["correta"]
    distratores_vals = list(result["distratores"])

    if len(distratores_vals) == 5:
        distratores_vals = _normalize_five_distractors(correta_val, distratores_vals)

    correta_str = format_number(correta_val)
    dist_strs = [format_number(d) for d in distratores_vals]
    all_values = [correta_str] + dist_strs

    # 1. Validação de Unicidade com Auto-Healing limitado a no máximo 1 distrator colidido
    unique_valid_distractors = {d for d in dist_strs if d != correta_str}
    num_collisions = 4 - len(unique_valid_distractors)

    if num_collisions > 1:
        raise ValueError(
            f"Colisão excessiva de alternativas no solver ({num_collisions} colisões em {all_values}). "
            f"O solver deve produzir pelo menos 3 distratores únicos distintos do gabarito."
        )
    elif num_collisions == 1 or len(set(all_values)) != 5:
        logger.warning(
            f"Auto-Healing: 1 colisão de alternativa detectada no solver ({all_values}). "
            f"Acionando auto-cura algorítmica para 1 distrator..."
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

    # 3. Tratamento de porcentagens: ex '2%' ou '15%' -> adiciona também 0.02, 0.15 e complementos (0.98, 0.85, 85)
    for match in re.finditer(r"(\d+(?:[\.,]\d+)?)\s*%", enunciado):
        val_str = match.group(1).replace(",", ".")
        try:
            val_pct = float(val_str)
            enun_floats.add(round(val_pct / 100.0, 6))
            if 0 < val_pct < 100:
                enun_floats.add(round(100.0 - val_pct, 6))
                enun_floats.add(round((100.0 - val_pct) / 100.0, 6))
                enun_floats.add(round((100.0 + val_pct) / 100.0, 6))
        except ValueError:
            pass

    # 4. Numerais por extenso e termos multiplicativos/fracionários em português
    for word in re.findall(r"[a-zA-ZÀ-ÿ]+", enunciado.lower()):
        if word in _WORDS_TO_NUMBERS:
            enun_floats.add(_WORDS_TO_NUMBERS[word])

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
