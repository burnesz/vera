import re
import io
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


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Extrai texto página a página a partir dos bytes de um arquivo PDF.
    Retorna uma lista de dicionários com 'page_number' e 'text'.
    """
    pages_data = []
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))

        for page_idx, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            # Limpeza e normalização de espaços
            cleaned_text = re.sub(r"\s+", " ", page_text).strip()
            if cleaned_text:
                pages_data.append({
                    "page_number": page_idx + 1,
                    "text": cleaned_text
                })
    except Exception as e:
        logger.error(f"Erro ao extrair texto do PDF: {e}")
        raise

    return pages_data


class MaterialChunker:
    """
    Segmentador de texto para materiais didáticos (RN-CHUNK01, RN-CHUNK02).
    Aplica divisão em janelas deslizantes com overlap configurável e preservação semântica.
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

    def _split_text(self, text: str) -> List[str]:
        """
        Divide o texto usando separadores decrescentes para respeitar limites semânticos.
        """
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            
            if end < text_len:
                # Procura o melhor ponto de quebra sem quebrar frases/palavras
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

            # Avança considerando o overlap configurável (RN-CHUNK02)
            start = max(end - self.chunk_overlap, start + 1)

        return chunks

    def process_pdf_material(
        self,
        filename: str,
        pdf_bytes: bytes
    ) -> List[Dict[str, Any]]:
        """
        Processa um arquivo PDF completo e retorna lista de chunks para vetorização semântica.
        """
        doc_metadata = parse_metadata_from_filename(filename)
        pages = extract_text_from_pdf_bytes(pdf_bytes)
        
        all_chunks = []
        chunk_counter = 0
        doc_slug = re.sub(r"[^a-zA-Z0-9]", "_", doc_metadata["title"].lower())

        for page in pages:
            page_num = page["page_number"]
            page_text = page["text"]
            text_splits = self._split_text(page_text)

            for split in text_splits:
                chunk_counter += 1
                chunk_id = f"mat_{doc_slug}_p{page_num}_c{chunk_counter}_{uuid.uuid4().hex[:6]}"

                chunk_payload = {
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
                }
                all_chunks.append(chunk_payload)

        logger.info(f"Arquivo '{filename}': {len(pages)} páginas processadas, {len(all_chunks)} chunks gerados.")
        return all_chunks
