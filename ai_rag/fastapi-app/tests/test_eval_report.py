"""Evaluation report comparison and link tracking status testing."""

import json
import uuid

import pytest

from models import EvalDataset, EvalReport, EvalTask
from service import eval_report_service


def _snapshot(**overrides):
    strategy = {
        "vector_enabled": "Yes",
        "bm25_enabled": "No",
        "rerank_enabled": "No",
        "query_rewrite_enabled": "No",
        "rewrite_type": None,
        "parent_recall_enabled": "No",
    }
    strategy.update(overrides)
    return json.dumps(strategy, ensure_ascii=False)


@pytest.fixture()
async def reports(db):
    """Create an assessment collection, two missions and two reports."""
    dataset = await EvalDataset.create(name="Comparison test set-unit testing")
    other = await EvalDataset.create(name="Another test set-module test is special for")
    task_one = await EvalTask.create(
        task_no=uuid.uuid4().hex, dataset_id=dataset.id, task_status="Completed", cost_millis=6000
    )
    task_two = await EvalTask.create(
        task_no=uuid.uuid4().hex, dataset_id=dataset.id, task_status="Completed", cost_millis=15000
    )
    task_other = await EvalTask.create(
        task_no=uuid.uuid4().hex, dataset_id=other.id, task_status="Completed", cost_millis=5000
    )
    report_one = await EvalReport.create(
        report_no=uuid.uuid4().hex,
        task_id=task_one.id,
        strategy_name="Baseline - Vector search only",
        strategy_snapshot=_snapshot(),
        case_count=5,
        context_recall_avg=0.62,
        context_precision_avg=0.44,
        faithfulness_avg=0.81,
        answer_relevancy_avg=0.88,
        overall_score=0.6875,
    )
    report_two = await EvalReport.create(
        report_no=uuid.uuid4().hex,
        task_id=task_two.id,
        strategy_name="Full - Hybrid search with reranking and rewriting",
        strategy_snapshot=_snapshot(
            bm25_enabled="Yes", rerank_enabled="Yes",
            query_rewrite_enabled="Yes", rewrite_type="Multi-query expansion",
            parent_recall_enabled="Yes",
        ),
        case_count=5,
        context_recall_avg=0.88,
        context_precision_avg=0.79,
        faithfulness_avg=0.91,
        answer_relevancy_avg=0.90,
        overall_score=0.87,
    )
    report_other = await EvalReport.create(
        report_no=uuid.uuid4().hex,
        task_id=task_other.id,
        strategy_name="Report on other evaluations",
        strategy_snapshot=_snapshot(),
        case_count=3,
        overall_score=0.5,
    )

    yield {
        "dataset": dataset,
        "one": report_one,
        "two": report_two,
        "other": report_other,
    }

    await EvalReport.filter(id__in=[report_one.id, report_two.id, report_other.id]).delete()
    await EvalTask.filter(id__in=[task_one.id, task_two.id, task_other.id]).delete()
    await EvalDataset.filter(id__in=[dataset.id, other.id]).delete()


def test_enabled_abilities_reads_snapshot():
    """A few steps from the strategic snapshot."""
    abilities = eval_report_service._enabled_abilities(
        _snapshot(bm25_enabled="Yes", rerank_enabled="Yes", query_rewrite_enabled="Yes", rewrite_type="HyDE")
    )
    assert abilities == ["Vector", "BM25", "Rerank", "HyDE"]


def test_enabled_abilities_handles_broken_snapshot():
    """The snapshot is not a valid JSON return to the empty list, without an anomaly."""
    assert eval_report_service._enabled_abilities("No, JSON.") == []
    assert eval_report_service._enabled_abilities(None) == []


async def test_select_reports_carries_cost_and_abilities(reports):
    """How many steps have been taken with the list of reports that is time-consuming and this strategy?"""
    items = await eval_report_service.select_reports(reports["dataset"].id)
    target = [item for item in items if item["id"] == reports["two"].id][0]
    assert target["cost_millis"] == 15000
    # Five, an average of 3000 milliseconds.
    assert target["avg_cost_millis"] == 3000
    assert "Rerank" in target["abilities"]


async def test_compare_requires_two_reports(reports):
    """Give a hint when you select only one."""
    with pytest.raises(Exception) as excinfo:
        await eval_report_service.compare([reports["one"].id])
    assert "select at least two reports" in str(excinfo.value)


async def test_compare_rejects_cross_dataset(reports):
    """The reports of the different assessment sets are not comparable, and there is no comparability in the use of different scores."""
    with pytest.raises(Exception) as excinfo:
        await eval_report_service.compare([reports["one"].id, reports["other"].id])
    assert "Only reports under the same evaluation set" in str(excinfo.value)


async def test_compare_builds_series(reports):
    """The results of the comparison are grouped by indicators, with a score per report in each group."""
    outcome = await eval_report_service.compare([reports["one"].id, reports["two"].id])

    assert len(outcome["columns"]) == 2
    assert outcome["columns"][0]["strategy_name"] == "Baseline - Vector search only"
    # Each of the four indicators will be clustered
    assert [item["metric"] for item in outcome["series"]] == [
        "Context recall", "Context precision", "Faithfulness", "Answer relevance"
    ]
    recall = [item for item in outcome["series"] if item["field"] == "context_recall_avg"][0]
    # The order is the same as that of the report in which it was sent.
    assert recall["values"] == [0.62, 0.88]


async def test_compare_keeps_requested_order(reports):
    """The order of the columns corresponds to the order of choice by the user."""
    outcome = await eval_report_service.compare([reports["two"].id, reports["one"].id])
    assert outcome["columns"][0]["strategy_name"] == "Full - Hybrid search with reranking and rewriting"
