"""Dialogue log and user feedback.

The pedals are the most valuable kind of data in this project: users say "this answer is not right."
And these are the most useful things for the knowledge base. Chapter 27 will take them as an example of how to measure them.
"""

from typing import List

from common.exception_handler import CustomException
from common.result import PageInfo
from models import ChatMessage, ChatSession, MessageFeedback, QaApp, User

FEEDBACK_TYPES = {"Like", "Dislike"}


async def submit(current_user: User, message_id: int | None, feedback_type: str, reason: str | None) -> None:
    """Provides feedback. The same message retains only one person ' s last response."""
    if message_id is None:
        raise CustomException("Message ID cannot be empty")
    if feedback_type not in FEEDBACK_TYPES:
        raise CustomException("Wrong parameter for feedback type")
    message = await ChatMessage.get_or_none(id=message_id)
    if message is None:
        raise CustomException("Can not get message: %s %s")
    # It doesn't make any sense to give a compliment to your question.
    if message.role != "assistant":
        raise CustomException("You can only give feedback on the answers.")
    # You can only score your answer in a session.
    # If you change the number, you can get feedback from someone else's conversation and then the feedback data settles into an evaluation.
    if current_user.role != "ADMIN":
        session = await ChatSession.get_or_none(id=message.session_id)
        if session is None or session.user_id != current_user.id:
            raise CustomException("You do not have permission to provide feedback on this answer.")
    existing = await MessageFeedback.get_or_none(message_id=message_id, user_id=current_user.id)
    if existing is not None:
        # User changed his mind and covered the last time; agreed remained unchanged, already deposited non-repeated sedimentation
        await MessageFeedback.filter(id=existing.id).update(
            feedback_type=feedback_type, reason=reason
        )
        return
    await MessageFeedback.create(
        message_id=message_id,
        user_id=current_user.id,
        feedback_type=feedback_type,
        reason=reason,
    )


async def select_by_message(message_ids: List[int], user_id: int | None = None) -> dict:
    """Take feedback from the message ID batch, and each answer is marked with its current pedal status.

    The user_id text adds one more mine field to each one, the value of which is the person 's own type.
    When the user turns to historical dialogue, it uses it to re-flame its own branding/stamp.
    """
    if not message_ids:
        return {}
    feedbacks = await MessageFeedback.filter(message_id__in=message_ids)
    grouped: dict[int, dict] = {}
    for item in feedbacks:
        stats = grouped.setdefault(item.message_id, {"Like": 0, "Dislike": 0, "mine": ""})
        stats[item.feedback_type] = stats.get(item.feedback_type, 0) + 1
        if user_id is not None and item.user_id == user_id:
            stats["mine"] = item.feedback_type
    return grouped


async def select_page(
    feedback_type: str = "",
    converted: str = "",
    page_num: int = 1,
    page_size: int = 10,
) -> PageInfo:
    """. Brings the corresponding questions and answers, which are not used by managers to jump back into a session."""
    query = MessageFeedback.all()
    if feedback_type:
        query = query.filter(feedback_type=feedback_type)
    if converted:
        query = query.filter(converted=converted)
    feedbacks = await query.order_by("-id").offset((page_num - 1) * page_size).limit(page_size)
    total = await query.count()

    message_ids = [item.message_id for item in feedbacks]
    messages = await ChatMessage.filter(id__in=message_ids)
    message_map = {message.id: message for message in messages}
    # The answer to the last one is the corresponding question, check it out by session and id.
    session_ids = {message.session_id for message in messages}
    all_messages = await ChatMessage.filter(session_id__in=session_ids).order_by("id")
    previous: dict[int, str] = {}
    last_user_content = {}
    for message in all_messages:
        if message.role == "user":
            last_user_content[message.session_id] = message.content
        else:
            previous[message.id] = last_user_content.get(message.session_id, "")

    return PageInfo(
        total=total,
        list=[
            {
                "id": item.id,
                "message_id": item.message_id,
                "feedback_type": item.feedback_type,
                "reason": item.reason,
                "converted": item.converted,
                "question": previous.get(item.message_id, ""),
                "answer": message_map[item.message_id].content if item.message_id in message_map else "",
                "create_time": item.create_time,
            }
            for item in feedbacks
        ],
    )


async def summary() -> dict:
    """Overview of feedback to overall satisfaction."""
    liked = await MessageFeedback.filter(feedback_type="Like").count()
    disliked = await MessageFeedback.filter(feedback_type="Dislike").count()
    pending = await MessageFeedback.filter(feedback_type="Dislike", converted="No").count()
    total = liked + disliked
    return {
        "liked": liked,
        "disliked": disliked,
        # The number of points that have not yet been settled into the assessment case is the stock to be dealt with in Chapter 27.
        "pending_convert": pending,
        # A 100 per cent response is not always available, so avoid misunderstandings.
        "satisfaction": round(liked / total * 100, 1) if total else None,
    }


async def select_sessions_with_app(
    app_id: int | None = None,
    keyword: str = "",
    page_num: int = 1,
    page_size: int = 10,
) -> PageInfo:
    """dialogue log list. Brings the application name and feedback from this dialogue."""
    query = ChatSession.all()
    if app_id:
        query = query.filter(app_id=app_id)
    if keyword:
        query = query.filter(title__contains=keyword)
    sessions = await query.order_by("-id").offset((page_num - 1) * page_size).limit(page_size)
    total = await query.count()

    app_ids = {item.app_id for item in sessions}
    apps = await QaApp.filter(id__in=list(app_ids))
    app_map = {app.id: app.name for app in apps}

    session_ids = [item.id for item in sessions]
    messages = await ChatMessage.filter(session_id__in=session_ids, role="assistant")
    message_ids = [message.id for message in messages]
    feedbacks = await MessageFeedback.filter(message_id__in=message_ids)
    message_session = {message.id: message.session_id for message in messages}
    # The statistics show that each session was called several times in praise and a few times on foot.
    # You have to give priority to the high-stamp session; you can put a nice number on it so you can see if anyone's been back in this conversation.
    like_count: dict[int, int] = {}
    # Counting how many times each session is stomped and priority given to a lot of sessions.
    dislike_count: dict[int, int] = {}
    for feedback in feedbacks:
        session_id = message_session.get(feedback.message_id)
        if not session_id:
            continue
        if feedback.feedback_type == "Dislike":
            dislike_count[session_id] = dislike_count.get(session_id, 0) + 1
        elif feedback.feedback_type == "Like":
            like_count[session_id] = like_count.get(session_id, 0) + 1

    return PageInfo(
        total=total,
        list=[
            {
                "id": item.id,
                "session_no": item.session_no,
                "app_id": item.app_id,
                "app_name": app_map.get(item.app_id),
                "title": item.title,
                "message_count": item.message_count,
                "source": item.source,
                "like_count": like_count.get(item.id, 0),
                "dislike_count": dislike_count.get(item.id, 0),
                "create_time": item.create_time,
            }
            for item in sessions
        ],
    )
