"""
RAG Pipeline Tests — chunking, embedding, retrieval.
"""

import pytest
from app.rag.chunking import FixedSizeChunking, SemanticChunking, get_chunker
from app.rag.embedding import MockEmbeddings, get_embedding_model


def test_fixed_chunking():
    chunker = FixedSizeChunking(chunk_size=50, chunk_overlap=10)
    text = "A" * 120
    chunks = chunker.chunk(text)
    assert len(chunks) >= 2
    for c in chunks:
        assert "text" in c
        assert "metadata" in c
        assert c["metadata"]["chunk_id"] >= 0


def test_fixed_chunking_empty():
    chunker = FixedSizeChunking()
    assert chunker.chunk("") == []


def test_semantic_chunking():
    chunker = SemanticChunking()
    text = "Paragraph one about banking.\n\nParagraph two about loans.\n\nParagraph three about compliance."
    chunks = chunker.chunk(text)
    assert len(chunks) >= 1


def test_get_chunker():
    assert isinstance(get_chunker("fixed"), FixedSizeChunking)
    assert isinstance(get_chunker("semantic"), SemanticChunking)


def test_mock_embeddings():
    model = MockEmbeddings(dimension=128)
    assert model.dimension == 128
    embs = model.embed(["hello", "world"])
    assert len(embs) == 2
    assert len(embs[0]) == 128
    q = model.embed_query("test")
    assert len(q) == 128


def test_get_embedding_model_mock():
    model = get_embedding_model("mock")
    assert isinstance(model, MockEmbeddings)
