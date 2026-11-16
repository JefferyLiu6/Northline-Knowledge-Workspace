"""Knowledge Base Management Interface."""

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from common.auth import get_current_user, require_admin
from common.result import Result
from models import User
from service import knowledge_base_service

router = APIRouter(prefix="/knowledgeBase")


class KnowledgeBasePayload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # The window may be filled in only part of the field, all allowed for None and must be checked in service.
    id: int | None = None
    name: str | None = None
    description: str | None = None
    status: str | None = None


@router.post("/add")
async def add(payload: KnowledgeBasePayload, current_user: User = Depends(require_admin)):
    # Current_user will be used to record the creator, so it's not underlined here.
    await knowledge_base_service.add(current_user, payload.model_dump(exclude_unset=True))
    return Result.success()


@router.put("/update")
async def update(payload: KnowledgeBasePayload, _: User = Depends(require_admin)):
    # The fields of document numbers, fragments, binding models are not maintained by this interface and only three can be changed in the window are updated
    await knowledge_base_service.update(payload.id, payload.model_dump(exclude_unset=True))
    return Result.success()


@router.delete("/delete/{kb_id}")
async def delete(kb_id: int, _: User = Depends(require_admin)):
    await knowledge_base_service.delete(kb_id)
    return Result.success()


@router.delete("/deleteBatch")
async def delete_batch(ids: List[int], _: User = Depends(require_admin)):
    await knowledge_base_service.delete_batch(ids)
    return Result.success()


@router.get("/selectById/{kb_id}")
async def select_one(kb_id: int, _: User = Depends(get_current_user)):
    return Result.success(await knowledge_base_service.select_by_id(kb_id))


@router.get("/selectAll")
async def select_all(_: User = Depends(get_current_user)):
    # For the bottom frame of the knowledge base for chapter 06 document management page
    return Result.success(await knowledge_base_service.select_all())


@router.get("/selectPage")
async def select_page(
    name: str = "",
    status: str = "",
    page_num: int = 1,
    page_size: int = 10,
    # The knowledge base is a management end asset and the list page requires administrator identity
    _: User = Depends(require_admin),
):
    return Result.success(await knowledge_base_service.select_page(name, status, page_num, page_size))
