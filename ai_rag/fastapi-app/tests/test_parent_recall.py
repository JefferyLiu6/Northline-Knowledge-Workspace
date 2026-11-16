"""Parent block backfills and threshold filter tests.

Reloading the parent block in MySQL, so a true knowledge base, documentation and parent-child fragments are built;
Without relying on vector banks and models, the refilling logic itself can be measured directly.
"""

import pytest

from models import KnowledgeBase, KnowledgeChunk, KnowledgeDocument
from service import retrieval_service

KB_NAME = "Test back to fill-in - module test exclusively"


@pytest.fixture()
async def parent_child(db):
    """Make a document and a set of parent-son clips, empty and delete."""
    kb = await KnowledgeBase.create(name=KB_NAME, status="Active")
    doc = await KnowledgeDocument.create(kb_id=kb.id, name="Reload test document.txt")
    parent = await KnowledgeChunk.create(
        kb_id=kb.id,
        document_id=doc.id,
        chunk_index=0,
        chunk_type="Parent chunk",
        content="The first involves a 24-month period of quality assurance. the second relates to non-manual damage and free maintenance during the guarantee period.",
        char_count=40,
        page_no=3,
    )
    child_one = await KnowledgeChunk.create(
        kb_id=kb.id,
        document_id=doc.id,
        parent_id=parent.id,
        chunk_index=0,
        chunk_type="Child chunk",
        content="The first is 24 months of quality assurance.",
        char_count=14,
        page_no=3,
    )
    child_two = await KnowledgeChunk.create(
        kb_id=kb.id,
        document_id=doc.id,
        parent_id=parent.id,
        chunk_index=1,
        chunk_type="Child chunk",
        content="Article 3 Overtime fees.",
        char_count=11,
        page_no=3,
    )
    plain = await KnowledgeChunk.create(
        kb_id=kb.id,
        document_id=doc.id,
        chunk_index=0,
        chunk_type="Standard chunk",
        content="General provisions of the policy on return for sale.",
        char_count=8,
    )

    yield {
        "kb": kb,
        "doc": doc,
        "parent": parent,
        "child_one": child_one,
        "child_two": child_two,
        "plain": plain,
    }

    await KnowledgeChunk.filter(kb_id=kb.id).delete()
    await KnowledgeDocument.filter(id=doc.id).delete()
    await KnowledgeBase.filter(id=kb.id).delete()


def _result_of(chunk, score, source="Vector search"):
    return {
        "chunk_id": chunk.id,
        "kb_id": chunk.kb_id,
        "document_id": chunk.document_id,
        "parent_chunk_id": chunk.parent_id,
        "chunk_type": chunk.chunk_type,
        "content": chunk.content,
        "score": score,
        "source": source,
    }


async def test_child_is_replaced_by_parent(parent_child):
    """The element is replaced by the parent block, and the contents are transformed into the whole parent block body."""
    results = [_result_of(parent_child["child_one"], 0.88)]

    merged = await retrieval_service._backfill_parents(results)

    assert len(merged) == 1
    assert merged[0]["chunk_id"] == parent_child["parent"].id
    assert merged[0]["chunk_type"] == "Parent chunk"
    assert merged[0]["content"] == parent_child["parent"].content
    # The score goes to the piece of life.
    assert merged[0]["score"] == 0.88
    # The source is marked and filled out, and notes which sub-block was killed.
    assert merged[0]["source"] == "Vector search→Parent chunk expansion"
    assert merged[0]["matched_chunk_id"] == parent_child["child_one"].id


async def test_two_children_of_same_parent_merge_into_one(parent_child):
    """The two sub-blocks under the same parent block are merged into one, and no duplicate model is issued."""
    results = [
        _result_of(parent_child["child_one"], 0.88),
        _result_of(parent_child["child_two"], 0.72),
    ]

    merged = await retrieval_service._backfill_parents(results)

    assert len(merged) == 1
    # Keep the score against the first piece.
    assert merged[0]["score"] == 0.88


async def test_plain_chunk_is_kept_as_is(parent_child):
    """The normal block has no parent. Keep it as it is."""
    results = [_result_of(parent_child["plain"], 0.65)]

    merged = await retrieval_service._backfill_parents(results)

    assert len(merged) == 1
    assert merged[0]["chunk_id"] == parent_child["plain"].id
    assert merged[0]["chunk_type"] == "Standard chunk"
    assert "Parent chunk expansion" not in merged[0]["source"]


async def test_missing_parent_falls_back_to_child(parent_child):
    """When the parent block is removed, it is returned to the child and this result does not disappear."""
    await KnowledgeChunk.filter(id=parent_child["parent"].id).delete()

    results = [_result_of(parent_child["child_one"], 0.88)]
    merged = await retrieval_service._backfill_parents(results)

    assert len(merged) == 1
    assert merged[0]["chunk_id"] == parent_child["child_one"].id
    assert merged[0]["chunk_type"] == "Child chunk"


async def test_no_child_chunk_skips_query(parent_child):
    """As a result, none of the sub-blocks returned directly from time to time without checking the database."""
    results = [_result_of(parent_child["plain"], 0.65)]
    merged = await retrieval_service._backfill_parents(results)
    assert merged is results
