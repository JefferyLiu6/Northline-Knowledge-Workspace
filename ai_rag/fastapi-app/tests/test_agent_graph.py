"""Agentic RAG status map test.

The figure itself does not touch the database, and all the places in the nodes that adjust models and tools are converted to false realizations.
It is the logic of branch direction, control ceilings and exit.
"""

import pytest

from ai import graph as agent_graph
from ai import model_factory, tools

DOCS = [
    {"chunk_id": 1, "document_id": 1, "score": 0.88, "content": "The duration of the guarantee period is 24 months."},
    {"chunk_id": 2, "document_id": 1, "score": 0.71, "content": "Non-manual damage is carried out free of charge during the period of Quality Assurance."},
]


class FakeReply:
    def __init__(self, content):
        self.content = content


class ScriptedModel:
    """The script returns the false model of content in turn, which is used to structure the judgement results for each node."""

    def __init__(self, script):
        self.script = list(script)
        self.prompts = []

    async def ainvoke(self, prompt, **kwargs):
        self.prompts.append(prompt)
        # Repeat the last one after the script is run out, and avoid testing because of the number of rounds.
        content = self.script.pop(0) if self.script else "Supported"
        return FakeReply(content)


@pytest.fixture()
def fake_env(monkeypatch, db):
    """Both models and retrieval tools are converted to false realizations, returning to a configured environment."""
    holder = {"model": None, "documents": DOCS, "invoked": []}

    async def fake_load_enabled(model_type):
        return object()

    def fake_build(config, temperature=0.0):
        return holder["model"]

    async def fake_invoke(tool_code, params, run_id=None, step_id=None):
        holder["invoked"].append((tool_code, params))
        return {"count": len(holder["documents"]), "results": holder["documents"]}

    monkeypatch.setattr(model_factory, "load_enabled", fake_load_enabled)
    monkeypatch.setattr(model_factory, "build_chat_model", fake_build)
    monkeypatch.setattr(tools, "invoke", fake_invoke)

    def setup(script, documents=None):
        holder["model"] = ScriptedModel(script)
        if documents is not None:
            holder["documents"] = documents
        return holder

    return setup


async def _run(script, documents=None, fake_env=None, query="How long is the warranty"):
    env = fake_env(script, documents)
    steps = []

    async def on_step(node, name, request, response):
        steps.append({"node": node, "name": name, "request": request, "response": response})

    compiled = agent_graph.build_graph()
    state = await compiled.ainvoke(
        {
            "original_query": query,
            "query": query,
            "kb_ids": [1],
            "history": [],
            "retry_count": 0,
            "regenerate_count": 0,
            "retrieve_count": 0,
            "on_step": on_step,
        },
        {"recursion_limit": agent_graph.MAX_GRAPH_STEPS * 3},
    )
    return state, steps, env


def test_build_context_truncates_long_documents():
    """When the context is framed to exceed the upper limit of length, requests are cut off from failure because they are too long."""
    long_docs = [{"content": "Words" * 5000} for _ in range(3)]
    context = agent_graph.build_context(long_docs)
    assert len(context) <= agent_graph.MAX_CONTEXT_CHARS + 100


def test_build_context_numbers_each_document():
    """Each paragraph is numbered and the model can be cited to its top position."""
    context = agent_graph.build_context(DOCS)
    assert "[Source 1]" in context
    assert "[Source 2]" in context


async def test_happy_path_answers_in_one_round(fake_env):
    """One hit: The associated generation is supported by the end of the walk."""
    state, steps, _ = await _run(["Relevant", "The duration of the guarantee period is 24 months.", "Supported"], fake_env=fake_env)

    assert state["finish_reason"] == "Answered"
    assert state["retrieve_count"] == 1
    assert state["retry_count"] == 0
    # Five steps: preparation of search questions, retrievals, judgemental relevance, generation, verification
    assert [item["node"] for item in steps] == ["rewrite", "retrieve", "grade", "generate", "check"]


