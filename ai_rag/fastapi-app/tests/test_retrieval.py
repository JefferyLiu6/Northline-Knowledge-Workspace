"""Retrieval test.

Both BM25 and RRF are pure Python calculations, not dependent on vector banks and models, which can be measured directly.
The vector search is connected to the PGVecor and the vector-retailing model, which is manually validated on the page.
"""

from ai import retriever
from service import retrieval_service

CHUNKS = [
    {"chunk_id": 1, "content": "The GTE-3000 series has 24 months of quality assurance and is free of charge for non-anthropogenic damage."},
    {"chunk_id": 2, "content": "Refunds were returned to payment accounts on a working day basis from 3 to 5 days after approval."},
    {"chunk_id": 3, "content": "This product supports privatization deployment and can be delivered to the client ' s own server environment."},
    {"chunk_id": 4, "content": "Post-sale service commitments: technical support from 9 to 18 p.m. on weekdays."},
]


def test_tokenize_splits_model_number():
    """The numeric numbers in the model are singled out by word, which is why keyword retrievals recognize models."""
    tokens = retriever.tokenize("GTE-3000 How long is the warranty?")
    assert "3000" in tokens
    assert "gte" in tokens
    # Dismissed words are thrown out, not in the ratings.
    assert "the" not in tokens


def test_bm25_finds_exact_model_number():
    """Vector-retrieval undetected model, BM25 with accurate hits."""
    results = retriever.bm25_search("GTE3000 warranty", CHUNKS, top_k=3)
    assert results
    assert results[0]["chunk_id"] == 1
    # Every result shows where you're coming from.
    assert results[0]["source"] == "BM25 search"


def test_bm25_returns_nothing_when_no_word_matches():
    """One word doesn't match the BM25."""
    results = retriever.bm25_search("Quantum computer lease price", CHUNKS, top_k=3)
    assert results == []


def test_bm25_ignores_zero_score_items():
    """The score is zero, and no extra segment to fill TopK."""
    results = retriever.bm25_search("Refunds", CHUNKS, top_k=4)
    assert len(results) < len(CHUNKS)
    assert all(item["score"] > 0 for item in results)


def test_rrf_ranks_item_hit_by_both_rankings_first():
    """The result of both calls is in front of only one round."""
    vector_ranking = [
        {"chunk_id": 2, "content": "b", "source": "Vector search"},
        {"chunk_id": 1, "content": "a", "source": "Vector search"},
    ]
    bm25_ranking = [
        {"chunk_id": 3, "content": "c", "source": "BM25 search"},
        {"chunk_id": 1, "content": "a", "source": "BM25 search"},
    ]
    fused = retriever.rrf_fuse([vector_ranking, bm25_ranking], k=60, top_k=5)
    # Number 1 is in line 2 on both tracks, and after adding up, it exceeds the two and three of each.
    assert fused[0]["chunk_id"] == 1
    # The source indicates which routes are calling back.
    assert fused[0]["source"] == "BM25 search+Vector search"


def test_rrf_dedupes_by_chunk_id():
    """When the same footage was recalled on both sides, only one was retained."""
    ranking_one = [{"chunk_id": 7, "content": "x", "source": "Vector search"}]
    ranking_two = [{"chunk_id": 7, "content": "x", "source": "BM25 search"}]
    fused = retriever.rrf_fuse([ranking_one, ranking_two], k=60, top_k=5)
    assert len(fused) == 1


def test_rrf_smaller_k_widens_gap_between_ranks():
    """k The smaller the score between neighbouring names is greater."""
    ranking = [
        {"chunk_id": 1, "content": "a", "source": "Vector search"},
        {"chunk_id": 2, "content": "b", "source": "Vector search"},
    ]
    with_large_k = retriever.rrf_fuse([ranking], k=60, top_k=5)
    with_small_k = retriever.rrf_fuse([ranking], k=1, top_k=5)
    large_gap = with_large_k[0]["score"] - with_large_k[1]["score"]
    small_gap = with_small_k[0]["score"] - with_small_k[1]["score"]
    assert small_gap > large_gap


def test_rrf_respects_top_k():
    """The integration results are cut by top_k."""
    ranking = [{"chunk_id": index, "content": "x", "source": "Vector search"} for index in range(1, 11)]
    fused = retriever.rrf_fuse([ranking], k=60, top_k=3)
    assert len(fused) == 3


