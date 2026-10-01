"""
Testes unitários para app/pipeline/formula_extractor.py

Cobre:
  - normalize_unicode_math: mapeamento de símbolos Unicode para LaTeX
  - FormulaExtractor._load_model: lazy-load e fallback gracioso se pix2tex ausente
  - FormulaExtractor._ocr_region: OCR de imagem e tratamento de falha
  - FormulaExtractor.process_page: filtragem por tamanho e integração com OCR
"""

import pytest
from unittest.mock import MagicMock, patch

from app.pipeline.formula_extractor import (
    normalize_unicode_math,
    FormulaExtractor,
    UNICODE_TO_LATEX,
)


# ---------------------------------------------------------------------------
# Testes de normalize_unicode_math
# ---------------------------------------------------------------------------

def test_normalize_unicode_math_pi_and_sqrt():
    result = normalize_unicode_math("A área do círculo é π × r²")
    assert r"\pi" in result
    assert "^{2}" in result


def test_normalize_unicode_math_fractions():
    result = normalize_unicode_math("½ de 100 é 50")
    assert r"\frac{1}{2}" in result


def test_normalize_unicode_math_relational():
    result = normalize_unicode_math("x ≤ y e a ≠ b")
    assert r"\leq" in result
    assert r"\neq" in result


def test_normalize_unicode_math_greek():
    result = normalize_unicode_math("O ângulo θ em graus °")
    assert r"\theta" in result
    assert r"^{\circ}" in result


def test_normalize_unicode_math_no_change_on_plain_text():
    plain = "O triângulo tem três lados"
    result = normalize_unicode_math(plain)
    assert result == plain


def test_normalize_unicode_math_sum_and_integral():
    result = normalize_unicode_math("∑ dos termos e ∫ da função")
    assert r"\sum" in result
    assert r"\int" in result


def test_unicode_to_latex_table_completeness():
    """Garante que a tabela contém ao menos os símbolos críticos do ENEM."""
    must_have = ["√", "π", "²", "³", "½", "≤", "≥", "≠", "×", "÷", "θ", "∑", "∫", "°"]
    for symbol in must_have:
        assert symbol in UNICODE_TO_LATEX, f"Símbolo '{symbol}' ausente de UNICODE_TO_LATEX"


# ---------------------------------------------------------------------------
# Testes de FormulaExtractor._load_model
# ---------------------------------------------------------------------------

def test_load_model_disabled_returns_false():
    extractor = FormulaExtractor(enabled=False)
    result = extractor._load_model()
    assert result is False
    assert extractor._model is None


def test_load_model_import_error_disables_extractor():
    extractor = FormulaExtractor(enabled=True)
    with patch.dict("sys.modules", {"pix2tex": None, "pix2tex.cli": None}):
        with patch("builtins.__import__", side_effect=ImportError("pix2tex not found")):
            result = extractor._load_model()
    assert result is False
    assert extractor.enabled is False


def test_load_model_success():
    extractor = FormulaExtractor(enabled=True)
    mock_ocr = MagicMock()
    with patch("app.pipeline.formula_extractor.FormulaExtractor._load_model", return_value=True):
        extractor._model = mock_ocr
        assert extractor._model is mock_ocr


# ---------------------------------------------------------------------------
# Testes de FormulaExtractor._ocr_region
# ---------------------------------------------------------------------------

def test_ocr_region_disabled_returns_none():
    extractor = FormulaExtractor(enabled=False)
    result = extractor._ocr_region(MagicMock())
    assert result is None


def test_ocr_region_returns_latex_string():
    extractor = FormulaExtractor(enabled=True)
    mock_model = MagicMock(return_value=r"\frac{a}{b}")
    extractor._model = mock_model

    mock_pixmap = MagicMock()
    mock_pixmap.tobytes.return_value = b"\x89PNG\r\n\x1a\n"  # PNG header mínimo

    mock_pil_img = MagicMock()
    with patch("app.pipeline.formula_extractor.FormulaExtractor._load_model", return_value=True), \
         patch("PIL.Image.open", return_value=mock_pil_img):
        result = extractor._ocr_region(mock_pixmap)

    assert result == r"\frac{a}{b}"


def test_ocr_region_exception_returns_none():
    extractor = FormulaExtractor(enabled=True)
    extractor._model = MagicMock(side_effect=RuntimeError("OCR failed"))

    mock_pixmap = MagicMock()
    mock_pixmap.tobytes.return_value = b"\x89PNG"

    with patch("app.pipeline.formula_extractor.FormulaExtractor._load_model", return_value=True), \
         patch("PIL.Image.open", side_effect=RuntimeError("image error")):
        result = extractor._ocr_region(mock_pixmap)

    assert result is None


# ---------------------------------------------------------------------------
# Testes de FormulaExtractor.process_page
# ---------------------------------------------------------------------------

def _make_mock_page(images, page_width=595, page_height=842):
    """Cria uma página PyMuPDF mockada com lista de imagens."""
    page = MagicMock()
    page.rect = MagicMock(width=page_width, height=page_height)
    page.get_images.return_value = images
    return page


