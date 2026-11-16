from service.file_service import public_url
"""Knowledge document management business logic."""

from common.document_guard import idle_document

import os
from typing import List

from ai import vector_store
from common.exception_handler import CustomException
from common.result import PageInfo
from models import KnowledgeBase, KnowledgeChunk, KnowledgeDocument, User

# Supported file type. Key is the suffix of a file, value is the type name that was stored in the file_type column,
# Chapter 07 Press file_type to determine which solver to use
FILE_TYPES = {
    ".pdf": "PDF",
    ".docx": "WORD",
    ".xlsx": "EXCEL",
    ".md": "MARKDOWN",
    ".txt": "TXT",
}


def resolve_file_type(file_name: str | None) -> str:
    """The type of document is extrapolated by the suffix, and the unsupported type is stopped directly."""
    if not file_name:
        raise CustomException("Please upload the file first.")
    # Splitext removes the suffix with a point, changes lower case to compatible . PDF uppercase
    suffix = os.path.splitext(file_name)[1].lower()
    file_type = FILE_TYPES.get(suffix)
    if file_type is None:
        raise CustomException("Do not support this file type for the time being. Upload PDF, Word, Excel, Markdown or TXT")
    return file_type


def document_dict(doc: KnowledgeDocument, kb_name: str | None = None) -> dict:
    return {
        "id": doc.id,
        "kb_id": doc.kb_id,
        # List page to show "What library does this document belong to" by calling to check the name of the library
        "kb_name": kb_name,
        "name": doc.name,
        "file_name": doc.file_name,
        "file_url": public_url(doc.file_url),
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "parse_status": doc.parse_status,
        "parse_error": doc.parse_error,
        "has_table": doc.has_table,
        "has_ocr": doc.has_ocr,
        "char_count": doc.char_count,
        "chunk_count": doc.chunk_count,
        "vector_status": doc.vector_status,
        "upload_user_id": doc.upload_user_id,
        "create_time": doc.create_time,
        "update_time": doc.update_time,
    }


async def _kb_name_map(docs: List[KnowledgeDocument]) -> dict:
    """The name of the knowledge base involved in this file was identified once and for all, avoiding a paragraph-by-article search."""
    kb_ids = {doc.kb_id for doc in docs}
    if not kb_ids:
        return {}
    bases = await KnowledgeBase.filter(id__in=list(kb_ids))
    return {kb.id: kb.name for kb in bases}


async def _refresh_document_count(kb_id: int) -> None:
    """Recounts the number of documents in the knowledge base and returns them, all adjusted once after adding or deleting them."""
    count = await KnowledgeDocument.filter(kb_id=kb_id).count()
    await KnowledgeBase.filter(id=kb_id).update(document_count=count)


async def _refresh_chunk_count(kb_id: int) -> None:
    """Recalculates and returns the number of segments in the knowledge base. Deleting a document will be associated with deleting it, so you have to focus on counting.

    The parent blocks are only for background refilling and do not participate in searching, the statistics are not taken into account and their calibre is consistent with chapter 09.
    """
    count = await KnowledgeChunk.filter(kb_id=kb_id).exclude(chunk_type="Parent chunk").count()
    await KnowledgeBase.filter(id=kb_id).update(chunk_count=count)


async def add(current_user: User, payload: dict) -> None:
    kb_id = payload.get("kb_id")
    if not kb_id:
        raise CustomException("Select the knowledge base to which you belong")
    kb = await KnowledgeBase.get_or_none(id=kb_id)
    if kb is None:
        raise CustomException("Knowledge base not found")
    # The deactivated library should not have been able to enter new information. The front-end zipper has been filtered and the back end stopped again.
    if kb.status != "Active":
        raise CustomException("This knowledge base is disabled and cannot be uploaded")
    file_url = payload.get("file_url")
    if not file_url:
        raise CustomException("Please upload the file first.")
    # If the document name is not filled, use upload on top of the file name to make sure that the list name bar is not empty
    file_name = payload.get("file_name")
    name = payload.get("name") or file_name
    if not name:
        raise CustomException("Please enter the document name")
    from service.file_service import resolve, storage_name
    file_type = resolve_file_type(file_name)
    resolve(storage_name(file_url))
    await KnowledgeDocument.create(
        kb_id=kb_id,
        name=name,
        file_name=file_name,
        file_url=file_url,
        file_type=file_type,
        file_size=payload.get("file_size") or 0,
        upload_user_id=current_user.id,
    )
    # Document number is the redundant column displayed directly on the list page of the knowledge base and synchronised as soon as added
    await _refresh_document_count(kb_id)


