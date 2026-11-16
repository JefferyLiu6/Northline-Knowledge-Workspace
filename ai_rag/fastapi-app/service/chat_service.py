"""Multi-turn Q&A.

Both modes share the same session, message, and reference source storage logic, differing only in the middle part:

    agent_enabled = No   Follow the straight chain of Chapters 15-19: retrieve once → stream generation
    agent_enabled = Yes   Follow the state graph of Chapter 22: the model decides whether to re-retrieve

Stream output uses SSE. The events received by the frontend have four types:
    reference  Reference source, sent before the main text to allow the page to render the source first
    progress   State graph node progress, only sent in Agentic mode, allowing the page to display the current progress
    delta      Text increment, outputting one character at a time
    done       End, including message ID and duration, allowing the frontend to perform likes and dislikes
"""

import asyncio
import json
import uuid
from typing import AsyncGenerator

from ai import model_factory, prompt_loader
from ai.graph import build_context
from common.exception_handler import CustomException
from common.times import cost_millis, now
from models import (
    ChatMessage,
    ChatSession,
    KnowledgeBase,
    MessageFeedback,
    MessageReference,
    QaApp,
    QaAppKb,
)
from service import agent_service, retrieval_service

ERROR_MAX_LENGTH = 500


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _event(event_type: str, payload: dict) -> dict:
    """Assemble an SSE event. sse-starlette sends it out with two keys: event and data."""
    return {"event": event_type, "data": _dump(payload)}


async def _load_app(app_id: int) -> tuple[QaApp, list[int]]:
    app = await QaApp.get_or_none(id=app_id)
    if app is None:
        raise CustomException("Q&A app not found")
    if app.status != "Active":
        raise CustomException("This application has been disabled")
    relations = await QaAppKb.filter(app_id=app_id)
    kb_ids = [item.kb_id for item in relations]
    if not kb_ids:
        raise CustomException("This application has not mounted a knowledge base; please configure it first in the Q&A application")
    # Disabled knowledge base does not participate in searching
    bases = await KnowledgeBase.filter(id__in=kb_ids, status="Active")
    usable = [kb.id for kb in bases]
    if not usable:
        raise CustomException("All knowledge bases mounted by this application have been disabled")
    return app, usable


async def open_session(app_id: int, user_id: int | None, source: str = "Admin portal") -> dict:
    """Create a new session. The frontend calls it before the user sends the first message."""
    app, _ = await _load_app(app_id)
    session = await ChatSession.create(
        session_no=uuid.uuid4().hex,
        app_id=app.id,
        user_id=user_id,
        source=source,
    )
    return {"session_id": session.id, "session_no": session.session_no, "app_name": app.name}


async def assert_session_access(session_id: int, user) -> ChatSession:
    """Retrieve the session and verify access permissions.

    The user side and management side use the same set of interfaces, with session_id just an incrementing number,
    If you don't check it, read the id and even ask questions in someone else's conversation.
    Administrators need to see all sessions in the conversation log, so only block regular users.
    """
    session = await ChatSession.get_or_none(id=session_id)
    if session is None:
        raise CustomException("Session not found")
    if user is not None and user.role != "ADMIN" and session.user_id != user.id:
        raise CustomException("No permission to access this session")
    return session


async def _load_history(session_id: int, max_history: int) -> list[dict]:
    """Retrieve the latest few rounds of conversation, return in chronological order by time.

    Only retrieve up to max_history entries, too many will bloat context and slow down speed.
    Retrieve by id in reverse order then reverse again to get the "latest few" instead of "earliest few".
    """
    if max_history <= 0:
        return []
    messages = await ChatMessage.filter(session_id=session_id).order_by("-id").limit(max_history)
    return [
        {"role": message.role, "content": message.content or ""}
        for message in reversed(messages)
    ]


async def _save_references(message_id: int, results: list[dict]) -> None:
    """Write the reference source into message_reference.

    Saved as content snapshot: fragments may be modified or deleted later, but the answer the user saw was based on that version.
    """
    for rank, item in enumerate(results, start=1):
        await MessageReference.create(
            message_id=message_id,
            chunk_id=item.get("chunk_id"),
            document_id=item.get("document_id"),
            chunk_content=item.get("content"),
            score=item.get("score"),
            rank_no=rank,
            retrieval_source=item.get("source"),
        )


def _reference_payload(results: list[dict]) -> list[dict]:
    """Return the retrieved passages shown in the expandable source list."""
    return [
        {
            "rank_no": rank,
            "chunk_id": item.get("chunk_id"),
            "document_id": item.get("document_id"),
            "score": item.get("score"),
            "content": item.get("content") or "",
        }
        for rank, item in enumerate(results, start=1)
    ]


