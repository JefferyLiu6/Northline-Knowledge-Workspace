"""Q&A Application Management and Multi-turn Q&A Interface."""

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sse_starlette.sse import EventSourceResponse

from common.auth import get_current_user, require_admin
from common.result import Result
from models import User
from service import chat_service, qa_app_service

router = APIRouter(prefix="/qaApp")


class QaAppPayload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    name: str | None = None
    description: str | None = None
    avatar: str | None = None
    # Mounted knowledge bank, at least one
    kb_ids: List[int] = []
    chat_model_id: int | None = None
    retrieval_strategy_id: int | None = None
    prompt_code: str | None = None
    agent_enabled: str | None = None
    max_history: int | None = None
    empty_answer: str | None = None
    share_enabled: str | None = None
    status: str | None = None


class SessionPayload(BaseModel):
    app_id: int
    # The same interface for management end testing and user-end Questions and Answers, with which the field distinguishes sources
    source: str = "Admin portal"


class AskPayload(BaseModel):
    session_id: int
    question: str = ""


@router.post("/add")
async def add(payload: QaAppPayload, current_user: User = Depends(require_admin)):
    await qa_app_service.add(current_user, payload.model_dump(exclude_unset=True))
    return Result.success()


@router.put("/update")
async def update(payload: QaAppPayload, _: User = Depends(require_admin)):
    await qa_app_service.update(payload.id, payload.model_dump(exclude_unset=True))
    return Result.success()


@router.delete("/delete/{app_id}")
async def delete(app_id: int, _: User = Depends(require_admin)):
    await qa_app_service.delete(app_id)
    return Result.success()


@router.get("/selectById/{app_id}")
async def select_one(app_id: int, _: User = Depends(get_current_user)):
    return Result.success(await qa_app_service.select_by_id(app_id))


@router.get("/selectEnabled")
async def select_enabled(_: User = Depends(get_current_user)):
    """Application list visible to the user side."""
    return Result.success(await qa_app_service.select_enabled())


@router.get("/selectPage")
async def select_page(
    name: str = "",
    status: str = "",
    page_num: int = 1,
    page_size: int = 10,
    _: User = Depends(require_admin),
):
    return Result.success(await qa_app_service.select_page(name, status, page_num, page_size))


@router.post("/session")
async def open_session(payload: SessionPayload, current_user: User = Depends(get_current_user)):
    """Create a session. The frontend calls it before sending the first message to get the session_id."""
    return Result.success(
        await chat_service.open_session(payload.app_id, current_user.id, payload.source)
    )


@router.post("/ask")
async def ask(payload: AskPayload, current_user: User = Depends(get_current_user)):
    """Streaming Q&A.

    The response is an SSE stream instead of a Result, the frontend uses EventSource or fetch to stream read.
    Event types: reference (citation source), progress (status node progress, only for Agentic mode),
    agent (Agent execution overview), delta (text increment), done (end), error (failure).
    """
    # The session attribution check was placed before the streaming, and the ultra vires request was stopped directly by an abnormal processor.
    # No, no, no. Two hundred. Wrong in the stream.
    await chat_service.assert_session_access(payload.session_id, current_user)
    return EventSourceResponse(
        chat_service.stream_chat(payload.session_id, payload.question, current_user.id)
    )


@router.get("/messages/{session_id}")
async def messages(session_id: int, current_user: User = Depends(get_current_user)):
    """The complete message list of a session, including reference sources."""
    await chat_service.assert_session_access(session_id, current_user)
    return Result.success(await chat_service.select_messages(session_id))


@router.delete("/session/{session_id}")
async def delete_session(session_id: int, current_user: User = Depends(get_current_user)):
    """Delete a session.

    Regular users can only delete their own sessions, ownership verification is done in the service and shared with /ask and /messages.
    """
    await chat_service.delete_session(session_id, current_user)
    return Result.success()


@router.get("/mySessions")
async def my_sessions(
    page_num: int = 1,
    page_size: int = 10,
    current_user: User = Depends(get_current_user),
):
    """The session list of the currently logged-in user, used by the user side for the left-side history dialog.

    It uses the same query as the management side's /sessions, the difference is that here
    user_id is taken from the token, the frontend cannot pass others.
    """
    return Result.success(
        await chat_service.select_sessions(None, current_user.id, page_num, page_size)
    )


@router.get("/sessions")
async def sessions(
    app_id: int | None = None,
    page_num: int = 1,
    page_size: int = 10,
    _: User = Depends(require_admin),
):
    """Session List."""
    return Result.success(await chat_service.select_sessions(app_id, None, page_num, page_size))
