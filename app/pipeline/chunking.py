import io
import re
import uuid
import logging
from typing import List, Dict, Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def parse_metadata_from_filename(filename: str) -> Dict[str, Any]:
    """
    Extrai metadados descritivos (nome do documento, título e tópico) a partir do nome do arquivo.
    Não realiza mapeamento artificial de habilidades, preservando a recuperação puramente semântica.
    Exemplo: 'ENEM_MAT_03_ciclo-trigonometrico.pdf' -> título/tópico 'Ciclo Trigonométrico'
    """
    clean_name = filename.split("/")[-1].replace(".pdf", "")
    
    # Remove prefixos comuns como ENEM_MAT_XX_ ou TEO_MT-VX_ para gerar um título legível
    formatted_topic = re.sub(r"^(ENEM_MAT_\d+_|TEO_[A-Z0-9\-_]+_)", "", clean_name, flags=re.IGNORECASE)
    formatted_topic = formatted_topic.replace("-", " ").replace("_", " ").strip().title()

    metadata = {
        "filename": filename.split("/")[-1],
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
    Segmentador estruturado de materiais didáticos com Unstructured (RN-CHUNK01, RN-CHUNK02).
    Utiliza partição de elementos (Title, NarrativeText, ListItem) e chunk_by_title,
    com fallback resiliente para pypdf e filtragem de ruídos/referências.
    """

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None
    ):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        self.fallback_count: int = 0

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
            include_page_breaks=True
        )

        filtered_elements = []
        discarded_after_ref_count = 0
        found_references = False

        for el in elements:
            el_type = type(el).__name__

            # 1. Descartar Header, Footer e PageNumber
            if el_type in DISCARD_ELEMENT_TYPES:
                continue

            el_text = str(getattr(el, "text", "") or "").strip()
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
            cleaned_text = HEADER_REGEX.sub("", el_text).strip()
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

        composite_chunks = chunk_by_title(
            filtered_elements,
            max_characters=self.chunk_size,
            overlap=self.chunk_overlap,
            combine_text_under_n_chars=150
        )

        chunks_data = []
        doc_slug = re.sub(r"[^a-zA-Z0-9]", "_", doc_metadata["title"].lower())

        for idx, chunk in enumerate(composite_chunks, 1):
            text = str(chunk.text).strip()
            if not text:
                continue

            page_num = 1
            if hasattr(chunk, "metadata") and getattr(chunk.metadata, "page_number", None):
                page_num = chunk.metadata.page_number

            chunk_id = f"mat_{doc_slug}_p{page_num}_c{idx}_{uuid.uuid4().hex[:6]}"

            chunks_data.append({
                "id": chunk_id,
                "text": text,
                "metadata": {
                    "document_name": doc_metadata["filename"],
                    "title": doc_metadata["title"],
                    "topic": doc_metadata["topic"],
                    "page_number": page_num,
                    "chunk_index": idx,
                    "source_type": doc_metadata["source_type"],
                    "extractor": "unstructured"
                }
            })

        logger.info(f"Unstructured: {len(chunks_data)} chunks gerados para '{filename}'.")
        return chunks_data

    def _process_with_fallback(
        self,
        filename: str,
        pdf_bytes: bytes,
        doc_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Processamento de fallback usando pypdf caso Unstructured não esteja disponível.
        Aplica filtros equivalentes de texto (cabeçalho, referências e tamanho mínimo de palavras).
        """
        from pypdf import PdfReader

        logger.info(f"Executando fallback com pypdf para '{filename}'...")
        reader = PdfReader(io.BytesIO(pdf_bytes))
        chunks_data = []
        chunk_counter = 0
        doc_slug = re.sub(r"[^a-zA-Z0-9]", "_", doc_metadata["title"].lower())
        found_references = False

        for page_idx, page in enumerate(reader.pages):
            if found_references:
                break

            page_text = page.extract_text() or ""
            # Remover cabeçalho institucional por regex
            page_text = HEADER_REGEX.sub("", page_text)
            cleaned_text = re.sub(r"\s+", " ", page_text).strip()
            if not cleaned_text:
                continue

            # Detecta seção de referências no início da página
            first_words = " ".join(cleaned_text.split()[:5])
            if REF_TITLE_REGEX.search(first_words):
                logger.info(f"Fallback pypdf: Seção de referências detectada na página {page_idx + 1} de '{filename}'. Truncando leitura.")
                found_references = True
                break

            text_splits = self._split_text_fallback(cleaned_text)
            page_num = page_idx + 1

            for split in text_splits:
                # Regras de descarte no fallback pypdf:
                # 1. Menos de 15 palavras
                words = [w for w in split.split() if w.strip()]
                if len(words) < 15:
                    continue

                # 2. >= 2 sinais de referência (URL, doi:, ISBN, "Consultado em")
                if _has_reference_signals(split):
                    continue

                chunk_counter += 1
                chunk_id = f"mat_{doc_slug}_p{page_num}_c{chunk_counter}_{uuid.uuid4().hex[:6]}"

                chunks_data.append({
                    "id": chunk_id,
                    "text": split,
                    "metadata": {
                        "document_name": doc_metadata["filename"],
                        "title": doc_metadata["title"],
                        "topic": doc_metadata["topic"],
                        "page_number": page_num,
                        "chunk_index": chunk_counter,
                        "source_type": doc_metadata["source_type"],
                        "extractor": "pypdf"
                    }
                })

        logger.info(f"Fallback pypdf: {len(chunks_data)} chunks gerados para '{filename}'.")
        return chunks_data

    def process_pdf_material(
        self,
        filename: str,
        pdf_bytes: bytes
    ) -> List[Dict[str, Any]]:
        """
        Processa o PDF didático. Tenta utilizar o Unstructured prioritariamente;
        caso ocorra qualquer exceção ou ausência de módulos, utiliza o fallback e registra a contagem.
        """
        doc_metadata = parse_metadata_from_filename(filename)
        
        try:
            return self._process_with_unstructured(filename, pdf_bytes, doc_metadata)
        except Exception as e:
            self.fallback_count += 1
            logger.warning(
                f"Unstructured falhou para '{filename}' ({e}). Acionando fallback pypdf... "
                f"(Total acumulado de PDFs em fallback: {self.fallback_count})"
            )
            return self._process_with_fallback(filename, pdf_bytes, doc_metadata)
