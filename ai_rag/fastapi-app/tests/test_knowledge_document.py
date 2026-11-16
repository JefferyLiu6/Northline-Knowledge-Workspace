"""Knowledge document management interface test.

Overwrites uploading files, file type verifications, synchronisation of the number of knowledge base documents, reset and delete after changing files.
"""

import pytest

KB_NAME = "Testing the library -- module test exclusively"
DOC_NAME = "Test document-unit test"


@pytest.fixture()
def kb_id(client, admin_headers):
    """Build a temporary knowledge base, which will be cleared with the documents under the library."""
    client.post(
        "/knowledgeBase/add",
        json={"name": KB_NAME, "description": "Autotest creation", "status": "Active"},
        headers=admin_headers,
    )
    page = client.get(
        "/knowledgeBase/selectPage",
        params={"name": KB_NAME, "page_num": 1, "page_size": 10},
        headers=admin_headers,
    ).json()
    created = [item for item in page["data"]["list"] if item["name"] == KB_NAME][0]

    yield created["id"]

    docs = client.get(
        "/knowledgeDocument/selectPage",
        params={"kb_id": created["id"], "page_num": 1, "page_size": 50},
        headers=admin_headers,
    ).json()
    doc_ids = [item["id"] for item in docs["data"]["list"]]
    if doc_ids:
        client.request(
            "DELETE", "/knowledgeDocument/deleteBatch", json=doc_ids, headers=admin_headers
        )
    client.delete(f"/knowledgeBase/delete/{created['id']}", headers=admin_headers)


def _add_doc(client, admin_headers, kb_id, file_name="Product manual.pdf"):
    uploaded = client.post("/files/upload", headers=admin_headers, files={"file": ("fixture.pdf", b"fixture")}).json()["data"]
    return client.post(
        "/knowledgeDocument/add",
        json={
            "kb_id": kb_id,
            "name": DOC_NAME,
            "file_name": file_name,
            "file_url": uploaded,
            "file_size": 20480,
        },
        headers=admin_headers,
    ).json()


def test_add_document_and_refresh_kb_count(client, admin_headers, kb_id):
    """After uploading a profile, the number of documents on the knowledge base is added to one."""
    assert _add_doc(client, admin_headers, kb_id)["code"] == "200"

    detail = client.get(f"/knowledgeBase/selectById/{kb_id}", headers=admin_headers).json()
    assert detail["data"]["document_count"] == 1

    page = client.get(
        "/knowledgeDocument/selectPage",
        params={"kb_id": kb_id, "page_num": 1, "page_size": 10},
        headers=admin_headers,
    ).json()
    doc = page["data"]["list"][0]
    # File type extrapolated by suffix, neither parsing nor quantifying, two states are initial values
    assert doc["file_type"] == "PDF"
    assert doc["parse_status"] == "Pending parsing"
    assert doc["vector_status"] == "Pending embedding"
    # List to show the name of the knowledge base to which it belongs, obtained by backend on kb_id check the knowledge bank table
    assert doc["kb_name"] == KB_NAME


def test_unsupported_file_type_is_rejected(client, admin_headers, kb_id):
    """A suffix that is not within the scope of support is stopped directly."""
    body = _add_doc(client, admin_headers, kb_id, file_name="Demonstration video.mp4")
    assert body["code"] == "500"
    assert body["msg"] == "Do not support this file type for the time being. Upload PDF, Word, Excel, Markdown or TXT"


def test_add_without_file_is_rejected(client, admin_headers, kb_id):
    """Gives a human cue when no file is uploaded."""
    body = client.post(
        "/knowledgeDocument/add",
        json={"kb_id": kb_id, "name": DOC_NAME},
        headers=admin_headers,
    ).json()
    assert body["code"] == "500"
    assert body["msg"] == "Please upload the file first."


def test_add_to_disabled_kb_is_rejected(client, admin_headers, kb_id):
    """When the knowledge base is disabled, it is not allowed to transmit documents in-house."""
    client.put(
        "/knowledgeBase/update",
        json={"id": kb_id, "name": KB_NAME, "status": "Disabled"},
        headers=admin_headers,
    )
    body = _add_doc(client, admin_headers, kb_id)
    assert body["code"] == "500"
    assert body["msg"] == "This knowledge base is disabled and cannot be uploaded"
    # Resume. Let's get the clamps cleaned up.
    client.put(
        "/knowledgeBase/update",
        json={"id": kb_id, "name": KB_NAME, "status": "Active"},
        headers=admin_headers,
    )


def test_replace_file_resets_parse_and_vector_status(client, admin_headers, kb_id):
    """After changing the file, the parsing results are invalidated and the status is returned to its initial value."""
    _add_doc(client, admin_headers, kb_id)
    page = client.get(
        "/knowledgeDocument/selectPage",
        params={"kb_id": kb_id, "page_num": 1, "page_size": 10},
        headers=admin_headers,
    ).json()
    doc_id = page["data"]["list"][0]["id"]

    body = client.put(
        "/knowledgeDocument/update",
        json={
            "id": doc_id,
            "kb_id": kb_id,
            "name": DOC_NAME,
            "file_name": "After-sale system.docx",
            "file_url": client.post("/files/upload", headers=admin_headers, files={"file": ("replacement.docx", b"fixture")}).json()["data"],
            "file_size": 10240,
        },
        headers=admin_headers,
    ).json()
    assert body["code"] == "200"

    detail = client.get(f"/knowledgeDocument/selectById/{doc_id}", headers=admin_headers).json()
    assert detail["data"]["file_type"] == "WORD"
    assert detail["data"]["parse_status"] == "Pending parsing"
    assert detail["data"]["vector_status"] == "Pending embedding"
    assert detail["data"]["char_count"] == 0


def test_delete_document_refresh_kb_count(client, admin_headers, kb_id):
    """Removes the document and reduces the number of documents on the knowledge base."""
    _add_doc(client, admin_headers, kb_id)
    page = client.get(
        "/knowledgeDocument/selectPage",
        params={"kb_id": kb_id, "page_num": 1, "page_size": 10},
        headers=admin_headers,
    ).json()
    doc_id = page["data"]["list"][0]["id"]

    client.delete(f"/knowledgeDocument/delete/{doc_id}", headers=admin_headers)

    detail = client.get(f"/knowledgeBase/selectById/{kb_id}", headers=admin_headers).json()
    assert detail["data"]["document_count"] == 0


def test_kb_with_documents_cannot_be_deleted(client, admin_headers, kb_id):
    """It is not allowed to delete a library when there are documents under the knowledge base."""
    _add_doc(client, admin_headers, kb_id)

    body = client.delete(f"/knowledgeBase/delete/{kb_id}", headers=admin_headers).json()
    assert body["code"] == "500"
    assert body["msg"] == "There are documents under this knowledge base, please delete them first"
