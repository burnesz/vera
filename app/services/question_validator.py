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
    Realiza a validação estrutural obrigatória do item inédito antes de salvar no banco:
    1. Parsing e conformidade com o schema Pydantic QuestaoIneditaLLMOutput (RN-Q02).
    2. Existência de exatamente 5 alternativas (A, B, C, D, E) com textos não vazios.
    3. Gabarito válido e restrito a uma única letra ('A' a 'E').
    4. Unicidade estrita das alternativas (RN-Q01: ausência de alternativas duplicadas).
    5. Verificação de originalidade (não plagiar enunciados dos exemplos few-shot fornecidos).

    Retorna: (is_valid, error_message, parsed_model_or_none)
    """
    # 1. Extração e decodificação do JSON
    if isinstance(raw_output, dict):
        data = raw_output
    else:
        json_str = extract_json_from_text(raw_output)
        try:
            data = json.loads(json_str)
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

    return True, None, validated_item
