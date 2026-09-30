"""
Validador estrutural e de integridade para questões inéditas geradas por LLM.
Implementa as regras RN-Q01 (validação estrutural de unicidade) e RN-Q02 (conformidade com schema).
"""

import json
import re
import logging
from typing import Union, Dict, Any, List, Optional, Tuple
from pydantic import ValidationError

from app.schemas.question import QuestaoIneditaLLMOutput

logger = logging.getLogger(__name__)


def extract_json_from_text(text: str) -> str:
    """
    Localiza e extrai o bloco de JSON dentro de uma string de resposta do modelo,
    mesmo que o modelo tenha incluído marcações markdown ```json ... ``` ou texto ao redor.
    """
    text = text.strip()
    # 1. Procura bloco delimitado por ```json ... ```
    match_md = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if match_md:
        return match_md.group(1).strip()

    # 2. Procura pelo primeiro '{' e último '}'
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace:last_brace + 1].strip()

    return text


def sanitize_latex_json_text(text: str) -> str:
    r"""
    Sanitiza strings de JSON contendo expressões matemáticas em LaTeX antes do json.loads().
    Resolve os seguintes problemas comuns gerados por LLMs:
    1. Formfeed corrompido: '\f' no JSON vira \x0c, deixando 'rac{a}{b}' em vez de '\frac{a}{b}'.
    2. Comandos LaTeX iniciados por caracteres válidos de escape JSON (\frac, \times, \right, \neq, \bar).
    3. Qualquer barra simples antes de comandos LaTeX (\sqrt, \cdot, etc.) que seja escape inválido em JSON.
    """
    if not text:
        return text

    # 1. Trata o caractere de controle form feed (chr(12) / \x0c) e resíduos literais
    text = text.replace("\x0crac", "\\\\frac")
    text = text.replace("\x0c", " ")
    text = text.replace(r"\x0crac", "\\\\frac")
    text = text.replace(r"\x0c", " ")

    # 2. Comandos LaTeX específicos que começam com letras de escape do JSON (\f, \t, \r, \n, \b)
    # Convertemos para barra dupla antes de qualquer outra operação:
    text = re.sub(r"(?<!\\)\\frac", r"\\\\frac", text)
    text = re.sub(r"(?<!\\)\\times", r"\\\\times", text)
    text = re.sub(r"(?<!\\)\\right", r"\\\\right", text)
    text = re.sub(r"(?<!\\)\\neq", r"\\\\neq", text)
    text = re.sub(r"(?<!\\)\\bar", r"\\\\bar", text)
    text = re.sub(r"(?<!\\)\\beta", r"\\\\beta", text)

    # 3. Qualquer barra simples não duplicada que não seja um escape válido de JSON:
    # No JSON, os escapes válidos são: \" \\ \/ \b \f \n \r \t \uXXXX
    text = re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r"\\\\", text)

    # 4. Corrige ocorrências de 'rac{' órfãs causadas por escape prévio de form feed
    text = re.sub(r"(?<![\\a-zA-Z])rac\{", r"\\frac{", text)

    return text


