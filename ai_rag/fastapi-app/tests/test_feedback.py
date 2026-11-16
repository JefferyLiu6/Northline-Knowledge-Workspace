"""Dialogue log and user feedback testing."""

import pytest

from models import ChatMessage, ChatSession, MessageFeedback, QaApp, QaAppKb, User
from service import feedback_service

APP_NAME = "Test feedback application -- module test exclusively"


@pytest.fixture()
async def feedback_env(db):
    """Create an application, a session, answer questions and delete them."""
    app = await QaApp.create(name=APP_NAME, app_code="unittestfb0001", status="Active")
    session = await ChatSession.create(session_no="unittestfbsession", app_id=app.id, title="How long is the warranty")
    question = await ChatMessage.create(session_id=session.id, role="user", content="How long is the warranty")
    answer = await ChatMessage.create(session_id=session.id, role="assistant", content="Quality assurance 24 months.")
    admin = await User.get_or_none(username="admin")

    yield {"app": app, "session": session, "question": question, "answer": answer, "admin": admin}

    await MessageFeedback.filter(message_id__in=[question.id, answer.id]).delete()
    await ChatMessage.filter(session_id=session.id).delete()
    await ChatSession.filter(id=session.id).delete()
    await QaAppKb.filter(app_id=app.id).delete()
    await QaApp.filter(id=app.id).delete()


async def test_submit_creates_feedback(feedback_env):
    """The pedals leave a record of feedback, and the default is not yet measured."""
    await feedback_service.submit(feedback_env["admin"], feedback_env["answer"].id, "Dislike", "Off-topic answer")

    record = await MessageFeedback.get_or_none(message_id=feedback_env["answer"].id)
    assert record.feedback_type == "Dislike"
    assert record.reason == "Off-topic answer"
    assert record.converted == "No"


async def test_second_submit_overwrites(feedback_env):
    """The same person changed his mind to cover the last time, without leaving two."""
    await feedback_service.submit(feedback_env["admin"], feedback_env["answer"].id, "Dislike", "Off-topic answer")
    await feedback_service.submit(feedback_env["admin"], feedback_env["answer"].id, "Like", None)

    records = await MessageFeedback.filter(message_id=feedback_env["answer"].id)
    assert len(records) == 1
    assert records[0].feedback_type == "Like"
    assert records[0].reason is None


async def test_feedback_on_question_is_rejected(feedback_env):
    """It would be pointless to give credit for the questions that had been asked."""
    with pytest.raises(Exception) as excinfo:
        await feedback_service.submit(feedback_env["admin"], feedback_env["question"].id, "Like", None)
    assert "You can only give feedback on the answers." in str(excinfo.value)


async def test_invalid_feedback_type_is_rejected(feedback_env):
    """The type of feedback only allows for praise and stepping."""
    with pytest.raises(Exception) as excinfo:
        await feedback_service.submit(feedback_env["admin"], feedback_env["answer"].id, "Whatever.", None)
    assert "Wrong parameter for feedback type" in str(excinfo.value)


async def test_select_by_message_groups_counts(feedback_env):
    """Take feedback based on a batch of messages and return to the number of punctuations per item."""
    await feedback_service.submit(feedback_env["admin"], feedback_env["answer"].id, "Like", None)

    grouped = await feedback_service.select_by_message([feedback_env["answer"].id])
    assert grouped[feedback_env["answer"].id]["Like"] == 1
    assert grouped[feedback_env["answer"].id]["Dislike"] == 0


async def test_select_page_carries_question_and_answer(feedback_env):
    """The feedback list contains the corresponding questions and answers, which are not used to jump back into sessions."""
    await feedback_service.submit(feedback_env["admin"], feedback_env["answer"].id, "Dislike", "Off-topic answer")

    page = await feedback_service.select_page(feedback_type="Dislike", page_num=1, page_size=10)
    target = [item for item in page.list if item["message_id"] == feedback_env["answer"].id][0]
    assert target["question"] == "How long is the warranty"
    assert target["answer"] == "Quality assurance 24 months."
    assert target["converted"] == "No"


async def test_summary_counts_pending_convert(feedback_env):
    """The statistics in the overview do not yet account for the number of points on which to evaluate."""
    await feedback_service.submit(feedback_env["admin"], feedback_env["answer"].id, "Dislike", None)

    stats = await feedback_service.summary()
    assert stats["disliked"] >= 1
    assert stats["pending_convert"] >= 1
    assert stats["satisfaction"] is not None


async def test_sessions_carry_dislike_count(feedback_env):
    """The dialogue log list shows that each session is counted several times."""
    await feedback_service.submit(feedback_env["admin"], feedback_env["answer"].id, "Dislike", None)

    page = await feedback_service.select_sessions_with_app(app_id=feedback_env["app"].id, page_num=1, page_size=10)
    target = [item for item in page.list if item["id"] == feedback_env["session"].id][0]
    assert target["app_name"] == APP_NAME
    assert target["dislike_count"] == 1
    assert target["title"] == "How long is the warranty"

class FakeUser:
    """Only fake users with id and roll are checked for use."""

    def __init__(self, user_id, role="USER"):
        self.id = user_id
        self.role = role


async def test_other_user_cannot_feedback(feedback_env):
    """Sessions cannot be scored when they are not themselves, and feedback data should then settle as an example of measurement."""
    await ChatSession.filter(id=feedback_env["session"].id).update(user_id=1001)

    with pytest.raises(Exception) as excinfo:
        await feedback_service.submit(FakeUser(1002), feedback_env["answer"].id, "Like", None)
    assert "permission to provide feedback" in str(excinfo.value)


async def test_select_by_message_marks_my_feedback(feedback_env):
    """When using_id, the person is brought back to his own point type and the user turns the history dialogue with it filling the button."""
    await feedback_service.submit(feedback_env["admin"], feedback_env["answer"].id, "Dislike", None)

    grouped = await feedback_service.select_by_message(
        [feedback_env["answer"].id], feedback_env["admin"].id
    )
    assert grouped[feedback_env["answer"].id]["mine"] == "Dislike"
