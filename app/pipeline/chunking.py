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


class MaterialChunker:
    """
    Segmentador estruturado de materiais didáticos com Unstructured (RN-CHUNK01, RN-CHUNK02).
    Utiliza partição de elementos (Title, NarrativeText, ListItem) e chunk_by_title,
    com fallback resiliente para pypdf.
    """

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None
    ):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

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
        Processa o PDF usando a biblioteca Unstructured com partição estruturada e chunk_by_title.
        """
        from unstructured.partition.pdf import partition_pdf
        from unstructured.chunking.title import chunk_by_title

        logger.info(f"Processando '{filename}' com Unstructured (particionamento semântico)...")
        elements = partition_pdf(
            file=io.BytesIO(pdf_bytes),
            strategy="fast",
            include_page_breaks=True
        )

        composite_chunks = chunk_by_title(
            elements,
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
                    "source_type": doc_metadata["source_type"]
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
        """
        from pypdf import PdfReader

        logger.info(f"Executando fallback com pypdf para '{filename}'...")
        reader = PdfReader(io.BytesIO(pdf_bytes))
        chunks_data = []
        chunk_counter = 0
        doc_slug = re.sub(r"[^a-zA-Z0-9]", "_", doc_metadata["title"].lower())

        for page_idx, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            cleaned_text = re.sub(r"\s+", " ", page_text).strip()
            if not cleaned_text:
                continue

            text_splits = self._split_text_fallback(cleaned_text)
            page_num = page_idx + 1

            for split in text_splits:
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
                        "source_type": doc_metadata["source_type"]
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
        caso ocorra qualquer exceção ou ausência de módulos, utiliza o fallback.
        """
        doc_metadata = parse_metadata_from_filename(filename)
        
        try:
            return self._process_with_unstructured(filename, pdf_bytes, doc_metadata)
        except Exception as e:
            logger.warning(f"Unstructured falhou para '{filename}' ({e}). Acionando fallback pypdf...")
            return self._process_with_fallback(filename, pdf_bytes, doc_metadata)
