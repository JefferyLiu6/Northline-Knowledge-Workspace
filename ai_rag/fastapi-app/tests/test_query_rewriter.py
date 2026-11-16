"""Query rewrite test.

The real rewrite is a dialogue model, and here we change the model factory to fake.
It is the part of the project that has been written by itself: multi-manufacture, original problem retention, bar ceilings and empty back to the bottom.
"""

import pytest

from ai import model_factory, prompt_loader, query_rewriter


class FakeReply:
    def __init__(self, content: str):
        self.content = content


class FakeModel:
    def __init__(self, content: str):
        self._content = content
        # Prompt, which records the actual distribution to models, is used to assert that templates are correctly rendered
        self.last_prompt = None

    async def ainvoke(self, prompt, **kwargs):
        self.last_prompt = prompt
        return FakeReply(self._content)


@pytest.fixture()
def fake_chat(monkeypatch):
    """Replace both the configuration and the construction model with a false realization, and return to the fake model for assertion."""
    holder = {}

    async def fake_load_enabled(model_type):
        return object()

    def fake_build(config, temperature=0.0):
        return holder["model"]

    monkeypatch.setattr(model_factory, "load_enabled", fake_load_enabled)
    monkeypatch.setattr(model_factory, "build_chat_model", fake_build)

    def setup(content):
        holder["model"] = FakeModel(content)
        return holder["model"]

    return setup


def test_split_lines_strips_numbering():
    """When the model returns a multi-line text with numbers, the number and bullet are cleared."""
    lines = query_rewriter._split_lines("1. Does the product support on-premises deployment?\n- Can it run on our own servers?\n\n2,Is local installation available?")
    assert lines == ["Does the product support on-premises deployment?", "Can it run on our own servers?", "Is local installation available?"]


async def test_multi_query_keeps_original_question(db, fake_chat):
    """The first of the results of multiple inquiries is always the original problem."""
    fake_chat("Does the product support on-premises deployment?\nCan it run on our own servers?\nIs local installation available?")

    queries = await query_rewriter.multi_query("Can it run in our own data center?", 3)

    assert queries[0] == "Can it run in our own data center?"
    assert "Does the product support on-premises deployment?" in queries
    # The original problem with the count rewrite, does not exceed the total number of count + 1
    assert len(queries) == 4


async def test_multi_query_dedupes_repeated_question(db, fake_chat):
    """The model takes the original problem over again."""
    fake_chat("Can it run in our own data center?\nDoes the product support on-premises deployment?")

    queries = await query_rewriter.multi_query("Can it run in our own data center?", 3)

    assert queries.count("Can it run in our own data center?") == 1
    assert len(queries) == 2


async def test_multi_query_count_is_capped(db, fake_chat):
    """The number of extensions is capped to prevent a question-and-answer session from magnifying the number of searches out of control."""
    model = fake_chat("\n".join(f"AI capability layer.{index}" for index in range(1, 20)))

    queries = await query_rewriter.multi_query("Original question", 99)

    assert len(queries) == query_rewriter.MAX_QUERY_COUNT + 1
    # The number of bars rendering into Prompt is also cut to the upper limit
    assert str(query_rewriter.MAX_QUERY_COUNT) in model.last_prompt


async def test_resolve_coreference_without_history_skips_model():
    """When there is no history of dialogue, return as it has been and do not call for useless models."""
    assert await query_rewriter.resolve_coreference("What about the deadline?", []) == "What about the deadline?"


async def test_resolve_coreference_rewrites_question(db, fake_chat):
    """There is history of substituting fingernails as an issue of independence."""
    model = fake_chat("GTE-3000 After 24 months warranty")

    history = [
        {"role": "user", "content": "How long is the warranty period for GTE-3000?"},
        {"role": "assistant", "content": "24 months."},
    ]
    rewritten = await query_rewriter.resolve_coreference("What about the deadline?", history)

    assert rewritten == "GTE-3000 After 24 months warranty"
    # History in "User/Associate"
    assert "User: How long is the warranty period for GTE-3000?" in model.last_prompt
    assert "Assistant: 24 months." in model.last_prompt


async def test_resolve_coreference_falls_back_on_empty_reply(db, fake_chat):
    """The model returns the empty content and does not allow the search to run with an empty string."""
    fake_chat("   ")

    history = [{"role": "user", "content": "Previous sentence"}]
    assert await query_rewriter.resolve_coreference("What about it?", history) == "What about it?"


async def test_hyde_prepends_original_question(db, fake_chat):
    """HyDE combines the original question with the false answer, retaining both intent and document."""
    fake_chat("This product supports on-premises deployment on customer-owned servers.")

    result = await query_rewriter.hyde("Can it run in our own data center?")

    assert result.startswith("Can it run in our own data center?")
    assert "on-premises deployment" in result


async def test_hyde_falls_back_on_empty_reply(db, fake_chat):
    """The false answer is to return the original question in time."""
    fake_chat("")
    assert await query_rewriter.hyde("Original question") == "Original question"


async def test_rewrite_returns_list_for_every_type(db, fake_chat):
    """The three rewrite returns the uniform value is a list, and the caller does not have to write three sets of branches."""
    fake_chat("Rewrite Results")

    assert isinstance(await query_rewriter.rewrite("Question", query_rewriter.MULTI_QUERY, 2), list)
    assert isinstance(await query_rewriter.rewrite("Question", query_rewriter.HYDE, 2), list)
    assert isinstance(
        await query_rewriter.rewrite("Question", query_rewriter.COREFERENCE, 2, [{"role": "user", "content": "Previous sentence"}]),
        list,
    )


async def test_rewrite_without_type_returns_original(db, fake_chat):
    """If not rewrite, search on the basis of the problem."""
    fake_chat("It shouldn't have been used.")
    assert await query_rewriter.rewrite("Original question", None, 3) == ["Original question"]


def test_rewrite_prompt_templates_exist(client, admin_headers):
    """The Prompt templates on which each of the three rewrites relies are in initialized data."""
    body = client.get("/promptTemplate/selectAll", headers=admin_headers).json()
    codes = {item["code"] for item in body["data"]}
    assert {"QUERY_REWRITE", "COREFERENCE_RESOLVE", "HYDE_ANSWER"} <= codes


async def test_hyde_template_renders(db):
    """HyDE templates only need a question for one variable."""
    content = await prompt_loader.render("HYDE_ANSWER", question="How long is the warranty")
    assert "How long is the warranty" in content
