"""The snippet interface is tested.

Overwrites the policy verification, default strategy uniqueness, recursive partitions, parent-son splits, segment editing and deletions.
"""

import os

import pytest

from service.file_service import UPLOAD_DIR

KB_NAME = "Testing the splitting library -- module test exclusively"
STRATEGY_NAME = "Test strategy-module test exclusively"
# Text separated by line break in three paragraphs, and the sequential fractions will be broken at line break
DOC_TEXT = "\n\n".join([f"Section {index}. This paragraph is long enough to verify that the two chunk sizes produce different results." for index in range(1, 13)])


@pytest.fixture()
def kb_id(client, admin_headers):
    client.post("/knowledgeBase/add", json={"name": KB_NAME, "status": "Active"}, headers=admin_headers)
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
        client.request("DELETE", "/knowledgeDocument/deleteBatch", json=doc_ids, headers=admin_headers)
    client.delete(f"/knowledgeBase/delete/{created['id']}", headers=admin_headers)


@pytest.fixture()
def parsed_doc(client, admin_headers, kb_id):
    """Creates a completed TXT document for cut-off testing."""
    file_name = "Cutting test text.txt"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = os.path.join(UPLOAD_DIR, file_name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(DOC_TEXT)

    client.post(
        "/knowledgeDocument/add",
        json={
            "kb_id": kb_id,
            "name": file_name,
            "file_name": file_name,
            "file_url": f"http://127.0.0.1:9090/files/download/{file_name}",
            "file_size": len(DOC_TEXT),
        },
        headers=admin_headers,
    )
    page = client.get(
        "/knowledgeDocument/selectPage",
        params={"kb_id": kb_id, "page_num": 1, "page_size": 10},
        headers=admin_headers,
    ).json()
    doc_id = page["data"]["list"][0]["id"]
    client.post(f"/knowledgeDocument/parse/{doc_id}", headers=admin_headers)

    yield doc_id

    if os.path.exists(path):
        os.remove(path)


def _cleanup_strategy(client, admin_headers):
    page = client.get(
        "/chunkStrategy/selectPage",
        params={"name": STRATEGY_NAME, "page_num": 1, "page_size": 10},
        headers=admin_headers,
    ).json()
    for item in page["data"]["list"]:
        if item["name"] == STRATEGY_NAME:
            client.delete(f"/chunkStrategy/delete/{item['id']}", headers=admin_headers)


def test_overlap_must_be_smaller_than_chunk_size(client, admin_headers):
    """The number of overlapping characters cannot be greater than or equal to the length of a segment."""
    body = client.post(
        "/chunkStrategy/add",
        json={"name": STRATEGY_NAME, "strategy_type": "Recursive chunking", "chunk_size": 200, "chunk_overlap": 200},
        headers=admin_headers,
    ).json()
    assert body["code"] == "500"
    assert body["msg"] == "Overlap character count must be less than segment length"


def test_parent_chunk_size_must_be_larger(client, admin_headers):
    """The length of the parent piece must be greater than that of the child."""
    body = client.post(
        "/chunkStrategy/add",
        json={
            "name": STRATEGY_NAME,
            "strategy_type": "Parent-child chunking",
            "chunk_size": 300,
            "chunk_overlap": 30,
            "parent_chunk_size": 300,
        },
        headers=admin_headers,
    ).json()
    assert body["code"] == "500"
    assert body["msg"] == "Parent block length must be greater than segment length"


def test_only_one_default_strategy(client, admin_headers):
    """After adding a default policy, the original default mark is cleared."""
    _cleanup_strategy(client, admin_headers)
    before = client.get("/chunkStrategy/selectAll", headers=admin_headers).json()
    old_default = [item for item in before["data"] if item["is_default"] == "Yes"][0]

    client.post(
        "/chunkStrategy/add",
        json={
            "name": STRATEGY_NAME,
            "strategy_type": "Recursive chunking",
            "chunk_size": 200,
            "chunk_overlap": 20,
            "is_default": "Yes",
        },
        headers=admin_headers,
    )
    after = client.get("/chunkStrategy/selectAll", headers=admin_headers).json()
    defaults = [item for item in after["data"] if item["is_default"] == "Yes"]
    assert len(defaults) == 1
    assert defaults[0]["name"] == STRATEGY_NAME

    # Restore: reset the original to default and delete test strategy
    client.put(
        "/chunkStrategy/update",
        json={
            "id": old_default["id"],
            "name": old_default["name"],
            "strategy_type": old_default["strategy_type"],
            "chunk_size": old_default["chunk_size"],
            "chunk_overlap": old_default["chunk_overlap"],
            "separators": old_default["separators"],
            "is_default": "Yes",
        },
        headers=admin_headers,
    )
    _cleanup_strategy(client, admin_headers)


def test_default_strategy_cannot_be_deleted(client, admin_headers):
    """The default policy does not allow deletion."""
    strategies = client.get("/chunkStrategy/selectAll", headers=admin_headers).json()
    default = [item for item in strategies["data"] if item["is_default"] == "Yes"][0]

    body = client.delete(f"/chunkStrategy/delete/{default['id']}", headers=admin_headers).json()
    assert body["code"] == "500"
    assert body["msg"] == "Default strategy cannot be deleted, please set other strategies as default first"


def test_split_recursive_creates_plain_chunks(client, admin_headers, kb_id, parsed_doc):
    """Recursive blocks cut out a set of flat blocks and synchronize the number of segments in the document and knowledge bank."""
    strategies = client.get("/chunkStrategy/selectAll", headers=admin_headers).json()
    recursive = [item for item in strategies["data"] if item["strategy_type"] == "Recursive chunking"][0]

    body = client.post(
        f"/knowledgeChunk/split/{parsed_doc}",
        params={"strategy_id": recursive["id"]},
        headers=admin_headers,
    ).json()
    assert body["code"] == "200"

    page = client.get(
        "/knowledgeChunk/selectPage",
        params={"document_id": parsed_doc, "page_num": 1, "page_size": 50},
        headers=admin_headers,
    ).json()
    chunks = page["data"]["list"]
    assert len(chunks) > 0
    assert all(chunk["chunk_type"] == "Standard chunk" for chunk in chunks)
    assert all(chunk["parent_id"] is None for chunk in chunks)

    detail = client.get(f"/knowledgeDocument/selectById/{parsed_doc}", headers=admin_headers).json()
    assert detail["data"]["chunk_count"] == page["data"]["total"]
    kb = client.get(f"/knowledgeBase/selectById/{kb_id}", headers=admin_headers).json()
    assert kb["data"]["chunk_count"] == page["data"]["total"]


def test_split_parent_child_links_children_to_parent(client, admin_headers, kb_id, parsed_doc):
    """Fathers and sons divide into pieces, each of which is directed to the real one."""
    strategies = client.get("/chunkStrategy/selectAll", headers=admin_headers).json()
    parent_child = [item for item in strategies["data"] if item["strategy_type"] == "Parent-child chunking"][0]

    client.post(
        f"/knowledgeChunk/split/{parsed_doc}",
        params={"strategy_id": parent_child["id"]},
        headers=admin_headers,
    )

    page = client.get(
        "/knowledgeChunk/selectPage",
        params={"document_id": parsed_doc, "page_num": 1, "page_size": 100},
        headers=admin_headers,
    ).json()
    chunks = page["data"]["list"]
    parents = [chunk for chunk in chunks if chunk["chunk_type"] == "Parent chunk"]
    children = [chunk for chunk in chunks if chunk["chunk_type"] == "Child chunk"]
    assert parents and children
    parent_ids = {chunk["id"] for chunk in parents}
    # Every piece is hanging under a real parent.
    assert all(chunk["parent_id"] in parent_ids for chunk in children)

    # Snippets count only the blocks involved in searching, but not the parent
    detail = client.get(f"/knowledgeDocument/selectById/{parsed_doc}", headers=admin_headers).json()
    assert detail["data"]["chunk_count"] == len(children)


def test_split_requires_parsed_document(client, admin_headers, kb_id):
    """Could not close temporary folder: %s"""
    client.post(
        "/knowledgeDocument/add",
        json={
            "kb_id": kb_id,
            "name": "Unsolved Document.txt",
            "file_name": "Unsolved Document.txt",
            "file_url": client.post("/files/upload", headers=admin_headers, files={"file": ("unparsed.txt", b"fixture")}).json()["data"],
        },
        headers=admin_headers,
    )
    page = client.get(
        "/knowledgeDocument/selectPage",
        params={"kb_id": kb_id, "name": "Unsolved Document", "page_num": 1, "page_size": 10},
        headers=admin_headers,
    ).json()
    doc_id = page["data"]["list"][0]["id"]

    body = client.post(f"/knowledgeChunk/split/{doc_id}", headers=admin_headers).json()
    assert body["code"] == "500"
    assert body["msg"] == "Parsing the document before severing it."


def test_update_chunk_resets_vector_status(client, admin_headers, parsed_doc):
    """After artificially modifying the fragments, both the segments and the document are re-quantified to be quantified."""
    client.post(f"/knowledgeChunk/split/{parsed_doc}", headers=admin_headers)
    page = client.get(
        "/knowledgeChunk/selectPage",
        params={"document_id": parsed_doc, "page_num": 1, "page_size": 10},
        headers=admin_headers,
    ).json()
    chunk_id = page["data"]["list"][0]["id"]

    body = client.put(
        "/knowledgeChunk/update",
        json={"id": chunk_id, "content": "Manually modified segment content."},
        headers=admin_headers,
    ).json()
    assert body["code"] == "200"

    detail = client.get(f"/knowledgeChunk/selectById/{chunk_id}", headers=admin_headers).json()
    assert detail["data"]["content"] == "Manually modified segment content."
    assert detail["data"]["char_count"] == len("Manually modified segment content.")
    assert detail["data"]["vector_status"] == "Pending embedding"


def test_empty_chunk_content_is_rejected(client, admin_headers, parsed_doc):
    """The content of the fragments is not allowed to be empty."""
    client.post(f"/knowledgeChunk/split/{parsed_doc}", headers=admin_headers)
    page = client.get(
        "/knowledgeChunk/selectPage",
        params={"document_id": parsed_doc, "page_num": 1, "page_size": 10},
        headers=admin_headers,
    ).json()
    chunk_id = page["data"]["list"][0]["id"]

    body = client.put(
        "/knowledgeChunk/update",
        json={"id": chunk_id, "content": "   "},
        headers=admin_headers,
    ).json()
    assert body["code"] == "500"
    assert body["msg"] == "Snippets cannot be empty"


def test_parent_chunk_cannot_be_deleted(client, admin_headers, parsed_doc):
    """Parent blocks are not allowed to be deleted separately."""
    strategies = client.get("/chunkStrategy/selectAll", headers=admin_headers).json()
    parent_child = [item for item in strategies["data"] if item["strategy_type"] == "Parent-child chunking"][0]
    client.post(
        f"/knowledgeChunk/split/{parsed_doc}",
        params={"strategy_id": parent_child["id"]},
        headers=admin_headers,
    )
    page = client.get(
        "/knowledgeChunk/selectPage",
        params={"document_id": parsed_doc, "chunk_type": "Parent chunk", "page_num": 1, "page_size": 10},
        headers=admin_headers,
    ).json()
    parent_id = page["data"]["list"][0]["id"]

    body = client.delete(f"/knowledgeChunk/delete/{parent_id}", headers=admin_headers).json()
    assert body["code"] == "500"
    assert body["msg"] == "Parent block cannot be removed separately. Please re-severe the whole document"


def test_resplit_replaces_old_chunks(client, admin_headers, parsed_doc):
    """Re-severing will clear the old footage and not mix it up."""
    strategies = client.get("/chunkStrategy/selectAll", headers=admin_headers).json()
    long_one = [item for item in strategies["data"] if item["strategy_type"] == "Recursive chunking" and item["chunk_size"] >= 500][0]
    short_one = [item for item in strategies["data"] if item["strategy_type"] == "Recursive chunking" and item["chunk_size"] < 500][0]

    client.post(f"/knowledgeChunk/split/{parsed_doc}", params={"strategy_id": long_one["id"]}, headers=admin_headers)
    first_total = client.get(
        "/knowledgeChunk/selectPage",
        params={"document_id": parsed_doc, "page_num": 1, "page_size": 100},
        headers=admin_headers,
    ).json()["data"]["total"]

    client.post(f"/knowledgeChunk/split/{parsed_doc}", params={"strategy_id": short_one["id"]}, headers=admin_headers)
    second_total = client.get(
        "/knowledgeChunk/selectPage",
        params={"document_id": parsed_doc, "page_num": 1, "page_size": 100},
        headers=admin_headers,
    ).json()["data"]["total"]

    # Shorter snippets cut more and did not leave the last round.
    assert second_total > first_total
    detail = client.get(f"/knowledgeDocument/selectById/{parsed_doc}", headers=admin_headers).json()
    assert detail["data"]["chunk_count"] == second_total
