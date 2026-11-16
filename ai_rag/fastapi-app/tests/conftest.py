"""Test the public kit.

The login is obtained at one time by the administrator token, and the subsequent chapters are tested using it to adjust protected interfaces.

Operating premises: MySQL started and implemented ai_rag.sql.

The test runs directly into the development library, where the knowledge base, evaluation and question-and-answer applications are kept.
If you don't clean it, run a few rounds down, and there are dozens of "test XX-module tests" in the real data on the page.
This document ends with an auto-cleaning kit, which is collected by name.
"""

import asyncio
import sys

import pytest
from fastapi.testclient import TestClient
from tortoise import Tortoise

from main import app
from settings import TORTOISE_ORM

# Tests the uniform suffix of data. When you write a new one, every name that will be stored is brought with it.
# Once you've run, the clip below will be removed automatically.
TEST_MARK = "Unit test fixture"


@pytest.fixture()
async def db():
    """Links to databases used for asymmetric testing.

    Tests to walk the interface are connected by TestCliet;
    The asymmetric test to directly adjust the service or ai layer function does not walk an interface, and you must initialize Tortoise.
    """
    await Tortoise.init(config=TORTOISE_ORM)
    from service.job_recovery_service import migrate_task_context
    await migrate_task_context()
    yield
    await Tortoise.close_connections()


@pytest.fixture()
def client():
    """Test client with a life cycle, access to the database on time and release connections upon exit."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def admin_headers(client):
    """Log in the administrator account in the initialised data and return to the request with token."""
    response = client.post("/login", json={"username": "admin", "password": "admin"})
    body = response.json()
    assert body["code"] == "200", "Administrator login failed, confirm that one_rag.sql has been executed and the password has not been changed"
    return {"token": body["data"]["token"]}


async def _sweep() -> dict:
    """Recover the test data by name and return how many entries have been deleted from each table.

    The order of deletions is from the first and second tabloids: delete the clips before deleting the document, and then delete the knowledge base.
    In turn, the main list is missing and the dependent table becomes a figure for orphans that cannot be traced.
    """
    await Tortoise.init(config=TORTOISE_ORM)
    from models import (
        AiModelConfig,
        ChatMessage,
        ChatSession,
        ChunkStrategy,
        EvalCase,
        EvalCaseResult,
        EvalDataset,
        EvalReport,
        EvalTask,
        FunctionTool,
        KnowledgeBase,
        KnowledgeChunk,
        KnowledgeDocument,
        MessageFeedback,
        MessageReference,
        PromptTemplate,
        QaApp,
        QaAppKb,
        RetrievalStrategy,
    )

    removed: dict[str, int] = {}

    async def drop(model, **filters):
        count = await model.filter(**filters).count()
        if count:
            await model.filter(**filters).delete()
            removed[model.__name__] = removed.get(model.__name__, 0) + count

    # Knowledge base: first snippets, then files, last library itself
    kb_ids = [item.id for item in await KnowledgeBase.filter(name__contains=TEST_MARK)]
    if kb_ids:
        await drop(KnowledgeChunk, kb_id__in=kb_ids)
        await drop(KnowledgeDocument, kb_id__in=kb_ids)
        await drop(QaAppKb, kb_id__in=kb_ids)
        await drop(KnowledgeBase, id__in=kb_ids)

    # Assessment set: use of examples, tasks, results and reports under the mandate, with final evaluation package
    dataset_ids = [item.id for item in await EvalDataset.filter(name__contains=TEST_MARK)]
    if dataset_ids:
        task_ids = [item.id for item in await EvalTask.filter(dataset_id__in=dataset_ids)]
        if task_ids:
            await drop(EvalCaseResult, task_id__in=task_ids)
            await drop(EvalReport, task_id__in=task_ids)
            await drop(EvalTask, id__in=task_ids)
        await drop(EvalCase, dataset_id__in=dataset_ids)
        await drop(EvalDataset, id__in=dataset_ids)

    # Question and answer application: Sessions, messages, references, feedback, final application
    app_ids = [item.id for item in await QaApp.filter(name__contains=TEST_MARK)]
    if app_ids:
        session_ids = [item.id for item in await ChatSession.filter(app_id__in=app_ids)]
        if session_ids:
            message_ids = [item.id for item in await ChatMessage.filter(session_id__in=session_ids)]
            if message_ids:
                await drop(MessageReference, message_id__in=message_ids)
                await drop(MessageFeedback, message_id__in=message_ids)
                await drop(ChatMessage, id__in=message_ids)
            await drop(ChatSession, id__in=session_ids)
        await drop(QaAppKb, app_id__in=app_ids)
        await drop(QaApp, id__in=app_ids)

    # There's no secondary data left. Delete it by name.
    for model in (ChunkStrategy, RetrievalStrategy, AiModelConfig, PromptTemplate):
        await drop(model, name__contains=TEST_MARK)
    # The list name is a tool_name, not a name
    await drop(FunctionTool, tool_name__contains=TEST_MARK)
    # The document may not be attached to the test library (for example, it was only built without a store)
    await drop(KnowledgeDocument, name__contains=TEST_MARK)

    await Tortoise.close_connections()
    return removed


@pytest.fixture(scope="session", autouse=True)
def sweep_test_data():
    """Once the test has run out, the test data is cleared from the development library.

    Autouse indicates that it is not quoted in any test display, and the whole session automatically takes effect;
    Yield did nothing before cleaning it up, so that did not affect the execution of the test itself.
    """
    yield
    # Event loop is closed,
    # Same as the main. py, replace with a Selector Event Loop
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    removed = asyncio.run(_sweep(), loop_factory=loop_factory)
    if removed:
        detail = ", ".join(f"{name} {count} items" for name, count in removed.items())
        print(f"\n [test data cleaning] {detail}")


@pytest.fixture(autouse=True)
def isolated_uploads(tmp_path, monkeypatch):
    from service import file_service
    monkeypatch.setattr(file_service, "UPLOAD_DIR", str(tmp_path))
    # Existing parser fixtures refer to their module's imported directory.
    for module in list(sys.modules.values()):
        if getattr(module, "__name__", "").startswith("test_") and hasattr(module, "UPLOAD_DIR"):
            monkeypatch.setattr(module, "UPLOAD_DIR", str(tmp_path))

def pytest_sessionstart(session):
    """Prevent the regression suite from modifying a normal app database."""
    from settings import PGVECTOR
    name = TORTOISE_ORM["connections"]["default"]["credentials"]["database"]
    if not name.endswith(("_test", "_check")) or not PGVECTOR["database"].endswith(("_test", "_check")):
        raise pytest.UsageError("Import seeds into dedicated *_test or *_check databases and set MYSQL_DATABASE / PGDATABASE before running tests.")
