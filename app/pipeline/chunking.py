import io
import re
import uuid
import logging
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.core.sanitizer import sanitize_utf8_string, sanitize_metadata

logger = logging.getLogger(__name__)


def parse_metadata_from_filename(filename: str) -> Dict[str, Any]:
    """
    Extrai metadados descritivos (nome do documento, título e tópico) a partir do nome do arquivo.
    Não realiza mapeamento artificial de habilidades, preservando a recuperação puramente semântica.
    Exemplo: 'ENEM_MAT_03_ciclo-trigonometrico.pdf' -> título/tópico 'Ciclo Trigonométrico'
    """
    clean_name = sanitize_utf8_string(filename.split("/")[-1].replace(".pdf", ""))
    
    # Remove prefixos comuns como ENEM_MAT_XX_ ou TEO_MT-VX_ para gerar um título legível
    formatted_topic = re.sub(r"^(ENEM_MAT_\d+_|TEO_[A-Z0-9\-_]+_)", "", clean_name, flags=re.IGNORECASE)
    formatted_topic = sanitize_utf8_string(formatted_topic.replace("-", " ").replace("_", " ").strip().title())

    metadata = {
        "filename": sanitize_utf8_string(filename.split("/")[-1]),
        "title": formatted_topic if formatted_topic else clean_name,
        "topic": formatted_topic if formatted_topic else clean_name,
        "source_type": "materiais_didaticos"
    }

    return metadata


HEADER_REGEX = re.compile(
    r"MATEM[ÁA]TICA\s+e\s+suas\s+tecnologias\s+[\w\d]+\s+VOLUME\s+[\w\d]+",
    re.IGNORECASE
)
REF_TITLE_REGEX = re.compile(
    r"^(?:refer[êe]ncias|bibliografia|liga[çc][õo]es\s+externas)\b",
    re.IGNORECASE
)
DISCARD_ELEMENT_TYPES = {"Header", "Footer", "PageNumber"}
# Número mínimo de palavras que um chunk do Unstructured deve conter para ser indexado.
# Garante que fragmentos residuais (ex: títulos isolados sem corpo) não poluam o namespace.
MIN_WORDS_UNSTRUCTURED = 20


def _has_reference_signals(text: str) -> bool:
    """Verifica se o texto possui >= 2 sinais típicos de referências bibliográficas/links."""
    sinais = 0
    if re.search(r"https?://|www\.", text, re.IGNORECASE):
        sinais += 1
    if re.search(r"\bdoi:\s*\S+", text, re.IGNORECASE):
        sinais += 1
    if re.search(r"\bisbn\b", text, re.IGNORECASE):
        sinais += 1
    if re.search(r"consultado\s+em", text, re.IGNORECASE):
        sinais += 1
    return sinais >= 2


