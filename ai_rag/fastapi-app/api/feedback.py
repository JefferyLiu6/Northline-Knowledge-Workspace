"""Dialogue logs and user feedback interface."""

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from common.auth import get_current_user, require_admin
from common.result import Result
from models import User
from service import feedback_service

router = APIRouter(prefix="/feedback")


class FeedbackPayload(BaseModel):
    message_id: int | None = None
    # ♪ Light up ♪ ♪ Light down ♪
    feedback_type: str = ""
    reason: str | None = None


class MessageIdsPayload(BaseModel):
    message_ids: List[int] = []


@router.post("/submit")
async def submit(payload: FeedbackPayload, current_user: User = Depends(get_current_user)):
    """Submit a like or dislike. Ordinary users can also call it, so use get_current_user."""
    await feedback_service.submit(
        current_user, payload.message_id, payload.feedback_type, payload.reason
    )
    return Result.success()


@router.post("/byMessages")
async def by_messages(payload: MessageIdsPayload, current_user: User = Depends(get_current_user)):
    """Batch cancel feedback, displaying like and dislike counts for each answer on the page."""
    return Result.success(
        await feedback_service.select_by_message(payload.message_ids, current_user.id)
    )


@router.get("/selectPage")
async def select_page(
    feedback_type: str = "",
    converted: str = "",
    page_num: int = 1,
    page_size: int = 10,
    _: User = Depends(require_admin),
):
    """List of feedback, including corresponding questions and answers."""
    return Result.success(
        await feedback_service.select_page(feedback_type, converted, page_num, page_size)
    )


@router.get("/summary")
async def summary(_: User = Depends(require_admin)):
    """Feedback overview."""
    return Result.success(await feedback_service.summary())


@router.get("/sessions")
async def sessions(
    app_id: int | None = None,
    keyword: str = "",
    page_num: int = 1,
    page_size: int = 10,
    _: User = Depends(require_admin),
):
    """List of dialogue logs, including application name and dislike counts."""
    return Result.success(
        await feedback_service.select_sessions_with_app(app_id, keyword, page_num, page_size)
    )
