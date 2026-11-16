from tortoise import fields
from tortoise.models import Model


class EvalDataset(Model):
    """Evaluation Set Table. A set of test cases constitutes an evaluation set, and one evaluation runs the entire set."""

    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=255)
    kb_id = fields.IntField(null=True)
    description = fields.CharField(max_length=1000, null=True)
    # Redundant statistical column, recalculation when adding and deleting cases
    case_count = fields.IntField(default=0)
    create_time = fields.DatetimeField(auto_now_add=True)
    update_time = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "eval_dataset"


class EvalCase(Model):
    """Evaluation Case Table.

    As mentioned in Chapter 26: among the four metrics, only Context Recall requires a standard answer,
    so question and ground_truth are the minimum requirements for one test case.
    """

    id = fields.IntField(primary_key=True)
    dataset_id = fields.IntField()
    question = fields.CharField(max_length=1000)
    ground_truth = fields.TextField(null=True)
    # The standard answer corresponds to a segment of ID, comma separated. With it Context Recall can be counted without the model.
    reference_chunk_ids = fields.CharField(max_length=500, null=True)
    # Manually recorded / document generated / feedback deposited
    source = fields.CharField(max_length=30, default="Manual entry")
    enabled = fields.CharField(max_length=10, default="Yes")
    remark = fields.CharField(max_length=500, null=True)
    create_time = fields.DatetimeField(auto_now_add=True)
    update_time = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "eval_case"


class EvalTask(Model):
    """Evaluation Task Table. One batch evaluation is recorded as one task."""

    id = fields.IntField(primary_key=True)
    task_no = fields.CharField(max_length=64, unique=True)
    dataset_id = fields.IntField()
    app_id = fields.IntField(null=True)
    retrieval_strategy_id = fields.IntField(null=True)
    # The strategy is a snapshot of the parameters. A week after the report, it makes sense to see which switches were turned on.
    strategy_snapshot = fields.TextField(null=True)
    judge_model_id = fields.IntField(null=True)
    task_status = fields.CharField(max_length=30, default="Pending")
    total_count = fields.IntField(default=0)
    success_count = fields.IntField(default=0)
    fail_count = fields.IntField(default=0)
    error_message = fields.CharField(max_length=500, null=True)
    start_time = fields.DatetimeField(null=True)
    end_time = fields.DatetimeField(null=True)
    cost_millis = fields.BigIntField(null=True)
    create_user_id = fields.IntField(null=True)
    create_time = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "eval_task"


class EvalCaseResult(Model):
    """Evaluation Result for a Single Case. One column for each of the four metrics."""

    id = fields.IntField(primary_key=True)
    task_id = fields.IntField()
    case_id = fields.IntField()
    answer = fields.TextField(null=True)
    retrieved_chunk_ids = fields.CharField(max_length=500, null=True)
    # Chapter 26, four indicators, 0 to 1
    faithfulness = fields.DecimalField(max_digits=5, decimal_places=4, null=True)
    answer_relevancy = fields.DecimalField(max_digits=5, decimal_places=4, null=True)
    context_precision = fields.DecimalField(max_digits=5, decimal_places=4, null=True)
    context_recall = fields.DecimalField(max_digits=5, decimal_places=4, null=True)
    avg_score = fields.DecimalField(max_digits=5, decimal_places=4, null=True)
    error_message = fields.CharField(max_length=500, null=True)
    cost_millis = fields.BigIntField(null=True)
    create_time = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "eval_case_result"


class EvalReport(Model):
    """Evaluation Report Table. After one task is completed, a summary report is generated, for cross-comparison in the dashboard in Chapter 29."""

    id = fields.IntField(primary_key=True)
    report_no = fields.CharField(max_length=64, unique=True)
    task_id = fields.IntField()
    strategy_name = fields.CharField(max_length=255, null=True)
    strategy_snapshot = fields.TextField(null=True)
    case_count = fields.IntField(default=0)
    faithfulness_avg = fields.DecimalField(max_digits=5, decimal_places=4, null=True)
    answer_relevancy_avg = fields.DecimalField(max_digits=5, decimal_places=4, null=True)
    context_precision_avg = fields.DecimalField(max_digits=5, decimal_places=4, null=True)
    context_recall_avg = fields.DecimalField(max_digits=5, decimal_places=4, null=True)
    overall_score = fields.DecimalField(max_digits=5, decimal_places=4, null=True)
    conclusion = fields.TextField(null=True)
    create_time = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "eval_report"
