"""Search Strategy Management and Retrieval Comparison Debugging Interface."""

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from common.auth import require_admin
from common.result import Result
from models import User
from service import retrieval_service, retrieval_strategy_service

router = APIRouter(prefix="/retrievalStrategy")


class RetrievalStrategyPayload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    name: str | None = None
    vector_enabled: str | None = None
    vector_top_k: int | None = None
    bm25_enabled: str | None = None
    bm25_top_k: int | None = None
    rrf_k: int | None = None
    rerank_enabled: str | None = None
    rerank_model_id: int | None = None
    rerank_top_n: int | None = None
    query_rewrite_enabled: str | None = None
    rewrite_type: str | None = None
    multi_query_count: int | None = None
    parent_recall_enabled: str | None = None
    # Threshold is divided into two by fractional order of magnitude: vector one-way recall cosine similarities, with reordered weights associated
    vector_score_threshold: float | None = None
    rerank_score_threshold: float | None = None
    is_default: str | None = None
    remark: str | None = None


class ComparePayload(BaseModel):
    kb_ids: List[int] = []
    # Up to four sets of policies to be compared in parallel on the page
    strategy_ids: List[int] = []
    document_ids: List[int] | None = None
    query: str = ""


@router.post("/add")
async def add(payload: RetrievalStrategyPayload, _: User = Depends(require_admin)):
    await retrieval_strategy_service.add(payload.model_dump(exclude_unset=True))
    return Result.success()


@router.put("/update")
async def update(payload: RetrievalStrategyPayload, _: User = Depends(require_admin)):
    await retrieval_strategy_service.update(payload.id, payload.model_dump(exclude_unset=True))
    return Result.success()


@router.post("/scoreScale")
async def score_scale(payload: RetrievalStrategyPayload, _: User = Depends(require_admin)):
    """Return the unit of the final score of this strategy based on the current form's switch combination.

    The strategy popup should inform the administrator which threshold will take effect before saving, while the calculation rules and retrieval pipeline
    are the same set, written in retrieval_service, the page calls this interface to get it, not rewritten on the frontend.
    """
    return Result.success(
        retrieval_service.predict_score_scale(payload.model_dump(exclude_unset=True))
    )


@router.delete("/delete/{strategy_id}")
async def delete(strategy_id: int, _: User = Depends(require_admin)):
    await retrieval_strategy_service.delete(strategy_id)
    return Result.success()


@router.get("/selectPage")
async def select_page(
    name: str = "",
    page_num: int = 1,
    page_size: int = 10,
    _: User = Depends(require_admin),
):
    return Result.success(await retrieval_strategy_service.select_page(name, page_num, page_size))


@router.post("/compare")
async def compare(payload: ComparePayload, current_user: User = Depends(require_admin)):
    """Debugging Interface: Run multiple strategies on the same question, return results side by side and archive them."""
    return Result.success(
        await retrieval_strategy_service.compare(
            current_user.id,
            payload.kb_ids,
            payload.query,
            payload.strategy_ids,
            payload.document_ids,
        )
    )


@router.get("/records")
async def records(
    kb_id: int | None = None,
    page_num: int = 1,
    page_size: int = 10,
    _: User = Depends(require_admin),
):
    """Debugging Record List."""
    return Result.success(await retrieval_strategy_service.select_records(kb_id, page_num, page_size))


@router.get("/records/{record_id}")
async def record(record_id: int, _: User = Depends(require_admin)):
    """Get the complete snapshot of a debugging record by ID."""
    return Result.success(await retrieval_strategy_service.select_record(record_id))


@router.get("/chunkTypes/{kb_id}")
async def chunk_types(kb_id: int, _: User = Depends(require_admin)):
    """Distribution of fragment types in the knowledge base, used to prompt whether to enable parent block filling."""
    return Result.success(await retrieval_strategy_service.kb_chunk_type_summary(kb_id))
