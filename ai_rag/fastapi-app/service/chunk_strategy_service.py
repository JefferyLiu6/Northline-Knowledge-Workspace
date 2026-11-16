"""Splitting strategy manages business logic."""

from typing import List

from common.exception_handler import CustomException
from common.result import PageInfo
from models import ChunkStrategy

# Two cut-off methods have been achieved, with a corresponding function in the one/ standard. py of chapter 09
STRATEGY_TYPES = {"Recursive chunking", "Parent-child chunking"}


def strategy_dict(strategy: ChunkStrategy) -> dict:
    return {
        "id": strategy.id,
        "name": strategy.name,
        "strategy_type": strategy.strategy_type,
        "chunk_size": strategy.chunk_size,
        "chunk_overlap": strategy.chunk_overlap,
        "parent_chunk_size": strategy.parent_chunk_size,
        "separators": strategy.separators,
        "is_default": strategy.is_default,
        "remark": strategy.remark,
        "create_time": strategy.create_time,
        "update_time": strategy.update_time,
    }


def _validate(payload: dict) -> None:
    """Validation for both adding and editing."""
    if not payload.get("name"):
        raise CustomException("Please enter the strategy name")
    strategy_type = payload.get("strategy_type")
    if strategy_type not in STRATEGY_TYPES:
        raise CustomException("Strategy type parameter error")
    chunk_size = payload.get("chunk_size") or 0
    if chunk_size <= 0:
        raise CustomException("Segment length must be greater than 0")
    chunk_overlap = payload.get("chunk_overlap") or 0
    # Overlapping is longer than the footage itself, and it's going to put a cut in the circle of death.
    if chunk_overlap >= chunk_size:
        raise CustomException("Overlap character count must be less than segment length")
    if strategy_type == "Parent-child chunking":
        parent_chunk_size = payload.get("parent_chunk_size") or 0
        # A parent must have a piece, or the father's parts will be reduced to ordinary pieces.
        if parent_chunk_size <= chunk_size:
            raise CustomException("Parent block length must be greater than segment length")


async def _clear_other_defaults(keep_id: int | None = None) -> None:
    """Clear the default marks of other strategies to ensure only one default in the whole table."""
    query = ChunkStrategy.filter(is_default="Yes")
    if keep_id is not None:
        query = query.exclude(id=keep_id)
    await query.update(is_default="No")


async def add(payload: dict) -> None:
    _validate(payload)
    if await ChunkStrategy.get_or_none(name=payload["name"]):
        raise CustomException("Duplicate strategy name")
    is_default = payload.get("is_default") or "No"
    if is_default == "Yes":
        await _clear_other_defaults()
    await ChunkStrategy.create(
        name=payload["name"],
        strategy_type=payload["strategy_type"],
        chunk_size=payload["chunk_size"],
        chunk_overlap=payload.get("chunk_overlap") or 0,
        # Recursive fractions do not use the length of a parent block, save an empty value rather than store a meaningless number
        parent_chunk_size=payload.get("parent_chunk_size") if payload["strategy_type"] == "Parent-child chunking" else None,
        separators=payload.get("separators"),
        is_default=is_default,
        remark=payload.get("remark"),
    )


async def update(strategy_id: int | None, payload: dict) -> None:
    if strategy_id is None:
        raise CustomException("Strategy ID cannot be empty")
    strategy = await ChunkStrategy.get_or_none(id=strategy_id)
    if strategy is None:
        raise CustomException("No splitting strategy found")
    _validate(payload)
    # If you change your name, you'll be stopped by yourself.
    if await ChunkStrategy.filter(name=payload["name"]).exclude(id=strategy_id).exists():
        raise CustomException("Duplicate strategy name")
    is_default = payload.get("is_default") or "No"
    if is_default == "Yes":
        await _clear_other_defaults(keep_id=strategy_id)
    await ChunkStrategy.filter(id=strategy_id).update(
        name=payload["name"],
        strategy_type=payload["strategy_type"],
        chunk_size=payload["chunk_size"],
        chunk_overlap=payload.get("chunk_overlap") or 0,
        parent_chunk_size=payload.get("parent_chunk_size") if payload["strategy_type"] == "Parent-child chunking" else None,
        separators=payload.get("separators"),
        is_default=is_default,
        remark=payload.get("remark"),
    )


async def delete(strategy_id: int) -> None:
    strategy = await ChunkStrategy.get_or_none(id=strategy_id)
    if strategy is None:
        raise CustomException("No splitting strategy found")
    # The default policy is the back of a knowledge base when it's not there.
    if strategy.is_default == "Yes":
        raise CustomException("Default strategy cannot be deleted, please set other strategies as default first")
    await ChunkStrategy.filter(id=strategy_id).delete()


async def select_all() -> List[dict]:
    strategies = await ChunkStrategy.all().order_by("-is_default", "id")
    return [strategy_dict(item) for item in strategies]


async def select_default() -> dict:
    """Take the default strategy, use it if the knowledge base hasn't been configured separately."""
    strategy = await ChunkStrategy.get_or_none(is_default="Yes")
    if strategy is None:
        raise CustomException("No default splitting strategy set, please set one in the splitting strategy first")
    return strategy_dict(strategy)


async def select_page(name: str = "", strategy_type: str = "", page_num: int = 1, page_size: int = 10) -> PageInfo:
    query = ChunkStrategy.filter(name__contains=name)
    if strategy_type:
        query = query.filter(strategy_type=strategy_type)
    strategies = await query.order_by("-id").offset((page_num - 1) * page_size).limit(page_size)
    total = await query.count()
    return PageInfo(total=total, list=[strategy_dict(item) for item in strategies])
