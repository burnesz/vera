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
    chunker = MaterialChunker(chunk_size=200, chunk_overlap=30)
    doc_metadata = {"filename": "test.pdf", "title": "Teste", "topic": "Teste", "source_type": "materiais_didaticos"}
    
    with patch("pypdf.PdfReader") as mock_reader_cls:
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Definição de Trigonometria e seno, cosseno e tangente."
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_reader_cls.return_value = mock_reader

        chunks = chunker._process_with_fallback("test.pdf", b"%PDF-mock", doc_metadata)
        assert len(chunks) == 1
        assert chunks[0]["metadata"]["title"] == "Teste"
        assert "Trigonometria" in chunks[0]["text"]


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
    mock_embedding_service.embed_documents.return_value = [[0.1] * 768]

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
