"""Evaluations and evaluation case tests.

Auto-generated models to adjust, where models are replaced with false realizations;
JSON's interpretation, feedback deposition and case synchronization are all of this project's own logic that can be measured directly.
"""

import pytest

from ai import model_factory
from models import (
    ChatMessage,
    ChatSession,
    EvalCase,
    EvalDataset,
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeDocument,
    MessageFeedback,
    QaApp,
    User,
)
from service import eval_dataset_service
from conftest import TEST_MARK

DATASET_NAME = "Test assessment - module test"


@pytest.fixture()
async def dataset(db):
    record = await EvalDataset.create(name=DATASET_NAME, description="Automation testing")
    yield record
    await EvalCase.filter(dataset_id=record.id).delete()
    await EvalDataset.filter(id=record.id).delete()


def test_parse_generated_handles_code_fence():
    """The model will also solve the case when it wraps JSON in a code block."""
    text = """Okay, here's the question-and-answer period:
```json
[{"question": "How long is the warranty", "ground_truth": "24 months"}]
```
"""
    pairs = eval_dataset_service.parse_generated(text)
    assert len(pairs) == 1
    assert pairs[0]["question"] == "How long is the warranty"


def test_parse_generated_drops_incomplete_items():
    """The missing questions or the missing standard answers are dropped directly and do not generate half an example."""
    text = '[{"question": "Question only"}, {"ground_truth": "Answer only"}, {"question": "Complete", "ground_truth": "Answer"}]'
    pairs = eval_dataset_service.parse_generated(text)
    assert len(pairs) == 1
    assert pairs[0]["question"] == "Complete"


def test_parse_generated_returns_empty_on_garbage():
    """The model does not return an empty list when JSON returns."""
    assert eval_dataset_service.parse_generated("I'm sorry. I can't do this.") == []


async def test_case_requires_ground_truth(dataset):
    """The absence of a standard answer, even in the context, must be filled out."""
    with pytest.raises(Exception) as excinfo:
        await eval_dataset_service.add_case({"dataset_id": dataset.id, "question": "How long is the warranty"})
    assert "Please enter the standard answer" in str(excinfo.value)


async def test_case_count_is_synced(dataset):
    """The number of cases in the assessment set changes after adding and deleting the example."""
    await eval_dataset_service.add_case(
        {"dataset_id": dataset.id, "question": "How long is the warranty", "ground_truth": "24 months"}
    )
    refreshed = await EvalDataset.get_or_none(id=dataset.id)
    assert refreshed.case_count == 1

    case = await EvalCase.filter(dataset_id=dataset.id).first()
    await eval_dataset_service.delete_case(case.id)
    refreshed = await EvalDataset.get_or_none(id=dataset.id)
    assert refreshed.case_count == 0


async def test_delete_dataset_removes_cases(dataset):
    """The evaluation of the collection should be followed by an example, leaving no case for orphans."""
    await eval_dataset_service.add_case(
        {"dataset_id": dataset.id, "question": "How long is the warranty", "ground_truth": "24 months"}
    )
    await eval_dataset_service.delete_dataset(dataset.id)
    assert await EvalCase.filter(dataset_id=dataset.id).count() == 0


async def test_generate_from_document(dataset, monkeypatch):
    """Automatically generated source-snippet ID, the source is marked as a document."""
    kb = await KnowledgeBase.create(name="Test-generation library -- module test exclusively", status="Active")
    doc = await KnowledgeDocument.create(kb_id=kb.id, name="Generate test documents.txt")
    chunk = await KnowledgeChunk.create(
        kb_id=kb.id,
        document_id=doc.id,
        chunk_index=0,
        chunk_type="Standard chunk",
        content="The GTE-3000 duration is 24 months.",
        char_count=20,
    )

    class FakeReply:
        # [snippet 1] from source_index to Prompt, that's the one built above
        content = '[{"question": "How long is the GTE-3000 warranty?", "ground_truth": "24 months", "source_index": 1}]'

    class FakeModel:
        async def ainvoke(self, prompt):
            return FakeReply()

    async def fake_load_enabled(model_type):
        return object()

    monkeypatch.setattr(model_factory, "load_enabled", fake_load_enabled)
    monkeypatch.setattr(model_factory, "build_chat_model", lambda config, temperature=0.0: FakeModel())

    created = await eval_dataset_service.generate_from_document(dataset.id, doc.id, 5)
    assert created == 1

    case = await EvalCase.filter(dataset_id=dataset.id).first()
    assert case.source == "Generated from document"
    assert case.reference_chunk_ids == str(chunk.id)
    assert case.enabled == "Yes"

    await KnowledgeChunk.filter(kb_id=kb.id).delete()
    await KnowledgeDocument.filter(id=doc.id).delete()
    await KnowledgeBase.filter(id=kb.id).delete()


async def test_generate_without_chunks_is_rejected(dataset):
    """The document does not provide a hint when the minutes have been cut."""
    kb = await KnowledgeBase.create(name="Vacabulary-module testing", status="Active")
    doc = await KnowledgeDocument.create(kb_id=kb.id, name="Document without splitting.txt")

    with pytest.raises(Exception) as excinfo:
        await eval_dataset_service.generate_from_document(dataset.id, doc.id, 5)
    assert "please parse and split first" in str(excinfo.value)

    await KnowledgeDocument.filter(id=doc.id).delete()
    await KnowledgeBase.filter(id=kb.id).delete()