def test_seed_retrieval_strategies(client, admin_headers):
    """Three sets of search strategies have been pre-positioned in the initialization data to cover baseline to full three."""
    body = client.get("/retrieval/strategies", headers=admin_headers).json()
    assert body["code"] == "200"
    names = {item["name"]: item for item in body["data"]}
    baseline = names["Baseline - Vector search only"]
    hybrid = names["Advanced - Hybrid search"]
    # The baseline is only a vector, which is the basis for chapter 13
    assert baseline["vector_enabled"] == "Yes"
    assert baseline["bm25_enabled"] == "No"
    assert baseline["is_default"] == "Yes"
    # BM25 open in step. RRF blends.
    assert hybrid["vector_enabled"] == "Yes"
    assert hybrid["bm25_enabled"] == "Yes"
    assert hybrid["rrf_k"] == 60


def test_search_without_kb_is_rejected(client, admin_headers):
    """A knowledge base is not selected to give a hint."""
    body = client.post(
        "/retrieval/search",
        json={"kb_ids": [], "query": "How long is the warranty"},
        headers=admin_headers,
    ).json()
    assert body["code"] == "500"
    assert body["msg"] == "Select a knowledge base"


def test_search_without_query_is_rejected(client, admin_headers):
    """Question is to give a hint when empty."""
    body = client.post(
        "/retrieval/search",
        json={"kb_ids": [1], "query": "   "},
        headers=admin_headers,
    ).json()
    assert body["code"] == "500"
    assert body["msg"] == "Please enter a search problem."

def test_rrf_scores_are_not_similarity_scale():
    """RRF ' s mixed score is the last number of names, and cosine similarities are not an outline.

    RRF scores are 1/ (k+) with only 1/61 at rrf_k=60 equals about 0.016,
    And the relevant segments under cosine similarities are measured at 0.46 to 0.77.
    This is an example of nailing the difference in the order of magnitude, which is a prerequisite that thresholds must be separated according to the outline.
    """
    vector_ranking = [
        {"chunk_id": 1, "content": "Contents I", "score": 0.82, "source": "Vector search"},
        {"chunk_id": 2, "content": "Component II", "score": 0.75, "source": "Vector search"},
    ]
    bm25_ranking = [
        {"chunk_id": 1, "content": "Contents I", "score": 6.4, "source": "BM25 search"},
        {"chunk_id": 3, "content": "Component III", "score": 3.1, "source": "BM25 search"},
    ]

    fused = retriever.rrf_fuse([vector_ranking, bm25_ranking], k=60, top_k=5)

    assert fused
    # The scores for each of the integrations are much smaller than the similarity threshold of 0.3 in the strategy.
    assert all(item["score"] < 0.05 for item in fused)
    # The one that hit both paths is still in the first place, which means that sorting itself is right. It's just a change of scale.
    assert fused[0]["chunk_id"] == 1


# A set of false recall results, scores by cosine resemblance.
COSINE_RESULTS = [
    {"chunk_id": 1, "content": "Contents I", "score": 0.62},
    {"chunk_id": 2, "content": "Component II", "score": 0.25},
]
# The same two, the fractions are replaced by a reordered order of magnitude. Only 0.14 - 0.20 of the relevant segments under this sequence are measured
RERANK_RESULTS = [
    {"chunk_id": 1, "content": "Contents I", "score": 0.19},
    {"chunk_id": 2, "content": "Component II", "score": 0.006},
]
# Each of the thresholds is marked by its own order of magnitude, between measured zones.
STRATEGY = {"vector_score_threshold": 0.3, "rerank_score_threshold": 0.05}


def test_threshold_uses_vector_field_for_cosine_scale():
    """The order of measure is a vector threshold when the cosine is similar."""
    kept, stage = retrieval_service.apply_score_threshold(
        COSINE_RESULTS, retrieval_service.SCALE_COSINE, STRATEGY
    )
    # 0.62 Stay, 0.25 below 0.3 and thrown out.
    assert [item["chunk_id"] for item in kept] == [1]
    assert "0.3" in stage["name"]
    assert retrieval_service.SCALE_COSINE in stage["name"]


