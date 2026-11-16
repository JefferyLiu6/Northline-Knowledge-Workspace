"""Questions and answers apply management business logic."""

import uuid
from typing import List

from common.exception_handler import CustomException
from common.result import PageInfo
from models import KnowledgeBase, QaApp, QaAppKb, User

STATUSES = {"Active", "Disabled"}
YES_NO = {"Yes", "No"}
# By default, use it when the manager doesn't fill it out.
DEFAULT_EMPTY_ANSWER = "No relevant content was found in the knowledge base."


async def app_dict(app: QaApp, with_kbs: bool = False) -> dict:
    data = {
        "id": app.id,
        "name": app.name,
        "app_code": app.app_code,
        "description": app.description,
        "avatar": app.avatar,
        "chat_model_id": app.chat_model_id,
        "retrieval_strategy_id": app.retrieval_strategy_id,
        "prompt_code": app.prompt_code,
        "agent_enabled": app.agent_enabled,
        "max_history": app.max_history,
        "empty_answer": app.empty_answer,
        "share_enabled": app.share_enabled,
        "status": app.status,
        "create_time": app.create_time,
        "update_time": app.update_time,
    }
    if with_kbs:
        relations = await QaAppKb.filter(app_id=app.id)
        kb_ids = [item.kb_id for item in relations]
        data["kb_ids"] = kb_ids
        bases = await KnowledgeBase.filter(id__in=kb_ids)
        # List page shows which library names are hanging
        data["kb_names"] = [kb.name for kb in bases]
    return data


def _validate(payload: dict) -> None:
    if not payload.get("name"):
        raise CustomException("Please enter the application name")
    if not payload.get("kb_ids"):
        raise CustomException("Please mount at least one knowledge base")
    if payload.get("agent_enabled") not in {None} | YES_NO:
        raise CustomException("Agent Switching Values can only be yes or no")
    status = payload.get("status")
    if status is not None and status not in STATUSES:
        raise CustomException("State parameter error")
    max_history = payload.get("max_history")
    if max_history is not None and not 0 <= max_history <= 20:
        raise CustomException("Historical message bar values range from 0 to 20")


async def _bind_knowledge_bases(app_id: int, kb_ids: List[int]) -> None:
    """Re-establish the relevance of applications and knowledge bases.

    The deletions are inserted first, and are simpler than the article-by-article additions to each other, and there is no separate business field in the linkage table.
    """
    await QaAppKb.filter(app_id=app_id).delete()
    for kb_id in kb_ids:
        await QaAppKb.create(app_id=app_id, kb_id=kb_id)


async def add(current_user: User, payload: dict) -> None:
    _validate(payload)
    if await QaApp.get_or_none(name=payload["name"]):
        raise CustomException("Apply name repeat")
    app = await QaApp.create(
        name=payload["name"],
        # Code used to share links, automatically generate, and the administrator doesn't care.
        app_code=uuid.uuid4().hex[:16],
        description=payload.get("description"),
        avatar=payload.get("avatar"),
        chat_model_id=payload.get("chat_model_id"),
        retrieval_strategy_id=payload.get("retrieval_strategy_id"),
        prompt_code=payload.get("prompt_code") or "RAG_ANSWER",
        agent_enabled=payload.get("agent_enabled") or "No",
        max_history=payload.get("max_history") if payload.get("max_history") is not None else 6,
        empty_answer=payload.get("empty_answer") or DEFAULT_EMPTY_ANSWER,
        share_enabled=payload.get("share_enabled") or "No",
        status=payload.get("status") or "Active",
        create_user_id=current_user.id,
    )
    await _bind_knowledge_bases(app.id, payload["kb_ids"])


async def update(app_id: int | None, payload: dict) -> None:
    if app_id is None:
        raise CustomException("Application ID cannot be empty")
    if await QaApp.get_or_none(id=app_id) is None:
        raise CustomException("Q&A app not found")
    _validate(payload)
    if await QaApp.filter(name=payload["name"]).exclude(id=app_id).exists():
        raise CustomException("Apply name repeat")
    await QaApp.filter(id=app_id).update(
        name=payload["name"],
        description=payload.get("description"),
        avatar=payload.get("avatar"),
        chat_model_id=payload.get("chat_model_id"),
        retrieval_strategy_id=payload.get("retrieval_strategy_id"),
        prompt_code=payload.get("prompt_code") or "RAG_ANSWER",
        agent_enabled=payload.get("agent_enabled") or "No",
        max_history=payload.get("max_history") if payload.get("max_history") is not None else 6,
        empty_answer=payload.get("empty_answer") or DEFAULT_EMPTY_ANSWER,
        share_enabled=payload.get("share_enabled") or "No",
        status=payload.get("status") or "Active",
    )
    await _bind_knowledge_bases(app_id, payload["kb_ids"])


async def delete(app_id: int) -> None:
    app = await QaApp.get_or_none(id=app_id)
    if app is None:
        raise CustomException("Q&A app not found")
    # And then we'll delete the link sheet. No orphans.
    await QaAppKb.filter(app_id=app_id).delete()
    await QaApp.filter(id=app_id).delete()


async def select_by_id(app_id: int) -> dict:
    app = await QaApp.get_or_none(id=app_id)
    if app is None:
        raise CustomException("Q&A app not found")
    return await app_dict(app, with_kbs=True)


async def select_by_code(app_code: str) -> dict:
    """Take the application by sharing code and use it on the user-end question and answer page."""
    app = await QaApp.get_or_none(app_code=app_code)
    if app is None:
        raise CustomException("Q&A app not found")
    if app.status != "Active":
        raise CustomException("This application has been disabled")
    return await app_dict(app, with_kbs=True)


async def select_enabled() -> List[dict]:
    """The application list that the user can see is only returned to normal status."""
    apps = await QaApp.filter(status="Active").order_by("-id")
    return [
        {
            "id": app.id,
            "name": app.name,
            "app_code": app.app_code,
            "description": app.description,
            "avatar": app.avatar,
            "agent_enabled": app.agent_enabled,
        }
        for app in apps
    ]


async def select_page(name: str = "", status: str = "", page_num: int = 1, page_size: int = 10) -> PageInfo:
    query = QaApp.filter(name__contains=name)
    if status:
        query = query.filter(status=status)
    apps = await query.order_by("-id").offset((page_num - 1) * page_size).limit(page_size)
    total = await query.count()
    return PageInfo(total=total, list=[await app_dict(app, with_kbs=True) for app in apps])
