"""Knowledge base management interface testing.

Overwrites the addition, name check, page split query, edits, deletes and cleans out your own created data.
"""

TEST_NAME = "Test knowledge base-module testing exclusively"


def _create(client, admin_headers, name=TEST_NAME):
    return client.post(
        "/knowledgeBase/add",
        json={"name": name, "description": "Autotest creation", "status": "Active"},
        headers=admin_headers,
    ).json()


def _find_id(client, admin_headers, name=TEST_NAME):
    body = client.get(
        "/knowledgeBase/selectPage",
        params={"name": name, "page_num": 1, "page_size": 10},
        headers=admin_headers,
    ).json()
    for item in body["data"]["list"]:
        if item["name"] == name:
            return item["id"]
    return None


def _cleanup(client, admin_headers, name=TEST_NAME):
    kb_id = _find_id(client, admin_headers, name)
    if kb_id is not None:
        client.delete(f"/knowledgeBase/delete/{kb_id}", headers=admin_headers)


def test_add_and_select_page(client, admin_headers):
    """Adds to a list of pages, with the number of documents and segments initially 0."""
    _cleanup(client, admin_headers)
    assert _create(client, admin_headers)["code"] == "200"

    body = client.get(
        "/knowledgeBase/selectPage",
        params={"name": TEST_NAME, "page_num": 1, "page_size": 10},
        headers=admin_headers,
    ).json()
    assert body["code"] == "200"
    assert body["data"]["total"] >= 1
    created = [item for item in body["data"]["list"] if item["name"] == TEST_NAME][0]
    assert created["document_count"] == 0
    assert created["chunk_count"] == 0
    assert created["status"] == "Active"

    _cleanup(client, admin_headers)


def test_add_duplicated_name_is_rejected(client, admin_headers):
    """Recreated knowledge base of the same name is not allowed."""
    _cleanup(client, admin_headers)
    _create(client, admin_headers)

    body = _create(client, admin_headers)
    assert body["code"] == "500"
    assert body["msg"] == "Replication of knowledge bank names"

    _cleanup(client, admin_headers)


def test_add_without_name_is_rejected(client, admin_headers):
    """Gives a human message when the name is empty."""
    body = client.post(
        "/knowledgeBase/add",
        json={"description": "No name"},
        headers=admin_headers,
    ).json()
    assert body["code"] == "500"
    assert body["msg"] == "Please enter the name of the knowledge base"


def test_update_keeps_own_name_available(client, admin_headers):
    """Keeping the original name saved while editing will not be stopped again by their own checks."""
    _cleanup(client, admin_headers)
    _create(client, admin_headers)
    kb_id = _find_id(client, admin_headers)

    body = client.put(
        "/knowledgeBase/update",
        json={"id": kb_id, "name": TEST_NAME, "description": "Changed the description.", "status": "Disabled"},
        headers=admin_headers,
    ).json()
    assert body["code"] == "200"

    detail = client.get(f"/knowledgeBase/selectById/{kb_id}", headers=admin_headers).json()
    assert detail["data"]["description"] == "Changed the description."
    assert detail["data"]["status"] == "Disabled"

    _cleanup(client, admin_headers)


def test_select_all_only_returns_normal_status(client, admin_headers):
    """The drop-down interface returns only the knowledge base of normal state."""
    _cleanup(client, admin_headers)
    _create(client, admin_headers)
    kb_id = _find_id(client, admin_headers)
    client.put(
        "/knowledgeBase/update",
        json={"id": kb_id, "name": TEST_NAME, "status": "Disabled"},
        headers=admin_headers,
    )

    body = client.get("/knowledgeBase/selectAll", headers=admin_headers).json()
    names = [item["name"] for item in body["data"]]
    assert TEST_NAME not in names

    _cleanup(client, admin_headers)


def test_normal_user_cannot_access(client):
    """General user-modern interface returns 403."""
    login = client.post("/login", json={"username": "morgan", "password": "123456"}).json()
    headers = {"token": login["data"]["token"]}
    body = client.get("/knowledgeBase/selectPage", headers=headers).json()
    assert body["code"] == "403"
    assert body["msg"] == "No operation permissions"
