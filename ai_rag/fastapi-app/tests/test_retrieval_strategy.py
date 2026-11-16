"""Retrieval strategy management and debugger testing.

The strategy CRUD is all directly measurable; the comparison interface on the debugger needs to be really running.
This covers only the path associated with parameter verification and archiving.
"""

STRATEGY_NAME = "Test search strategy-module test"


def _cleanup(client, admin_headers):
    page = client.get(
        "/retrievalStrategy/selectPage",
        params={"name": STRATEGY_NAME, "page_num": 1, "page_size": 10},
        headers=admin_headers,
    ).json()
    for item in page["data"]["list"]:
        if item["name"] == STRATEGY_NAME:
            client.delete(f"/retrievalStrategy/delete/{item['id']}", headers=admin_headers)


def _payload(**overrides):
    payload = {
        "name": STRATEGY_NAME,
        "vector_enabled": "Yes",
        "vector_top_k": 5,
        "bm25_enabled": "No",
        "bm25_top_k": 0,
        "rrf_k": 60,
        "rerank_enabled": "No",
        "rerank_top_n": 3,
        "query_rewrite_enabled": "No",
        "multi_query_count": 3,
        "parent_recall_enabled": "No",
        "vector_score_threshold": 0.3,
        "rerank_score_threshold": 0.05,
        "is_default": "No",
    }
    payload.update(overrides)
    return payload


def test_both_recalls_disabled_is_rejected(client, admin_headers):
    """When both circuits are turned off, the strategy is not implemented and it stops."""
    body = client.post(
        "/retrievalStrategy/add",
        json=_payload(vector_enabled="No", bm25_enabled="No"),
        headers=admin_headers,
    ).json()
    assert body["code"] == "500"
    assert body["msg"] == "Vector Retrieval and BM25 Retrieval at least one to enable"


def test_rewrite_without_type_is_rejected(client, admin_headers):
    """Enables the query rewrite but does not choose how to rewrite it."""
    body = client.post(
        "/retrievalStrategy/add",
        json=_payload(query_rewrite_enabled="Yes"),
        headers=admin_headers,
    ).json()
    assert body["code"] == "500"
    assert body["msg"] == "When enabling query rewrite, you must choose how to rewrite"


def test_rerank_top_n_must_be_positive(client, admin_headers):
    """The number of bars to be kept when reordering is enabled must be greater than 0."""
    body = client.post(
        "/retrievalStrategy/add",
        json=_payload(rerank_enabled="Yes", rerank_top_n=0),
        headers=admin_headers,
    ).json()
    assert body["code"] == "500"
    assert body["msg"] == "The number of bars to be saved when reordering is enabled must be greater than 0"


def test_vector_threshold_range_is_checked(client, admin_headers):
    """The cosine likeness threshold must be between 0 and 1."""
    body = client.post(
        "/retrievalStrategy/add",
        json=_payload(vector_score_threshold=1.5),
        headers=admin_headers,
    ).json()
    assert body["code"] == "500"
    assert body["msg"] == "Cosine similarity threshold must be between 0 and 1"


def test_rerank_threshold_range_is_checked(client, admin_headers):
    """Recalculation of relevant sub-limits is individually verified, and an error is identified as which threshold was wrongly filled."""
    body = client.post(
        "/retrievalStrategy/add",
        json=_payload(rerank_score_threshold=1.5),
        headers=admin_headers,
    ).json()
    assert body["code"] == "500"
    assert body["msg"] == "Reranking relevance threshold must be between 0 and 1"


def test_two_thresholds_are_stored_separately(client, admin_headers):
    """The two thresholds are separate and do not cover each other.

    The cosine similarities and reordered correlations are two scales, one of which is measured to be 0.46 - 0.77,
    The other falls 0.14 ~ 0.20, and the same number has a completely different meaning on both sides, so it must be stored separately.
    """
    _cleanup(client, admin_headers)
    client.post(
        "/retrievalStrategy/add",
        json=_payload(vector_score_threshold=0.3, rerank_score_threshold=0.05),
        headers=admin_headers,
    )
    page = client.get(
        "/retrievalStrategy/selectPage",
        params={"name": STRATEGY_NAME, "page_num": 1, "page_size": 10},
        headers=admin_headers,
    ).json()
    saved = page["data"]["list"][0]
    assert saved["vector_score_threshold"] == 0.3
    assert saved["rerank_score_threshold"] == 0.05
    _cleanup(client, admin_headers)


