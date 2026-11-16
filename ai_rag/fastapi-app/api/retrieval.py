"""Search Interface."""

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from common.auth import require_admin
from common.result import Result
from models import User
from service import retrieval_service

router = APIRouter(prefix="/retrieval")


class SearchPayload(BaseModel):
    # On which knowledge base to search, select at least one page
    kb_ids: List[int] = []
    # Which search policy to use, default strategy when not transmitting
    strategy_id: int | None = None
    # Restricted to search only in a few documents, without sending the entire knowledge base
    document_ids: List[int] | None = None
    query: str = ""
    # The last few rounds of dialogue point to the way that this is done and it's used to fill up the current problem.
    history: List[dict] | None = None


@router.post("/search")
async def search(payload: SearchPayload, _: User = Depends(require_admin)):
    """Execute a search according to the specified strategy, return results, time consumption at each stage and total time consumption."""
    return Result.success(
        await retrieval_service.retrieve_by_strategy(
            payload.kb_ids,
            payload.query,
            payload.strategy_id,
            payload.document_ids,
            payload.history,
        )
    )


@router.get("/strategies")
async def strategies(_: User = Depends(require_admin)):
    """Dropdown data for search strategy."""
    from models import RetrievalStrategy

    items = await RetrievalStrategy.all().order_by("-is_default", "id")
    return Result.success([retrieval_service.strategy_dict(item) for item in items])


@router.get("/knowledgeBases")
async def knowledge_bases(_: User = Depends(require_admin)):
    """Dropdown data for the knowledge base on the search test page, with fragment count."""
    return Result.success(await retrieval_service.kb_options_with_chunks())
