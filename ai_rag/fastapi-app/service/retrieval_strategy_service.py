"""Retrieval strategy management business logic."""

import json
from decimal import Decimal
from typing import List

from common.exception_handler import CustomException
from common.result import PageInfo
from common.times import cost_millis, now
from models import KnowledgeChunk, RetrievalStrategy
from models.process import RetrievalDebugRecord
from service import retrieval_service

REWRITE_TYPES = {"Multi-query expansion", "Coreference resolution", "HyDE"}
YES_NO = {"Yes", "No"}
# A debugger comparison allows for a maximum of several strategies.
# It's time to rewrite and rehash.
MAX_COMPARE_STRATEGIES = 4


def _validate(payload: dict) -> None:
    if not payload.get("name"):
        raise CustomException("Please enter the strategy name")
    for field in ("vector_enabled", "bm25_enabled", "rerank_enabled", "query_rewrite_enabled", "parent_recall_enabled"):
        value = payload.get(field)
        if value is not None and value not in YES_NO:
            raise CustomException("Switch can only be yes or no")
    # If both roads are turned off, this strategy will not be able to carry out any search.
    if payload.get("vector_enabled") != "Yes" and payload.get("bm25_enabled") != "Yes":
        raise CustomException("Vector Retrieval and BM25 Retrieval at least one to enable")
    if payload.get("query_rewrite_enabled") == "Yes" and payload.get("rewrite_type") not in REWRITE_TYPES:
        raise CustomException("When enabling query rewrite, you must choose how to rewrite")
    for field, label in (("vector_top_k", "Vector search result count"), ("bm25_top_k", "BM25 search result count")):
        value = payload.get(field)
        if value is not None and value < 0:
            raise CustomException(f"{label} cannot be negative")
    if payload.get("rerank_enabled") == "Yes":
        top_n = payload.get("rerank_top_n") or 0
        if top_n <= 0:
            raise CustomException("The number of bars to be saved when reordering is enabled must be greater than 0")
    # Each threshold corresponds to two fractions of an order of magnitude, each in a range from 0 to 1, but with different meanings, and is verified separately.
    for field, label in (
        ("vector_score_threshold", "Cosine similarity threshold"),
        ("rerank_score_threshold", "Reranking relevance threshold"),
    ):
        threshold = payload.get(field)
        if threshold is not None and not 0 <= float(threshold) <= 1:
            raise CustomException(f"{label} must be between 0 and 1")


async def _clear_other_defaults(keep_id: int | None = None) -> None:
    """Only one default policy is allowed for the entire table."""
    query = RetrievalStrategy.filter(is_default="Yes")
    if keep_id is not None:
        query = query.exclude(id=keep_id)
    await query.update(is_default="No")


def _fields(payload: dict) -> dict:
    """Makes the request a field dictionary that can be written directly in the library."""
    def threshold_of(field: str) -> Decimal | None:
        value = payload.get(field)
        if value is None:
            return None
        # The column type is decimal (5,3) and the excess decimal places will be cut off from the database and alerted.
        return Decimal(str(value)).quantize(Decimal("0.001"))

    return {
        "name": payload["name"],
        "vector_enabled": payload.get("vector_enabled") or "No",
        "vector_top_k": payload.get("vector_top_k") or 0,
        "bm25_enabled": payload.get("bm25_enabled") or "No",
        "bm25_top_k": payload.get("bm25_top_k") or 0,
        "rrf_k": payload.get("rrf_k") or 60,
        "rerank_enabled": payload.get("rerank_enabled") or "No",
        "rerank_model_id": payload.get("rerank_model_id"),
        "rerank_top_n": payload.get("rerank_top_n") or 3,
        "query_rewrite_enabled": payload.get("query_rewrite_enabled") or "No",
        # When you turn off the rewrite, clear it together and avoid leaving an invalid residual value.
        "rewrite_type": payload.get("rewrite_type") if payload.get("query_rewrite_enabled") == "Yes" else None,
        "multi_query_count": payload.get("multi_query_count") or 3,
        "parent_recall_enabled": payload.get("parent_recall_enabled") or "No",
        # Vector thresholds will only be effective when the final fraction is a cosine similarity, and re-allocation thresholds will be effective only when reordering starts.
        # Both are stored in the original form. Which will be effective on the page is determined by the current policy switch combination
        "vector_score_threshold": threshold_of("vector_score_threshold"),
        "rerank_score_threshold": threshold_of("rerank_score_threshold"),
        "remark": payload.get("remark"),
    }


async def add(payload: dict) -> None:
    _validate(payload)
    if await RetrievalStrategy.get_or_none(name=payload["name"]):
        raise CustomException("Duplicate strategy name")
    is_default = payload.get("is_default") or "No"
    if is_default == "Yes":
        await _clear_other_defaults()
    await RetrievalStrategy.create(is_default=is_default, **_fields(payload))