def test_threshold_uses_rerank_field_for_rerank_scale():
    """The order of magnitude is the reordering of relevant minutes, compared to a recalculation threshold, not 0.3 for the vector.

    This is the initial failure: recalculations are measured to be as high as 0.2 and below.
    Take the cosine threshold of 0.3 to the card, none of which will be left.
    """
    kept, stage = retrieval_service.apply_score_threshold(
        RERANK_RESULTS, retrieval_service.SCALE_RERANK, STRATEGY
    )
    # 0.19 It's a relevant segment, it has to be left; 0.006 is an entirely irrelevant level of quantum and should be thrown
    assert [item["chunk_id"] for item in kept] == [1]
    assert "0.05" in stage["name"]
    # If you change the threshold of the vector, it'll be killed by mistake.
    assert STRATEGY["vector_score_threshold"] > RERANK_RESULTS[0]["score"]


def test_threshold_is_skipped_for_rrf_scale_but_leaves_a_trace():
    """RRF rank does not support the threshold, this step skips but must leave marks in the schedule.

    The silent skipping will make the threshold box on the page seem to be working, but it's still empty.
    The reason for skipping the output line is therefore also documented.
    """
    fused_results = [{"chunk_id": 1, "content": "Contents I", "score": 0.0328}]
    kept, stage = retrieval_service.apply_score_threshold(
        fused_results, retrieval_service.SCALE_RRF, STRATEGY
    )
    # None of them should be filtered.
    assert kept == fused_results
    assert stage is not None
    assert "not applicable" in stage["name"]


def test_threshold_explains_why_everything_was_filtered_out():
    """When all thresholds are cut off, the details are made clear as a threshold card and not as an access to the knowledge base."""
    low_results = [{"chunk_id": 1, "content": "Contents I", "score": 0.006}]
    kept, stage = retrieval_service.apply_score_threshold(
        low_results, retrieval_service.SCALE_RERANK, STRATEGY
    )
    assert kept == []
    # This maximum score and threshold is to appear in the detail, and the page will be prompted to use it.
    assert any("0.0060" in line and "0.05" in line for line in stage["detail"])


def test_threshold_does_nothing_when_that_scale_has_no_value():
    """The outline supports thresholds, but if this is not filled in, it does not filter or record the stage."""
    kept, stage = retrieval_service.apply_score_threshold(
        COSINE_RESULTS, retrieval_service.SCALE_COSINE, {"rerank_score_threshold": 0.05}
    )
    assert kept == COSINE_RESULTS
    assert stage is None


def test_predict_score_scale_covers_every_switch_combination():
    """This is the only rule for extrapolating the volume by a combination of switches, and pages are taken through an interface and do not rewrite at the front end.

    This example nails all four directions and changes the search pipe to see if the predictions have changed.
    """
    predict = retrieval_service.predict_score_scale

    # Only vectors, no rewrite: single-way queries, scores are cosine similarities
    assert predict({"vector_enabled": "Yes"}) == retrieval_service.SCALE_COSINE
    # BM25: The score is BM25, no upper bounds.
    assert predict({"bm25_enabled": "Yes"}) == retrieval_service.SCALE_BM25
    # Both ways open: two lists to merge
    assert (
        predict({"vector_enabled": "Yes", "bm25_enabled": "Yes"})
        == retrieval_service.SCALE_RRF
    )
    # Rehearsal: The last step is to reorder the score. It doesn't matter if we go ahead or get together.
    assert (
        predict({"vector_enabled": "Yes", "bm25_enabled": "Yes", "rerank_enabled": "Yes"})
        == retrieval_service.SCALE_RERANK
    )


def test_predict_score_scale_counts_multi_query_rankings():
    """The multiple query extension will allow single paths to be added to the list, as well as RRF integration.

    Seeing only "a few paths" leaves out this situation and miscalculates a single vector strategy to cosine resemblance.
    """
    predict = retrieval_service.predict_score_scale

    multi = {
        "vector_enabled": "Yes",
        "query_rewrite_enabled": "Yes",
        "rewrite_type": "Multi-query expansion",
        "multi_query_count": 3,
    }
    assert predict(multi) == retrieval_service.SCALE_RRF

    # Indicator decomposition and HyDE only produces one query, the list is still one, the order of magnitude remains unchanged.
    for rewrite_type in ("Coreference resolution", "HyDE"):
        one = dict(multi, rewrite_type=rewrite_type)
        assert predict(one) == retrieval_service.SCALE_COSINE