@idle_document
async def update(doc_id: int | None, payload: dict) -> None:
    if doc_id is None:
        raise CustomException("Document ID cannot be empty")
    doc = await KnowledgeDocument.get_or_none(id=doc_id)
    if doc is None:
        raise CustomException("Document not found")
    name = payload.get("name")
    if not name:
        raise CustomException("Please enter the document name")
    file_url = payload.get("file_url")
    if not file_url:
        raise CustomException("Please upload the file first.")
    file_name = payload.get("file_name")
    from service.file_service import resolve, storage_name
    file_type = resolve_file_type(file_name)
    resolve(storage_name(file_url))
    update_data = {
        "name": name,
        "file_name": file_name,
        "file_url": file_url,
        "file_type": file_type,
        "file_size": payload.get("file_size") or 0,
    }
    # Changed to file, the number of words, fragments and parsing status that were previously disassembled is all disabled and returned to their initial state.
    # Reconstruct and quantifying is required
    if payload.get("kb_id", doc.kb_id) != doc.kb_id:
        raise CustomException("Moving documents requires uploading into the destination knowledge base")
    if storage_name(file_url) != storage_name(doc.file_url):
        await _clear_vectors(doc)
        await KnowledgeChunk.filter(document_id=doc_id).delete()
        await _refresh_chunk_count(doc.kb_id)
        update_data.update(
            parsed_text=None,
            parse_status="Pending parsing",
            parse_error=None,
            has_table="No",
            has_ocr="No",
            char_count=0,
            chunk_count=0,
            vector_status="Pending embedding",
        )
    await KnowledgeDocument.filter(id=doc_id).update(**update_data)


async def _clear_vectors(doc: KnowledgeDocument) -> None:
    """Delete the document and remove its vector from the vector library to avoid leaving a trace of an orphan who has not been identified.

    Only quantifiable documents require a vector library, and no direct leap to quantification.
    So that you can delete the document normally without PGVector.
    """
    await vector_store.delete_by_document(doc.id)


@idle_document
async def delete(doc_id: int) -> None:
    doc = await KnowledgeDocument.get_or_none(id=doc_id)
    if doc is None:
        raise CustomException("Document not found")
    kb_id = doc.kb_id
    await _clear_vectors(doc)
    # You'll have to clear the document together if it's missing.
    await KnowledgeChunk.filter(document_id=doc_id).delete()
    await KnowledgeDocument.filter(id=doc_id).delete()
    # Delete the document to reduce the number of documents on the knowledge base
    await _refresh_document_count(kb_id)
    await _refresh_chunk_count(kb_id)


async def delete_batch(ids: List[int]) -> None:
    for doc_id in ids:
        await delete(doc_id)


async def select_by_id(doc_id: int) -> dict:
    doc = await KnowledgeDocument.get_or_none(id=doc_id)
    if doc is None:
        raise CustomException("Document not found")
    kb = await KnowledgeBase.get_or_none(id=doc.kb_id)
    return document_dict(doc, kb.name if kb else None)


async def select_page(
    kb_id: int | None = None,
    name: str = "",
    parse_status: str = "",
    page_num: int = 1,
    page_size: int = 10,
) -> PageInfo:
    # Name From the top of page document name input box, empty string equals without this condition
    query = KnowledgeDocument.filter(name__contains=name)
    # kb_id from the bottom frame of the knowledge base, not a document that represents all libraries checked
    if kb_id:
        query = query.filter(kb_id=kb_id)
    # Parse_status from parsing state
    if parse_status:
        query = query.filter(parse_status=parse_status)
    docs = await query.order_by("-id").offset((page_num - 1) * page_size).limit(page_size)
    total = await query.count()
    kb_names = await _kb_name_map(docs)
    return PageInfo(total=total, list=[document_dict(doc, kb_names.get(doc.kb_id)) for doc in docs])
