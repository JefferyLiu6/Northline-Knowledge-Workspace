"""Evaluation report comparison and traceability status.

The comparison table required in Chapter 26 is generated here: multiple reports side by side, four metrics plus time.
"""

import json

from common.exception_handler import CustomException
from models import EvalDataset, EvalReport, EvalTask

# Metric keys and display labels shared by the report and chart
METRICS = [
    ("context_recall_avg", "Context recall"),
    ("context_precision_avg", "Context precision"),
    ("faithfulness_avg", "Faithfulness"),
    ("answer_relevancy_avg", "Answer relevance"),
]


def _float(value) -> float | None:
    return float(value) if value is not None else None


def _enabled_abilities(snapshot: str | None) -> list[str]:
    """Read the steps enabled in the strategy snapshot, and use it to label each bar on the chart."""
    if not snapshot:
        return []
    try:
        strategy = json.loads(snapshot)
    except json.JSONDecodeError:
        return []
    abilities = []
    if strategy.get("vector_enabled") == "Yes":
        abilities.append("Vector")
    if strategy.get("bm25_enabled") == "Yes":
        abilities.append("BM25")
    if strategy.get("rerank_enabled") == "Yes":
        abilities.append("Rerank")
    if strategy.get("query_rewrite_enabled") == "Yes":
        abilities.append(strategy.get("rewrite_type") or "Rewrite")
    if strategy.get("parent_recall_enabled") == "Yes":
        abilities.append("Parent chunk expansion")
    return abilities


async def select_reports(dataset_id: int | None = None, limit: int = 20) -> list[dict]:
    """Report list. Reports under the same evaluation set are comparable, so support filtering by evaluation set."""
    tasks_query = EvalTask.all()
    if dataset_id:
        tasks_query = tasks_query.filter(dataset_id=dataset_id)
    tasks = await tasks_query.order_by("-id").limit(limit)
    task_map = {task.id: task for task in tasks}
    if not task_map:
        return []
    reports = await EvalReport.filter(task_id__in=list(task_map.keys())).order_by("-id")
    return [
        {
            "id": report.id,
            "task_id": report.task_id,
            "dataset_id": task_map[report.task_id].dataset_id,
            "strategy_name": report.strategy_name,
            "abilities": _enabled_abilities(report.strategy_snapshot),
            "case_count": report.case_count,
            "context_recall_avg": _float(report.context_recall_avg),
            "context_precision_avg": _float(report.context_precision_avg),
            "faithfulness_avg": _float(report.faithfulness_avg),
            "answer_relevancy_avg": _float(report.answer_relevancy_avg),
            "overall_score": _float(report.overall_score),
            # Time-consuming task. Chapter 26 says it has to be in the comparison table.
            "cost_millis": task_map[report.task_id].cost_millis,
            "avg_cost_millis": round(task_map[report.task_id].cost_millis / report.case_count)
            if task_map[report.task_id].cost_millis and report.case_count
            else None,
            "conclusion": report.conclusion,
            "create_time": report.create_time,
        }
        for report in reports
    ]


async def compare(report_ids: list[int]) -> dict:
    """Assemble several reports into a structure that can be directly used in charts.

    Reports under the same evaluation set are comparable—different cases mean scores cannot be compared.
    """
    if len(report_ids) < 2:
        raise CustomException("Please select at least two reports for comparison.")
    reports = await EvalReport.filter(id__in=report_ids)
    if len(reports) != len(report_ids):
        raise CustomException("Some reports do not exist; please refresh and retry.")
    tasks = await EvalTask.filter(id__in=[report.task_id for report in reports])
    task_map = {task.id: task for task in tasks}
    dataset_ids = {task_map[report.task_id].dataset_id for report in reports}
    if len(dataset_ids) > 1:
        raise CustomException("Only reports under the same evaluation set can be compared; different evaluation sets have different cases, so scores are not comparable.")

    # Listed in order of report ID, the order of the top rows on the page is consistent with the order of user selection
    ordered = sorted(reports, key=lambda item: report_ids.index(item.id))
    columns = [
        {
            "report_id": report.id,
            "strategy_name": report.strategy_name,
            "abilities": _enabled_abilities(report.strategy_snapshot),
            "case_count": report.case_count,
            "overall_score": _float(report.overall_score),
            "cost_millis": task_map[report.task_id].cost_millis,
            "conclusion": report.conclusion,
        }
        for report in ordered
    ]
    # Lines of each indicator, the scores in each report are lined up and the page is rendered directly into a column chart.
    series = []
    for field, label in METRICS:
        series.append(
            {
                "metric": label,
                "field": field,
                "values": [_float(getattr(report, field)) for report in ordered],
            }
        )
    dataset = await EvalDataset.get_or_none(id=list(dataset_ids)[0])
    return {
        "dataset_name": dataset.name if dataset else None,
        "columns": columns,
        "series": series,
    }