async def stream_chat(
    session_id: int,
    question: str,
    user_id: int | None = None,
) -> AsyncGenerator[dict, None]:
    """The complete flow of one Q&A, emit SSE events as it runs."""
    if not question or not question.strip():
        raise CustomException("Please enter a question")
    session = await ChatSession.get_or_none(id=session_id)
    if session is None:
        raise CustomException("Session not found")
    app, kb_ids = await _load_app(session.app_id)
    started = now()

    # The user's message first, even if it fails, the question remains on the record.
    user_message = await ChatMessage.create(
        session_id=session_id, role="user", content=question.strip()
    )
    # The session title takes the first question, and the list page recognizes which conversation this is.
    if not session.title:
        await ChatSession.filter(id=session_id).update(title=question.strip()[:100])

    history = await _load_history(session_id, app.max_history)
    # This one just landed in there, too. Get rid of it. That's the answer to the question.
    history = [item for item in history if item["content"] != question.strip()]

    assistant_message = await ChatMessage.create(session_id=session_id, role="assistant", content="")
    try:
        if app.agent_enabled == "Yes":
            async for event in _run_agent(app, kb_ids, question, history, session, assistant_message, user_id):
                yield event
        else:
            async for event in _run_direct(app, kb_ids, question, history, session, assistant_message):
                yield event
        await ChatSession.filter(id=session_id).update(
            message_count=await ChatMessage.filter(session_id=session_id).count()
        )
        yield _event(
            "done",
            {
                "message_id": assistant_message.id,
                "user_message_id": user_message.id,
                "cost_millis": cost_millis(started),
            },
        )
    except Exception as exc:
        message = exc.message if isinstance(exc, CustomException) else f"Answer Failed:{exc}"
        await ChatMessage.filter(id=assistant_message.id).update(
            error_message=message[:ERROR_MAX_LENGTH],
            cost_millis=cost_millis(started),
        )
        # If you fail, you have to send an incident. Otherwise the front ends are going around all the time.
        yield _event("error", {"message": message})


async def _run_direct(
    app: QaApp,
    kb_ids: list[int],
    question: str,
    history: list[dict],
    session: ChatSession,
    assistant_message: ChatMessage,
) -> AsyncGenerator[dict, None]:
    """Linear pipeline: retrieve once, stream generate."""
    started = now()
    strategy = await retrieval_service.load_strategy(app.retrieval_strategy_id)
    outcome = await retrieval_service.retrieve(kb_ids, question, strategy, history=history)
    results = outcome["results"]

    if not results:
        # If you can't retrieve it, go to the back door. You don't make up models.
        answer = app.empty_answer or "No relevant content was found in the knowledge base."
        await ChatMessage.filter(id=assistant_message.id).update(
            content=answer,
            rewritten_query=outcome["queries"][-1],
            strategy_snapshot=_dump(strategy),
            finish_reason="No retrieval",
            cost_millis=cost_millis(started),
        )
        yield _event("delta", {"text": answer})
        return

    await _save_references(assistant_message.id, results)
    # Quote first. Pages can rewrite the source before it's finished.
    yield _event("reference", {"references": _reference_payload(results)})

    prompt = await prompt_loader.render(
        app.prompt_code or "RAG_ANSWER",
        context=build_context(results),
        question=question,
    )
    config = await model_factory.load_enabled(model_factory.CHAT)
    if app.chat_model_id:
        from models import AiModelConfig

        # Apply the specified model and use the specified model, which is deleted and returned to default
        specified = await AiModelConfig.get_or_none(id=app.chat_model_id)
        if specified is not None:
            config = specified
    model = model_factory.build_chat_model(config)

    pieces = []
    async for chunk in model.astream(prompt):
        text = str(chunk.content or "")
        if not text:
            continue
        pieces.append(text)
        yield _event("delta", {"text": text})
    answer = "".join(pieces)
    await ChatMessage.filter(id=assistant_message.id).update(
        content=answer,
        rewritten_query=outcome["queries"][-1],
        strategy_snapshot=_dump(strategy),
        finish_reason="Answered",
        cost_millis=cost_millis(started),
    )


