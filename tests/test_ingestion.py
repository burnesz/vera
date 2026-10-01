import pytest
from unittest.mock import MagicMock, patch

from app.pipeline.chunking import parse_metadata_from_filename, MaterialChunker
from app.services.vectorstore import EmbeddingService, PineconeVectorStore
from app.pipeline.index_embeddings import run_materials_ingestion


def test_parse_metadata_from_filename_enem():
    filename = "ENEM_MAT_03_ciclo-trigonometrico.pdf"
    meta = parse_metadata_from_filename(filename)

    assert meta["filename"] == "ENEM_MAT_03_ciclo-trigonometrico.pdf"
    assert meta["topic"] == "Ciclo Trigonometrico"
    assert meta["title"] == "Ciclo Trigonometrico"
    assert meta["source_type"] == "materiais_didaticos"
    assert "habilidades" not in meta


def test_parse_metadata_financeira():
    filename = "ENEM_MAT_06_taxa-de-cambio.pdf"
    meta = parse_metadata_from_filename(filename)

    assert meta["topic"] == "Taxa De Cambio"
    assert meta["source_type"] == "materiais_didaticos"


def test_chunker_splitting_fallback():
    chunker = MaterialChunker(chunk_size=100, chunk_overlap=20)
    sample_text = (
        "O ciclo trigonométrico é uma circunferência de raio unitário utilizada para representar "
        "as razões trigonométricas como seno, cosseno e tangente. "
        "Ele é fundamental para o estudo de funções periódicas no ENEM."
    )

    splits = chunker._split_text_fallback(sample_text)
    assert len(splits) >= 2
    for s in splits:
        assert len(s) <= 120
        assert len(s.strip()) > 0


def test_chunker_overlap_validation():
    with pytest.raises(ValueError):
        MaterialChunker(chunk_size=100, chunk_overlap=120)


def test_chunker_process_with_fallback():
    """_process_with_fallback delega para _process_with_pymupdf."""
    chunker = MaterialChunker(chunk_size=300, chunk_overlap=30, formula_extraction_enabled=False)
    doc_metadata = {"filename": "test.pdf", "title": "Teste", "topic": "Teste", "source_type": "materiais_didaticos"}

    # Bloco de texto com 18 palavras (> 15 min) e sem ref
    text_block = (
        "Definição de Trigonometria e seno, cosseno e tangente no triângulo retângulo "
        "e círculo trigonométrico para o ENEM."
    )
    # Formato de bloco retornado por page.get_text("blocks"): (x0, y0, x1, y1, text, block_no, block_type)
    mock_block = (0, 0, 100, 20, text_block, 0, 0)

    mock_page = MagicMock()
    mock_page.rect = MagicMock(width=595, height=842)
    mock_page.get_text.return_value = [mock_block]
    mock_page.get_images.return_value = []

    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
    mock_doc.__enter__ = MagicMock(return_value=mock_doc)
    mock_doc.__exit__ = MagicMock(return_value=False)
    mock_doc.close = MagicMock()

    with patch("pymupdf.open", return_value=mock_doc):
        chunks = chunker._process_with_fallback("test.pdf", b"%PDF-mock", doc_metadata)

    assert len(chunks) == 1
    assert chunks[0]["metadata"]["title"] == "Teste"
    assert chunks[0]["metadata"]["extractor"] == "pymupdf"
    assert "Trigonometria" in chunks[0]["text"]
    assert "has_formulas" in chunks[0]["metadata"]


def test_chunker_fallback_filters_references_and_short():
    """PyMuPDF fallback deve descartar chunks curtos e com sinais de referência."""
    chunker = MaterialChunker(chunk_size=300, chunk_overlap=30, formula_extraction_enabled=False)
    doc_metadata = {"filename": "test.pdf", "title": "Teste", "topic": "Teste", "source_type": "materiais_didaticos"}

    ref_block = (0, 0, 100, 20, "Referência https://site.com/artigo ISBN 978-85-1234 e Consultado em 2024.", 0, 0)
    short_block = (0, 30, 100, 50, "Texto muito curto.", 1, 0)
    valid_block = (
        0, 60, 100, 80,
        "A função afim é uma função polinomial do primeiro grau definida por f(x) = ax + b com a diferente de zero.",
        2, 0
    )

    def make_page(blocks):
        p = MagicMock()
        p.rect = MagicMock(width=595, height=842)
        p.get_text.return_value = blocks
        p.get_images.return_value = []
        return p

    pages = [
        make_page([ref_block]),
        make_page([short_block]),
        make_page([valid_block]),
    ]

    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter(pages))
    mock_doc.close = MagicMock()

    with patch("pymupdf.open", return_value=mock_doc):
        chunks = chunker._process_with_fallback("test.pdf", b"%PDF-mock", doc_metadata)

    # Deve reter apenas o bloco válido da página 3
    assert len(chunks) == 1
    assert "função afim" in chunks[0]["text"]