def sanitize_parsed_dict_values(data: Any) -> Any:
    """
    Limpa recursivamente valores de strings no dicionário decodificado, garantindo que
    quaisquer resíduos de form feed (\x0c) ou comandos LaTeX incompletos sejam restaurados.
    """
    if isinstance(data, str):
        val = data.replace("\x0crac", r"\frac")
        val = val.replace("\x0c", " ")
        val = re.sub(r"(?<![\\a-zA-Z])rac\{", r"\\frac{", val)
        return val
    elif isinstance(data, dict):
        return {k: sanitize_parsed_dict_values(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_parsed_dict_values(v) for v in data]
    return data


def check_command_gabarito_alignment(
    enunciado: str,
    alternativas: Dict[str, str],
    gabarito: str,
    justificativa: str,
    scratchpad: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Valida a consistência semântica entre o comando da questão e a alternativa indicada no gabarito:
    Detecta o erro clássico de 'Shortcut Reasoning' / parada em passo intermediário:
    Ex: se o enunciado pede 'valor total' ou 'ao todo', e a justificativa/scratchpad calcula um produto final
    (ex: N * unitário = total), o gabarito NÃO pode ser o valor unitário intermediário.
    """
    clean_enunciado = enunciado.lower()
    clean_just = justificativa.lower()
    clean_scratch = (scratchpad or "").lower()
    combined_reasoning = f"{clean_scratch}\n{clean_just}"

    alt_escolhida = alternativas.get(gabarito, "").strip()

    # Checagem de 'valor total' vs 'valor unitário':
    asks_for_total = any(k in clean_enunciado for k in ["valor total", "ao todo", "quantia total", "custo total", "total pago", "total arrecadado"])
    if asks_for_total:
        # Procura multiplicações do tipo N * X = Y ou N x X = Y no raciocínio
        mult_match = re.search(r"(\d+)\s*(?:[xX*×]|vezes)\s*(\d+(?:[\.,]\d+)?)\s*=\s*(\d+(?:[\.,]\d+)?)", combined_reasoning)
        if mult_match:
            qtd, unit, total_val = mult_match.groups()

            def norm_num(n_str: str) -> str:
                return re.sub(r"[^\d]", "", n_str.split(",")[0].split(".")[0])

            unit_norm = norm_num(unit)
            total_norm = norm_num(total_val)
            alt_norm = norm_num(alt_escolhida)

            if alt_norm and unit_norm and total_norm:
                if alt_norm == unit_norm and alt_norm != total_norm:
                    msg = (
                        f"Inconsistência semântica de comando (Shortcut Reasoning): O enunciado solicita o 'valor total' ({total_val}), "
                        f"mas o gabarito selecionado ({gabarito}) aponta para o valor unitário intermediário ({alt_escolhida})."
                    )
                    logger.warning(msg)
                    return False, msg

    return True, None


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    """Calcula a similaridade de Jaccard com base nos conjuntos de palavras."""
    words_a = set(re.findall(r"\w+", text_a.lower()))
    words_b = set(re.findall(r"\w+", text_b.lower()))
    if not words_a or not words_b:
        return 0.0
    intersection = len(words_a.intersection(words_b))
    union = len(words_a.union(words_b))
    return intersection / union if union > 0 else 0.0


def validate_questao_inedita(
    raw_output: Union[str, Dict[str, Any]],
    few_shot_exemplos: Optional[List[Dict[str, Any]]] = None
) -> Tuple[bool, Optional[str], Optional[QuestaoIneditaLLMOutput]]:
    """
    Realiza a validação estrutural e semântica obrigatória do item inédito antes de salvar no banco:
    1. Parsing e conformidade com o schema Pydantic QuestaoIneditaLLMOutput (RN-Q02).
    2. Sanitização de sintaxe LaTeX pré-parsing e pós-parsing.
    3. Existência de exatamente 5 alternativas (A, B, C, D, E) com textos não vazios.
    4. Gabarito válido e restrito a uma única letra ('A' a 'E').
    5. Unicidade estrita das alternativas (RN-Q01: ausência de alternativas duplicadas).
    6. Verificação de originalidade (não plagiar enunciados dos exemplos few-shot fornecidos).
    7. Validação semântica de alinhamento comando-gabarito (mitigação de shortcut reasoning).

    Retorna: (is_valid, error_message, parsed_model_or_none)
    """
    # 1. Extração, sanitização de LaTeX e decodificação do JSON
    if isinstance(raw_output, dict):
        data = sanitize_parsed_dict_values(raw_output)
    else:
        json_str = extract_json_from_text(raw_output)
        json_str = sanitize_latex_json_text(json_str)
        try:
            data = json.loads(json_str)
            data = sanitize_parsed_dict_values(data)
        except json.JSONDecodeError as e:
            msg = f"Falha ao decodificar JSON gerado pelo LLM: {str(e)}"
            logger.warning(msg)
            return False, msg, None

    if not isinstance(data, dict):
        msg = f"O retorno do LLM não é um objeto JSON/dicionário. Tipo obtido: {type(data).__name__}"
        logger.warning(msg)
        return False, msg, None

    # 2. Validação via Pydantic Schema (inclui validação de alternativas e unicidade - RN-Q01 e RN-Q02)
    try:
        validated_item = QuestaoIneditaLLMOutput.model_validate(data)
    except ValidationError as e:
        error_details = []
        for err in e.errors():
            loc = " -> ".join(str(l) for l in err.get("loc", []))
            msg = err.get("msg", "")
            error_details.append(f"[{loc}]: {msg}")
        msg = f"Erro de validação estrutural do item (RN-Q01/RN-Q02): {'; '.join(error_details)}"
        logger.warning(msg)
        return False, msg, None

    # 3. Verificação de anti-plágio com exemplos few-shot (não permitir cópia literal do banco)
    if few_shot_exemplos:
        enunciado_gerado = validated_item.enunciado
        for ex in few_shot_exemplos:
            ex_enunciado = ex.get("enunciado", "")
            if not ex_enunciado:
                continue
            sim = _jaccard_similarity(enunciado_gerado, ex_enunciado)
            if sim > 0.85:
                msg = f"Item gerado é excessivamente similar a um exemplo histórico de treino (similaridade Jaccard={sim:.2f}). Item descartado por ineditismo."
                logger.warning(msg)
                return False, msg, None

    # 4. Validação semântica de alinhamento comando-gabarito
    is_aligned, align_error = check_command_gabarito_alignment(
        enunciado=validated_item.enunciado,
        alternativas=validated_item.alternativas,
        gabarito=validated_item.gabarito,
        justificativa=validated_item.justificativa,
        scratchpad=validated_item.thought_scratchpad
    )
    if not is_aligned:
        return False, align_error, None

    return True, None, validated_item

