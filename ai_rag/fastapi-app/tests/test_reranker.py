"""Recalculate components for testing.

API Key is needed to call the 100-smelled rehearsing interface, and here you can replace the mold_factory.rerank with a fake.
Validated is that part of the project itself: conversion of results, reordering of returns by interface, fractions and source overlay.
"""

from json import dumps

import pytest

from ai import model_factory, reranker
from common.exception_handler import CustomException
from models import AiModelConfig


@pytest.mark.asyncio
async def test_ollama_rerank_preserves_indices_and_checks_evidence(monkeypatch):
    replies = iter((
        {"score": 4, "evidence": "Missing quote"},
        {"score": 2, "evidence": "Partial answer"},
        {"score": 4, "evidence": "Full answer"},
    ))

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def post(self, url, *, json: dict):
            assert url == "http://127.0.0.1:11434/v1/chat/completions"
            assert json["model"] == "llama3.1:8b"
            return model_factory.httpx.Response(200, json={
                "choices": [{"message": {"content": dumps(next(replies))}}],
            })

    monkeypatch.setattr(model_factory.httpx, "AsyncClient", FakeClient)
    config = AiModelConfig(
        protocol=model_factory.OLLAMA_RERANK,
        base_url="http://127.0.0.1:11434/v1",
        api_key="ollama",
        model_name="llama3.1:8b",
    )
    ranked = await model_factory.rerank(config, "Question", ["No answer", "Partial answer", "Full answer"], 3)
    assert ranked == [
        {"index": 2, "relevance_score": 1.0},
        {"index": 1, "relevance_score": 0.5},
        {"index": 0, "relevance_score": 0.25},
    ]

RESULTS = [
    {"chunk_id": 11, "content": "General provisions of the policy on return for sale", "score": 0.81, "source": "Vector search", "document_id": 1},
    {"chunk_id": 12, "content": "Post-sale service commitments", "score": 0.79, "source": "Vector search", "document_id": 1},
    {"chunk_id": 13, "content": "3 to 5 working days for refunds received", "score": 0.72, "source": "BM25 search", "document_id": 2},
]


def _fake_config() -> AiModelConfig:
    # No library, only one memory object is constructed for components
    return AiModelConfig(
        id=999,
        name="Test Regroup Configuration",
        model_type="Reranking model",
        protocol="Native DashScope",
        base_url="https://example.com/api/v1",
        api_key="sk-test",
        model_name="gte-rerank-v2",
    )


def test_to_documents_keeps_metadata():
    """Page_content when converting to Document. The rest of the fields are in metadata."""
    documents = reranker.to_documents(RESULTS)
    assert documents[0].page_content == "General provisions of the policy on return for sale"
    assert documents[0].metadata["chunk_id"] == 11
    assert documents[0].metadata["source"] == "Vector search"
    # The text does not repeat in metadata
    assert "content" not in documents[0].metadata


@pytest.mark.asyncio
async def test_rerank_reorders_by_interface_result(monkeypatch):
    """Reorder the interfaces in order to return, and the real answer comes first."""

    async def fake_rerank(config, query, documents, top_n):
        # Index points to the list of documents passed back from the interface
        return [
            {"index": 2, "relevance_score": 0.93},
            {"index": 0, "relevance_score": 0.41},
        ]

    monkeypatch.setattr(model_factory, "rerank", fake_rerank)

    compressor = reranker.DashScopeRerank(config=_fake_config(), top_n=2)
    documents = reranker.to_documents(RESULTS)
    ranked = await compressor.acompress_documents(documents, "How long do you think the refunds will be paid?")
    results = reranker.from_documents(ranked)

    # The one in the rough sift is re-listed to be number 1.
    assert results[0]["chunk_id"] == 13
    assert len(results) == 2
    # The score was reordered to a correlation score.
    assert results[0]["score"] == 0.93
    # The source keeps the rough sift and reorders it.
    assert results[0]["source"] == "BM25 search→Rerank"


@pytest.mark.asyncio
async def test_rerank_ignores_out_of_range_index(monkeypatch):
    """The interface returns to the cross-border subscript and does not allow it to crash the entire search."""

    async def fake_rerank(config, query, documents, top_n):
        return [
            {"index": 99, "relevance_score": 0.99},
            {"index": 1, "relevance_score": 0.55},
        ]

    monkeypatch.setattr(model_factory, "rerank", fake_rerank)

    compressor = reranker.DashScopeRerank(config=_fake_config(), top_n=2)
    ranked = await compressor.acompress_documents(reranker.to_documents(RESULTS), "Question")
    results = reranker.from_documents(ranked)

    assert len(results) == 1
    assert results[0]["chunk_id"] == 12


@pytest.mark.asyncio
async def test_rerank_empty_result_is_rejected(monkeypatch):
    """Gives a hint when you do not return one of the interfaces."""

    async def fake_rerank(config, query, documents, top_n):
        return []

    monkeypatch.setattr(model_factory, "rerank", fake_rerank)

    compressor = reranker.DashScopeRerank(config=_fake_config(), top_n=2)
    with pytest.raises(CustomException) as excinfo:
        await compressor.acompress_documents(reranker.to_documents(RESULTS), "Question")
    assert excinfo.value.message == "The reranking interface does not return results, please check the reranking model configuration"


@pytest.mark.asyncio
async def test_rerank_empty_documents_returns_empty():
    """Do not adjust the interface when no candidate document is available."""
    compressor = reranker.DashScopeRerank(config=_fake_config(), top_n=3)
    assert await compressor.acompress_documents([], "Question") == []


def test_sync_interface_is_not_supported():
    """Synchronization interfaces clearly report errors and avoid the misuse of synchronous paths."""
    compressor = reranker.DashScopeRerank(config=_fake_config(), top_n=3)
    with pytest.raises(NotImplementedError):
        compressor.compress_documents(reranker.to_documents(RESULTS), "Question")
