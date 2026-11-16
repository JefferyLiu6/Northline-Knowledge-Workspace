"""To quantify business logic.

Send the knowledge footage into vector models and write the vectors obtained into PGVector.

Only the fragments that are retrieved need vectors: ordinary blocks and sub-blocks do not want a parent.
The role of the parent block is to fill out the full context after a hit by the neutron block, and it does not itself participate in similarity matching.
"""

from common.document_guard import idle_document, idle_knowledge_base

import asyncio

from ai import model_factory, vector_store
from common.exception_handler import CustomException
from common.times import cost_millis, now
from models import (
    AiModelConfig,
    DocumentProcessTask,
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeDocument,
)

ERROR_MAX_LENGTH = 500
# How many text lines are sent to vector models at a time. A hundred copies of text-embeding-v4 receive up to 10 singles,
# "batch size is invalid, it should not be returned than 10",
# So take 10: both interface ceilings and avoid too many requests slowing down the overall speed
BATCH_SIZE = 10
# Only these two pieces require vectors, and the parent blocks do not participate in searching.
SEARCHABLE_TYPES = ["Standard chunk", "Child chunk"]


def _truncate(message: str) -> str:
    return message[:ERROR_MAX_LENGTH]


async def _bind_embedding_model(kb: KnowledgeBase, config: AiModelConfig) -> None:
    """The knowledge base and vector models are tied together and intermediate models are blocked.

    The vectors in the library were created from the one that was tied up, and then a model.
    The encoded vectors of new questions and the old vectors in the library are not in the same semantic space, and it makes no sense to calculate similarities.
    Therefore, no direct change is permitted after the binding and this library must be emptied of its vector.
    """
    if kb.embedding_model_id is None:
        await KnowledgeBase.filter(id=kb.id).update(embedding_model_id=config.id)
        return
    if kb.embedding_model_id != config.id:
        raise CustomException(
            "The knowledge base has tied up another vector model, and the direct replacement of models will make it impossible to match the old and new vectors."
            "Please re-quantify the emptied vector on the knowledge base."
        )


@idle_document
async def start_vectorize(doc_id: int) -> tuple[int, dict]:
    """Verify the task and return to the mission ID and vector model configuration that will be used this time."""
    doc = await KnowledgeDocument.get_or_none(id=doc_id)
    if doc is None:
        raise CustomException("Document not found")
    if doc.vector_status == "Embedding in progress":
        raise CustomException("This document is being quantified. Please wait.")
    total = await KnowledgeChunk.filter(document_id=doc_id, chunk_type__in=SEARCHABLE_TYPES).count()
    if total == 0:
        raise CustomException("The document has not yet been able to quantify the fragments, please cut first.")
    kb = await KnowledgeBase.get_or_none(id=doc.kb_id)
    if kb is None:
        raise CustomException("Knowledge base not found")
    # Take an enabled vector model, and this step will give a hint if it is not set for Key or when it is not.
    config = await model_factory.load_enabled(model_factory.EMBEDDING)
    await _bind_embedding_model(kb, config)
    task = await DocumentProcessTask.create(
        kb_id=doc.kb_id,
        document_id=doc.id,
        task_type="Embed",
        task_status="Processing",
        total_count=total,
        start_time=now(),
    )
    await KnowledgeDocument.filter(id=doc_id).update(vector_status="Embedding in progress")
    return task.id, {"config_id": config.id, "total": total}