async def test_convert_from_feedback(dataset):
    """The point-step sedimentation is used, the standard answer is left blank and the default deactivated, with feedback marked as deposited."""
    app = await QaApp.create(name="Application for sediment testing - module test", app_code="unittestcv0001", status="Active")
    session = await ChatSession.create(session_no="unittestcvsession", app_id=app.id)
    await ChatMessage.create(session_id=session.id, role="user", content="How long do you think the refunds will be paid?")
    answer = await ChatMessage.create(session_id=session.id, role="assistant", content="I don't know.")
    admin = await User.get_or_none(username="admin")
    feedback = await MessageFeedback.create(
        message_id=answer.id, user_id=admin.id, feedback_type="Dislike", reason="No answer."
    )

    created = await eval_dataset_service.convert_from_feedback(dataset.id)
    assert created >= 1

    case = await EvalCase.filter(dataset_id=dataset.id, source="From feedback").first()
    assert case.question == "How long do you think the refunds will be paid?"
    # Standard answers will be filled manually before they are enabled.
    assert case.ground_truth == ""
    assert case.enabled == "No"
    assert "From feedback" in case.remark

    # The feedback is marked as deposited. Next time, it won't be repeated.
    refreshed = await MessageFeedback.get_or_none(id=feedback.id)
    assert refreshed.converted == "Yes"

    await MessageFeedback.filter(id=feedback.id).delete()
    await ChatMessage.filter(session_id=session.id).delete()
    await ChatSession.filter(id=session.id).delete()
    await QaApp.filter(id=app.id).delete()


async def test_convert_without_pending_is_rejected(dataset):
    """Give a hint when there are no points to be deposited."""
    await MessageFeedback.filter(feedback_type="Dislike", converted="No").update(converted="Yes")
    with pytest.raises(Exception) as excinfo:
        await eval_dataset_service.convert_from_feedback(dataset.id)
    assert "No pending clicked issues to accumulate" in str(excinfo.value)


async def test_generated_cases_reference_only_their_own_chunk(dataset, monkeypatch):
    """Each example is only a piece of your own I.D., not all the pieces of the entire document.

    Context Recall is "Aimed Reference Snippet / All Reference Snippet".
    If the whole document is taken as a reference, the answer is only in one paragraph.
    And you ask to recall the whole story to be a good point, and the denominator is big enough, so that's an indicator that never goes up.
    Top_k=5 with 9 periods in the document, the highest theoretical score is only 5/9.
    """
    kb = await KnowledgeBase.create(name=f"{TEST_MARK} - Source library", status="Active")
    doc = await KnowledgeDocument.create(kb_id=kb.id, name="Multisession documents.txt")
    chunks = []
    for index, text in enumerate(["24 months of integrity.", "Power adaptor warranty for 12 months.", "Reimbursable maintenance warranty for 3 months."]):
        chunks.append(
            await KnowledgeChunk.create(
                kb_id=kb.id, document_id=doc.id, chunk_index=index,
                chunk_type="Standard chunk", content=text, char_count=len(text),
            )
        )

    class FakeReply:
        # 3 questions and answers from paragraphs 1, 2 and 3, respectively
        content = (
            '[{"question": "How long is the device warranty?", "ground_truth": "24 months", "source_index": 1},'
            ' {"question": "How long is the adapter warranty?", "ground_truth": "12 months", "source_index": 2},'
            ' {"question": "How long is the paid repair warranty?", "ground_truth": "3 months", "source_index": 3}]'
        )

    class FakeModel:
        async def ainvoke(self, prompt):
            return FakeReply()

    async def fake_load_enabled(model_type):
        return object()

    monkeypatch.setattr(model_factory, "load_enabled", fake_load_enabled)
    monkeypatch.setattr(model_factory, "build_chat_model", lambda config, temperature=0.0: FakeModel())

    await eval_dataset_service.generate_from_document(dataset.id, doc.id, 3)
    cases = await EvalCase.filter(dataset_id=dataset.id).order_by("id")

    references = [case.reference_chunk_ids for case in cases]
    # Three examples point to each of the same pieces, not all.
    assert references == [str(chunks[0].id), str(chunks[1].id), str(chunks[2].id)]
    # Each one is a single piece, not the whole three.
    assert all("," not in item for item in references)


async def test_generated_case_without_source_index_leaves_reference_empty(dataset, monkeypatch):
    """The model is left blank when it has no indication of the source, allowing Context Recall to return to semantic judgement.

    It's better to leave space than to remember a series of wrong pieces: the wrong reference will calculate a fraction that looks normal and is not meaningful.
    """
    kb = await KnowledgeBase.create(name=f"{TEST_MARK} - Library without source labels", status="Active")
    doc = await KnowledgeDocument.create(kb_id=kb.id, name="No source label.txt")
    await KnowledgeChunk.create(
        kb_id=kb.id, document_id=doc.id, chunk_index=0,
        chunk_type="Standard chunk", content="24 months of integrity.", char_count=12,
    )

    class FakeReply:
        # The model is not obeying. It's not giving source_index.
        content = '[{"question": "How long is the device warranty?", "ground_truth": "24 months"}]'

    class FakeModel:
        async def ainvoke(self, prompt):
            return FakeReply()

    async def fake_load_enabled(model_type):
        return object()

    monkeypatch.setattr(model_factory, "load_enabled", fake_load_enabled)
    monkeypatch.setattr(model_factory, "build_chat_model", lambda config, temperature=0.0: FakeModel())

    await eval_dataset_service.generate_from_document(dataset.id, doc.id, 1)
    case = await EvalCase.filter(dataset_id=dataset.id).first()
    assert case.reference_chunk_ids is None
