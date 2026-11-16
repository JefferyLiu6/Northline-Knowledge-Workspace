"""Batch evaluation.

Run through all cases in the evaluation set, then calculate the four metrics using LLM-as-judge, and summarize into a report.

The complete process for a single case:

    Strategy retrieval → Answer generation → Calculate four metrics → Record in eval_case_result

When you run, average the fractions of all cases and store them with a strategic snapshot in the eval_report.
Chapter 29 contains a cross-cutting comparison of multiple reports.
"""

import json
import uuid

from ai import evaluator, model_factory, prompt_loader
from ai.graph import build_context
from common.exception_handler import CustomException
from common.result import PageInfo
from common.times import cost_millis, now
from models import (
    EvalCase,
    EvalCaseResult,
    EvalDataset,
    EvalReport,
    EvalTask,
    RetrievalStrategy,
)
from service import retrieval_service

ERROR_MAX_LENGTH = 500
# Complete definition of the four indicators: what to measure, which to measure, how much to meet, and which to lower.
# This is read in both the concluding text and the indicator card on the page, without a separate set of thresholds and illustrations at the front end.
#
# Stage puts the indicator on two paragraphs of RAG: The search section is responsible for "finding out what you need."
# The generation section is responsible for "writing answers based on information". When the score is low, it depends on which part it belongs.
# I'm not sure if it's the right thing to do.
METRICS = [
    {
        "field": "context_recall",
        "label": "Context recall",
        "en": "Context Recall",
        "stage": "Get the information.",
        # The page card shows this directly, and the learner knows what he's doing without remembering his indicator name.
        "plain": "Did you find out what the standard answer says?",
        "threshold": 0.7,
        "advice": "The information we're looking for is not back. We suggest a hybrid search or rewrite.",
    },
    {
        "field": "context_precision",
        "label": "Context precision",
        "en": "Context Precision",
        "stage": "Get the information.",
        "plain": "In the files we found, is it useful to be in front?",
        "threshold": 0.6,
        "advice": "Useful information is in the back. It's recommended to reschedule.",
    },
    {
        "field": "faithfulness",
        "label": "Faithfulness",
        "en": "Faithfulness",
        "stage": "Write the answer.",
        "plain": "Every word in the answer. Any source in the file?",
        "threshold": 0.8,
        "advice": "There's no source in the answer. It's suggested to tighten restrictions on RAG_ANSWER templates.",
    },
    {
        "field": "answer_relevancy",
        "label": "Answer relevance",
        "en": "Answer Relevancy",
        "stage": "Write the answer.",
        "plain": "Is the answer to that question?",
        "threshold": 0.7,
        "advice": "The answer is no question. It's suggested to adjust the generation of Prompt",
    },
]
# The maximum number of strips is measured at a time. Chapter 26 states that the costs are mainly in input token, and that the cost of the evaluation is estimated to be more than one token.
# 20 are already hundreds of thousands of tokens in size, and the default is here.
MAX_CASE_COUNT = 20


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


async def start(
    dataset_id: int,
    strategy_id: int | None,
    user_id: int | None,
    prompt_code: str = "RAG_ANSWER",
) -> tuple[int, dict]:
    """Verifying tasks."""
    dataset = await EvalDataset.get_or_none(id=dataset_id)
    if dataset is None:
        raise CustomException("Evaluation dataset not found")
    cases = await EvalCase.filter(dataset_id=dataset_id, enabled="Yes")
    if not cases:
        raise CustomException("For those examples that are not used in this evaluation, please supplement the standard answers and enable them")
    if len(cases) > MAX_CASE_COUNT:
        raise CustomException(
            f"Run at most {MAX_CASE_COUNT} cases per evaluation. This dataset has {len(cases)} enabled cases. "
            "Please disable some of them or break them into more than one evaluation."
        )
    strategy = await retrieval_service.load_strategy(strategy_id)
    # The referee model and the question-and-answer model are configured with the same dialogue model, first to confirm its usefulness
    judge_config = await model_factory.load_enabled(model_factory.CHAT)
    task = await EvalTask.create(
        task_no=uuid.uuid4().hex,
        dataset_id=dataset_id,
        retrieval_strategy_id=strategy["id"],
        # It's a week after the report. It makes sense to know which switches were turned on.
        strategy_snapshot=_dump(strategy),
        judge_model_id=judge_config.id,
        task_status="Evaluating",
        total_count=len(cases),
        start_time=now(),
        create_user_id=user_id,
    )
    return task.id, {"strategy": strategy, "prompt_code": prompt_code}