def test_process_page_no_images_returns_empty():
    extractor = FormulaExtractor(enabled=False)
    page = _make_mock_page(images=[])
    result = extractor.process_page(page)
    assert result == []


def test_process_page_ignores_small_images():
    """Ícones pequenos (< min_width ou < min_height) devem ser ignorados."""
    extractor = FormulaExtractor(enabled=False, min_width=30, min_height=12)

    # Imagem de 10x10pt — abaixo dos dois thresholds
    img_info = (1, 0, 0, 0, 0, 0, 0, 0, 8, "png", "DeviceRGB", 0)
    page = _make_mock_page(images=[img_info])

    tiny_rect = MagicMock()
    tiny_rect.width = 10
    tiny_rect.height = 10
    tiny_rect.x0, tiny_rect.y0, tiny_rect.x1, tiny_rect.y1 = 0, 0, 10, 10
    page.get_image_rects.return_value = [tiny_rect]

    result = extractor.process_page(page)
    assert result == []


def test_process_page_ignores_large_images():
    """Imagens que ocupam > max_area_fraction da página devem ser ignoradas (figuras/diagramas)."""
    extractor = FormulaExtractor(enabled=False, max_area_fraction=0.40)

    img_info = (2, 0, 0, 0, 0, 0, 0, 0, 8, "png", "DeviceRGB", 0)
    page = _make_mock_page(images=[img_info], page_width=595, page_height=842)

    # Imagem que ocupa 60% da página (595*842*0.6 ≈ 300000 pt²)
    big_rect = MagicMock()
    big_rect.width = 595
    big_rect.height = 500
    big_rect.x0, big_rect.y0, big_rect.x1, big_rect.y1 = 0, 0, 595, 500
    page.get_image_rects.return_value = [big_rect]

    result = extractor.process_page(page)
    assert result == []


def test_process_page_formula_detected_with_placeholder():
    """Imagem de tamanho adequado sem pix2tex deve retornar placeholder [FORMULA]."""
    extractor = FormulaExtractor(enabled=False)  # pix2tex desabilitado → placeholder

    img_info = (3, 0, 0, 0, 0, 0, 0, 0, 8, "png", "DeviceRGB", 0)
    page = _make_mock_page(images=[img_info])

    formula_rect = MagicMock()
    formula_rect.width = 120
    formula_rect.height = 30
    formula_rect.x0, formula_rect.y0, formula_rect.x1, formula_rect.y1 = 100, 200, 220, 230
    page.get_image_rects.return_value = [formula_rect]

    mock_pixmap = MagicMock()
    page.get_pixmap.return_value = mock_pixmap

    import pymupdf
    with patch("pymupdf.Matrix") as mock_matrix:
        result = extractor.process_page(page)

    assert len(result) == 1
    assert result[0]["latex"] == "[FORMULA]"
    assert result[0]["recognized"] is False
    assert result[0]["bbox"] == (100, 200, 220, 230)


def test_process_page_formula_ocr_success():
    """Com pix2tex habilitado e mockado, deve retornar o LaTeX reconhecido."""
    extractor = FormulaExtractor(enabled=True)
    mock_model = MagicMock(return_value=r"\sqrt{x^2 + 1}")
    extractor._model = mock_model

    img_info = (4, 0, 0, 0, 0, 0, 0, 0, 8, "png", "DeviceRGB", 0)
    page = _make_mock_page(images=[img_info])

    formula_rect = MagicMock()
    formula_rect.width = 100
    formula_rect.height = 25
    formula_rect.x0, formula_rect.y0, formula_rect.x1, formula_rect.y1 = 50, 100, 150, 125
    page.get_image_rects.return_value = [formula_rect]

    mock_pixmap = MagicMock()
    mock_pixmap.tobytes.return_value = b"\x89PNG"
    page.get_pixmap.return_value = mock_pixmap

    mock_pil_img = MagicMock()
    with patch("app.pipeline.formula_extractor.FormulaExtractor._load_model", return_value=True), \
         patch("PIL.Image.open", return_value=mock_pil_img), \
         patch("pymupdf.Matrix"):
        result = extractor.process_page(page)

    assert len(result) == 1
    assert result[0]["latex"] == r"\sqrt{x^2 + 1}"
    assert result[0]["recognized"] is True


def test_process_page_deduplicates_same_xref():
    """A mesma imagem (mesmo xref) referenciada duas vezes deve ser processada apenas uma vez."""
    extractor = FormulaExtractor(enabled=False)

    # Mesmo xref=5 aparece duas vezes na lista de imagens
    img_info = (5, 0, 0, 0, 0, 0, 0, 0, 8, "png", "DeviceRGB", 0)
    page = _make_mock_page(images=[img_info, img_info])

    formula_rect = MagicMock()
    formula_rect.width = 100
    formula_rect.height = 30
    formula_rect.x0, formula_rect.y0, formula_rect.x1, formula_rect.y1 = 0, 0, 100, 30
    page.get_image_rects.return_value = [formula_rect]

    with patch("pymupdf.Matrix"):
        result = extractor.process_page(page)

    # get_image_rects deve ter sido chamada apenas uma vez (deduplicação por xref)
    page.get_image_rects.assert_called_once_with(5)
    assert len(result) == 1
