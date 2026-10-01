"""
formula_extractor.py — Detecção e extração de fórmulas matemáticas de PDFs.

Duas camadas complementares:
  1. normalize_unicode_math(): converte símbolos Unicode matemáticos (√, ², π…)
     para notação LaTeX inline, sem dependências adicionais.
  2. FormulaExtractor: usa PyMuPDF para identificar regiões de imagem candidatas
     a fórmulas e pix2tex (LaTeX-OCR) para convertê-las em strings LaTeX.

O pix2tex é carregado sob demanda (lazy-load) na primeira chamada, minimizando
o impacto no startup da aplicação.  Se o módulo não estiver instalado ou a
extração falhar, o chunk ainda é gerado — apenas sem o LaTeX da imagem.
"""

import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tabela de mapeamento: Unicode matemático → LaTeX inline
# Cobre os símbolos mais frequentes nas apostilas de Matemática do ENEM.
# ---------------------------------------------------------------------------
UNICODE_TO_LATEX: dict = {
    # Raízes
    "√": r"\sqrt",
    "∛": r"\sqrt[3]",
    "∜": r"\sqrt[4]",
    # Constantes / letras gregas comuns no ENEM
    "π": r"\pi",
    "∞": r"\infty",
    "α": r"\alpha",
    "β": r"\beta",
    "γ": r"\gamma",
    "θ": r"\theta",
    "φ": r"\phi",
    "Δ": r"\Delta",
    "δ": r"\delta",
    "μ": r"\mu",
    "σ": r"\sigma",
    # Operadores relacionais
    "≠": r"\neq",
    "≤": r"\leq",
    "≥": r"\geq",
    "≈": r"\approx",
    "≡": r"\equiv",
    "∝": r"\propto",
    # Operadores aritméticos
    "÷": r"\div",
    "×": r"\times",
    "·": r"\cdot",
    "−": "-",
    # Superscripts (texto → LaTeX expoente)
    "²": "^{2}",
    "³": "^{3}",
    "¹": "^{1}",
    # Frações Unicode
    "½": r"\frac{1}{2}",
    "¼": r"\frac{1}{4}",
    "¾": r"\frac{3}{4}",
    "⅓": r"\frac{1}{3}",
    "⅔": r"\frac{2}{3}",
    # Conjuntos e lógica
    "∈": r"\in",
    "∉": r"\notin",
    "⊂": r"\subset",
    "⊃": r"\supset",
    "∩": r"\cap",
    "∪": r"\cup",
    "∅": r"\emptyset",
    "∀": r"\forall",
    "∃": r"\exists",
    # Somatório / integral
    "∑": r"\sum",
    "∏": r"\prod",
    "∫": r"\int",
    # Setas
    "→": r"\rightarrow",
    "←": r"\leftarrow",
    "↔": r"\leftrightarrow",
    "⇒": r"\Rightarrow",
    "⇔": r"\Leftrightarrow",
    # Geometria
    "°": r"^{\circ}",
    "⊥": r"\perp",
    "∥": r"\parallel",
    "∠": r"\angle",
    "△": r"\triangle",
}


def normalize_unicode_math(text: str) -> str:
    """
    Substitui símbolos Unicode matemáticos por seus equivalentes LaTeX inline.
    Operação leve, sem dependências externas; aplicada a todos os blocos de texto
    antes de chunking para melhorar legibilidade para o LLM.

    Exemplo:
        "área = π × r²" → "área = \\pi × r^{2}"
    """
    for symbol, latex in UNICODE_TO_LATEX.items():
        text = text.replace(symbol, latex)
    return text


# ---------------------------------------------------------------------------
# FormulaExtractor — OCR de regiões de imagem via pix2tex
# ---------------------------------------------------------------------------

