"""Serialize document commands and reject changes during background processing."""
from functools import wraps
from tortoise.transactions import in_transaction
from models import KnowledgeDocument, DocumentProcessTask, KnowledgeBase, KnowledgeChunk
from common.exception_handler import CustomException

def idle_document(function):
    @wraps(function)
    async def guarded(doc_id, *args, **kwargs):
        # Establish a consistent snapshot only after acquiring the row locks.
        doc = await KnowledgeDocument.get_or_none(id=doc_id)
        async with in_transaction():
            if doc:
                await KnowledgeBase.filter(id=doc.kb_id).select_for_update().first()
            await KnowledgeDocument.filter(id=doc_id).select_for_update().first()
            if await DocumentProcessTask.filter(document_id=doc_id, task_status="Processing").select_for_update().first():
                raise CustomException("Document processing is in progress; wait before changing it")
            return await function(doc_id, *args, **kwargs)
    return guarded

def idle_chunk(function):
    @wraps(function)
    async def guarded(chunk_id, *args, **kwargs):
        chunk = await KnowledgeChunk.get_or_none(id=chunk_id)
        if chunk is None:
            raise CustomException("No snippets found")
        @idle_document
        async def execute(doc_id):
            return await function(chunk_id, *args, **kwargs)
        return await execute(chunk.document_id)
    return guarded

def idle_knowledge_base(function):
    @wraps(function)
    async def guarded(kb_id, *args, **kwargs):
        async with in_transaction():
            await KnowledgeBase.filter(id=kb_id).select_for_update().first()
            if await DocumentProcessTask.filter(kb_id=kb_id, task_status="Processing").select_for_update().first():
                raise CustomException("Wait for document processing before clearing embeddings")
            return await function(kb_id, *args, **kwargs)
    return guarded