def test_rewrite_type_is_cleared_when_disabled(client, admin_headers):
    """Turn off the rewrite in such a way as to clear it together, without leaving any non-effective residual value."""
    _cleanup(client, admin_headers)
    client.post(
        "/retrievalStrategy/add",
        json=_payload(query_rewrite_enabled="Yes", rewrite_type="Multi-query expansion"),
        headers=admin_headers,
    )
    page = client.get(
        "/retrievalStrategy/selectPage",
        params={"name": STRATEGY_NAME, "page_num": 1, "page_size": 10},
        headers=admin_headers,
    ).json()
    created = page["data"]["list"][0]
    assert created["rewrite_type"] == "Multi-query expansion"

    client.put(
        "/retrievalStrategy/update",
        json=_payload(id=created["id"], query_rewrite_enabled="No", rewrite_type="Multi-query expansion"),
        headers=admin_headers,
    )
    page = client.get(
        "/retrievalStrategy/selectPage",
        params={"name": STRATEGY_NAME, "page_num": 1, "page_size": 10},
        headers=admin_headers,
    ).json()
    assert page["data"]["list"][0]["rewrite_type"] is None

    _cleanup(client, admin_headers)


def test_only_one_default_strategy(client, admin_headers):
    """The original default mark was cleared after adding a new default policy."""
    _cleanup(client, admin_headers)
    before = client.get("/retrieval/strategies", headers=admin_headers).json()
    old_default = [item for item in before["data"] if item["is_default"] == "Yes"][0]

    client.post("/retrievalStrategy/add", json=_payload(is_default="Yes"), headers=admin_headers)
    after = client.get("/retrieval/strategies", headers=admin_headers).json()
    defaults = [item for item in after["data"] if item["is_default"] == "Yes"]
    assert len(defaults) == 1
    assert defaults[0]["name"] == STRATEGY_NAME

    # Restore. Update the interface is full line overlaying: untransmitted fields are always returned by default,
    # So here we're going to go back the way we were, and it's only about_default.
    # Just a few fields will erase the strategy's recall bar, thresholds and so on.
    restore = dict(old_default)
    restore["is_default"] = "Yes"
    client.put("/retrievalStrategy/update", json=restore, headers=admin_headers)

    # Confirm that recovery is in place, and the configuration was not cleared by hand in this case.
    restored = client.get("/retrieval/strategies", headers=admin_headers).json()
    same = [item for item in restored["data"] if item["id"] == old_default["id"]][0]
    assert same["vector_top_k"] == old_default["vector_top_k"]
    assert same["vector_score_threshold"] == old_default["vector_score_threshold"]
    _cleanup(client, admin_headers)


def test_default_strategy_cannot_be_deleted(client, admin_headers):
    """The default policy does not allow deletion."""
    strategies = client.get("/retrieval/strategies", headers=admin_headers).json()
    default = [item for item in strategies["data"] if item["is_default"] == "Yes"][0]
    body = client.delete(f"/retrievalStrategy/delete/{default['id']}", headers=admin_headers).json()
    assert body["code"] == "500"
    assert body["msg"] == "Default strategy cannot be deleted, please set other strategies as default first"


def test_compare_requires_strategies(client, admin_headers):
    """A set of strategies is not chosen to give a human face."""
    body = client.post(
        "/retrievalStrategy/compare",
        json={"kb_ids": [1], "strategy_ids": [], "query": "Warranty period"},
        headers=admin_headers,
    ).json()
    assert body["code"] == "500"
    assert body["msg"] == "Please select at least one search strategy."


def test_compare_limits_strategy_count(client, admin_headers):
    """A few days later, the government announced that it would not be able to do so."""
    body = client.post(
        "/retrievalStrategy/compare",
        json={"kb_ids": [1], "strategy_ids": [1, 2, 3, 1, 2], "query": "Warranty period"},
        headers=admin_headers,
    ).json()
    assert body["code"] == "500"
    assert body["msg"] == "Compare up to 4 strategies at a time"


def test_records_list_is_available(client, admin_headers):
    """Debug log list interface is available and does not return the snapshot text."""
    body = client.get(
        "/retrievalStrategy/records",
        params={"page_num": 1, "page_size": 5},
        headers=admin_headers,
    ).json()
    assert body["code"] == "200"
    for item in body["data"]["list"]:
        assert "result_snapshot" not in item


def test_chunk_type_summary(client, admin_headers):
    """Snippet type distribution returns three types of bar number."""
    body = client.get("/retrievalStrategy/chunkTypes/1", headers=admin_headers).json()
    assert body["code"] == "200"
    assert set(body["data"].keys()) == {"plain", "child", "parent"}
