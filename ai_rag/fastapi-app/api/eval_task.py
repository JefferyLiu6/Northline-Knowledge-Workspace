"""Batch evaluation interface."""

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel

from common.auth import require_admin
from common.result import Result
from models import User
from service import eval_task_service

router = APIRouter(prefix="/evalTask")


class StartPayload(BaseModel):
    dataset_id: int
    # Which search strategy to evaluate, default when not transmitting
    strategy_id: int | None = None
    # The measured generation Prompt, a template to run again will compare the effects of Propt
    prompt_code: str = "RAG_ANSWER"


@router.post("/start")
async def start(
    payload: StartPayload,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin),
):
    """Trigger a batch evaluation. The interface only creates the task and returns, with the actual evaluation running in the background."""
    task_id, context = await eval_task_service.start(
        payload.dataset_id, payload.strategy_id, current_user.id, payload.prompt_code
    )
    background_tasks.add_task(eval_task_service.run, task_id, context)
    return Result.success("Evaluation has started, refresh later to view results")


@router.get("/selectPage")
async def select_page(
    dataset_id: int | None = None,
    page_num: int = 1,
    page_size: int = 10,
    _: User = Depends(require_admin),
):
    """List of evaluation tasks."""
    return Result.success(await eval_task_service.select_tasks(dataset_id, page_num, page_size))


@router.delete("/delete/{task_id}")
async def delete(task_id: int, _: User = Depends(require_admin)):
    """Delete an evaluation task, along with the test case results and reports."""
    await eval_task_service.delete(task_id)
    return Result.success()


@router.get("/results/{task_id}")
async def results(task_id: int, _: User = Depends(require_admin)):
    """Detailed results and summary report for an evaluation."""
    return Result.success(await eval_task_service.select_results(task_id))
