"""Knowledge Snippet Business Logic.

Comprises two parts: slicing documents into segments (writing), and query and maintenance of segments (reading and deleting).
"""

from common.document_guard import idle_document, idle_chunk

import asyncio
import json
from typing import List

from ai import splitter, vector_store
from common.exception_handler import CustomException
from common.result import PageInfo
from common.times import cost_millis, now
from models import (
    ChunkStrategy,
    DocumentProcessTask,
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeDocument,
)
from service import chunk_strategy_service

ERROR_MAX_LENGTH = 500


def chunk_dict(chunk: KnowledgeChunk) -> dict:
    return {
        "id": chunk.id,
        "kb_id": chunk.kb_id,
        "document_id": chunk.document_id,
        "parent_id": chunk.parent_id,
        "chunk_index": chunk.chunk_index,
        "chunk_type": chunk.chunk_type,
        "content": chunk.content,
        "char_count": chunk.char_count,
        "page_no": chunk.page_no,
        "title_path": chunk.title_path,
        "vector_status": chunk.vector_status,
        "create_time": chunk.create_time,
        "update_time": chunk.update_time,
    }


async def _refresh_counts(document_id: int, kb_id: int) -> None:
    """Recalculates the number of fragments on the document and knowledge base.

    A parent block is only a context container for generation, does not participate in searching, does not count the number of statistical clips.
    The number of fragments on the list page is thus consistent with the number of clips that are actually retrieved.
    """
    doc_count = await KnowledgeChunk.filter(document_id=document_id).exclude(chunk_type="Parent chunk").count()
    await KnowledgeDocument.filter(id=document_id).update(chunk_count=doc_count)
    kb_count = await KnowledgeChunk.filter(kb_id=kb_id).exclude(chunk_type="Parent chunk").count()
    await KnowledgeBase.filter(id=kb_id).update(chunk_count=kb_count)


async def _resolve_strategy(kb_id: int, strategy_id: int | None) -> dict:
    """I'm not sure what strategy to use for this one.

    Priority: The > Knowledge Bank, which is temporarily selected on the page, binds itself to the > global default policy.
    """
    if strategy_id:
        strategy = await ChunkStrategy.get_or_none(id=strategy_id)
        if strategy is None:
            raise CustomException("No splitting strategy found")
        return chunk_strategy_service.strategy_dict(strategy)
    kb = await KnowledgeBase.get_or_none(id=kb_id)
    if kb is not None and kb.chunk_strategy_id:
        strategy = await ChunkStrategy.get_or_none(id=kb.chunk_strategy_id)
        if strategy is not None:
            return chunk_strategy_service.strategy_dict(strategy)
    return await chunk_strategy_service.select_default()


@idle_document
async def start_split(doc_id: int, strategy_id: int | None, *, strategy_snapshot: dict | None = None) -> tuple[int, dict]:
    """Validate joint tasks, return task ID and the strategy to be used this time."""
    doc = await KnowledgeDocument.get_or_none(id=doc_id)
    if doc is None:
        raise CustomException("Document not found")
    if doc.parse_status != "Parsed":
        raise CustomException("Parsing the document before severing it.")
    if not doc.parsed_text:
        raise CustomException("The document does not parse text. Please re-configurate.")
    strategy = strategy_snapshot or await _resolve_strategy(doc.kb_id, strategy_id)
    task = await DocumentProcessTask.create(
        kb_id=doc.kb_id,
        document_id=doc.id,
        task_type="Text Splitting",
        context_json=json.dumps(strategy, default=str),
        task_status="Processing",
        total_count=1,
        start_time=now(),
    )
    return task.id, strategy


