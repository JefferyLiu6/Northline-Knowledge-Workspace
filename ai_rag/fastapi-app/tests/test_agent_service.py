"""Agentic RAG performs landing tests.

The branch logic of the graph was measured in test_agent_graph.py, and here's the outside layer:
Runs records, steps records, quotes from source back checks, and the countercheck "even if you fail to retrieve them."
"""

import pytest

from ai import graph as agent_graph
from ai import model_factory, tools
from common.exception_handler import CustomException
from models import AgentRun, AgentStep, KnowledgeBase, KnowledgeChunk, KnowledgeDocument
from service import agent_service

KB_NAME = "Test Agent Library-module test exclusively"


class FakeReply:
    def __init__(self, content):
        self.content = content


class ScriptedModel:
    def __init__(self, script):
        self.script = list(script)

    async def ainvoke(self, prompt, **kwargs):
        return FakeReply(self.script.pop(0) if self.script else "Supported")


@pytest.fixture()
async def agent_env(monkeypatch, db):
    """Build a real knowledge base and snippets to replace models and retrieval tools with false realizations."""
    kb = await KnowledgeBase.create(name=KB_NAME, status="Active")
    doc = await KnowledgeDocument.create(kb_id=kb.id, name="Agent test document.txt")
    chunk = await KnowledgeChunk.create(
        kb_id=kb.id,
        document_id=doc.id,
        chunk_index=0,
        chunk_type="Standard chunk",
        content="The duration of the guarantee period is 24 months.",
        char_count=11,
        page_no=2,
    )
    holder = {"model": None, "results": [{"chunk_id": chunk.id, "document_id": doc.id, "score": 0.9, "content": chunk.content}]}

    async def fake_load_enabled(model_type):
        return object()

    def fake_build(config, temperature=0.0):
        return holder["model"]

    async def fake_invoke(tool_code, params, run_id=None, step_id=None):
        return {"count": len(holder["results"]), "results": holder["results"]}

    monkeypatch.setattr(model_factory, "load_enabled", fake_load_enabled)
    monkeypatch.setattr(model_factory, "build_chat_model", fake_build)
    monkeypatch.setattr(tools, "invoke", fake_invoke)

    def setup(script, results=None):
        holder["model"] = ScriptedModel(script)
        if results is not None:
            holder["results"] = results
        return holder

    yield {"kb": kb, "doc": doc, "chunk": chunk, "setup": setup}

    await AgentStep.filter(run_id__in=[item.id for item in await AgentRun.filter(user_id=-1)]).delete()
    await AgentRun.filter(user_id=-1).delete()
    await KnowledgeChunk.filter(kb_id=kb.id).delete()
    await KnowledgeDocument.filter(id=doc.id).delete()
    await KnowledgeBase.filter(id=kb.id).delete()


async def test_run_writes_run_and_steps(agent_env):
    """A running record and a number of steps were left after the run."""
    agent_env["setup"](["Relevant", "Quality assurance 24 months.", "Supported"])

    outcome = await agent_service.run([agent_env["kb"].id], "How long is the warranty", user_id=-1)

    assert outcome["finish_reason"] == "Answered"
    assert outcome["retrieve_count"] == 1
    assert outcome["total_step"] == 5

    run_record = await AgentRun.get_or_none(id=outcome["run_id"])
    assert run_record.run_status == "Completed"
    assert run_record.total_step == 5
    assert run_record.retrieve_count == 1
    assert run_record.cost_millis is not None

    steps = await AgentStep.filter(run_id=outcome["run_id"]).order_by("step_index")
    assert [step.node_name for step in steps] == ["rewrite", "retrieve", "grade", "generate", "check"]
    # Step sequence number continuously increment from 1 and time line sorted according to it
    assert [step.step_index for step in steps] == [1, 2, 3, 4, 5]
    # Retrieve that step and write the tool code to match the tool_call_log.
    assert steps[1].tool_code == "search_knowledge"


async def test_references_come_from_database(agent_env):
    """The reference source is the chunk_id back to the database, which is based on the contents of the library."""
    agent_env["setup"](["Relevant", "Answer", "Supported"])

    outcome = await agent_service.run([agent_env["kb"].id], "How long is the warranty", user_id=-1)

    assert len(outcome["references"]) == 1
    reference = outcome["references"][0]
    assert reference["chunk_id"] == agent_env["chunk"].id
    # The text came from the database, not the model.
    assert reference["content"] == agent_env["chunk"].content
    assert reference["page_no"] == 2
    assert reference["rank_no"] == 1


async def test_deleted_chunk_is_skipped_in_references(agent_env):
    """The clip has been deleted and skipped, without showing a source where no point remains open."""
    agent_env["setup"](
        ["Relevant", "Answer", "Supported"],
        results=[{"chunk_id": 999999, "document_id": 1, "score": 0.9, "content": "A segment that no longer exists"}],
    )

    outcome = await agent_service.run([agent_env["kb"].id], "How long is the warranty", user_id=-1)

    assert outcome["references"] == []


async def test_fallback_clears_references(agent_env):
    """The source of the quotes is not attached."""
    agent_env["setup"](["Irrelevant"] * 20)

    outcome = await agent_service.run([agent_env["kb"].id], "Where's the company's annual meeting?", user_id=-1)

    assert outcome["answer"] == "No relevant content was found in the knowledge base."
    assert outcome["finish_reason"] == "Irrelevant retrieval results"
    assert outcome["references"] == []
    # It's a normal end to the choreography. The active state is finished, not failed.
    run_record = await AgentRun.get_or_none(id=outcome["run_id"])
    assert run_record.run_status == "Completed"


async def test_run_without_retrieve_is_marked_failed(agent_env, monkeypatch):
    """A search failed when it did not occur and the compiled answers were not returned to the user."""
    agent_env["setup"](["Relevant", "Answer", "Supported"])

    # You change the search nodes to nothing, and you're like, "Models answer directly without adjusting their tools."
    async def no_retrieve(state):
        return {"documents": [{"chunk_id": 1, "content": "Empty information."}]}

    monkeypatch.setattr(agent_graph, "retrieve_node", no_retrieve)

    with pytest.raises(CustomException) as excinfo:
        await agent_service.run([agent_env["kb"].id], "How long is the warranty", user_id=-1)
    assert "did not perform any retrieval" in excinfo.value.message

    # The failure of running also leaves a record, and we can find out why.
    run_record = await AgentRun.filter(user_id=-1).order_by("-id").first()
    assert run_record.run_status == "Run failed"
    assert "did not perform any retrieval" in run_record.error_message


async def test_empty_query_is_rejected(agent_env):
    """Question is to give a human message when empty, without running records."""
    with pytest.raises(CustomException) as excinfo:
        await agent_service.run([agent_env["kb"].id], "   ", user_id=-1)
    assert excinfo.value.message == "Please enter a question"


async def test_select_steps_returns_timeline(agent_env):
    """The step-time line interface returns the running profile and steps in sequence."""
    agent_env["setup"](["Relevant", "Answer", "Supported"])
    outcome = await agent_service.run([agent_env["kb"].id], "How long is the warranty", user_id=-1)

    timeline = await agent_service.select_steps(outcome["run_id"])

    assert timeline["run"]["run_status"] == "Completed"
    assert len(timeline["steps"]) == 5
    assert timeline["steps"][0]["step_name"] == "Prepare search query"
    assert timeline["steps"][-1]["step_name"] == "Verify whether the answer is supported by information"
