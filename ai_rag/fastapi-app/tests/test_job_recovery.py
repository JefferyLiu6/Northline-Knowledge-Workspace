"""Restart cleanup and retry preserve valid inputs and discard partial derived output."""
import json
from unittest.mock import AsyncMock,patch
import pytest
from common.exception_handler import CustomException
from common.runtime_lease import backend_lease
from models import KnowledgeBase,KnowledgeDocument,KnowledgeChunk,DocumentProcessTask
from service import file_service,job_recovery_service,chunk_strategy_service

@pytest.fixture
async def interrupted_doc(db,tmp_path):
    kb=await KnowledgeBase.create(name="Unit test fixture recovery",status="Active")
    (tmp_path/"recovery.txt").write_text("Recovery test source.")
    doc=await KnowledgeDocument.create(kb_id=kb.id,name="Unit test fixture recovery",
        file_name="recovery.txt",file_url=file_service.DOWNLOAD_PREFIX+"recovery.txt",file_type="TXT",
        parsed_text="Recovery test source.",parse_status="Parsed",vector_status="Embedding in progress",chunk_count=1)
    await KnowledgeChunk.create(kb_id=kb.id,document_id=doc.id,chunk_index=0,content="Partial evidence",char_count=16,vector_status="Completed")
    yield kb,doc
    await DocumentProcessTask.filter(document_id=doc.id).delete()
    await KnowledgeChunk.filter(document_id=doc.id).delete()
    await KnowledgeDocument.filter(id=doc.id).delete()
    await KnowledgeBase.filter(id=kb.id).delete()

@pytest.mark.asyncio
@pytest.mark.parametrize("stage",["Document parsing","Text Splitting","Embed"])
async def test_restart_clears_partial_output_and_records_failure(interrupted_doc,stage):
    kb,doc=interrupted_doc
    task=await DocumentProcessTask.create(kb_id=kb.id,document_id=doc.id,task_type=stage,task_status="Processing",total_count=4,success_count=1)
    with patch("ai.vector_store.delete_by_document",new=AsyncMock()) as clear:
        assert await job_recovery_service.recover_interrupted()==1
        assert await job_recovery_service.recover_interrupted()==0
        clear.assert_awaited_once_with(doc.id)
    task=await DocumentProcessTask.get(id=task.id)
    assert task.task_status=="Failed" and "restart" in task.error_message
    updated=await KnowledgeDocument.get(id=doc.id)
    chunks=await KnowledgeChunk.filter(document_id=doc.id)
    if stage=="Embed":
        assert len(chunks)==1 and chunks[0].vector_status=="Pending embedding"
        assert updated.vector_status=="Failed" and updated.parsed_text
    else:
        assert not chunks and updated.chunk_count==0
        assert updated.parse_status==("Parsing failed" if stage=="Document parsing" else "Parsed")

@pytest.mark.asyncio
async def test_recovery_failure_remains_retryable_on_next_start(interrupted_doc):
    kb,doc=interrupted_doc
    task=await DocumentProcessTask.create(kb_id=kb.id,document_id=doc.id,task_type="Embed",task_status="Processing")
    with patch("ai.vector_store.delete_by_document",new=AsyncMock(side_effect=RuntimeError("offline"))):
        with pytest.raises(RuntimeError):
            await job_recovery_service.recover_interrupted()
    assert (await DocumentProcessTask.get(id=task.id)).task_status=="Processing"

@pytest.mark.asyncio
async def test_split_retry_uses_recorded_strategy(interrupted_doc):
    kb,doc=interrupted_doc
    strategy=await chunk_strategy_service.select_default()
    strategy["chunk_size"]=77
    task=await DocumentProcessTask.create(kb_id=kb.id,document_id=doc.id,task_type="Text Splitting",task_status="Failed",
                                         context_json=json.dumps(strategy,default=str))
    new_id,stage,function,arguments=await job_recovery_service.start_retry(doc.id)
    assert new_id!=task.id and stage=="Text Splitting" and arguments[-1]["chunk_size"]==77
    assert (await DocumentProcessTask.get(id=task.id)).task_status=="Failed"
    with pytest.raises(CustomException,match="processing"):
        await job_recovery_service.start_retry(doc.id)

@pytest.mark.asyncio
async def test_completed_step_cannot_be_retried(interrupted_doc):
    kb,doc=interrupted_doc
    await DocumentProcessTask.create(kb_id=kb.id,document_id=doc.id,task_type="Embed",task_status="Completed")
    with pytest.raises(CustomException,match="latest failed"):
        await job_recovery_service.start_retry(doc.id)

@pytest.mark.asyncio
async def test_second_backend_cannot_claim_active_database(db):
    async with backend_lease():
        with pytest.raises(RuntimeError,match="Another backend"):
            async with backend_lease():
                pytest.fail("Second backend acquired ownership")

def test_retry_requires_administrator(client):
    login=client.post("/login",json={"username":"morgan","password":"123456"}).json()
    response=client.post("/knowledgeDocument/retry/1",headers={"token":login["data"]["token"]}).json()
    assert response["code"]=="403"