async def update(strategy_id: int | None, payload: dict) -> None:
    if strategy_id is None:
        raise CustomException("Strategy ID cannot be empty")
    if await RetrievalStrategy.get_or_none(id=strategy_id) is None:
        raise CustomException("No search policy found")
    _validate(payload)
    if await RetrievalStrategy.filter(name=payload["name"]).exclude(id=strategy_id).exists():
        raise CustomException("Duplicate strategy name")
    is_default = payload.get("is_default") or "No"
    if is_default == "Yes":
        await _clear_other_defaults(keep_id=strategy_id)
    await RetrievalStrategy.filter(id=strategy_id).update(is_default=is_default, **_fields(payload))


async def delete(strategy_id: int) -> None:
    strategy = await RetrievalStrategy.get_or_none(id=strategy_id)
    if strategy is None:
        raise CustomException("No search policy found")
    # The default strategy is to use the back of a question-and-answer application when it's not appropriate.
    if strategy.is_default == "Yes":
        raise CustomException("Default strategy cannot be deleted, please set other strategies as default first")
    await RetrievalStrategy.filter(id=strategy_id).delete()


async def select_page(name: str = "", page_num: int = 1, page_size: int = 10) -> PageInfo:
    query = RetrievalStrategy.filter(name__contains=name)
    items = await query.order_by("-is_default", "id").offset((page_num - 1) * page_size).limit(page_size)
    total = await query.count()
    return PageInfo(total=total, list=[retrieval_service.strategy_dict(item) for item in items])


async def compare(
    user_id: int,
    kb_ids: List[int],
    query: str,
    strategy_ids: List[int],
    document_ids: List[int] | None = None,
) -> dict:
    """Debugging table: The same problem has a variety of strategies, and the results are returned in parallel and archived."""
    if not strategy_ids:
        raise CustomException("Please select at least one search strategy.")
    if len(strategy_ids) > MAX_COMPARE_STRATEGIES:
        raise CustomException(f"Compare up to {MAX_COMPARE_STRATEGIES} strategies at a time")
    started = now()
    columns = []
    for strategy_id in strategy_ids:
        strategy = await retrieval_service.load_strategy(strategy_id)
        try:
            outcome = await retrieval_service.retrieve(kb_ids, query, strategy, document_ids)
            await retrieval_service._fill_document_name(outcome["results"])
            columns.append(outcome)
        except CustomException as exc:
            # One set of strategies has failed without affecting the others. Put the reasons for failure in this column.
            columns.append(
                {
                    "strategy_id": strategy_id,
                    "strategy_name": strategy["name"],
                    "results": [],
                    "stages": [],
                    "queries": [query],
                    "cost_millis": 0,
                    "error": exc.message,
                }
            )
    total_cost = cost_millis(started)
    # Archived to facilitate a back-to-back review.
    await RetrievalDebugRecord.create(
        kb_id=kb_ids[0] if kb_ids else 0,
        query=query,
        strategy_ids=",".join(str(item) for item in strategy_ids),
        result_snapshot=json.dumps(columns, ensure_ascii=False, default=str),
        cost_millis=total_cost,
        create_user_id=user_id,
    )
    return {"query": query, "columns": columns, "cost_millis": total_cost}


async def select_records(kb_id: int | None = None, page_num: int = 1, page_size: int = 10) -> PageInfo:
    """Debugs the log list, does not return a snapshot text and avoids the list returning too big."""
    query = RetrievalDebugRecord.all()
    if kb_id:
        query = query.filter(kb_id=kb_id)
    records = await query.order_by("-id").offset((page_num - 1) * page_size).limit(page_size)
    total = await query.count()
    return PageInfo(
        total=total,
        list=[
            {
                "id": record.id,
                "kb_id": record.kb_id,
                "query": record.query,
                "strategy_ids": record.strategy_ids,
                "cost_millis": record.cost_millis,
                "create_time": record.create_time,
            }
            for record in records
        ],
    )


async def select_record(record_id: int) -> dict:
    """Get the complete snapshot of a debugging record by ID."""
    record = await RetrievalDebugRecord.get_or_none(id=record_id)
    if record is None:
        raise CustomException("Debug records not found")
    return {
        "id": record.id,
        "query": record.query,
        "cost_millis": record.cost_millis,
        "create_time": record.create_time,
        "columns": json.loads(record.result_snapshot) if record.result_snapshot else [],
    }


async def kb_chunk_type_summary(kb_id: int) -> dict:
    """This library is distributed by the type of clip, and there's a hint on the page whether to open a parent block back."""
    plain = await KnowledgeChunk.filter(kb_id=kb_id, chunk_type="Standard chunk").count()
    child = await KnowledgeChunk.filter(kb_id=kb_id, chunk_type="Child chunk").count()
    parent = await KnowledgeChunk.filter(kb_id=kb_id, chunk_type="Parent chunk").count()
    return {"plain": plain, "child": child, "parent": parent}
