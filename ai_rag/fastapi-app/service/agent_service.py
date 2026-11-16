"""Agentic RAG execution.

Responsible for three things: running the state graph, writing each step into agent_run and agent_step, and performing a reverse database lookup after completion.

The graph itself does not interact with the database; data is stored through an on_step callback injection—
This allows ai/graph.py to be tested independently of the database.
"""

import json
import uuid

from ai import graph as agent_graph
from common.exception_handler import CustomException
from common.times import cost_millis, now
from models import AgentRun, AgentStep, KnowledgeChunk

ERROR_MAX_LENGTH = 500
# Write entry and return to agent_step with maximum number of words in order to prevent a record from holding on to dozens of kBs
STEP_PAYLOAD_MAX = 4000


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)[:STEP_PAYLOAD_MAX]


class StepRecorder:
    """Write the execution status of each node in the state graph into agent_step.

    A class is used to accumulate steps across nodes—each step increments the index by one,
    The timeline of Chapter 23 is displayed in this order.
    """

    def __init__(self, run_id: int, on_progress=None):
        self.run_id = run_id
        self.index = 0
        # Caller's progress echoes. The logout is for chapter 23.
        # This is a real-time push to the page, so that users can know when they're waiting.
        self.on_progress = on_progress

    async def __call__(self, node: str, name: str, request: dict, response: dict) -> None:
        self.index += 1
        await AgentStep.create(
            run_id=self.run_id,
            step_index=self.index,
            step_name=name,
            node_name=node,
            # The search node is using a tool, you can encode it and you can match it to the tool_call_log.
            tool_code="search_knowledge" if node == "retrieve" else None,
            request_params=_dump(request),
            response_result=_dump(response),
            step_status="Completed",
            start_time=now(),
            end_time=now(),
            cost_millis=0,
        )
        if self.on_progress is not None:
            # The decision (unrelevant, unsupported) to take this step is a resonance.
            # It makes it clear why this time re-trying is not just about waiting.
            # The callbacks are just for outgoing progress. Failures do not affect the status chart itself.
            try:
                self.on_progress(node, name, self.index, response)
            except Exception:
                pass


async def _fill_references(documents: list[dict]) -> list[dict]:
    """Look up the database by chunk_id to assemble reference sources.

    The rule from Chapter 20: references must be looked up using the actual chunk_id returned by the tool,
    Do not rely on the model's "based on rule 3" in the answer—this numbering is fabricated.
    """
    chunk_ids = [item["chunk_id"] for item in documents if item.get("chunk_id")]
    if not chunk_ids:
        return []
    chunks = await KnowledgeChunk.filter(id__in=chunk_ids)
    chunk_map = {chunk.id: chunk for chunk in chunks}
    references = []
    for rank, item in enumerate(documents, start=1):
        chunk = chunk_map.get(item.get("chunk_id"))
        # The clips were deleted and skipped without showing a source where the dots could not be opened.
        if chunk is None:
            continue
        references.append(
            {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "content": chunk.content,
                "page_no": chunk.page_no,
                "score": item.get("score"),
                "rank_no": rank,
            }
        )
    return references


