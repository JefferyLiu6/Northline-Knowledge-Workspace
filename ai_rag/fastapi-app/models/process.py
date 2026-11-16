from tortoise import fields
from tortoise.models import Model


class DocumentProcessTask(Model):
    """Document Processing Task Table.

    Parsing, splitting, and vectorization are time-consuming operations. The interface cannot wait indefinitely,
    so each trigger creates a task record first. The page uses it to view progress and failure reasons.
    """

    id = fields.IntField(primary_key=True)
    kb_id = fields.IntField()
    # The whole library is empty when re-established, and the single piece of process points to a specific document
    document_id = fields.IntField(null=True)
    task_type = fields.CharField(max_length=30)
    task_status = fields.CharField(max_length=30, default="Pending")
    context_json = fields.TextField(null=True)
    total_count = fields.IntField(default=0)
    success_count = fields.IntField(default=0)
    fail_count = fields.IntField(default=0)
    # 500 words cut before writing the library, and thousands of words are often missing out from the third-party library.
    error_message = fields.CharField(max_length=500, null=True)
    start_time = fields.DatetimeField(null=True)
    end_time = fields.DatetimeField(null=True)
    cost_millis = fields.BigIntField(null=True)
    create_time = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "document_process_task"


class RetrievalDebugRecord(Model):
    """Recall Debug Record Table.

    Each strategy comparison in the debug panel is stored as a record, keeping the original retrieved results as they were.
    After adjusting parameters, you can compare the differences before and after by reviewing them later.
    """

    id = fields.IntField(primary_key=True)
    kb_id = fields.IntField()
    query = fields.CharField(max_length=1000)
    # The strategy for participating in the comparison ID, comma separated
    strategy_ids = fields.CharField(max_length=255, null=True)
    # Full snapshots of the results from the strategies recalled by JSON, with fragments, fractions and stages timed
    result_snapshot = fields.TextField(null=True)
    cost_millis = fields.BigIntField(null=True)
    create_user_id = fields.IntField(null=True)
    create_time = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "retrieval_debug_record"


class AgentRun(Model):
    """Agent Execution Record Table.

    One Agentic question and answer session is recorded as one execution record. It records how many rounds were run, how many times retrieval was performed,
    and whether the final answer was normal or fell back to a default response.
    """

    id = fields.IntField(primary_key=True)
    run_no = fields.CharField(max_length=64, unique=True)
    app_id = fields.IntField(null=True)
    session_id = fields.IntField(null=True)
    message_id = fields.IntField(null=True)
    user_id = fields.IntField(null=True)
    run_type = fields.CharField(max_length=100, null=True)
    run_status = fields.CharField(max_length=50, default="Running")
    current_step = fields.IntField(default=0)
    total_step = fields.IntField(default=0)
    # Number of actual searches. After the execution, check it out. 0 means this operation has never been retrieved.
    retrieve_count = fields.IntField(default=0)
    rewrite_count = fields.IntField(default=0)
    input_snapshot = fields.TextField(null=True)
    output_summary = fields.TextField(null=True)
    error_message = fields.CharField(max_length=500, null=True)
    start_time = fields.DatetimeField(null=True)
    end_time = fields.DatetimeField(null=True)
    cost_millis = fields.BigIntField(null=True)
    create_time = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "agent_run"


class AgentStep(Model):
    """Agent Execution Step Table.

    Each node in the state diagram is recorded as one entry when executed. node_name is the node name in the diagram,
    step_name is the human-readable label, and the timeline in Chapter 23 is sorted by step_index.
    """

    id = fields.IntField(primary_key=True)
    run_id = fields.IntField()
    step_index = fields.IntField(default=0)
    step_name = fields.CharField(max_length=255, null=True)
    node_name = fields.CharField(max_length=100, null=True)
    tool_code = fields.CharField(max_length=100, null=True)
    request_params = fields.TextField(null=True)
    response_result = fields.TextField(null=True)
    step_status = fields.CharField(max_length=50, default="Running")
    error_message = fields.CharField(max_length=500, null=True)
    start_time = fields.DatetimeField(null=True)
    end_time = fields.DatetimeField(null=True)
    cost_millis = fields.BigIntField(null=True)
    create_time = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "agent_step"


class ToolCallLog(Model):
    """Tool Call Log Table.

    Each time the Agent calls a tool, it is recorded as one entry, whether successful or not.
    The page statistics the success rate by tool code, showing which tool is most frequently called and which is most likely to fail.
    """

    id = fields.IntField(primary_key=True)
    run_id = fields.IntField(null=True)
    step_id = fields.IntField(null=True)
    tool_code = fields.CharField(max_length=100)
    tool_name = fields.CharField(max_length=255, null=True)
    request_params = fields.TextField(null=True)
    response_result = fields.TextField(null=True)
    call_status = fields.CharField(max_length=20, default="Succeeded")
    error_message = fields.CharField(max_length=500, null=True)
    cost_millis = fields.BigIntField(null=True)
    create_time = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "tool_call_log"