async def run_vectorize(doc_id: int, task_id: int, context: dict) -> None:
    """Backstage task: a batch call vector model and write to the vector library."""
    doc = await KnowledgeDocument.get_or_none(id=doc_id)
    if doc is None:
        return
    started = now()
    success = 0
    failed = 0
    try:
        config = await AiModelConfig.get_or_none(id=context["config_id"])
        if config is None:
            raise CustomException("Vector model configuration has been deleted. Please reconfigure and try again")
        embeddings = model_factory.build_embeddings(config)
        chunks = await KnowledgeChunk.filter(
            document_id=doc_id, chunk_type__in=SEARCHABLE_TYPES
        ).order_by("id")
        # Distributed, network requests per batch
        for start in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[start : start + BATCH_SIZE]
            texts = [chunk.content for chunk in batch]
            try:
                vectors = await embeddings.aembed_documents(texts)
            except Exception as exc:
                # A batch of failures does not affect the others.
                failed += len(batch)
                await KnowledgeChunk.filter(id__in=[chunk.id for chunk in batch]).update(
                    vector_status="Failed"
                )
                await DocumentProcessTask.filter(id=task_id).update(
                    error_message=_truncate(model_factory.translate_exception(exc))
                )
                continue
            rows = [
                {
                    "chunk_id": chunk.id,
                    "kb_id": chunk.kb_id,
                    "document_id": chunk.document_id,
                    "parent_chunk_id": chunk.parent_id,
                    "chunk_type": chunk.chunk_type,
                    "title_path": chunk.title_path,
                    "content": chunk.content,
                    "embedding": vector,
                }
                for chunk, vector in zip(batch, vectors)
            ]
            await vector_store.upsert(rows)
            await KnowledgeChunk.filter(id__in=[chunk.id for chunk in batch]).update(
                vector_status="Completed"
            )
            success += len(batch)
            # Update the progress every batch. Update the page to see where it's going.
            await DocumentProcessTask.filter(id=task_id).update(
                success_count=success, fail_count=failed
            )
        # Any one of these failures, the whole document labels fail. The manager can see that this is not done.
        status = "Completed" if failed == 0 else "Failed"
        await KnowledgeDocument.filter(id=doc_id).update(vector_status=status)
        await DocumentProcessTask.filter(id=task_id).update(
            task_status="Completed" if failed == 0 else "Failed",
            success_count=success,
            fail_count=failed,
            end_time=now(),
            cost_millis=cost_millis(started),
        )
    except Exception as exc:
        message = exc.message if isinstance(exc, CustomException) else f"Items{exc}"
        await KnowledgeDocument.filter(id=doc_id).update(vector_status="Failed")
        await DocumentProcessTask.filter(id=task_id).update(
            task_status="Failed",
            success_count=success,
            fail_count=failed,
            error_message=_truncate(message),
            end_time=now(),
            cost_millis=cost_millis(started),
        )


@idle_document
async def clear_document_vectors(doc_id: int) -> int:
    """Clears the vector of a document and returns it to be quantified."""
    doc = await KnowledgeDocument.get_or_none(id=doc_id)
    if doc is None:
        raise CustomException("Document not found")
    deleted = await vector_store.delete_by_document(doc_id)
    await KnowledgeChunk.filter(document_id=doc_id).update(vector_status="Pending embedding")
    await KnowledgeDocument.filter(id=doc_id).update(vector_status="Pending embedding")
    return deleted


@idle_knowledge_base
async def clear_kb_vectors(kb_id: int) -> int:
    """Clear the entire knowledge base and release the vector model.

    Once cleared, this library can be re-created using a different vector model.
    """
    kb = await KnowledgeBase.get_or_none(id=kb_id)
    if kb is None:
        raise CustomException("Knowledge base not found")
    if await DocumentProcessTask.filter(kb_id=kb_id, task_status="Processing").exists():
        raise CustomException("Wait for document processing before clearing embeddings")
    deleted = await vector_store.delete_by_kb(kb_id)
    await KnowledgeChunk.filter(kb_id=kb_id).update(vector_status="Pending embedding")
    await KnowledgeDocument.filter(kb_id=kb_id).update(vector_status="Pending embedding")
    # Next time you untie, the current model will be rebound to quantify.
    await KnowledgeBase.filter(id=kb_id).update(embedding_model_id=None)
    return deleted


async def kb_vector_status(kb_id: int) -> dict:
    """A quantitative overview of the knowledge base is used to determine whether it can start a question-and-answer session."""
    kb = await KnowledgeBase.get_or_none(id=kb_id)
    if kb is None:
        raise CustomException("Knowledge base not found")
    total = await KnowledgeChunk.filter(kb_id=kb_id, chunk_type__in=SEARCHABLE_TYPES).count()
    done = await KnowledgeChunk.filter(
        kb_id=kb_id, chunk_type__in=SEARCHABLE_TYPES, vector_status="Completed"
    ).count()
    vector_count = await vector_store.count_by_kb(kb_id)
    model_name = None
    if kb.embedding_model_id:
        config = await AiModelConfig.get_or_none(id=kb.embedding_model_id)
        model_name = config.model_name if config else None
    return {
        "kb_id": kb_id,
        "kb_name": kb.name,
        # There should be a number of fragments of vectors.
        "searchable_count": total,
        # Snippet table marked as number of completed
        "done_count": done,
        # The number of vectors that actually exist in the vector library and the lack of compatibility on either side
        "vector_count": vector_count,
        "embedding_model": model_name,
    }


async def health_check() -> str:
    """Connectivity Check for Vector Database"""
    return await vector_store.health_check()
