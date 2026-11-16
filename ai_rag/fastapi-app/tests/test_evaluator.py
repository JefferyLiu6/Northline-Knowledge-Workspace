"""Evaluation indicator testing.

The referee adjusts the model and replaces it here with a false realization;
Disaggregated, weighted algorithms, direct contrast session ID are all of this project ' s own logic that can be measured directly.
"""

import pytest

from ai import evaluator, model_factory


def test_parse_verdicts_reads_yes_and_no():
    """The line-by-line conclusions are correctly interpreted."""
    assert evaluator.parse_verdicts("Yes\nNo\nYes", 3) == [True, False, True]


def test_parse_verdicts_strips_numbering():
    """The model can also be interpreted with a number."""
    assert evaluator.parse_verdicts("1. Yes\n2. No", 2) == [True, False]


def test_parse_verdicts_pads_missing_as_false():
    """The model is not filled by a few lines of output, and the scores are conservative and optimistic."""
    assert evaluator.parse_verdicts("Yes", 3) == [True, False, False]


def test_parse_verdicts_truncates_extra():
    """Models cut the desired number when more than one line is exported."""
    assert evaluator.parse_verdicts("Yes\nYes\nNo", 2) == [True, True]


def test_parse_verdicts_treats_unknown_as_false():
    """The models were conservatively judged not to have passed when they did not respond in a format."""
    assert evaluator.parse_verdicts("I'm not sure\nYes", 2) == [False, True]


def test_precision_at_k_rewards_top_rank():
    """The relevant row 1 is much more accurate than the 4th."""
    top = evaluator.precision_at_k([True, False, False, False])
    bottom = evaluator.precision_at_k([False, False, False, True])
    assert top == 1.0
    assert bottom == 0.25
    assert top > bottom


def test_precision_at_k_all_relevant_is_one():
    """The accuracy is full when all relevant."""
    assert evaluator.precision_at_k([True, True, True]) == 1.0


def test_precision_at_k_none_relevant_is_zero():
    """One of the related none-time precisions is zero."""
    assert evaluator.precision_at_k([False, False]) == 0.0


def test_precision_at_k_empty_is_zero():
    """The accuracy of none was 0, no abnormality."""
    assert evaluator.precision_at_k([]) == 0.0


def test_cosine_identical_vectors():
    """The cosine similarities of the same vector are 1."""
    assert round(evaluator.cosine([1.0, 0.0], [1.0, 0.0]), 6) == 1.0


def test_cosine_orthogonal_vectors():
    """The cosine resemblance of the orient vector is 0."""
    assert round(evaluator.cosine([1.0, 0.0], [0.0, 1.0]), 6) == 0.0


def test_cosine_handles_zero_vector():
    """Zero vectors do not lead to zero errors."""
    assert evaluator.cosine([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_build_context_truncates():
    """The information that is given to the decision has been cut for too long."""
    contents = ["Words" * 3000 for _ in range(5)]
    context = evaluator.build_context(contents)
    assert len(context) <= evaluator.MAX_JUDGE_CHARS + 100


async def test_context_recall_uses_reference_ids_without_model(db):
    """The example is used to compare the fragments of ID directly, without adjusting the model."""
    # Should have recalled 1, 2, 2 and 2, actually called back 1 and 2 and had nothing to do with 9
    score = await evaluator.context_recall(
        ground_truth="It won't be used.",
        contents=[],
        reference_chunk_ids=[1, 2, 3],
        retrieved_chunk_ids=[1, 2, 9],
    )
    assert round(score, 4) == round(2 / 3, 4)


async def test_context_recall_full_hit(db):
    """All recalls that should be recalled will be completed in the context."""
    score = await evaluator.context_recall("", [], [5, 6], [5, 6, 7])
    assert score == 1.0


class FakeReply:
    def __init__(self, content):
        self.content = content


class ScriptedModel:
    def __init__(self, script):
        self.script = list(script)
        self.prompts = []

    async def ainvoke(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return FakeReply(self.script.pop(0) if self.script else "No")


@pytest.fixture()
def fake_judge(monkeypatch, db):
    holder = {}

    async def fake_load_enabled(model_type):
        return object()

    def fake_build(config, temperature=0.0):
        return holder["model"]

    monkeypatch.setattr(model_factory, "load_enabled", fake_load_enabled)
    monkeypatch.setattr(model_factory, "build_chat_model", fake_build)

    def setup(script):
        holder["model"] = ScriptedModel(script)
        return holder["model"]

    return setup


async def test_faithfulness_counts_supported_statements(fake_judge):
    """The answer is three sentences, two supportive and two-thirds faithful."""
    fake_judge([
        # First call: open statement
        "The warranty lasts 24 months.\nQualifying repairs are free.\nAccidental damage is covered.",
        # Second call: Article by article
        "Yes\nYes\nNo",
    ])

    score = await evaluator.faithfulness("Body of Answers", ["Content of information"])
    assert round(score, 4) == round(2 / 3, 4)


async def test_faithfulness_zero_when_no_statements(fake_judge):
    """Return 0 when the statement cannot be removed, and no abnormality will occur."""
    fake_judge(["", "Yes"])
    assert await evaluator.faithfulness("", ["Sources"]) == 0.0


async def test_context_precision_uses_rank(fake_judge):
    """The final level of accuracy is significantly lower than the top."""
    fake_judge(["No\nNo\nNo\nYes"])
    score = await evaluator.context_precision("Question", ["a", "b", "c", "d"])
    assert score == 0.25


async def test_context_recall_falls_back_to_model(fake_judge):
    """No session ID is used to determine whether standard answers are covered."""
    fake_judge([
        "The insurance period is 24 months \n overbilling.",
        "Yes\nNo",
    ])
    score = await evaluator.context_recall("Standard answers", ["Sources"], None, [1, 2])
    assert score == 0.5
