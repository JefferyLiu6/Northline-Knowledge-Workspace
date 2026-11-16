"""Agentic RAG execution interface."""

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from common.auth import require_admin
from common.result import Result
from models import User
from service import agent_service

router = APIRouter(prefix="/agent")


class RunPayload(BaseModel):
    kb_ids: List[int] = []
    query: str = ""
    # Multiple rounds of dialogue, no first round.
    history: List[dict] | None = None


@router.post("/run")
async def run(payload: RunPayload, current_user: User = Depends(require_admin)):
    """Run an Agentic question-answering once, returning the answer, reference sources, and the number of steps taken this time."""
    return Result.success(
        await agent_service.run(
            payload.kb_ids,
            payload.query,
            user_id=current_user.id,
            history=payload.history,
        )
    )


@router.get("/runs")
async def runs(
    run_status: str = "",
    session_id: int | None = None,
    page_num: int = 1,
    page_size: int = 10,
    _: User = Depends(require_admin),
):
    """List of run records."""
    return Result.success(
        await agent_service.select_runs(run_status, session_id, page_num, page_size)
    )


@router.get("/steps/{run_id}")
async def steps(run_id: int, _: User = Depends(require_admin)):
    """Complete timeline of steps for a single run."""
    return Result.success(await agent_service.select_steps(run_id))