def test_chunker_unstructured_filters():
    chunker = MaterialChunker(chunk_size=1200, chunk_overlap=150)
    doc_metadata = {"filename": "apostila.pdf", "title": "Apostila", "topic": "Apostila", "source_type": "materiais_didaticos"}

    class MockElement:
        def __init__(self, type_name, text):
            self._type_name = type_name
            self.text = text
        def __repr__(self):
            return f"<{self._type_name}: {self.text}>"

    # Mock types
    class Header(MockElement): pass
    class Footer(MockElement): pass
    class PageNumber(MockElement): pass
    class Title(MockElement): pass
    class NarrativeText(MockElement): pass

    mock_elements = [
        Header("Header", "Cabeçalho da Página 1"),
        Title("Title", "MATEMÁTICA e suas tecnologias 02 VOLUME 3 Introdução"),
        NarrativeText("NarrativeText", "MATEMÁTICA e suas tecnologias 02 VOLUME 3 Conteúdo pedagógico de logaritmos e suas propriedades operatórias fundamentais."),
        PageNumber("PageNumber", "1"),
        Footer("Footer", "Rodapé da Página 1"),
        Title("Title", "Referências"),
        NarrativeText("NarrativeText", "https://site.org/livro-de-matematica Springer 2020"),
        NarrativeText("NarrativeText", "Mais uma referência ignorada."),
    ]

    mock_pdf_mod = MagicMock()
    mock_pdf_mod.partition_pdf.return_value = mock_elements

    with patch.dict("sys.modules", {"unstructured.partition.pdf": mock_pdf_mod}), \
         patch("unstructured.chunking.title.chunk_by_title") as mock_chunk_by_title:

        mock_chunk = MagicMock()
        # Texto com >= 20 palavras para passar o filtro MIN_WORDS_UNSTRUCTURED
        mock_chunk.text = (
            "Conteúdo pedagógico de logaritmos e suas propriedades operatórias fundamentais. "
            "O logaritmo de um número é o expoente ao qual a base deve ser elevada para obter esse número."
        )
        mock_chunk.metadata.page_number = 1
        mock_chunk_by_title.return_value = [mock_chunk]

        chunks = chunker._process_with_unstructured("apostila.pdf", b"%PDF-fake", doc_metadata)

        # Verifica filtros de elementos aplicados antes de chunk_by_title
        filtered_passed = mock_chunk_by_title.call_args[0][0]
        passed_texts = [getattr(el, "text", "") for el in filtered_passed]

        assert not any("Cabeçalho" in t for t in passed_texts)
        assert not any("Rodapé" in t for t in passed_texts)
        assert not any("Referências" in t for t in passed_texts)
        assert not any("Springer" in t for t in passed_texts)
        assert not any("VOLUME" in t for t in passed_texts)
        assert any("Conteúdo pedagógico" in t for t in passed_texts)
        assert chunks[0]["metadata"]["extractor"] == "unstructured"

        # Verifica que os novos parâmetros de qualidade são passados ao chunk_by_title
        call_kwargs = mock_chunk_by_title.call_args[1]
        assert call_kwargs["combine_text_under_n_chars"] == 400, (
            "combine_text_under_n_chars deve ser 400 para fundir elementos curtos agressivamente"
        )
        assert "new_after_n_chars" in call_kwargs, (
            "new_after_n_chars (limite suave) deve ser passado para evitar cortes prematuros"
        )
        assert call_kwargs["new_after_n_chars"] == int(1200 * 0.75)


def test_chunker_unstructured_min_words_filter():
    """Chunks residuais com menos de MIN_WORDS_UNSTRUCTURED palavras devem ser descartados."""
    from app.pipeline.chunking import MIN_WORDS_UNSTRUCTURED

    chunker = MaterialChunker(chunk_size=1200, chunk_overlap=150)
    doc_metadata = {"filename": "apostila.pdf", "title": "Apostila", "topic": "Apostila", "source_type": "materiais_didaticos"}

    mock_pdf_mod = MagicMock()
    mock_pdf_mod.partition_pdf.return_value = []

    with patch.dict("sys.modules", {"unstructured.partition.pdf": mock_pdf_mod}), \
         patch("unstructured.chunking.title.chunk_by_title") as mock_chunk_by_title:

        # chunk curto (5 palavras — abaixo do limiar)
        short_chunk = MagicMock()
        short_chunk.text = "Tópico introdutório de geometria."
        short_chunk.metadata.page_number = 1

        # chunk válido com 25 palavras
        long_chunk = MagicMock()
        long_chunk.text = (
            "A geometria analítica estuda figuras geométricas usando sistemas de coordenadas "
            "e equações algébricas. É essencial para resolver questões do ENEM envolvendo "
            "retas, círculos e parábolas no plano cartesiano."
        )
        long_chunk.metadata.page_number = 2

        mock_chunk_by_title.return_value = [short_chunk, long_chunk]

        chunks = chunker._process_with_unstructured("apostila.pdf", b"%PDF-fake", doc_metadata)

        # Apenas o chunk longo deve sobreviver
        assert len(chunks) == 1, (
            f"Esperado 1 chunk após filtro de {MIN_WORDS_UNSTRUCTURED} palavras mínimas, obtido {len(chunks)}"
        )
        assert "geometria analítica" in chunks[0]["text"]


