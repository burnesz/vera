"""
Verificação automática de consistência do feedback pedagógico (RN-FB04).

Pós-processamento determinístico (sem LLM) aplicado ao texto exibido ao estudante
(bloco <resposta>) antes de persisti-lo, conforme o passo 5 do fluxo de feedback do
pré-projeto: o feedback deve ser consistente com o gabarito oficial e com a habilidade
da Matriz de Referência do item.

Violações detectadas (códigos estáveis, reutilizáveis na avaliação quantitativa):
- VAZIO: resposta ausente ou curta demais para ser uma explicação.
- MARCADA_COMO_CORRETA: o texto afirma que a alternativa marcada (errada) é a correta.
- CORRETA_DIVERGENTE: o texto afirma que outra alternativa (nem gabarito nem marcada) é a correta.
- GABARITO_AUSENTE: o texto não cita a alternativa do gabarito nem o seu conteúdo/valor.
- HABILIDADE_DIVERGENTE: o texto atribui o item a uma habilidade (Hxx) diferente da oficial.
"""
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

MIN_FEEDBACK_CHARS = 40

# Letras de alternativa sempre em maiúscula (o (?-i:...) impede que "a"/"e" casem como letras).
_LETRA = r"\**\(?(?-i:([A-E]))\)?\**(?![\wÀ-ÿ])"
_REF = r"(?:alternativa|letra|op[cç][aã]o)"
_SER = r"(?:é|e|est[aá]|seria|era|foi)"

# Afirmações explícitas de qual alternativa é a correta.
_CORRECTNESS_PATTERNS = [
    # "a alternativa C é a correta", "letra (C) está correta", "alternativa C é a resposta certa"
    re.compile(
        rf"{_REF}\s*{_LETRA}\s*,?\s*{_SER}\s+(?:a\s+)?(?:resposta\s+|alternativa\s+|op[cç][aã]o\s+)?(?:correta|certa)",
        re.IGNORECASE,
    ),
    # "a resposta correta é a alternativa C", "alternativa correta: C"
    re.compile(
        rf"(?:resposta|alternativa|op[cç][aã]o)\s+(?:correta|certa)\s*(?:{_SER}|:)\s*(?:a\s+|o\s+)?(?:{_REF}\s*)?{_LETRA}",
        re.IGNORECASE,
    ),
    # "o gabarito é C", "gabarito oficial: alternativa C"
    re.compile(
        rf"gabarito\s*(?:oficial\s*)?(?:{_SER}|:|indica)\s*(?:a\s+|o\s+)?(?:{_REF}\s*)?{_LETRA}",
        re.IGNORECASE,
    ),
]

_HABILIDADE_PATTERN = re.compile(r"(?<![\w])H\s?(\d{1,2})(?![\w])")
_NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)*")


@dataclass
class FeedbackVerification:
    """Resultado da verificação automática de um feedback."""
    aprovado: bool
    violacoes: List[str] = field(default_factory=list)
    detalhes: List[str] = field(default_factory=list)