async def run(task_id: int, context: dict) -> None:
    """Back-office tasks: running questions and answers on a rule-by-article basis, with scores."""
    task = await EvalTask.get_or_none(id=task_id)
    if task is None:
        return
    started = now()
    strategy = context["strategy"]
    prompt_code = context["prompt_code"]
    success = 0
    failed = 0
    try:
        dataset = await EvalDataset.get_or_none(id=task.dataset_id)
        cases = await EvalCase.filter(dataset_id=task.dataset_id, enabled="Yes").order_by("id")
        kb_ids = [dataset.kb_id] if dataset and dataset.kb_id else []
        if not kb_ids:
            raise CustomException("There is no associated knowledge base for the evaluation set. Set it up on the assessment first")

        for case in cases:
            case_started = now()
            try:
                outcome = await retrieval_service.retrieve(kb_ids, case.question, strategy)
                results = outcome["results"]
                contents = [item["content"] for item in results]
                retrieved_ids = [item["chunk_id"] for item in results if item.get("chunk_id")]

                answer = await _generate(prompt_code, contents, case.question)
                reference_ids = _parse_ids(case.reference_chunk_ids)
                scores = await evaluator.evaluate_case(
                    case.question,
                    case.ground_truth or "",
                    answer,
                    contents,
                    retrieved_ids,
                    reference_ids,
                )
                await EvalCaseResult.create(
                    task_id=task_id,
                    case_id=case.id,
                    answer=answer,
                    retrieved_chunk_ids=",".join(str(item) for item in retrieved_ids),
                    cost_millis=cost_millis(case_started),
                    **scores,
                )
                success += 1
            except Exception as exc:
                # The single failure does not affect the whole batch. Keep running down on this result.
                message = exc.message if isinstance(exc, CustomException) else str(exc)
                await EvalCaseResult.create(
                    task_id=task_id,
                    case_id=case.id,
                    error_message=message[:ERROR_MAX_LENGTH],
                    cost_millis=cost_millis(case_started),
                )
                failed += 1
            # Once each one runs up to update, you can see where it's going.
            await EvalTask.filter(id=task_id).update(success_count=success, fail_count=failed)

        await _build_report(task_id, strategy)
        await EvalTask.filter(id=task_id).update(
            task_status="Completed" if failed == 0 else "Failed",
            success_count=success,
            fail_count=failed,
            end_time=now(),
            cost_millis=cost_millis(started),
        )
    except Exception as exc:
        message = exc.message if isinstance(exc, CustomException) else f"Evaluation failed:{exc}"
        await EvalTask.filter(id=task_id).update(
            task_status="Failed",
            success_count=success,
            fail_count=failed,
            error_message=message[:ERROR_MAX_LENGTH],
            end_time=now(),
            cost_millis=cost_millis(started),
        )


def _parse_ids(raw: str | None) -> list[int]:
    if not raw:
        return []
    ids = []
    for item in raw.split(","):
        item = item.strip()
        if item.isdigit():
            ids.append(int(item))
    return ids


async def _generate(prompt_code: str, contents: list[str], question: str) -> str:
    """The answer is generated by the evaluated Prompt."""
    prompt = await prompt_loader.render(
        prompt_code,
        context=build_context([{"content": item} for item in contents]),
        question=question,
    )
    config = await model_factory.load_enabled(model_factory.CHAT)
    model = model_factory.build_chat_model(config)
    reply = await model.ainvoke(prompt, max_tokens=768)
    return str(reply.content).strip()


def _average(values: list) -> float | None:
    """Counts average points. One success is never returned to the void, and none of it returns 0 leads to misunderstanding."""
    numbers = [float(item) for item in values if item is not None]
    if not numbers:
        return None
    return round(sum(numbers) / len(numbers), 4)


async def _build_report(task_id: int, strategy: dict) -> None:
    """The results of the mission, where applicable, are consolidated in a single report."""
    results = await EvalCaseResult.filter(task_id=task_id, error_message=None)
    recall = _average([item.context_recall for item in results])
    precision = _average([item.context_precision for item in results])
    faithful = _average([item.faithfulness for item in results])
    relevancy = _average([item.answer_relevancy for item in results])
    overall = _average([value for value in (recall, precision, faithful, relevancy) if value is not None])
    await EvalReport.create(
        report_no=uuid.uuid4().hex,
        task_id=task_id,
        strategy_name=strategy["name"],
        strategy_snapshot=_dump(strategy),
        case_count=len(results),
        context_recall_avg=recall,
        context_precision_avg=precision,
        faithfulness_avg=faithful,
        answer_relevancy_avg=relevancy,
        overall_score=overall,
        conclusion=_conclusion(recall, precision, faithful, relevancy),
    )


def _conclusion(recall, precision, faithful, relevancy) -> str:
    """The low-scoring indicator is translated into which ring to adjust, as per the cross-check table in chapter 26."""
    values = {
        "context_recall": recall,
        "context_precision": precision,
        "faithfulness": faithful,
        "answer_relevancy": relevancy,
    }
    advices = [
        f"{item['label']}Low,{item['advice']}"
        for item in METRICS
        if values[item["field"]] is not None and values[item["field"]] < item["threshold"]
    ]
    if not advices:
        return "All four indicators are within reasonable range."
    return "; ".join(advices) + "."


def metric_cards(report) -> list[dict]:
    """Data for four indicator cards on the page.

    The indicators note, the line of achievement and the low-time recommendations were drawn from METRICS, which was the same source as the text of the conclusions.
    On that basis, the lower mark was reded and there was no need to determine how low it was or to write a separate note.
    """
    cards = []
    for item in METRICS:
        raw = getattr(report, f"{item['field']}_avg", None)
        value = float(raw) if raw is not None else None
        cards.append(
            {
                **item,
                "value": value,
                # If you don't get the score, you don't get it.
                "ok": None if value is None else value >= item["threshold"],
            }
        )
    return cards