def test_process_pdf_material_fallback_on_empty_unstructured():
    """
    Quando Unstructured retorna 0 chunks (PDF com muitos ops gráficos),
    process_pdf_material deve acionar o fallback PyMuPDF automaticamente.
    """
    chunker = MaterialChunker(chunk_size=1200, chunk_overlap=150, formula_extraction_enabled=False)

    mock_pdf_mod = MagicMock()
    mock_pdf_mod.partition_pdf.return_value = []

    text_block = (
        0, 0, 100, 20,
        "A progressão geométrica é uma sequência numérica em que cada termo é obtido "
        "multiplicando o anterior por uma razão constante, chamada de razão da PG.",
        0, 0
    )
    mock_page = MagicMock()
    mock_page.rect = MagicMock(width=595, height=842)
    mock_page.get_text.return_value = [text_block]
    mock_page.get_images.return_value = []

    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
    mock_doc.close = MagicMock()

    with patch.dict("sys.modules", {"unstructured.partition.pdf": mock_pdf_mod}), \
         patch("unstructured.chunking.title.chunk_by_title", return_value=[]), \
         patch("pymupdf.open", return_value=mock_doc):

        result = chunker.process_pdf_material(
            "raw/ENEM_MAT_01_progressao-geometrica.pdf",
            b"%PDF-mock"
        )

    assert len(result) == 1, (
        "Fallback PyMuPDF deve ser acionado quando Unstructured retorna 0 chunks"
    )
    assert result[0]["metadata"]["extractor"] == "pymupdf"
    assert chunker.fallback_count == 1




def test_embedding_service_prefixes():
    service = EmbeddingService(model_name="dummy-model")
    
    mock_model = MagicMock()
    mock_model.encode.return_value = [[0.1, 0.2], [0.3, 0.4]]
    service._model = mock_model

    # Testa prefixo 'passage: ' em documentos
    docs = ["Texto 1", "Texto 2"]
    res_docs = service.embed_documents(docs)
    
    mock_model.encode.assert_called_with(
        ["passage: Texto 1", "passage: Texto 2"],
        normalize_embeddings=True,
        show_progress_bar=False
    )
    assert len(res_docs) == 2

    # Testa prefixo 'query: ' em queries
    query = "O que é seno?"
    res_q = service.embed_query(query)
    mock_model.encode.assert_called_with(
        "query: O que é seno?",
        normalize_embeddings=True,
        show_progress_bar=False
    )


def test_pinecone_upsert_batches():
    mock_embedding_service = MagicMock()
    mock_embedding_service.embed_documents.return_value = [[0.1] * 1024]

    mock_pc = MagicMock()
    mock_index = MagicMock()
    mock_pc.list_indexes.return_value = [{"name": "vera-math-index"}]
    mock_pc.Index.return_value = mock_index

    vector_store = PineconeVectorStore(
        api_key="fake-key",
        index_name="vera-math-index",
        embedding_service=mock_embedding_service
    )
    vector_store._pc = mock_pc
    vector_store._index = mock_index

    chunks = [
        {
            "id": "chunk_1",
            "text": "Conteúdo didático sobre trigonometria",
            "metadata": {"title": "Ciclo Trigonométrico", "topic": "Ciclo Trigonométrico"}
        }
    ]

    count = vector_store.upsert_chunks(chunks, namespace="materiais_didaticos", batch_size=50)
    assert count == 1
    mock_index.upsert.assert_called_once()
    
    upsert_args = mock_index.upsert.call_args[1]
    assert upsert_args["namespace"] == "materiais_didaticos"
    assert upsert_args["vectors"][0]["id"] == "chunk_1"
    assert upsert_args["vectors"][0]["metadata"]["text"] == "Conteúdo didático sobre trigonometria"