async def run_split(doc_id: int, task_id: int, strategy: dict) -> None:
    """Backstage task: Sever and write the segment."""
    doc = await KnowledgeDocument.get_or_none(id=doc_id)
    if doc is None:
        return
    started = now()
    try:
        # Cut is a pure CPU operation, drop to the thread for execution and do not block the event cycle.
        chunks = await asyncio.to_thread(splitter.split, doc.parsed_text, strategy)
        if not chunks:
            raise CustomException("No snippets were separated. Check the cut parameters.")
        # (a) Clear the old part of this document before re-severing it to avoid mixing new and old pieces;
        # The old footage should be cleared together, otherwise the vectors will leave an orphan vector pointing to the deleted fragments.
        await vector_store.delete_by_document(doc_id)
        # Clear the old part of this document before cutting it again, and avoid mixing up old pieces.
        await KnowledgeChunk.filter(document_id=doc_id).delete()
        # Created_ids record the true id of a stored segment by using the subscript of the returned list,
        # It's the only way to convert a parent_index into a database.
        created_ids: list[int] = []
        for chunk in chunks:
            parent_id = None
            if chunk.parent_index is not None:
                parent_id = created_ids[chunk.parent_index]
            created = await KnowledgeChunk.create(
                kb_id=doc.kb_id,
                document_id=doc.id,
                parent_id=parent_id,
                chunk_index=chunk.chunk_index,
                chunk_type=chunk.chunk_type,
                content=chunk.content,
                char_count=len(chunk.content),
                page_no=chunk.page_no,
            )
            created_ids.append(created.id)
        # The footage has changed. All the vectors previously written into the vector library have been destroyed.
        await KnowledgeDocument.filter(id=doc_id).update(vector_status="Pending embedding")
        await _refresh_counts(doc_id, doc.kb_id)
        await DocumentProcessTask.filter(id=task_id).update(
            task_status="Completed",
            success_count=len(chunks),
            total_count=len(chunks),
            end_time=now(),
            cost_millis=cost_millis(started),
        )
    except Exception as exc:
        message = exc.message if isinstance(exc, CustomException) else f"Split failed:{exc}"
        await DocumentProcessTask.filter(id=task_id).update(
            task_status="Failed",
            fail_count=1,
            error_message=message[:ERROR_MAX_LENGTH],
            end_time=now(),
            cost_millis=cost_millis(started),
        )


@idle_chunk
async def update_content(chunk_id: int | None, content: str | None) -> None:
    """Manually corrects the contents of a fragment."""
    if chunk_id is None:
        raise CustomException("Snippet ID cannot be empty")
    if not content or not content.strip():
        raise CustomException("Snippets cannot be empty")
    chunk = await KnowledgeChunk.get_or_none(id=chunk_id)
    if chunk is None:
        raise CustomException("No snippets found")
    if chunk.chunk_type == "Parent chunk":
        raise CustomException("Edit and reparse the source document to change a parent chunk")
    await vector_store.delete_by_chunk_ids([chunk_id])
    text = content.strip()
    await KnowledgeChunk.filter(id=chunk_id).update(
        content=text,
        char_count=len(text),
        # It's changed. The previous vector corresponds to the old text and has to be re-quantified.
        vector_status="Pending embedding",
    )
    await KnowledgeDocument.filter(id=chunk.document_id).update(vector_status="Pending embedding")


@idle_chunk
async def delete(chunk_id: int) -> None:
    chunk = await KnowledgeChunk.get_or_none(id=chunk_id)
    if chunk is None:
        raise CustomException("No snippets found")
    # Deleting a parent block will lose its target, retrieve the neutron block and fail to get the full context.
    if chunk.chunk_type == "Parent chunk":
        raise CustomException("Parent block cannot be removed separately. Please re-severe the whole document")
    # The footage's gone. It's going to be deleted from the vector library, otherwise it can hit something that doesn't exist.
    await vector_store.delete_by_chunk_ids([chunk_id])
    await KnowledgeChunk.filter(id=chunk_id).delete()
    await _refresh_counts(chunk.document_id, chunk.kb_id)


async def delete_batch(ids: List[int]) -> None:
    chunks = await KnowledgeChunk.filter(id__in=ids)
    if any(chunk.chunk_type == "Parent chunk" for chunk in chunks):
        raise CustomException("Check to include a parent block, which cannot be removed separately")
    for chunk in chunks:
        await delete(chunk.id)


async def select_by_id(chunk_id: int) -> dict:
    chunk = await KnowledgeChunk.get_or_none(id=chunk_id)
    if chunk is None:
        raise CustomException("No snippets found")
    return chunk_dict(chunk)


async def select_page(
    document_id: int | None = None,
    kb_id: int | None = None,
    chunk_type: str = "",
    keyword: str = "",
    page_num: int = 1,
    page_size: int = 10,
) -> PageInfo:
    query = KnowledgeChunk.all()
    # Document_id from the top of the page document to frame the most common filter dimensions
    if document_id:
        query = query.filter(document_id=document_id)
    if kb_id:
        query = query.filter(kb_id=kb_id)
    # hunk_type pulls a frame from the snippet type to look only at a piece or just a piece of a piece when a parent splits it.
    if chunk_type:
        query = query.filter(chunk_type=chunk_type)
    # Keyword blurs the match in the text of a session to quickly locate which part of a sentence is cut
    if keyword:
        query = query.filter(content__contains=keyword)
    # Ordered by serial number within the document, the sequence of segments seen on the page is identical to the original text
    chunks = await query.order_by("chunk_type", "chunk_index").offset((page_num - 1) * page_size).limit(page_size)
    total = await query.count()
    return PageInfo(total=total, list=[chunk_dict(chunk) for chunk in chunks])
