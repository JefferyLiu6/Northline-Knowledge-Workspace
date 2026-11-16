"""Question and answer applications with multiple question and answer tests.

Applying the configured CRUDs are all directly measurable; retrieval and model calls in flow-based question-and-answer sessions are replaced with false realizations.
The validation was for sessions, messages, the storage of reference sources and spin-off branches.
"""

import json

import pytest

from ai import model_factory
from models import ChatMessage, ChatSession, KnowledgeBase, MessageReference, QaApp, QaAppKb
from service import chat_service, retrieval_service

APP_NAME = "Test question and answer application -- module test exclusively"
KB_NAME = "Test quiz-module test exclusively"


@pytest.fixture()
async def qa_env(db):
    """Build a knowledge base and a question-and-answer application with it."""
    kb = await KnowledgeBase.create(name=KB_NAME, status="Active")
    app = await QaApp.create(
        name=APP_NAME,
        app_code="unittestcode01",
        prompt_code="RAG_ANSWER",
        agent_enabled="No",
        max_history=4,
        empty_answer="No relevant content was found in the knowledge base.",
        status="Active",
    )
    await QaAppKb.create(app_id=app.id, kb_id=kb.id)

    yield {"kb": kb, "app": app}

    sessions = await ChatSession.filter(app_id=app.id)
    session_ids = [item.id for item in sessions]
    messages = await ChatMessage.filter(session_id__in=session_ids)
    await MessageReference.filter(message_id__in=[item.id for item in messages]).delete()
    await ChatMessage.filter(session_id__in=session_ids).delete()
    await ChatSession.filter(app_id=app.id).delete()
    await QaAppKb.filter(app_id=app.id).delete()
    await QaApp.filter(id=app.id).delete()
    await KnowledgeBase.filter(id=kb.id).delete()


class FakeChunk:
    def __init__(self, content):
        self.content = content


class FakeStreamModel:
    """A false model of a word-to-word vomiting is used to verify the flow fractions."""

    def __init__(self, text):
        self.text = text

    async def astream(self, prompt):
        for char in self.text:
            yield FakeChunk(char)


@pytest.fixture()
def fake_chain(monkeypatch):
    """Both the search and dialogue models were replaced by false ones."""
    holder = {"results": [], "answer": "The duration of the guarantee period is 24 months."}

    async def fake_retrieve(kb_ids, query, strategy, document_ids=None, history=None):
        return {
            "query": query,
            "queries": [query],
            "strategy_id": strategy["id"],
            "strategy_name": strategy["name"],
            "results": holder["results"],
            "stages": [],
            "cost_millis": 1,
        }

    async def fake_load_enabled(model_type):
        return object()

    def fake_build(config, temperature=0.0):
        return FakeStreamModel(holder["answer"])

    monkeypatch.setattr(retrieval_service, "retrieve", fake_retrieve)
    monkeypatch.setattr(model_factory, "load_enabled", fake_load_enabled)
    monkeypatch.setattr(model_factory, "build_chat_model", fake_build)

    def setup(results=None, answer=None):
        if results is not None:
            holder["results"] = results
        if answer is not None:
            holder["answer"] = answer
        return holder

    return setup


async def _collect(session_id, question):
    events = []
    async for event in chat_service.stream_chat(session_id, question, user_id=-1):
        events.append({"event": event["event"], "data": json.loads(event["data"])})
    return events


def test_app_requires_knowledge_base(client, admin_headers):
    """The application must mount at least one knowledge base."""
    body = client.post(
        "/qaApp/add",
        json={"name": "Unlisted Application", "kb_ids": []},
        headers=admin_headers,
    ).json()
    assert body["code"] == "500"
    assert body["msg"] == "Please mount at least one knowledge base"


def test_max_history_range_is_checked(client, admin_headers):
    """History message bar numbers have a range of values."""
    body = client.post(
        "/qaApp/add",
        json={"name": "History is out of range.", "kb_ids": [1], "max_history": 50},
        headers=admin_headers,
    ).json()
    assert body["code"] == "500"
    assert body["msg"] == "Historical message bar values range from 0 to 20"


