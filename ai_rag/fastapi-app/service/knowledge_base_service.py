"""The knowledge base manages business logic."""

from typing import List

from common.exception_handler import CustomException
from common.result import PageInfo
from models import KnowledgeBase, User

# The knowledge base has only normal and deactivated status, and the inactive library does not participate in question-and-answer searches
STATUSES = {"Active", "Disabled"}


def knowledge_base_dict(kb: KnowledgeBase) -> dict:
    # Each column of the table is taken from this field.
    return {
        "id": kb.id,
        "name": kb.name,
        "description": kb.description,
        "embedding_model_id": kb.embedding_model_id,
        "chunk_strategy_id": kb.chunk_strategy_id,
        "document_count": kb.document_count,
        "chunk_count": kb.chunk_count,
        "status": kb.status,
        "create_user_id": kb.create_user_id,
        "create_time": kb.create_time,
        "update_time": kb.update_time,
    }


async def add(current_user: User, payload: dict) -> None:
    name = payload.get("name")
    if not name:
        raise CustomException("Please enter the name of the knowledge base")
    # The same name knowledge base will allow the administrator to select a wrong library when uploading the document.
    if await KnowledgeBase.get_or_none(name=name):
        raise CustomException("Replication of knowledge bank names")
    status = payload.get("status") or "Active"
    if status not in STATUSES:
        raise CustomException("State parameter error")
    await KnowledgeBase.create(
        name=name,
        description=payload.get("description"),
        status=status,
        # Record creator, list page displays "who built it" and facilitates subsequent screening by person
        create_user_id=current_user.id,
    )


async def update(kb_id: int | None, payload: dict) -> None:
    if kb_id is None:
        raise CustomException("The knowledge base ID cannot be empty")
    kb = await KnowledgeBase.get_or_none(id=kb_id)
    if kb is None:
        raise CustomException("Knowledge base not found")
    name = payload.get("name")
    if not name:
        raise CustomException("Please enter the name of the knowledge base")
    # If you change your name, you'll be stopped by yourself.
    duplicated = await KnowledgeBase.filter(name=name).exclude(id=kb_id).exists()
    if duplicated:
        raise CustomException("Replication of knowledge bank names")
    status = payload.get("status") or kb.status
    if status not in STATUSES:
        raise CustomException("State parameter error")
    await KnowledgeBase.filter(id=kb_id).update(
        name=name,
        description=payload.get("description"),
        status=status,
    )


async def delete(kb_id: int) -> None:
    kb = await KnowledgeBase.get_or_none(id=kb_id)
    if kb is None:
        raise CustomException("Knowledge base not found")
    # The library also contains files that are not allowed to be deleted, so that the files and segments do not turn into orphan data that cannot be attributed.
    if kb.document_count > 0:
        raise CustomException("There are documents under this knowledge base, please delete them first")
    await KnowledgeBase.filter(id=kb_id).delete()


async def delete_batch(ids: List[int]) -> None:
    # As long as there's a library with the file on it, the whole batch will not be deleted.
    blocked = await KnowledgeBase.filter(id__in=ids, document_count__gt=0).first()
    if blocked is not None:
        raise CustomException(f"Knowledge base[{blocked.name}]still has documents, please delete the documents first")
    await KnowledgeBase.filter(id__in=ids).delete()


async def select_by_id(kb_id: int) -> dict:
    kb = await KnowledgeBase.get_or_none(id=kb_id)
    if kb is None:
        raise CustomException("Knowledge base not found")
    return knowledge_base_dict(kb)


async def select_all() -> List[dict]:
    # For chapter 06 document management pages to be used as a knowledge base bottom frame, only return to the normal state library
    bases = await KnowledgeBase.filter(status="Active").order_by("-id")
    return [knowledge_base_dict(kb) for kb in bases]


async def select_page(name: str = "", status: str = "", page_num: int = 1, page_size: int = 10) -> PageInfo:
    # Name From the top name input box, empty string equals without this condition
    query = KnowledgeBase.filter(name__contains=name)
    # status from state frame, select the exact match
    if status:
        query = query.filter(status=status)
    bases = await query.order_by("-id").offset((page_num - 1) * page_size).limit(page_size)
    total = await query.count()
    return PageInfo(total=total, list=[knowledge_base_dict(kb) for kb in bases])