@patch("app.pipeline.index_embeddings.R2StorageService")
@patch("app.pipeline.index_embeddings.MaterialChunker")
def test_run_materials_ingestion_dry_run(mock_chunker_cls, mock_storage_cls):
    mock_storage = MagicMock()
    mock_storage.bucket_name = "vera"
    mock_storage.list_files.return_value = [{"key": "ENEM_MAT_03_ciclo-trigonometrico.pdf", "size": 1024}]
    mock_storage.download_file_bytes.return_value = b"%PDF-1.4 mock pdf"
    mock_storage_cls.return_value = mock_storage

    mock_chunker = MagicMock()
    mock_chunker.process_pdf_material.return_value = [
        {"id": "chunk_1", "text": "Texto", "metadata": {"title": "Ciclo Trigonométrico"}}
    ]
    mock_chunker_cls.return_value = mock_chunker

    result = run_materials_ingestion(dry_run=True)

    assert result["status"] == "success"
    assert result["total_files"] == 1
    assert result["processed_files"] == 1
    assert result["total_chunks"] == 1
    assert result["total_vectors_upserted"] == 0


def test_utf8_sanitizer_removes_surrogates_and_null_bytes():
    from app.core.sanitizer import sanitize_utf8_string, sanitize_metadata
    import orjson

    # String com surrogates inválidos e byte nulo
    corrupted_str = "Fórmula: \ud800 x² + y² = r² \udfff \x00 Fim"
    cleaned = sanitize_utf8_string(corrupted_str)
    
    assert "\ud800" not in cleaned
    assert "\udfff" not in cleaned
    assert "\x00" not in cleaned
    assert "x² + y² = r²" in cleaned

    # orjson.dumps deve serializar sem lançar TypeError
    dumped = orjson.dumps({"text": cleaned})
    assert b"x\xc2\xb2 + y\xc2\xb2 = r\xc2\xb2" in dumped

    # Metadados aninhados
    meta = {
        "title": "Álgebra \ud800",
        "page_number": 42,
        "score": 0.99,
        "nested": {"topic": "Função \udfff afim"},
        "tags": ["tag1", "tag_\x00_2"]
    }
    cleaned_meta = sanitize_metadata(meta)
    assert cleaned_meta["page_number"] == 42
    assert cleaned_meta["score"] == 0.99
    assert cleaned_meta["title"] == "Álgebra"
    assert cleaned_meta["nested"]["topic"] == "Função  afim"
    
    dumped_meta = orjson.dumps(cleaned_meta)
    assert isinstance(dumped_meta, bytes)


def test_pinecone_upsert_sanitizes_surrogates_preventing_orjson_error():
    import orjson
    from app.services.vectorstore import PineconeVectorStore

    mock_embedding_service = MagicMock()
    mock_embedding_service.embed_documents.return_value = [[0.1] * 1024]

    mock_pc = MagicMock()
    mock_index = MagicMock()
    mock_pc.list_indexes.return_value = [{"name": "vera-math-index"}]
    mock_pc.Index.return_value = mock_index

    # Simula o comportamento do cliente HTTP do Pinecone com orjson
    def fake_upsert(vectors, namespace):
        # Validação estrita de orjson idêntica à do Pinecone SDK
        orjson.dumps({"vectors": vectors, "namespace": namespace})
        return {"upserted_count": len(vectors)}

    mock_index.upsert.side_effect = fake_upsert

    vector_store = PineconeVectorStore(
        api_key="fake-key",
        index_name="vera-math-index",
        embedding_service=mock_embedding_service
    )
    vector_store._pc = mock_pc
    vector_store._index = mock_index

    corrupted_chunks = [
        {
            "id": "chunk_corrupted_\ud800_1",
            "text": "Geometria com caracteres surrogates \ud800\udfff e byte nulo \x00 no texto.",
            "metadata": {
                "title": "Trigonometria \ud800",
                "topic": "Ciclo \udfff",
                "page_number": 1
            }
        }
    ]

    # Não deve lançar TypeError: str is not valid UTF-8: surrogates not allowed
    count = vector_store.upsert_chunks(corrupted_chunks, namespace="materiais_didaticos", batch_size=50)
    assert count == 1
    mock_index.upsert.assert_called_once()


def test_clear_namespace_handles_404():
    from app.services.vectorstore import PineconeVectorStore

    mock_pc = MagicMock()
    mock_index = MagicMock()
    mock_pc.list_indexes.return_value = [{"name": "vera-math-index"}]
    mock_pc.Index.return_value = mock_index

    # Simula erro 404 do Pinecone quando o namespace não existe
    mock_index.delete.side_effect = Exception("[404] Namespace not found")

    vector_store = PineconeVectorStore(api_key="fake-key", index_name="vera-math-index")
    vector_store._pc = mock_pc
    vector_store._index = mock_index

    # Não deve subir exceção
    vector_store.clear_namespace("materiais_didaticos")
    mock_index.delete.assert_called_once_with(delete_all=True, namespace="materiais_didaticos")