async def test_irrelevant_result_triggers_rewrite_and_retry(fake_env):
    """Return to rewrite nodes when relevant and retrieve them again."""
    state, steps, _ = await _run(
        # First retrieval is irrelevant. Rewrite, retrieve again, then generate a supported answer.
        ["Irrelevant", "A different question.", "Relevant", "Answer", "Supported"],
        fake_env=fake_env,
    )

    assert state["finish_reason"] == "Answered"
    # The search took place twice.
    assert state["retrieve_count"] == 2
    assert state["retry_count"] == 1
    nodes = [item["node"] for item in steps]
    assert nodes.count("retrieve") == 2
    assert nodes.count("rewrite") == 2


async def test_retry_limit_falls_back(fake_env):
    """It was decided that it was irrelevant and tried again until after the ceiling."""
    state, steps, _ = await _run(["Irrelevant"] * 20, fake_env=fake_env)

    assert state["answer"] == "No relevant content was found in the knowledge base."
    assert state["finish_reason"] == "Irrelevant retrieval results"
    # The number of retryes is capped
    assert state["retry_count"] == agent_graph.MAX_RETRIEVE_RETRY
    assert steps[-1]["node"] == "fallback"
    # Empty quotes when you go around, and no irrelevant source will appear on the page.
    assert state["documents"] == []


async def test_empty_recall_counts_as_irrelevant(fake_env):
    """None of them was directly judged irrelevant and did not waste a model call."""
    state, steps, _ = await _run(["Irrelevant"] * 20, documents=[], fake_env=fake_env)

    assert state["finish_reason"] == "Irrelevant retrieval results"
    grade_steps = [item for item in steps if item["node"] == "grade"]
    assert grade_steps[0]["response"]["relevant"] is False
    # It's not supposed to appear when there's no information.
    assert "verdict" not in grade_steps[0]["response"]


async def test_ungrounded_answer_triggers_regenerate(fake_env):
    """When the answer is found to be unsupported, it returns to the node of creation and rewrite."""
    state, steps, _ = await _run(
        ["Relevant", "First edition of the answer", "Unsupported", "Second edition of the answer", "Supported"],
        fake_env=fake_env,
    )

    assert state["finish_reason"] == "Answered"
    assert state["answer"] == "Second edition of the answer"
    nodes = [item["node"] for item in steps]
    assert nodes.count("generate") == 2
    assert nodes.count("check") == 2
    # Regenerated without retrace
    assert state["retrieve_count"] == 1


async def test_regenerate_limit_falls_back(fake_env):
    """He's been sentenced to no support, regenerated to the upper limit."""
    state, steps, _ = await _run(
        ["Relevant"] + ["Answer", "Unsupported"] * 10,
        fake_env=fake_env,
    )

    assert state["answer"] == "No relevant content was found in the knowledge base."
    assert state["regenerate_count"] == agent_graph.MAX_REGENERATE
    assert steps[-1]["node"] == "fallback"


async def test_verdict_tolerates_extra_words(fake_env):
    """The model can also correctly interpret the findings of the judgment by two more words."""
    state, _, _ = await _run(
        ["This information is relevant.", "Answer", "That's a good answer."],
        fake_env=fake_env,
    )
    assert state["finish_reason"] == "Answered"


async def test_first_round_uses_original_query(fake_env):
    """The first round is not rewritten, and the user ' s original questions are used directly to retrieve it."""
    _, _, holder = await _run(["Relevant", "Answer", "Supported"], fake_env=fake_env)
    # The first time a search tool was used, query was the original problem of user input.
    assert holder["invoked"][0][1]["query"] == "How long is the warranty"


async def test_retry_uses_rewritten_query(fake_env):
    """When retrying, replace it with a rewrite question to retrieve it without using the original problem."""
    _, _, holder = await _run(
        ["Irrelevant", "A different question.", "Relevant", "Answer", "Supported"],
        fake_env=fake_env,
    )
    assert holder["invoked"][0][1]["query"] == "How long is the warranty"
    # The second search was for rewrite results.
    assert holder["invoked"][1][1]["query"] == "A different question."
