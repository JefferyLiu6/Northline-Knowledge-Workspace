"""Knowledge Document Management Interface."""

from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, ConfigDict

from common.auth import get_current_user, require_admin
from common.result import Result
from models import User
from service import document_parse_service, knowledge_document_service

router = APIRouter(prefix="/knowledgeDocument")


class KnowledgeDocumentPayload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # The window may be filled in only part of the field, all allowed for None and must be checked in service.
    id: int | None = None
    kb_id: int | None = None
    name: str | None = None
    file_name: str | None = None
    file_url: str | None = None
    file_size: int | None = None


@router.post("/add")
async def add(payload: KnowledgeDocumentPayload, current_user: User = Depends(require_admin)):
    # Current_user uses it to record uploads, so there's no delineation here.
    await knowledge_document_service.add(current_user, payload.model_dump(exclude_unset=True))
    return Result.success()


@router.put("/update")
async def update(payload: KnowledgeDocumentPayload, _: User = Depends(require_admin)):
    await knowledge_document_service.update(payload.id, payload.model_dump(exclude_unset=True))
    return Result.success()


@router.delete("/delete/{doc_id}")
async def delete(doc_id: int, _: User = Depends(require_admin)):
    await knowledge_document_service.delete(doc_id)
    return Result.success()


@router.delete("/deleteBatch")
async def delete_batch(ids: List[int], _: User = Depends(require_admin)):
    await knowledge_document_service.delete_batch(ids)
    return Result.success()


@router.get("/selectById/{doc_id}")
async def select_one(doc_id: int, _: User = Depends(get_current_user)):
    return Result.success(await knowledge_document_service.select_by_id(doc_id))


@router.post("/parse/{doc_id}")
async def parse(doc_id: int, background_tasks: BackgroundTasks, _: User = Depends(require_admin)):
    """Trigger Document Parsing. The interface only sets the status to parsing and returns, the actual parsing runs in the background."""
    task_id = await document_parse_service.start_parse(doc_id)
    # The function registered atad_task will be executed after the response is sent, and the front does not have to wait for resolution to end
    background_tasks.add_task(document_parse_service.run_parse, doc_id, task_id)
    return Result.success()


@router.get("/parsedText/{doc_id}")
async def parsed_text(doc_id: int, _: User = Depends(require_admin)):
    """View the parsed text for the popup on the page."""
    return Result.success(await document_parse_service.select_parsed_text(doc_id))


@router.get("/tasks/{doc_id}")
async def tasks(doc_id: int, _: User = Depends(require_admin)):
    """Check the processing task record of a document."""
    return Result.success(await document_parse_service.select_tasks(doc_id))


@router.get("/selectPage")
async def select_page(
    kb_id: int | None = None,
    name: str = "",
    parse_status: str = "",
    page_num: int = 1,
    page_size: int = 10,
    _: User = Depends(require_admin),
):
    return Result.success(
        await knowledge_document_service.select_page(kb_id, name, parse_status, page_num, page_size)
    )


@router.post("/retry/{doc_id}")
async def retry(doc_id: int, background_tasks: BackgroundTasks, _: User = Depends(require_admin)):
    from service.job_recovery_service import start_retry
    task_id, stage, function, arguments = await start_retry(doc_id)
    background_tasks.add_task(function, *arguments)
    return Result.success({"task_id": task_id, "task_type": stage})
