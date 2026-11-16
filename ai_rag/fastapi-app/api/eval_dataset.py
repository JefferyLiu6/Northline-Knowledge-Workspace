"""Evaluation set and test case interface."""

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from common.auth import require_admin
from common.result import Result
from models import User
from service import eval_dataset_service

router = APIRouter(prefix="/evalDataset")


class DatasetPayload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    name: str | None = None
    kb_id: int | None = None
    description: str | None = None


class CasePayload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    dataset_id: int | None = None
    question: str | None = None
    ground_truth: str | None = None
    reference_chunk_ids: str | None = None
    source: str | None = None
    enabled: str | None = None
    remark: str | None = None


class GeneratePayload(BaseModel):
    dataset_id: int
    document_id: int
    count: int = 5


class ConvertPayload(BaseModel):
    dataset_id: int
    # Not a pass sign of the deposition of all pending dot steppings.
    feedback_ids: List[int] | None = None


@router.post("/add")
async def add_dataset(payload: DatasetPayload, _: User = Depends(require_admin)):
    await eval_dataset_service.add_dataset(payload.model_dump(exclude_unset=True))
    return Result.success()


@router.put("/update")
async def update_dataset(payload: DatasetPayload, _: User = Depends(require_admin)):
    await eval_dataset_service.update_dataset(payload.id, payload.model_dump(exclude_unset=True))
    return Result.success()


@router.delete("/delete/{dataset_id}")
async def delete_dataset(dataset_id: int, _: User = Depends(require_admin)):
    await eval_dataset_service.delete_dataset(dataset_id)
    return Result.success()


@router.get("/selectAll")
async def select_all(_: User = Depends(require_admin)):
    return Result.success(await eval_dataset_service.select_datasets())


@router.get("/selectPage")
async def select_page(name: str = "", page_num: int = 1, page_size: int = 10, _: User = Depends(require_admin)):
    return Result.success(await eval_dataset_service.select_dataset_page(name, page_num, page_size))


@router.post("/case/add")
async def add_case(payload: CasePayload, _: User = Depends(require_admin)):
    await eval_dataset_service.add_case(payload.model_dump(exclude_unset=True))
    return Result.success()


@router.put("/case/update")
async def update_case(payload: CasePayload, _: User = Depends(require_admin)):
    await eval_dataset_service.update_case(payload.id, payload.model_dump(exclude_unset=True))
    return Result.success()


@router.delete("/case/delete/{case_id}")
async def delete_case(case_id: int, _: User = Depends(require_admin)):
    await eval_dataset_service.delete_case(case_id)
    return Result.success()


@router.get("/case/selectPage")
async def select_case_page(
    dataset_id: int | None = None,
    source: str = "",
    keyword: str = "",
    page_num: int = 1,
    page_size: int = 10,
    _: User = Depends(require_admin),
):
    return Result.success(
        await eval_dataset_service.select_case_page(dataset_id, source, keyword, page_num, page_size)
    )


@router.get("/case/referenceChunks/{case_id}")
async def reference_chunks(case_id: int, _: User = Depends(require_admin)):
    """The original text of the source chunk for a test case, used for manual verification against the standard answer."""
    return Result.success(await eval_dataset_service.reference_chunks(case_id))


@router.post("/generate")
async def generate(payload: GeneratePayload, _: User = Depends(require_admin)):
    """Let the model generate question-answer pairs from document chunks."""
    created = await eval_dataset_service.generate_from_document(
        payload.dataset_id, payload.document_id, payload.count
    )
    return Result.success(f"Generated {created} Test Cases")


@router.post("/convert")
async def convert(payload: ConvertPayload, _: User = Depends(require_admin)):
    """Convert a problem that was clicked to a test case, leaving the standard answer blank for manual filling."""
    created = await eval_dataset_service.convert_from_feedback(
        payload.dataset_id, payload.feedback_ids
    )
    return Result.success(f"Accumulated {created} Test Cases, Please Add Standard Answer First to Enable")