async def select_tasks(dataset_id: int | None = None, page_num: int = 1, page_size: int = 10) -> PageInfo:
    query = EvalTask.all()
    if dataset_id:
        query = query.filter(dataset_id=dataset_id)
    tasks = await query.order_by("-id").offset((page_num - 1) * page_size).limit(page_size)
    total = await query.count()
    # On the list, show "What's this evaluation about? What strategy is it about?"
    # And on the list, we're going to show "What's this review about? What's the strategy?"
    datasets = await EvalDataset.filter(id__in=[item.dataset_id for item in tasks])
    dataset_names = {item.id: item.name for item in datasets}
    # The strategy name is taken from the mission's own strategy_snapshot and not from the report:
    # The report is produced only after it has run out.
    # And Snapshot wrote it all the way to the end when he was on a mission.
    strategy_names = {}
    for item in tasks:
        try:
            strategy_names[item.id] = json.loads(item.strategy_snapshot or "{}").get("name")
        except json.JSONDecodeError:
            strategy_names[item.id] = None
    return PageInfo(
        total=total,
        list=[
            {
                "id": item.id,
                "task_no": item.task_no,
                "dataset_id": item.dataset_id,
                "dataset_name": dataset_names.get(item.dataset_id),
                "strategy_name": strategy_names.get(item.id),
                "retrieval_strategy_id": item.retrieval_strategy_id,
                "task_status": item.task_status,
                "total_count": item.total_count,
                "success_count": item.success_count,
                "fail_count": item.fail_count,
                "error_message": item.error_message,
                "cost_millis": item.cost_millis,
                "create_time": item.create_time,
            }
            for item in tasks
        ],
    )


async def delete(task_id: int) -> None:
    """Delete one evaluation task, along with its case-by-case findings and reports.

    The three tables are a complete record of an evaluation, leaving any single one of the orphan data that will become irrelevant:
    The report was empty without the task and no one knew who had run.
    """
    task = await EvalTask.get_or_none(id=task_id)
    if task is None:
        raise CustomException("Evaluation task not found")
    if task.task_status == "Evaluating":
        raise CustomException("This evaluation's still running. We'll delete it when it's over.")
    await EvalCaseResult.filter(task_id=task_id).delete()
    await EvalReport.filter(task_id=task_id).delete()
    await EvalTask.filter(id=task_id).delete()


async def select_results(task_id: int) -> dict:
    """The detailed results of a single evaluation include four indicators per case."""
    task = await EvalTask.get_or_none(id=task_id)
    if task is None:
        raise CustomException("Evaluation task not found")
    report = await EvalReport.get_or_none(task_id=task_id)
    dataset = await EvalDataset.get_or_none(id=task.dataset_id)
    dataset_name = dataset.name if dataset else None
    results = await EvalCaseResult.filter(task_id=task_id).order_by("id")
    case_ids = [item.case_id for item in results]
    cases = await EvalCase.filter(id__in=case_ids)
    case_map = {case.id: case for case in cases}
    return {
        "task": {
            "id": task.id,
            "task_status": task.task_status,
            "total_count": task.total_count,
            "success_count": task.success_count,
            "fail_count": task.fail_count,
            "cost_millis": task.cost_millis,
            "strategy_snapshot": task.strategy_snapshot,
        },
        "report": {
            "strategy_name": report.strategy_name,
            # The title of the report is to spell out what this evaluation is, or the reports will not be divided together.
            "dataset_name": dataset_name,
            "case_count": report.case_count,
            "context_recall_avg": float(report.context_recall_avg) if report.context_recall_avg is not None else None,
            "context_precision_avg": float(report.context_precision_avg) if report.context_precision_avg is not None else None,
            "faithfulness_avg": float(report.faithfulness_avg) if report.faithfulness_avg is not None else None,
            "answer_relevancy_avg": float(report.answer_relevancy_avg) if report.answer_relevancy_avg is not None else None,
            "overall_score": float(report.overall_score) if report.overall_score is not None else None,
            "conclusion": report.conclusion,
            # Every card with a line and a standard, the page doesn't have to judge how low it is.
            "metrics": metric_cards(report),
        }
        if report
        else None,
        "results": [
            {
                "id": item.id,
                "case_id": item.case_id,
                "question": case_map[item.case_id].question if item.case_id in case_map else "",
                "ground_truth": case_map[item.case_id].ground_truth if item.case_id in case_map else "",
                "answer": item.answer,
                "context_recall": float(item.context_recall) if item.context_recall is not None else None,
                "context_precision": float(item.context_precision) if item.context_precision is not None else None,
                "faithfulness": float(item.faithfulness) if item.faithfulness is not None else None,
                "answer_relevancy": float(item.answer_relevancy) if item.answer_relevancy is not None else None,
                "avg_score": float(item.avg_score) if item.avg_score is not None else None,
                "error_message": item.error_message,
                "cost_millis": item.cost_millis,
            }
            for item in results
        ],
    }
