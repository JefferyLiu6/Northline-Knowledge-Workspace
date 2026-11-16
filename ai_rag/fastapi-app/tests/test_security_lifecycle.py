"""Regression coverage for document integrity and access controls."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from datetime import datetime,timedelta,timezone
import jwt
import pytest
from common.passwords import hash_password, verify_password
from common.exception_handler import CustomException
from models import KnowledgeBase, KnowledgeDocument, KnowledgeChunk, DocumentProcessTask
from service import knowledge_document_service, document_parse_service, retrieval_service, file_service
from conftest import TEST_MARK

def test_hashes_use_salt_and_reject_plaintext():
    first,second=hash_password("secret"),hash_password("secret")
    assert first!=second and "secret" not in first
    assert verify_password("secret",first)
    assert not verify_password("wrong",first)
    assert not verify_password("secret","secret")

def test_anonymous_files_rejected(client):
    assert client.post("/files/upload",files={"file":("doc.txt",b"test")}).json()["code"]=="401"
    assert client.get("/files/download/Customer FAQ.md").json()["code"]=="401"

def test_unique_uploads_and_traversal(client,admin_headers):
    def upload(name,content):
        return client.post("/files/upload",headers=admin_headers,files={"file":(name,content)}).json()
    assert upload("../escape.txt",b"bad")["code"]!="200"
    first=upload("same # name.txt",b"first")["data"]
    second=upload("same # name.txt",b"second")["data"]
    assert first!=second
    assert client.get(first,headers=admin_headers).content==b"first"
    assert client.get(second,headers=admin_headers).content==b"second"

def test_regular_user_cannot_read_admin_resources(client):
    body=client.post("/login",json={"username":"morgan","password":"123456"}).json()
    headers={"token":body["data"]["token"]}
    for endpoint in ["/user/selectAll","/knowledgeChunk/selectById/153","/files/download/Customer FAQ.md"]:
        assert client.get(endpoint,headers=headers).json()["code"]=="403"

def test_old_key_rejected(client):
    token=jwt.encode({"sub":"1","exp":datetime.now(timezone.utc)+timedelta(hours=1)},
        "ai-rag-advanced-knowledge-platform-jwt-secret",algorithm="HS256")
    assert client.get("/user/selectAll",headers={"token":token}).json()["code"]=="401"

@pytest.fixture
async def lifecycle_doc(db,tmp_path):
    kb=await KnowledgeBase.create(name=TEST_MARK+" lifecycle",status="Active")
    (tmp_path/"old.txt").write_text("old evidence")
    doc=await KnowledgeDocument.create(kb_id=kb.id,name=TEST_MARK+" lifecycle",file_name="old.txt",
        file_url=file_service.DOWNLOAD_PREFIX+"old.txt",file_type="TXT",parsed_text="old evidence",
        parse_status="Parsed",vector_status="Pending embedding",chunk_count=1)
    await KnowledgeChunk.create(kb_id=kb.id,document_id=doc.id,chunk_index=0,chunk_type="Standard chunk",content="old evidence",char_count=12)
    yield kb,doc
    await DocumentProcessTask.filter(document_id=doc.id).delete()
    await KnowledgeChunk.filter(document_id=doc.id).delete()
    await KnowledgeDocument.filter(id=doc.id).delete()
    await KnowledgeBase.filter(id=kb.id).delete()

@pytest.mark.asyncio
async def test_replacement_removes_old_index(lifecycle_doc,tmp_path):
    kb,doc=lifecycle_doc
    (tmp_path/"new.txt").write_text("new evidence")
    with patch("ai.vector_store.delete_by_document",new=AsyncMock()) as delete:
        await knowledge_document_service.update(doc.id,dict(kb_id=kb.id,name=doc.name,file_name="new.txt",
            file_url=file_service.DOWNLOAD_PREFIX+"new.txt"))
        delete.assert_awaited_once_with(doc.id)
    updated=await KnowledgeDocument.get(id=doc.id)
    assert updated.parsed_text is None and updated.chunk_count==0
    assert not await KnowledgeChunk.filter(document_id=doc.id).exists()

@pytest.mark.asyncio
async def test_reparse_invalidates_old_index(lifecycle_doc):
    kb,doc=lifecycle_doc
    with patch("ai.vector_store.delete_by_document",new=AsyncMock()) as delete:
        await document_parse_service.start_parse(doc.id)
        delete.assert_awaited_once_with(doc.id)
    assert not await KnowledgeChunk.filter(document_id=doc.id).exists()
    assert (await KnowledgeDocument.get(id=doc.id)).parsed_text is None

@pytest.mark.asyncio
async def test_delete_cleans_vectors_despite_pending_status(lifecycle_doc):
    _,doc=lifecycle_doc
    with patch("ai.vector_store.delete_by_document",new=AsyncMock()) as delete:
        await knowledge_document_service.delete(doc.id)
        delete.assert_awaited_once_with(doc.id)
    assert not await KnowledgeDocument.filter(id=doc.id).exists()

@pytest.mark.asyncio
async def test_active_job_blocks_deletion(lifecycle_doc):
    kb,doc=lifecycle_doc
    await DocumentProcessTask.create(kb_id=kb.id,document_id=doc.id,task_type="Embed",task_status="Processing")
    with pytest.raises(CustomException,match="processing"):
        await knowledge_document_service.delete(doc.id)
    assert await KnowledgeDocument.filter(id=doc.id).exists()

@pytest.mark.asyncio
async def test_retrieval_rejects_wrong_embedding_model(lifecycle_doc):
    kb,_=lifecycle_doc
    await KnowledgeBase.filter(id=kb.id).update(embedding_model_id=99999)
    with patch("ai.model_factory.load_enabled",new=AsyncMock(return_value=SimpleNamespace(id=2))):
        with pytest.raises(CustomException,match="mismatch"):
            await retrieval_service._vector_recall([kb.id],"question",{},None)

@pytest.mark.asyncio
async def test_bound_model_identity_cannot_be_edited(db):
    from models import AiModelConfig
    from service import ai_model_config_service
    config = await AiModelConfig.get(id=2)
    payload = ai_model_config_service.config_dict(config, mask_key=False)
    payload["model_name"] = "incompatible-embedding-model"
    with pytest.raises(CustomException, match="Clear bound"):
        await ai_model_config_service.update(config.id, payload)
    assert (await AiModelConfig.get(id=2)).model_name == config.model_name

@pytest.mark.asyncio
async def test_manual_chunk_edit_removes_old_vector(lifecycle_doc):
    from service import knowledge_chunk_service
    _, doc = lifecycle_doc
    chunk = await KnowledgeChunk.filter(document_id=doc.id).first()
    with patch("ai.vector_store.delete_by_chunk_ids", new=AsyncMock()) as delete:
        await knowledge_chunk_service.update_content(chunk.id, "replacement evidence")
        delete.assert_awaited_once_with([chunk.id])
    assert (await KnowledgeChunk.get(id=chunk.id)).content == "replacement evidence"

def test_fake_avatar_rejected(client):
    data = client.post("/login", json={"username":"morgan","password":"123456"}).json()["data"]
    response = client.post("/files/upload", headers={"token":data["token"]},
                           files={"file":("fake.png", b"not an image", "image/png")}).json()
    assert response["code"] != "200"

def test_logout_clears_file_cookie(client, admin_headers):
    assert client.cookies.get("file_session")
    assert client.post("/logout").json()["code"] == "200"
    assert not client.cookies.get("file_session")

@pytest.mark.asyncio
async def test_concurrent_parse_commands_create_only_one_task(lifecycle_doc):
    import asyncio
    _, doc = lifecycle_doc
    with patch("ai.vector_store.delete_by_document", new=AsyncMock()):
        results = await asyncio.gather(document_parse_service.start_parse(doc.id),
                                       document_parse_service.start_parse(doc.id), return_exceptions=True)
    assert sum(isinstance(result, int) for result in results) == 1
    assert sum(isinstance(result, CustomException) for result in results) == 1
    assert await DocumentProcessTask.filter(document_id=doc.id, task_status="Processing").count() == 1

@pytest.mark.asyncio
async def test_password_change_revokes_previous_token(db):
    from common.auth import create_token, get_current_user
    from models import User
    user = await User.create(username="portfolio-token-test", name="test", password=hash_password("before"), role="USER")
    try:
        token = create_token(user)
        assert (await get_current_user(token)).id == user.id
        await User.filter(id=user.id).update(password=hash_password("after"))
        with pytest.raises(CustomException, match="expired"):
            await get_current_user(token)
    finally:
        await User.filter(id=user.id).delete()

@pytest.mark.asyncio
async def test_parent_chunk_cannot_diverge_from_children(lifecycle_doc):
    from service import knowledge_chunk_service
    _, doc = lifecycle_doc
    chunk = await KnowledgeChunk.filter(document_id=doc.id).first()
    await KnowledgeChunk.filter(id=chunk.id).update(chunk_type="Parent chunk")
    with pytest.raises(CustomException, match="reparse"):
        await knowledge_chunk_service.update_content(chunk.id, "independent replacement")
