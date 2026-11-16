"""Vectorization Interface."""

from fastapi import APIRouter, BackgroundTasks, Depends

from common.auth import require_admin
from common.result import Result
from models import User
from service import vectorize_service

router = APIRouter(prefix="/vectorize")


@router.post("/document/{doc_id}")
async def vectorize_document(
    doc_id: int,
    background_tasks: BackgroundTasks,
    _: User = Depends(require_admin),
):
    """Trigger vectorization of a document. The interface only creates a task and returns, the actual call runs in the background."""
    task_id, context = await vectorize_service.start_vectorize(doc_id)
    background_tasks.add_task(vectorize_service.run_vectorize, doc_id, task_id, context)
    return Result.success()


@router.delete("/document/{doc_id}")
async def clear_document(doc_id: int, _: User = Depends(require_admin)):
    """Clear the vector of a document."""
    deleted = await vectorize_service.clear_document_vectors(doc_id)
    return Result.success(f"Cleared {deleted} Vectors")


@router.delete("/knowledgeBase/{kb_id}")
async def clear_knowledge_base(kb_id: int, _: User = Depends(require_admin)):
    """Clear all vectors of the knowledge base and unbind from the model, used for replacing the vector model."""
    deleted = await vectorize_service.clear_kb_vectors(kb_id)
    return Result.success(f"Cleared {deleted} Vectors, Can Switch to Other Vector Models for Re-Vectorization")


@router.get("/status/{kb_id}")
async def status(kb_id: int, _: User = Depends(require_admin)):
    """Overview of vectorization for the knowledge base."""
    return Result.success(await vectorize_service.kb_vector_status(kb_id))


@router.get("/health")
async def health(_: User = Depends(require_admin)):
    """Connectivity Check for Vector Database"""
    return Result.success(await vectorize_service.health_check())