def _normalize_text(text: str) -> str:
    """Minúsculas, sem acentos, sem LaTeX/pontuação e com espaços colapsados."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"\\[a-z]+", " ", text)  # comandos LaTeX (\times, \frac...)
    text = re.sub(r"[^a-z0-9,.%]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_number(token: str) -> Optional[float]:
    """Converte números no formato pt-BR ou en-US ("1.250,50", "1250.5", "250") em float."""
    t = token.strip(".,")
    if not t:
        return None
    if "," in t and "." in t:
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif "," in t:
        parts = t.split(",")
        t = t.replace(",", ".") if len(parts) == 2 else t.replace(",", "")
    elif t.count(".") > 1 or re.fullmatch(r"\d{1,3}\.\d{3}", t):
        t = t.replace(".", "")
    try:
        return float(t)
    except ValueError:
        return None


def _extract_numbers(text: str) -> Set[float]:
    numbers: Set[float] = set()
    for token in _NUMBER_PATTERN.findall(text or ""):
        value = _parse_number(token)
        if value is not None:
            numbers.add(round(value, 6))
    return numbers


def _mentions_letter(content: str, letra: str) -> bool:
    """Verifica se a letra é citada como alternativa: "alternativa C", "letra C", "(C)", "C)"."""
    # A letra é casada sem IGNORECASE ((?-i:...)); apenas as palavras de apoio ignoram caixa.
    L = rf"\**\(?(?-i:{letra})\)?\**(?![\wÀ-ÿ])"
    patterns = [
        rf"{_REF}\s*{L}",
        rf"\((?-i:{letra})\)",
        rf"(?<![\wÀ-ÿ])(?-i:{letra})\)",
        rf"gabarito\s*(?:oficial\s*)?(?:{_SER}|:)?\s*(?:a\s+)?{L}",
    ]
    for p in patterns:
        if re.search(p, content, re.IGNORECASE):
            return True
    return False


def _mentions_answer_content(content: str, texto_gabarito: str) -> bool:
    """Verifica se o conteúdo/valor da alternativa correta aparece no feedback."""
    if not texto_gabarito or not texto_gabarito.strip():
        return False

    numeros_gabarito = _extract_numbers(texto_gabarito)
    if numeros_gabarito:
        numeros_feedback = _extract_numbers(content)
        return all(
            any(abs(n - m) <= 1e-6 * max(1.0, abs(n)) for m in numeros_feedback)
            for n in numeros_gabarito
        )

    alvo = _normalize_text(texto_gabarito)
    return len(alvo) >= 3 and alvo in _normalize_text(content)


def verify_feedback(
    content: str,
    gabarito: str,
    alternativa_marcada: str,
    alternativas: Dict[str, str],
    habilidade_codigo: str,
) -> FeedbackVerification:
    """
    Verifica o texto do feedback (bloco <resposta>) contra o gabarito oficial e a habilidade do item.
    """
    violacoes: List[str] = []
    detalhes: List[str] = []
    texto = (content or "").strip()
    gab = (gabarito or "").strip().upper()
    marcada = (alternativa_marcada or "").strip().upper()

    if len(texto) < MIN_FEEDBACK_CHARS:
        return FeedbackVerification(
            aprovado=False,
            violacoes=["VAZIO"],
            detalhes=[f"Feedback com {len(texto)} caracteres (mínimo {MIN_FEEDBACK_CHARS})."],
        )

    # 1. Afirmações explícitas de correção
    letras_afirmadas: Set[str] = set()
    for pattern in _CORRECTNESS_PATTERNS:
        for match in pattern.finditer(texto):
            letras_afirmadas.add(match.group(1).upper())

    for letra in sorted(letras_afirmadas - {gab}):
        if letra == marcada:
            violacoes.append("MARCADA_COMO_CORRETA")
            detalhes.append(f"O feedback afirma que a alternativa marcada ({letra}) é a correta; o gabarito é {gab}.")
        else:
            violacoes.append("CORRETA_DIVERGENTE")
            detalhes.append(f"O feedback afirma que a alternativa {letra} é a correta; o gabarito é {gab}.")

    # 2. Ancoragem no gabarito (letra ou conteúdo/valor da alternativa correta)
    if gab not in letras_afirmadas and not _mentions_letter(texto, gab):
        if not _mentions_answer_content(texto, (alternativas or {}).get(gab, "")):
            violacoes.append("GABARITO_AUSENTE")
            detalhes.append(f"O feedback não cita a alternativa {gab} nem o seu conteúdo/valor.")

    # 3. Aderência à Matriz de Referência (habilidade do item)
    hab_oficial = (habilidade_codigo or "").strip().upper()
    hab_num = hab_oficial.replace("H", "").lstrip("0")
    citadas = {m.group(1).lstrip("0") for m in _HABILIDADE_PATTERN.finditer(texto)}
    divergentes = sorted(c for c in citadas if c and c != hab_num)
    if hab_num and divergentes:
        violacoes.append("HABILIDADE_DIVERGENTE")
        detalhes.append(
            f"O feedback cita habilidade(s) {', '.join('H' + d.zfill(2) for d in divergentes)}; "
            f"a habilidade oficial do item é {hab_oficial}."
        )

    return FeedbackVerification(aprovado=not violacoes, violacoes=violacoes, detalhes=detalhes)


def build_correction_hint(
    verificacao: FeedbackVerification,
    gabarito: str,
    alternativa_marcada: str,
    habilidade_codigo: str,
) -> str:
    """Instrução corretiva anexada ao prompt na nova tentativa (Stateless Retry)."""
    problemas = "\n".join(f"- {d}" for d in verificacao.detalhes)
    return (
        "\n\nATENÇÃO — CORREÇÃO OBRIGATÓRIA: uma versão anterior deste feedback foi reprovada na verificação "
        f"automática pelos seguintes motivos:\n{problemas}\n"
        f"Na <resposta>, afirme explicitamente que a resposta correta é a alternativa {gabarito}, "
        f"trate a alternativa {alternativa_marcada} como incorreta e cite apenas a habilidade {habilidade_codigo}.\n"
    )