async def run(
    kb_ids: list[int],
    query: str,
    user_id: int | None = None,
    app_id: int | None = None,
    session_id: int | None = None,
    history: list[dict] | None = None,
    on_progress=None,
) -> dict:
    """Execute one Agentic Q&A.

    on_progress is called once after each node is executed, with parameters (node name, step name, step number, conclusion of this step).
    The Q&A interface in Chapter 24 uses it to send progress events to SSE, allowing the page to display the current progress.
    """
    if not query or not query.strip():
        raise CustomException("Please enter a question")
    if not kb_ids:
        raise CustomException("Select a knowledge base")
    started = now()
    run_record = await AgentRun.create(
        run_no=uuid.uuid4().hex,
        app_id=app_id,
        session_id=session_id,
        user_id=user_id,
        run_type="Agentic Q&A",
        run_status="Running",
        input_snapshot=_dump({"query": query, "kb_ids": kb_ids}),
        start_time=started,
    )
    recorder = StepRecorder(run_record.id, on_progress=on_progress)
    try:
        compiled = agent_graph.build_graph()
        final_state = await compiled.ainvoke(
            {
                "original_query": query,
                "query": query,
                "kb_ids": kb_ids,
                "history": history or [],
                "retry_count": 0,
                "regenerate_count": 0,
                "retrieve_count": 0,
                "on_step": recorder,
            },
            # LangGraph has its own regressive cap, and a business-side cap double insurance
            {"recursion_limit": agent_graph.MAX_GRAPH_STEPS * 3},
        )
        retrieve_count = final_state.get("retrieve_count", 0)
        # Counter-checking: Models may have produced an answer without a single search, and this operation cannot be considered successful.
        if retrieve_count == 0:
            raise CustomException(
                "This run did not perform any retrieval; the answer is not reliable."
                "Please check if the knowledge base has been vectorized and if the retrieval tool is disabled"
            )
        answer = final_state.get("answer") or ""
        references = await _fill_references(final_state.get("documents") or [])
        await AgentRun.filter(id=run_record.id).update(
            run_status="Completed",
            current_step=recorder.index,
            total_step=recorder.index,
            retrieve_count=retrieve_count,
            rewrite_count=final_state.get("retry_count", 0),
            output_summary=answer[:5000],
            end_time=now(),
            cost_millis=cost_millis(started),
        )
        return {
            "run_id": run_record.id,
            "run_no": run_record.run_no,
            "answer": answer,
            "references": references,
            "finish_reason": final_state.get("finish_reason") or "Answered",
            "retrieve_count": retrieve_count,
            "retry_count": final_state.get("retry_count", 0),
            "total_step": recorder.index,
            "cost_millis": cost_millis(started),
        }
    except Exception as exc:
        message = exc.message if isinstance(exc, CustomException) else f"Execution Failed:{exc}"
        await AgentRun.filter(id=run_record.id).update(
            run_status="Run failed",
            current_step=recorder.index,
            total_step=recorder.index,
            error_message=message[:ERROR_MAX_LENGTH],
            end_time=now(),
            cost_millis=cost_millis(started),
        )
        raise CustomException(message)


async def select_runs(
    run_status: str = "",
    session_id: int | None = None,
    page_num: int = 1,
    page_size: int = 10,
):
    """List of run records."""
    from common.result import PageInfo

    query = AgentRun.all()
    if run_status:
        query = query.filter(run_status=run_status)
    if session_id:
        query = query.filter(session_id=session_id)
    runs = await query.order_by("-id").offset((page_num - 1) * page_size).limit(page_size)
    total = await query.count()
    return PageInfo(
        total=total,
        list=[
            {
                "id": item.id,
                "run_no": item.run_no,
                "run_type": item.run_type,
                "run_status": item.run_status,
                "total_step": item.total_step,
                "retrieve_count": item.retrieve_count,
                "rewrite_count": item.rewrite_count,
                "output_summary": item.output_summary,
                "error_message": item.error_message,
                "cost_millis": item.cost_millis,
                "create_time": item.create_time,
            }
            for item in runs
        ],
    )


async def select_steps(run_id: int) -> dict:
    """The complete timeline of steps for one run, for use by the page in Chapter 23."""
    run_record = await AgentRun.get_or_none(id=run_id)
    if run_record is None:
        raise CustomException("No run record found")
    steps = await AgentStep.filter(run_id=run_id).order_by("step_index")
    return {
        "run": {
            "id": run_record.id,
            "run_no": run_record.run_no,
            "run_status": run_record.run_status,
            "total_step": run_record.total_step,
            "retrieve_count": run_record.retrieve_count,
            "rewrite_count": run_record.rewrite_count,
            "input_snapshot": run_record.input_snapshot,
            "output_summary": run_record.output_summary,
            "error_message": run_record.error_message,
            "cost_millis": run_record.cost_millis,
            "create_time": run_record.create_time,
        },
        "steps": [
            {
                "id": step.id,
                "step_index": step.step_index,
                "step_name": step.step_name,
                "node_name": step.node_name,
                "tool_code": step.tool_code,
                "request_params": step.request_params,
                "response_result": step.response_result,
                "step_status": step.step_status,
                "error_message": step.error_message,
                "cost_millis": step.cost_millis,
            }
            for step in steps
        ],
    }