class MaterialChunker:
    """
    Segmentador estruturado de materiais didáticos (RN-CHUNK01, RN-CHUNK02).

    Hierarquia de extratores:
    1. **Unstructured** (prioridade): particionamento semântico via chunk_by_title.
       - `max_characters` (= CHUNK_SIZE): limite rígido.
       - `new_after_n_chars` (= CHUNK_SIZE * 0.75): limite suave para evitar cortes prematuros.
       - `combine_text_under_n_chars` (= 400): fusão agressiva de elementos curtos.
       - Filtro pós-chunking: descarta chunks < MIN_WORDS_UNSTRUCTURED palavras.
    2. **PyMuPDF** (fallback): extrator alternativo ativado quando o Unstructured
       retorna 0 chunks (PDF detectado como 'complexo') ou lança exceção.
       - Extrai texto por blocos com ordem de leitura natural.
       - Normaliza símbolos Unicode matemáticos para notação LaTeX inline.
       - Detecta regiões de imagem candidatas a fórmulas e aplica OCR via pix2tex
         (LaTeX-OCR) quando `formula_extraction_enabled=True`.
       - Fórmulas reconhecidas são inseridas no texto como `$$LaTeX$$`.
       - Chunking via janela deslizante com overlap, igual ao fallback pypdf.
    """

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        formula_extraction_enabled: Optional[bool] = None,
    ):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        self.formula_extraction_enabled = (
            formula_extraction_enabled
            if formula_extraction_enabled is not None
            else settings.FORMULA_EXTRACTION_ENABLED
        )
        self.fallback_count: int = 0
        self._unstructured_available: Optional[bool] = None

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap não pode ser maior ou igual a chunk_size")

    def _split_text_fallback(self, text: str) -> List[str]:
        """
        Divisão de texto de contingência usando separadores decrescentes.
        """
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            
            if end < text_len:
                cut = -1
                for sep in ["\n\n", "\n", ". ", "? ", "! ", "; ", " "]:
                    idx = text.rfind(sep, start + (self.chunk_size // 2), end)
                    if idx != -1:
                        cut = idx + len(sep)
                        break
                if cut != -1:
                    end = cut

            chunk_str = text[start:end].strip()
            if chunk_str:
                chunks.append(chunk_str)

            if end >= text_len:
                break

            start = max(end - self.chunk_overlap, start + 1)

        return chunks

    def _process_with_unstructured(
        self,
        filename: str,
        pdf_bytes: bytes,
        doc_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Processa o PDF usando a biblioteca Unstructured com partição estruturada e chunk_by_title,
        filtrando elementos indesejados antes da segmentação.
        """
        from unstructured.partition.pdf import partition_pdf
        from unstructured.chunking.title import chunk_by_title

        logger.info(f"Processando '{filename}' com Unstructured (particionamento semântico)...")
        elements = partition_pdf(
            file=io.BytesIO(pdf_bytes),
            strategy="fast",
            include_page_breaks=True,
            languages=["por"]
        )

        filtered_elements = []
        discarded_after_ref_count = 0
        found_references = False

        for el in elements:
            el_type = type(el).__name__

            # 1. Descartar Header, Footer e PageNumber
            if el_type in DISCARD_ELEMENT_TYPES:
                continue

            el_text = sanitize_utf8_string(str(getattr(el, "text", "") or "").strip())
            if not el_text:
                continue

            # 2. Se já encontramos o título de referências/bibliografia, descarta ele e tudo depois
            if found_references:
                discarded_after_ref_count += 1
                continue

            # 3. Detectar início da seção "Referências|Bibliografia|Ligações externas"
            if (el_type == "Title" or len(el_text.split()) <= 4) and REF_TITLE_REGEX.search(el_text):
                found_references = True
                discarded_after_ref_count += 1
                continue

            # 4. Remover cabeçalho padrão por regex
            cleaned_text = sanitize_utf8_string(HEADER_REGEX.sub("", el_text).strip())
            if not cleaned_text:
                continue

            if cleaned_text != el_text:
                el.text = cleaned_text

            filtered_elements.append(el)

        if discarded_after_ref_count > 0:
            logger.info(
                f"'{filename}': Seção de referências/bibliografia detectada. "
                f"Descartados {discarded_after_ref_count} elementos subsequentes."
            )

        # new_after_n_chars: limite suave — evita quebrar em títulos enquanto o chunk
        # ainda está pequeno; só inicia novo chunk após atingir 75% do limite máximo.
        soft_limit = int(self.chunk_size * 0.75)

        composite_chunks = chunk_by_title(
            filtered_elements,
            max_characters=self.chunk_size,
            new_after_n_chars=soft_limit,
            overlap=self.chunk_overlap,
            # Fusão agressiva: elementos menores que 400 chars são sempre fundidos com
            # o próximo, evitando chunks de uma única frase ou título isolado.
            combine_text_under_n_chars=400,
        )

        chunks_data = []
        skipped_short = 0
        doc_slug = re.sub(r"[^a-zA-Z0-9]", "_", doc_metadata["title"].lower())

        for idx, chunk in enumerate(composite_chunks, 1):
            text = sanitize_utf8_string(str(chunk.text).strip())
            if not text:
                continue

            # Filtro pós-chunking: descarta fragmentos residuais com poucas palavras
            # (ex: título isolado que sobrou após uma seção de referências)
            word_count = len([w for w in text.split() if w.strip()])
            if word_count < MIN_WORDS_UNSTRUCTURED:
                skipped_short += 1
                continue

            page_num = 1
            if hasattr(chunk, "metadata") and getattr(chunk.metadata, "page_number", None):
                page_num = chunk.metadata.page_number

            chunk_id = sanitize_utf8_string(f"mat_{doc_slug}_p{page_num}_c{idx}_{uuid.uuid4().hex[:6]}")

            chunks_data.append({
                "id": chunk_id,
                "text": text,
                "metadata": sanitize_metadata({
                    "document_name": doc_metadata["filename"],
                    "title": doc_metadata["title"],
                    "topic": doc_metadata["topic"],
                    "page_number": page_num,
                    "chunk_index": idx,
                    "source_type": doc_metadata["source_type"],
                    "extractor": "unstructured"
                })
            })

        if skipped_short > 0:
            logger.info(
                f"Unstructured: {skipped_short} chunk(s) residuais descartados "
                f"(< {MIN_WORDS_UNSTRUCTURED} palavras) em '{filename}'."
            )
        logger.info(f"Unstructured: {len(chunks_data)} chunks gerados para '{filename}'.")
        return chunks_data

    def _process_with_fallback(
        self,
        filename: str,
        pdf_bytes: bytes,
        doc_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Fallback de extração: delega para _process_with_pymupdf, que usa PyMuPDF
        com normalização Unicode→LaTeX e OCR de fórmulas-imagem via pix2tex.
        Mantém a assinatura original para compatibilidade com process_pdf_material.
        """
        return self._process_with_pymupdf(filename, pdf_bytes, doc_metadata)

    def _process_with_pymupdf(
        self,
        filename: str,
        pdf_bytes: bytes,
        doc_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extração estruturada via PyMuPDF com suporte a fórmulas matemáticas.

        - Texto: extraído por blocos (ordem de leitura natural) com normalização
          de símbolos Unicode para notação LaTeX inline.
        - Fórmulas-imagem: detectadas por bounding box e convertidas para LaTeX
          via pix2tex quando FORMULA_EXTRACTION_ENABLED=True; inseridas no texto
          como blocos `$$LaTeX$$` antes do parágrafo adjacente.
        - Chunking: janela deslizante com overlap (mesmo algoritmo do fallback pypdf).
        - Filtragem: cabeçalhos institucionais, seção de referências e chunks < 15 palavras.
        - Campo `has_formulas` nos metadados indica se o chunk contém fórmulas LaTeX.
        """
        import pymupdf
        from app.pipeline.formula_extractor import FormulaExtractor, normalize_unicode_math

        logger.info(
            f"Processando '{filename}' com PyMuPDF"
            f"{' + pix2tex (fórmulas)' if self.formula_extraction_enabled else ''} ..."
        )

        extractor = FormulaExtractor(enabled=self.formula_extraction_enabled)
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        chunks_data: List[Dict[str, Any]] = []
        chunk_counter = 0
        doc_slug = re.sub(r"[^a-zA-Z0-9]", "_", doc_metadata["title"].lower())
        found_references = False
        all_formula_regions: List[Dict[str, Any]] = []  # acumula para log final

        try:
            for page_idx, page in enumerate(doc):
                if found_references:
                    break

                page_num = page_idx + 1

                # 1. Detecta regiões de imagem candidatas a fórmulas (bounding boxes)
                formula_regions = extractor.process_page(page)
                # Indexa as fórmulas por posição vertical para inserção no texto
                formula_regions_sorted = sorted(formula_regions, key=lambda r: r["bbox"][1])
                all_formula_regions.extend(formula_regions_sorted)

                # 2. Extrai texto por blocos (sort=True → ordem de leitura)
                blocks = page.get_text("blocks", sort=True)
                page_parts: List[str] = []
                formula_inserted = set()

                for block in blocks:
                    bx0, by0, bx1, by1, raw_text = block[0], block[1], block[2], block[3], block[4]

                    # Insere placeholder de fórmulas cujo bounding box está acima
                    # do topo deste bloco de texto (dentro de margem de 40pt)
                    for i, formula in enumerate(formula_regions_sorted):
                        if i in formula_inserted:
                            continue
                        fx0, fy0, fx1, fy1 = formula["bbox"]
                        if fy1 <= by0 + 40:
                            page_parts.append(f"$${formula['latex']}$$")
                            formula_inserted.add(i)

                    text = sanitize_utf8_string((raw_text or "").strip())
                    text = HEADER_REGEX.sub("", text).strip()
                    text = sanitize_utf8_string(text)
                    if not text:
                        continue

                    # Detecta início da seção de referências
                    first_words = " ".join(text.split()[:5])
                    if REF_TITLE_REGEX.search(first_words):
                        logger.info(
                            f"PyMuPDF: Seção de referências detectada na página {page_num} "
                            f"de '{filename}'. Truncando leitura."
                        )
                        found_references = True
                        break

                    # Normaliza símbolos Unicode matemáticos → LaTeX
                    text = normalize_unicode_math(text)
                    page_parts.append(text)

                # Adiciona fórmulas restantes que ficaram após o último bloco de texto
                for i, formula in enumerate(formula_regions_sorted):
                    if i not in formula_inserted:
                        page_parts.append(f"$${formula['latex']}$$")

                full_page_text = sanitize_utf8_string("\n".join(page_parts))
                has_formulas = "$$" in full_page_text

                # 3. Divide em chunks usando a janela deslizante
                for split in self._split_text_fallback(full_page_text):
                    split = sanitize_utf8_string(split)
                    words = [w for w in split.split() if w.strip()]
                    if len(words) < 15:
                        continue
                    if _has_reference_signals(split):
                        continue

                    chunk_counter += 1
                    chunk_id = sanitize_utf8_string(
                        f"mat_{doc_slug}_p{page_num}_c{chunk_counter}_{uuid.uuid4().hex[:6]}"
                    )
                    chunks_data.append({
                        "id": chunk_id,
                        "text": split,
                        "metadata": sanitize_metadata({
                            "document_name": doc_metadata["filename"],
                            "title": doc_metadata["title"],
                            "topic": doc_metadata["topic"],
                            "page_number": page_num,
                            "chunk_index": chunk_counter,
                            "source_type": doc_metadata["source_type"],
                            "extractor": "pymupdf",
                            "has_formulas": has_formulas,
                        })
                    })
        finally:
            doc.close()

        recognized = sum(1 for f in all_formula_regions if f["recognized"])
        if all_formula_regions:
            logger.info(
                f"PyMuPDF: {len(chunks_data)} chunks gerados para '{filename}' "
                f"({recognized}/{len(all_formula_regions)} fórmulas reconhecidas via pix2tex)."
            )
        else:
            logger.info(f"PyMuPDF: {len(chunks_data)} chunks gerados para '{filename}'.")

        return chunks_data


    def process_pdf_material(
        self,
        filename: str,
        pdf_bytes: bytes
    ) -> List[Dict[str, Any]]:
        """
        Processa o PDF didático. Tenta utilizar o Unstructured prioritariamente;
        caso ocorra qualquer exceção, ausência de módulos, ou retorno vazio
        (ex: PDF com muitos ops gráficos que o Unstructured abandona), utiliza o
        fallback pypdf e registra a contagem.
        """
        doc_metadata = parse_metadata_from_filename(filename)

        if self._unstructured_available is False:
            return self._process_with_pymupdf(filename, pdf_bytes, doc_metadata)

        try:
            res = self._process_with_unstructured(filename, pdf_bytes, doc_metadata)
            self._unstructured_available = True

            # Fallback automático quando Unstructured retorna 0 chunks.
            # Causa mais comum: PDFs com alto número de ops gráficos fazem o Unstructured
            # detectar o documento como "muito complexo" e abandonar a extração de texto
            # (falling back to hi_res without text extraction), produzindo 0 elementos.
            # PyMuPDF consegue extrair a camada de texto nesses casos e ainda recupera
            # fórmulas-imagem via pix2tex.
            if not res:
                self.fallback_count += 1
                logger.warning(
                    f"Unstructured retornou 0 chunks para '{filename}' "
                    f"(possível PDF com muitos ops gráficos detectado como complexo). "
                    f"Acionando fallback PyMuPDF... "
                    f"(Total acumulado de PDFs em fallback: {self.fallback_count})"
                )
                return self._process_with_pymupdf(filename, pdf_bytes, doc_metadata)

            return res
        except (ImportError, ModuleNotFoundError) as e:
            self._unstructured_available = False
            self.fallback_count += 1
            logger.info(
                f"Dependências do Unstructured para PDF ausentes ({e}). "
                f"Utilizando fallback resiliente via PyMuPDF para este e os próximos materiais."
            )
            return self._process_with_pymupdf(filename, pdf_bytes, doc_metadata)
        except Exception as e:
            self.fallback_count += 1
            logger.warning(
                f"Unstructured falhou para '{filename}' ({e}). Acionando fallback PyMuPDF... "
                f"(Total acumulado de PDFs em fallback: {self.fallback_count})"
            )
            return self._process_with_pymupdf(filename, pdf_bytes, doc_metadata)