async def _run_agent(
    app: QaApp,
    kb_ids: list[int],
    question: str,
    history: list[dict],
    session: ChatSession,
    assistant_message: ChatMessage,
    user_id: int | None,
) -> AsyncGenerator[dict, None]:
    """Agentic pipeline: run the state graph, send the answer all at once.

    The state graph needs repeated judgment and retries in the middle, can't determine the final answer while running,
    So this path doesn't do character-by-character streaming, send the answer after the whole segment is done.

    Although the main text can't be streamed, a progress event is sent after each node is completed,
    The page uses it to show progress like "judging if the retrieval is relevant", avoiding waiting for tens of seconds.
    """
    started = now()
    # The status chart runs inside the ainvoke, node echoes can't get straight yield out.
    # Turns the loop back into an event with a queue: move back to Reese, and the following loop is removed and sent to the front end
    progress_queue: asyncio.Queue = asyncio.Queue()

    def on_progress(node: str, name: str, index: int, detail: dict) -> None:
        progress_queue.put_nowait(
            {"node": node, "name": name, "index": index, "detail": detail or {}}
        )

    task = asyncio.create_task(
        agent_service.run(
            kb_ids,
            question,
            user_id=user_id,
            app_id=app.id,
            session_id=session.id,
            history=history,
            on_progress=on_progress,
        )
    )
    # And before the status chart is finished, we'll keep sending out the progress in the queue.
    while not task.done() or not progress_queue.empty():
        try:
            step = await asyncio.wait_for(progress_queue.get(), timeout=0.3)
        except asyncio.TimeoutError:
            continue
        yield _event("progress", step)
    outcome = await task
    references = [
        {
            "chunk_id": item["chunk_id"],
            "document_id": item.get("document_id"),
            "score": item.get("score"),
            "content": item.get("content"),
            "source": "Agentic search",
        }
        for item in outcome["references"]
    ]
    if references:
        await _save_references(assistant_message.id, references)
        yield _event("reference", {"references": _reference_payload(references)})
    # Run a few steps, retrieve several times and send them to the front end. The page shows the workload of Agent
    yield _event(
        "agent",
        {
            "run_id": outcome["run_id"],
            "total_step": outcome["total_step"],
            "retrieve_count": outcome["retrieve_count"],
            "retry_count": outcome["retry_count"],
            "finish_reason": outcome["finish_reason"],
        },
    )
    yield _event("delta", {"text": outcome["answer"]})
    await ChatMessage.filter(id=assistant_message.id).update(
        content=outcome["answer"],
        agent_run_id=outcome["run_id"],
        finish_reason=outcome["finish_reason"],
        cost_millis=cost_millis(started),
    )


async def delete_session(session_id: int, user) -> None:
    """Delete a session, along with its messages, reference sources, and feedback.

    These tables are connected by session_id / message_id, not deleting cleanly will leave
    Unmatched messages and feedback, the conversation log and feedback statistics in Chapter 25 will be polluted.
    Delete in order from the innermost to the outermost: references and feedback are attached to messages, messages are attached to sessions.
    """
    await assert_session_access(session_id, user)
    message_ids = [
        message.id for message in await ChatMessage.filter(session_id=session_id).only("id")
    ]
    if message_ids:
        await MessageReference.filter(message_id__in=message_ids).delete()
        await MessageFeedback.filter(message_id__in=message_ids).delete()
        await ChatMessage.filter(session_id=session_id).delete()
    await ChatSession.filter(id=session_id).delete()


async def select_messages(session_id: int) -> list[dict]:
    """A complete list of messages for a session, including the reference sources for each answer."""
    messages = await ChatMessage.filter(session_id=session_id).order_by("id")
    message_ids = [message.id for message in messages]
    references = await MessageReference.filter(message_id__in=message_ids).order_by("rank_no")
    grouped: dict[int, list] = {}
    for reference in references:
        grouped.setdefault(reference.message_id, []).append(
            {
                "rank_no": reference.rank_no,
                "chunk_id": reference.chunk_id,
                "document_id": reference.document_id,
                "score": float(reference.score) if reference.score is not None else None,
                "content": reference.chunk_content,
            }
        )
    return [
        {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "rewritten_query": message.rewritten_query,
            "agent_run_id": message.agent_run_id,
            "finish_reason": message.finish_reason,
            "error_message": message.error_message,
            "cost_millis": message.cost_millis,
            "create_time": message.create_time,
            "references": grouped.get(message.id, []),
        }
        for message in messages
    ]


async def select_sessions(app_id: int | None = None, user_id: int | None = None, page_num: int = 1, page_size: int = 10):
    """Session List."""
    from common.result import PageInfo

    query = ChatSession.all()
    if app_id:
        query = query.filter(app_id=app_id)
    if user_id:
        query = query.filter(user_id=user_id)
    sessions = await query.order_by("-id").offset((page_num - 1) * page_size).limit(page_size)
    total = await query.count()
    return PageInfo(
        total=total,
        list=[
            {
                "id": item.id,
                "session_no": item.session_no,
                "app_id": item.app_id,
                "title": item.title,
                "message_count": item.message_count,
                "source": item.source,
                "create_time": item.create_time,
            }
            for item in sessions
        ],
    )
