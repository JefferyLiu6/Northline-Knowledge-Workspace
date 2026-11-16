"""Evaluation report comparison and traceability interface."""

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from common.auth import require_admin
from common.result import Result
from models import User
from service import eval_report_service

router = APIRouter(prefix="/evalReport")


class ComparePayload(BaseModel):
    # At least two times to compare.
    report_ids: List[int] = []


@router.get("/selectAll")
async def select_all(dataset_id: int | None = None, _: User = Depends(require_admin)):
    """List of reports, including four metrics, overall score, and time taken."""
    return Result.success(await eval_report_service.select_reports(dataset_id))


@router.post("/compare")
async def compare(payload: ComparePayload, _: User = Depends(require_admin)):
    """Assemble several reports into a structure that can be directly used in charts."""
    return Result.success(await eval_report_service.compare(payload.report_ids))