class FormulaExtractor:
    """
    Detecta regiões de imagem candidatas a fórmulas matemáticas em páginas
    PyMuPDF e converte cada região para LaTeX usando pix2tex (LaTeX-OCR).

    Parâmetros de filtro de região (todos configuráveis):
      - min_width / min_height: ignora ícones e elementos gráficos minúsculos.
      - max_area_fraction: ignora figuras grandes (diagramas, gráficos de barra)
        que ocupam grande parte da página — provavelmente não são fórmulas.

    Uso:
        extractor = FormulaExtractor(enabled=settings.FORMULA_EXTRACTION_ENABLED)
        formulas = extractor.process_page(pymupdf_page)
        # formulas → [{"bbox": (x0,y0,x1,y1), "latex": "...", "recognized": True}, ...]
    """

    # Tamanho mínimo de uma região para ser considerada candidata a fórmula.
    # Valores em pontos PDF (1 pt ≈ 0.35 mm).
    DEFAULT_MIN_WIDTH: float = 30.0
    DEFAULT_MIN_HEIGHT: float = 12.0
    # Uma fórmula não deve ocupar mais que X% da área da página.
    DEFAULT_MAX_AREA_FRACTION: float = 0.40
    # Zoom aplicado ao render da região antes do OCR (melhora qualidade da imagem).
    RENDER_ZOOM: float = 2.5

    def __init__(
        self,
        enabled: bool = True,
        min_width: float = DEFAULT_MIN_WIDTH,
        min_height: float = DEFAULT_MIN_HEIGHT,
        max_area_fraction: float = DEFAULT_MAX_AREA_FRACTION,
    ):
        self.enabled = enabled
        self.min_width = min_width
        self.min_height = min_height
        self.max_area_fraction = max_area_fraction
        self._model = None  # lazy-loaded na primeira chamada

    # ------------------------------------------------------------------
    # Carregamento do modelo
    # ------------------------------------------------------------------

    def _load_model(self) -> bool:
        """
        Carrega o modelo pix2tex na primeira chamada.
        Retorna True se bem-sucedido, False caso contrário.
        """
        if self._model is not None:
            return True
        try:
            from pix2tex.cli import LatexOCR
            self._model = LatexOCR()
            logger.info("pix2tex (LaTeX-OCR) carregado com sucesso para extração de fórmulas.")
            return True
        except ImportError:
            logger.warning(
                "pix2tex não encontrado. Extração de fórmulas-imagem desabilitada. "
                "Instale com: pip install pix2tex"
            )
            self.enabled = False
            return False
        except Exception as exc:
            logger.warning(f"Falha ao carregar pix2tex ({exc}). Extração de fórmulas-imagem desabilitada.")
            self.enabled = False
            return False

    # ------------------------------------------------------------------
    # OCR de uma região de imagem
    # ------------------------------------------------------------------

    def _ocr_region(self, pixmap) -> Optional[str]:
        """
        Aplica pix2tex a um pixmap PyMuPDF e retorna a string LaTeX.
        Retorna None se o modelo não estiver disponível ou a OCR falhar.
        """
        if not self.enabled:
            return None
        if not self._load_model():
            return None
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(pixmap.tobytes("png")))
            latex = self._model(img)
            return latex.strip() if latex and latex.strip() else None
        except Exception as exc:
            logger.debug(f"pix2tex OCR falhou para região: {exc}")
            return None

    # ------------------------------------------------------------------
    # Processamento de uma página completa
    # ------------------------------------------------------------------

    def process_page(self, page) -> list:
        """
        Itera sobre as imagens embutidas na página PyMuPDF, filtra candidatas
        a fórmulas por tamanho e tenta OCR com pix2tex.

        Retorna lista de dicts:
            {
                "bbox": (x0, y0, x1, y1),   # coordenadas na página (pt)
                "latex": str,                # LaTeX reconhecido ou placeholder
                "recognized": bool,          # True = pix2tex teve resultado
            }
        """
        import pymupdf

        page_rect = page.rect
        page_area = page_rect.width * page_rect.height
        results = []
        seen_xrefs = set()

        for img_info in page.get_images(full=True):
            xref = img_info[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)

            rects = page.get_image_rects(xref)
            for rect in rects:
                w, h = rect.width, rect.height

                # Filtro 1: ignora elementos muito pequenos (ícones, decorações)
                if w < self.min_width or h < self.min_height:
                    continue

                # Filtro 2: ignora imagens grandes demais (figuras, diagramas de layout)
                if (w * h) / page_area > self.max_area_fraction:
                    continue

                # Renderiza a região em alta resolução para OCR
                mat = pymupdf.Matrix(self.RENDER_ZOOM, self.RENDER_ZOOM)
                try:
                    pix = page.get_pixmap(clip=rect, matrix=mat)
                except Exception as exc:
                    logger.debug(f"Falha ao renderizar região de fórmula: {exc}")
                    continue

                latex = self._ocr_region(pix)

                results.append({
                    "bbox": (rect.x0, rect.y0, rect.x1, rect.y1),
                    "latex": latex if latex else "[FORMULA]",
                    "recognized": latex is not None,
                })

        return results