async def test_open_session_creates_record(qa_env):
    """Make a record of the meeting and the title is empty at this time."""
    outcome = await chat_service.open_session(qa_env["app"].id, user_id=-1)

    session = await ChatSession.get_or_none(id=outcome["session_id"])
    assert session is not None
    assert session.title is None
    assert outcome["app_name"] == APP_NAME


async def test_stream_chat_emits_reference_delta_done(qa_env, fake_chain):
    """A regular question-and-answer series of citations, textual additions and the closing of three types of events."""
    fake_chain(results=[{"chunk_id": 1, "document_id": 1, "score": 0.9, "content": "The duration of the guarantee period is 24 months.", "source": "Vector search"}])
    session = await chat_service.open_session(qa_env["app"].id, user_id=-1)

    events = await _collect(session["session_id"], "How long is the warranty")

    kinds = [item["event"] for item in events]
    assert kinds[0] == "reference"
    assert "delta" in kinds
    assert kinds[-1] == "done"
    # It's a whole set of answers.
    answer = "".join(item["data"]["text"] for item in events if item["event"] == "delta")
    assert answer == "The duration of the guarantee period is 24 months."


async def test_messages_and_references_are_saved(qa_env, fake_chain):
    """The questions and answers were given in one piece, citing a snapshot of the content."""
    fake_chain(results=[{"chunk_id": 7, "document_id": 3, "score": 0.88, "content": "Quality assurance 24 months.", "source": "Vector search"}])
    session = await chat_service.open_session(qa_env["app"].id, user_id=-1)

    await _collect(session["session_id"], "How long is the warranty")

    messages = await chat_service.select_messages(session["session_id"])
    assert [item["role"] for item in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "How long is the warranty"
    assert messages[1]["content"] == "The duration of the guarantee period is 24 months."
    assert messages[1]["finish_reason"] == "Answered"
    # The source of the quote is hanging from the answer to that message.
    assert len(messages[1]["references"]) == 1
    assert messages[1]["references"][0]["chunk_id"] == 7
    assert messages[1]["references"][0]["content"] == "Quality assurance 24 months."


async def test_session_title_comes_from_first_question(qa_env, fake_chain):
    """The title of the session will be taken as a first question."""
    fake_chain(results=[{"chunk_id": 1, "content": "Contents", "source": "Vector search"}])
    session = await chat_service.open_session(qa_env["app"].id, user_id=-1)

    await _collect(session["session_id"], "First question.")
    await _collect(session["session_id"], "Second question.")

    record = await ChatSession.get_or_none(id=session["session_id"])
    assert record.title == "First question."
    # Four messages: two questions.
    assert record.message_count == 4


async def test_empty_recall_uses_fallback_answer(qa_env, fake_chain):
    """When the information is not retrieved, the configuration of the ploy is applied and models are not made up."""
    fake_chain(results=[])
    session = await chat_service.open_session(qa_env["app"].id, user_id=-1)

    events = await _collect(session["session_id"], "Where's the company's annual meeting?")

    kinds = [item["event"] for item in events]
    # No reference event
    assert "reference" not in kinds
    answer = "".join(item["data"]["text"] for item in events if item["event"] == "delta")
    assert answer == "No relevant content was found in the knowledge base."

    messages = await chat_service.select_messages(session["session_id"])
    assert messages[1]["finish_reason"] == "No retrieval"
    assert messages[1]["references"] == []


async def test_disabled_app_is_rejected(qa_env, fake_chain):
    """The application is disabled and cannot be used for further meetings."""
    await QaApp.filter(id=qa_env["app"].id).update(status="Disabled")
    with pytest.raises(Exception) as excinfo:
        await chat_service.open_session(qa_env["app"].id, user_id=-1)
    assert "disabled" in str(excinfo.value)


async def test_app_without_usable_kb_is_rejected(qa_env, fake_chain):
    """Gives a human voice hint when all the knowledge repositories are disabled on board."""
    await KnowledgeBase.filter(id=qa_env["kb"].id).update(status="Disabled")
    with pytest.raises(Exception) as excinfo:
        await chat_service.open_session(qa_env["app"].id, user_id=-1)
    assert "disabled" in str(excinfo.value)


async def test_empty_question_is_rejected(qa_env, fake_chain):
    """Question is to give a hint when empty."""
    session = await chat_service.open_session(qa_env["app"].id, user_id=-1)
    with pytest.raises(Exception) as excinfo:
        await _collect(session["session_id"], "   ")
    assert "Please enter a question" in str(excinfo.value)


async def test_history_is_limited(qa_env, fake_chain):
    """The number of historical messages brought into the model is limited by max_history."""
    fake_chain(results=[{"chunk_id": 1, "content": "Contents", "source": "Vector search"}])
    session = await chat_service.open_session(qa_env["app"].id, user_id=-1)
    for index in range(5):
        await _collect(session["session_id"], f"Step {index} Question rewrite")

    history = await chat_service._load_history(session["session_id"], qa_env["app"].max_history)
    assert len(history) == qa_env["app"].max_history
    # The most recent ones, not the first.
    assert history[-1]["content"] == "The duration of the guarantee period is 24 months."

class FakeUser:
    """Only the id and roll fields are fake users, enough to be judged by aset_session_access."""

    def __init__(self, user_id, role="USER"):
        self.id = user_id
        self.role = role


async def test_other_user_cannot_access_session(qa_env):
    """General users do not have access to another person ' s session, and user-and management interfaces are shared, which is the only intercept point."""
    session = await chat_service.open_session(qa_env["app"].id, user_id=1001, source="User portal")

    with pytest.raises(Exception) as excinfo:
        await chat_service.assert_session_access(session["session_id"], FakeUser(1002))
    assert "No permission to access this session" in str(excinfo.value)


async def test_owner_and_admin_can_access_session(qa_env):
    """The session itself is accessible to the administrator, who also has access to all sessions of the dialogue log."""
    session = await chat_service.open_session(qa_env["app"].id, user_id=1001, source="User portal")

    owner_view = await chat_service.assert_session_access(session["session_id"], FakeUser(1001))
    admin_view = await chat_service.assert_session_access(
        session["session_id"], FakeUser(9999, role="ADMIN")
    )
    assert owner_view.id == session["session_id"]
    assert admin_view.id == session["session_id"]


async def test_delete_session_removes_messages_and_references(qa_env, fake_chain):
    """Deleting messages is cleared with reference sources and no dirty data on belongings are left untraceable."""
    fake_chain(results=[{"chunk_id": 1, "content": "Contents", "source": "Vector search"}])
    session = await chat_service.open_session(qa_env["app"].id, user_id=1001, source="User portal")
    session_id = session["session_id"]
    await _collect(session_id, "How long is it going to be?")
    message_ids = [item.id for item in await ChatMessage.filter(session_id=session_id)]
    assert message_ids
    assert await MessageReference.filter(message_id__in=message_ids).count() > 0

    await chat_service.delete_session(session_id, FakeUser(1001))

    assert await ChatSession.filter(id=session_id).count() == 0
    assert await ChatMessage.filter(session_id=session_id).count() == 0
    assert await MessageReference.filter(message_id__in=message_ids).count() == 0


async def test_delete_session_rejects_other_user(qa_env):
    """Others ' sessions cannot be deleted, and attributions and readings are shared in the same section."""
    session = await chat_service.open_session(qa_env["app"].id, user_id=1001, source="User portal")

    with pytest.raises(Exception) as excinfo:
        await chat_service.delete_session(session["session_id"], FakeUser(1002))
    assert "No permission to access this session" in str(excinfo.value)

