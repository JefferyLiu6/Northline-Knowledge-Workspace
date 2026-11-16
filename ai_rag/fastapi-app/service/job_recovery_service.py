"""Recover interrupted document stages after exclusive backend ownership is acquired."""
import json
from tortoise import connections
from tortoise.transactions import in_transaction
from ai import vector_store
from common.document_guard import idle_document
from common.exception_handler import CustomException
from common.times import now
from models import DocumentProcessTask, KnowledgeDocument, KnowledgeChunk

SUPPORTED = {"Document parsing", "Text Splitting", "Embed"}

async def migrate_task_context():
    db = connections.get("default")
    rows = await db.execute_query_dict(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'document_process_task' AND COLUMN_NAME = 'context_json'"
    )
    if not rows:
        await db.execute_script("ALTER TABLE document_process_task ADD COLUMN context_json TEXT NULL")

async def recover_interrupted():
    """Run before accepting requests, never while another backend owns the database."""
    tasks = await DocumentProcessTask.filter(task_status="Processing", task_type__in=list(SUPPORTED)).order_by("id")
    for task in tasks:
        async with in_transaction():
            doc = await KnowledgeDocument.get_or_none(id=task.document_id)
            if doc:
                # Always remove partial vectors, even if status writes never committed.
                await vector_store.delete_by_document(doc.id)
                if task.task_type in {"Document parsing", "Text Splitting"}:
                    await KnowledgeChunk.filter(document_id=doc.id).delete()
                    updates = {"chunk_count": 0, "vector_status": "Pending embedding"}
                    if task.task_type == "Document parsing":
                        updates.update(parse_status="Parsing failed", parsed_text=None, char_count=0,
                                       parse_error="Parsing was interrupted by a backend restart. Retry this step.")
                    await KnowledgeDocument.filter(id=doc.id).update(**updates)
                    from service.knowledge_document_service import _refresh_chunk_count
                    await _refresh_chunk_count(doc.kb_id)
                else:
                    await KnowledgeChunk.filter(document_id=doc.id).update(vector_status="Pending embedding")
                    await KnowledgeDocument.filter(id=doc.id).update(vector_status="Failed")
            await DocumentProcessTask.filter(id=task.id).update(
                task_status="Failed", end_time=now(),
                error_message=f"{task.task_type} was interrupted by a backend restart. Partial output was cleared; retry this step.",
                success_count=0, fail_count=max(task.total_count, 1),
            )
    return len(tasks)

@idle_document
async def start_retry(doc_id):
    task = await DocumentProcessTask.filter(document_id=doc_id).order_by("-id").first()
    if not task or task.task_status != "Failed" or task.task_type not in SUPPORTED:
        raise CustomException("Only the latest failed document-processing step can be retried")
    from service import document_parse_service, knowledge_chunk_service, vectorize_service
    if task.task_type == "Document parsing":
        new_id = await document_parse_service.start_parse(doc_id)
        return new_id, task.task_type, document_parse_service.run_parse, (doc_id, new_id)
    if task.task_type == "Text Splitting":
        if not task.context_json:
            raise CustomException("This older task has no saved strategy. Use Split into chunks and choose a strategy.")
        snapshot = json.loads(task.context_json)
        new_id, strategy = await knowledge_chunk_service.start_split(doc_id, None, strategy_snapshot=snapshot)
        return new_id, task.task_type, knowledge_chunk_service.run_split, (doc_id, new_id, strategy)
    new_id, context = await vectorize_service.start_vectorize(doc_id)
    return new_id, task.task_type, vectorize_service.run_vectorize, (doc_id, new_id, context)
