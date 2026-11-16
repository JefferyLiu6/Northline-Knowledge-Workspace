"""Document parsing business logic.

Parsing may involve OCR, taking from hundreds of milliseconds to tens of seconds, the interface can't wait synchronously,
So the interface only creates the task and changes the status to "parsing" before returning, the real parsing runs in the background task.
Refresh the page list to see the latest status.
"""

from common.document_guard import idle_document

import asyncio

from ai import loader
from common.exception_handler import CustomException
from common.times import cost_millis, now
from models import DocumentProcessTask, KnowledgeDocument

# Write upper limit on length of the error_message column, with unusual information from third-party libraries often thousands of words
ERROR_MAX_LENGTH = 500


def _truncate(message: str) -> str:
    return message[:ERROR_MAX_LENGTH]


def _local_path(doc: KnowledgeDocument) -> str:
    """Construct the local path from the disk filename, if the file is gone, parsing is impossible."""
    if not doc.file_name:
        raise CustomException("This document has no associated file, please re-upload")
    from service.file_service import resolve, storage_name
    file_path = resolve(storage_name(doc.file_url))
    return file_path


@idle_document
async def start_parse(doc_id: int) -> int:
    """Validate and set the document to parsing, return the newly created task ID."""
    doc = await KnowledgeDocument.get_or_none(id=doc_id)
    if doc is None:
        raise CustomException("Document not found")
    if doc.parse_status == "Parsing":
        raise CustomException("This document is currently being parsed, please wait")
    # Confirm that the file is still on disk and avoid creating a task before you find out there's no document to resolve.
    _local_path(doc)
    from service.knowledge_document_service import _clear_vectors, _refresh_chunk_count
    from models import KnowledgeChunk
    await _clear_vectors(doc)
    await KnowledgeChunk.filter(document_id=doc_id).delete()
    await _refresh_chunk_count(doc.kb_id)
    await KnowledgeDocument.filter(id=doc_id).update(parsed_text=None, chunk_count=0, vector_status="Pending embedding")
    task = await DocumentProcessTask.create(
        kb_id=doc.kb_id,
        document_id=doc.id,
        task_type="Document parsing",
        task_status="Processing",
        total_count=1,
        start_time=now(),
    )
    # Status is first parsing. Pages are refreshed to see it running and blocking repeat clicks
    await KnowledgeDocument.filter(id=doc_id).update(parse_status="Parsing", parse_error=None)
    return task.id


async def run_parse(doc_id: int, task_id: int) -> None:
    """Background task: actually read the file, write the parsing results."""
    doc = await KnowledgeDocument.get_or_none(id=doc_id)
    if doc is None:
        return
    started = now()
    try:
        file_path = _local_path(doc)
        # Parsing is a clean CPU synchronisation, drop to the thread for execution, and does not block other requests on the event cycle
        outcome = await asyncio.to_thread(loader.parse, file_path, doc.file_type)
        text = outcome.text.strip()
        if not text:
            raise CustomException("No text was parsed, please confirm the file content is not empty")
        await KnowledgeDocument.filter(id=doc_id).update(
            parse_status="Parsed",
            parse_error=None,
            parsed_text=text,
            # Character numbers are the size references before the cut, and chapter 09 estimates how many segments can be cut by it.
            char_count=len(text),
            has_table="Yes" if outcome.has_table else "No",
            has_ocr="Yes" if outcome.has_ocr else "No",
            # Disassemble existing segments and vectors after re-profiling, returning to initial values in quantitative status
            vector_status="Pending embedding",
            chunk_count=0,
        )
        await DocumentProcessTask.filter(id=task_id).update(
            task_status="Completed",
            success_count=1,
            end_time=now(),
            cost_millis=cost_millis(started),
        )
    except Exception as exc:
        # The reason for failure is to be written both in the document and on the list page, as well as in the task record.
        message = exc.message if isinstance(exc, CustomException) else f"Parsing Failed:{exc}"
        await KnowledgeDocument.filter(id=doc_id).update(
            parse_status="Parsing failed",
            parse_error=_truncate(message),
        )
        await DocumentProcessTask.filter(id=task_id).update(
            task_status="Failed",
            fail_count=1,
            error_message=_truncate(message),
            end_time=now(),
            cost_millis=cost_millis(started),
        )


async def select_parsed_text(doc_id: int) -> dict:
    """Review the analysis results for the "View Analysis Text" popup on the page."""
    doc = await KnowledgeDocument.get_or_none(id=doc_id)
    if doc is None:
        raise CustomException("Document not found")
    return {
        "id": doc.id,
        "name": doc.name,
        "parse_status": doc.parse_status,
        "parse_error": doc.parse_error,
        "char_count": doc.char_count,
        "has_table": doc.has_table,
        "has_ocr": doc.has_ocr,
        "parsed_text": doc.parsed_text,
    }


async def select_tasks(document_id: int) -> list[dict]:
    """View the processing task records of a document in reverse chronological order."""
    tasks = await DocumentProcessTask.filter(document_id=document_id).order_by("-id").limit(20)
    return [
        {
            "id": task.id,
            "task_type": task.task_type,
            "task_status": task.task_status,
            "can_retry": task.id == tasks[0].id and task.task_status == "Failed" and task.task_type in {"Document parsing", "Text Splitting", "Embed"},
            "success_count": task.success_count,
            "total_count": task.total_count,
            "fail_count": task.fail_count,
            "error_message": task.error_message,
            "start_time": task.start_time,
            "end_time": task.end_time,
            "cost_millis": task.cost_millis,
        }
        for task in tasks
    ]
