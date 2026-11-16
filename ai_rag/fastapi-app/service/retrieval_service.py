"""Retrieve business logic.

Recall to a search strategy, returning the list of segments with fractions and sources.
This chapter enables vector search, BM25 retrieval and RRF integration of three paths.
The following chapters continue to rehash, rewrite and fill in the parent block on this function.
"""

import asyncio
from typing import List

from ai import model_factory, query_rewriter, reranker, retriever, vector_store
from ai.query_rewriter import MULTI_QUERY
from common.exception_handler import CustomException
from common.times import cost_millis, now
from models import (
    AiModelConfig,
    ChunkStrategy,
    KnowledgeBase,
    KnowledgeChunk,
    RetrievalStrategy,
)

# BM25 Limit the maximum number of readings at a time by entering all candidate segments into memory indexes.
# To avoid eating the memory when the knowledge base is so big.
BM25_CANDIDATE_LIMIT = 5000
# Only the pieces that will be retrieved will be called back, and the father's piece is left to fill in after he hits.
SEARCHABLE_TYPES = ["Standard chunk", "Child chunk"]

# This field in the search pipe is over and over again at different stages, with a new order of magnitude every time it is covered:
#
#     Vector search Cosine resemblance 0 to 1, actual relevant snippet 0.46 ~ 0.77, irrelevant 0.14 ~ 0.23
#     BM25 Retrieval BM25 score. No upper bounds, no comparison between different questions.
#     RRF Integration RRF Seconds 1/ (rrf_k+n), rf_k=60 only 0.016~0.033
#     Rehearsals 0 to 1, actual footage 0.14 ~ 0.20, irrelevant 0.006
#
# The number of scores alone does not tell which one it is, so the outline goes on as a visible message.
# The threshold filters the way you know what you're comparing to.
# The score in the search pipe will be overwritten at different stages, with a new order of quantities for each time it covers.
SCALE_COSINE = "Cosine Similarity"
SCALE_BM25 = "BM25 score"
SCALE_RRF = "RRF rank"
SCALE_RERANK = "Recalculate Relevant Divisions"

# Which threshold field is the order of magnitude?
# Only values of cosine similarities and reordered relative fractions have absolute meanings and can be proportional to a fixed threshold;
# The range of values for both is a different order of magnitude, so each of them is given a threshold in the strategy table.
# The BM25 score is not upper, the RRF rankings are only for rank and rank, none of which is in this table, and no threshold filter is used when encountered.
THRESHOLD_FIELD_BY_SCALE = {
    SCALE_COSINE: "vector_score_threshold",
    SCALE_RERANK: "rerank_score_threshold",
}


def predict_score_scale(strategy: dict) -> str:
    """When the strategy is completed, which order of magnitude will be the score when it is calculated by policy configuration.

    This is "pre-event," and the score_scale in retrive, which follows the results, is not the same thing:
    In a post entitled "The World of Human Rights", Retrieve wrote about what had actually happened this time (BM25, when he didn't call back, was the only one on the list).
    This function only looks at the switch combination and answers, "Where does this configuration normally go?"

    The strategy management page is to tell managers which threshold value to fill before saving, and can only be projected by configuration;
    But the extrapolation rule must be consistent with retrieve's pipe, so just write one here.
    Pages are retrieved through an interface and do not be written again at the front end.
    """
    # We're rehearsing. The last step is to reorder the score.
    if strategy.get("rerank_enabled") == "Yes":
        return SCALE_RERANK
    # A few calls were made, and two lists were created when both paths opened.
    routes = sum(
        1 for field in ("vector_enabled", "bm25_enabled") if strategy.get(field) == "Yes"
    )
    # The multi-check extension splits one question into several questions, and each query is called back to a list on every road;
    # Index decomposition and HyDE output of only one query, without prejudice to the number of singles
    queries = 1
    if strategy.get("query_rewrite_enabled") == "Yes" and strategy.get("rewrite_type") == MULTI_QUERY:
        queries = strategy.get("multi_query_count") or 1
    # RRF blends after more than one list becomes 1/ (k+)
    if routes * queries > 1:
        return SCALE_RRF
    # One-way search points are the way it's done.
    return SCALE_COSINE if strategy.get("vector_enabled") == "Yes" else SCALE_BM25


def strategy_dict(strategy: RetrievalStrategy) -> dict:
    fields = {
        "id": strategy.id,
        "name": strategy.name,
        "vector_enabled": strategy.vector_enabled,
        "vector_top_k": strategy.vector_top_k,
        "bm25_enabled": strategy.bm25_enabled,
        "bm25_top_k": strategy.bm25_top_k,
        "rrf_k": strategy.rrf_k,
        "rerank_enabled": strategy.rerank_enabled,
        "rerank_model_id": strategy.rerank_model_id,
        "rerank_top_n": strategy.rerank_top_n,
        "query_rewrite_enabled": strategy.query_rewrite_enabled,
        "rewrite_type": strategy.rewrite_type,
        "multi_query_count": strategy.multi_query_count,
        "parent_recall_enabled": strategy.parent_recall_enabled,
        "vector_score_threshold": float(strategy.vector_score_threshold) if strategy.vector_score_threshold is not None else None,
        "rerank_score_threshold": float(strategy.rerank_score_threshold) if strategy.rerank_score_threshold is not None else None,
        "metadata_filter": strategy.metadata_filter,
        "is_default": strategy.is_default,
        "remark": strategy.remark,
        "create_time": strategy.create_time,
        "update_time": strategy.update_time,
    }
    # The list page then indicates which thresholds are actually in effect for this strategy, and determines that the rules are not rewritten at the front end
    fields["score_scale"] = predict_score_scale(fields)
    return fields


async def load_strategy(strategy_id: int | None) -> dict:
    """Retrieval policy, using default policy when not specified."""
    if strategy_id:
        strategy = await RetrievalStrategy.get_or_none(id=strategy_id)
        if strategy is None:
            raise CustomException("No search policy found")
        return strategy_dict(strategy)
    strategy = await RetrievalStrategy.get_or_none(is_default="Yes")
    if strategy is None:
        raise CustomException("No default search policy set. Please insert one in the search policy first")
    return strategy_dict(strategy)


async def _load_candidates(kb_ids: List[int], document_ids: List[int] | None) -> List[dict]:
    """Reads the selected segment for BM25 from MySQL.

    BM25 Counts within memory and does not rely on vector banks, so the candidate snippets are taken directly from the knownege_chunk table.
    """
    query = KnowledgeChunk.filter(kb_id__in=kb_ids, chunk_type__in=SEARCHABLE_TYPES)
    if document_ids:
        query = query.filter(document_id__in=document_ids)
    chunks = await query.limit(BM25_CANDIDATE_LIMIT)
    return [
        {
            "chunk_id": chunk.id,
            "kb_id": chunk.kb_id,
            "document_id": chunk.document_id,
            "parent_chunk_id": chunk.parent_id,
            "chunk_type": chunk.chunk_type,
            "title_path": chunk.title_path,
            "content": chunk.content,
        }
        for chunk in chunks
    ]


async def _vector_recall(kb_ids: List[int], query: str, strategy: dict, document_ids: List[int] | None) -> List[dict]:
    """Vector search: Encode the problem into a vector and go to PGVector to find the most recent ones."""
    config = await model_factory.load_enabled(model_factory.EMBEDDING)
    bases = await KnowledgeBase.filter(id__in=kb_ids)
    if any(kb.embedding_model_id not in (None, config.id) for kb in bases):
        raise CustomException("Embedding model mismatch: restore the bound model or rebuild the index")
    embeddings = model_factory.build_embeddings(config)
    vector = await embeddings.aembed_query(query)
    return await vector_store.search(
        kb_ids=kb_ids,
        embedding=vector,
        top_k=strategy["vector_top_k"],
        document_ids=document_ids,
        chunk_types=SEARCHABLE_TYPES,
    )


async def _bm25_recall(kb_ids: List[int], query: str, strategy: dict, document_ids: List[int] | None) -> List[dict]:
    """BM25 Retrieval: Match keywords in the candidate segment."""
    candidates = await _load_candidates(kb_ids, document_ids)
    # Splitting and scoring are pure CPU operations, thrown into a thread to perform without blocking the cycle of events
    return await asyncio.to_thread(
        retriever.bm25_search, query, candidates, strategy["bm25_top_k"]
    )


async def retrieve(
    kb_ids: List[int],
    query: str,
    strategy: dict,
    document_ids: List[int] | None = None,
    history: List[dict] | None = None,
) -> dict:
    """A strategic search is carried out to return the results and stages of a time-consuming process.

    The returned stage records how many pages per road were recalled and how long it took.
    The debugging table of chapter 19 shows it directly as a strategy comparison.
    """
    if not query or not query.strip():
        raise CustomException("Please enter a search problem.")
    if not kb_ids:
        raise CustomException("Select a knowledge base")
    started = now()
    stages: List[dict] = []
    rankings: List[List[dict]] = []
    # And the rankings are matched by a log of how many points come back from each route.
    ranking_scales: List[str] = []

    # Rewrite the question before searching. Rewrite a set of output queries, and each of the next paths runs one at a time.
    queries = [query]
    if strategy["query_rewrite_enabled"] == "Yes":
        stage_started = now()
        queries = await query_rewriter.rewrite(
            query,
            strategy.get("rewrite_type"),
            strategy["multi_query_count"],
            history,
        )
        stages.append(
            {
                "name": f"Query rewrite ({strategy.get('rewrite_type') or 'Unconfigurated'})",
                "count": len(queries),
                "cost_millis": cost_millis(stage_started),
                "detail": queries,
            }
        )

    if strategy["vector_enabled"] == "Yes":
        stage_started = now()
        total = 0
        for one in queries:
            vector_results = await _vector_recall(kb_ids, one, strategy, document_ids)
            # Every query is recalled as an example for integration.
            rankings.append(vector_results)
            # The score returned from the library is converted by cosine distance
            ranking_scales.append(SCALE_COSINE)
            total += len(vector_results)
        stages.append(
            {
                "name": "Vector search",
                "count": total,
                "cost_millis": cost_millis(stage_started),
            }
        )

    if strategy["bm25_enabled"] == "Yes":
        stage_started = now()
        total = 0
        for one in queries:
            bm25_results = await _bm25_recall(kb_ids, one, strategy, document_ids)
            rankings.append(bm25_results)
            # The BM25 score is not high, it's only for sorting.
            ranking_scales.append(SCALE_BM25)
            total += len(bm25_results)
        stages.append(
            {
                "name": "BM25 search",
                "count": total,
                "cost_millis": cost_millis(stage_started),
            }
        )

    if not rankings:
        raise CustomException("This policy does not enable any search along the way. Please enable at least vector or BM25 searches")

    # The blank list was filtered and one rewrite query should not have taken a place in integration if none of it had been recalled.
    # The scale and the list correspond to one another, so we can't just sift together.
    survivors = [(scale, ranking) for scale, ranking in zip(ranking_scales, rankings) if ranking]
    # What's the score in the current resultes, which is constantly rewrited as the pipe goes down
    score_scale = None
    if not survivors:
        results = []
    elif len(survivors) == 1:
        # It's not the only way to integrate. The result of this road is that the score is the same as it does.
        score_scale, results = survivors[0]
    else:
        stage_started = now()
        # RRF does not look at scores by name, and the scores of each of the integrated stripes become 1/(k+nominal) this level of measure.
        # About 0.016 to 0.03, and the cosine similarities with vector searches are not an outline
        # RRF does not look at scores by name, and the scores of each integrated line become 1/ (k+nominal) this scale
        score_scale = SCALE_RRF
        rankings = [ranking for _, ranking in survivors]
        results = retriever.rrf_fuse(
            rankings,
            k=strategy["rrf_k"],
            top_k=max(strategy["vector_top_k"], strategy["bm25_top_k"]),
        )
        stages.append(
            {
                "name": "RRF fusion",
                "count": len(results),
                "cost_millis": cost_millis(stage_started),
            }
        )

    if strategy["rerank_enabled"] == "Yes" and results:
        stage_started = now()
        before = len(results)
        results = await _rerank(query, results, strategy)
        # The re-allocation model gave a new score to cover the points of the rough sift phase and then the order of magnitude became reordered.
        # It's also 0 to 1, but it's not the same thing as cosine: only 0.14 ~ 0.20 is relevant to actual force.
        # Take the cosine threshold of 0.3 and cut off all results, so the two thresholds are separated.
        score_scale = SCALE_RERANK
        stages.append(
            {
                "name": "Rerank",
                # Reordering is a subtraction: how many are sifted in, how many left behind after the rehearsal.
                "count": f"{before} → {len(results)}",
                "cost_millis": cost_millis(stage_started),
            }
        )

    if strategy["parent_recall_enabled"] == "Yes" and results:
        stage_started = now()
        before = len(results)
        results = await _backfill_parents(results)
        stages.append(
            {
                "name": "Parent chunk expansion",
                # The pieces are replaced by the parent pieces, and when they belong to the same parent, they merge into one.
                "count": f"{before} → {len(results)}",
                "cost_millis": cost_millis(stage_started),
            }
        )

    # The score was dropped below the threshold, leaving "no knowledge base" on which to base the judgment.
    results, threshold_stage = apply_score_threshold(results, score_scale, strategy)
    if threshold_stage:
        stages.append(threshold_stage)

    return {
        "query": query,
        # Query actually used to retrieve, different from original problem when rewrited
        "queries": queries,
        "strategy_id": strategy["id"],
        "strategy_name": strategy["name"],
        "results": results,
        # What's the score in the result of which the page labels the fractional column without calling it "Similarity"?
        "score_scale": score_scale,
        "stages": stages,
        "cost_millis": cost_millis(started),
    }


def apply_score_threshold(
    results: List[dict], score_scale: str | None, strategy: dict
) -> tuple[List[dict], dict | None]:
    """Filters the current fractional order to the threshold and returns the result of the filtering and the line that you want to add to the schedule.

    The field at which the threshold is taken is determined by the order of magnitude: the end of the line is a cosine similarity, using vector thresholds.
    Recalculation thresholds are used to reorder the relevant points; BM25 fractions or RRF slots are not filtered.
    Because the absolute values of these two fractions do not represent the degree of relevance and the fixed threshold ratio is irrelevant.

    The second return value is a stage record, none of which can be remembered. Filtering and skipping leave marks:
    The threshold box on the page is not really in effect and must be visible from the schedule.
    """
    if not results:
        return results, None

    threshold_field = THRESHOLD_FIELD_BY_SCALE.get(score_scale)

    if threshold_field is None:
        # This time, the programme does not support thresholds. There is nothing to say about a threshold that doesn't fit in the strategy.
        # It's the right thing to tell me why it didn't work.
        configured = any(
            strategy.get(field) is not None for field in THRESHOLD_FIELD_BY_SCALE.values()
        )
        if not configured:
            return results, None
        return results, {
            "name": "Threshold filter (not applicable at this time)",
            "count": f"{len(results)} → {len(results)}",
            "cost_millis": 0,
            "detail": [
                f"Score scale: {score_scale}",
                "Rank-based scores cannot be compared with a fixed threshold.",
                "Enable reranking to apply a relevance threshold to the final scores.",
            ],
        }

    threshold = strategy.get(threshold_field)
    if threshold is None:
        # Outline supports thresholds, but this slot is not filled and is treated without filtering
        return results, None

    # No fractions result in non-comparison, avoid missing fields being deleted
    kept = [item for item in results if item.get("score") is None or item["score"] >= threshold]
    scores = [item["score"] for item in results if item.get("score") is not None]
    detail = [f"Score scale: {score_scale}, threshold {threshold}"]
    if scores:
        detail.append(f"Score range: {min(scores):.4f} to {max(scores):.4f}")
    if scores and not kept:
        # And when it was cut off, it made sense. Without that sentence, only 0 bars could be seen on the page.
        # It makes people think it's a knowledge base that doesn't cut or quantify, looking for a place where there's no problem.
        detail.append(
            f"All results fell below the threshold of {threshold}. The highest score was {max(scores):.4f}. "
            f"If the knowledge base has an answer, try lowering this strategy’s threshold."
        )
    stage = {
        "name": f"Threshold filtering ({score_scale} ≥ {threshold})",
        "count": f"{len(results)} → {len(kept)}",
        "cost_millis": 0,
        "detail": detail,
    }
    return kept, stage


async def _rerank(query: str, results: List[dict], strategy: dict) -> List[dict]:
    """The rough sift results are handed over to the reordered model.

    The policy specifies the reorder model and uses the one that is currently enabled without specifying it.
    """
    config = None
    if strategy.get("rerank_model_id"):
        config = await AiModelConfig.get_or_none(id=strategy["rerank_model_id"])
    if config is None:
        config = await model_factory.load_enabled(model_factory.RERANK)
    compressor = reranker.DashScopeRerank(config=config, top_n=strategy["rerank_top_n"])
    documents = reranker.to_documents(results)
    ranked = await compressor.acompress_documents(documents, query)
    return reranker.from_documents(ranked)


async def retrieve_by_strategy(
    kb_ids: List[int],
    query: str,
    strategy_id: int | None = None,
    document_ids: List[int] | None = None,
    history: List[dict] | None = None,
) -> dict:
    """The search test entrance on the page: Retrieve by policy ID for configuration."""
    strategy = await load_strategy(strategy_id)
    # The search results are given with the name of the document, and the page shows "What document is this from"
    outcome = await retrieve(kb_ids, query, strategy, document_ids, history)
    await _fill_document_name(outcome["results"])
    return outcome


async def _backfill_parents(results: List[dict]) -> List[dict]:
    """Change the life of a piece to its parent.

    A small block, semanticly focused when searching, hits more accurately; a large parent block, complete context, and the model is only fully answered.
    That's what chapter 09 was built for.

    Several sub-blocks are merged into a single section when they belong to the same parent block, avoiding duplicate distribution of the same paragraph to models.
    The normal block has no parent. Keep it as it is.
    """
    parent_ids = {
        item["parent_chunk_id"]
        for item in results
        if item.get("chunk_type") == "Child chunk" and item.get("parent_chunk_id")
    }
    if not parent_ids:
        return results
    parents = await KnowledgeChunk.filter(id__in=list(parent_ids))
    parent_map = {parent.id: parent for parent in parents}

    merged: List[dict] = []
    # It's a parent piece that's been put in the results.
    used_parents: set[int] = set()
    for item in results:
        parent_id = item.get("parent_chunk_id")
        if item.get("chunk_type") != "Child chunk" or not parent_id:
            merged.append(item)
            continue
        parent = parent_map.get(parent_id)
        if parent is None:
            # If the parent is deleted or the data are inconsistent, return it with a subblock and not allow this result to disappear.
            merged.append(item)
            continue
        if parent_id in used_parents:
            continue
        used_parents.add(parent_id)
        expanded = dict(item)
        expanded.update(
            {
                "chunk_id": parent.id,
                "chunk_type": "Parent chunk",
                "content": parent.content,
                "page_no": parent.page_no,
                # Sorting bits and fractions follows the piece of life, and the father doesn't score himself.
                "source": f"{item.get('source', '')}→Parent chunk expansion",
                # Write down which sub-block was killed, and the little piece on the page can be traced back to the actual match.
                "matched_chunk_id": item["chunk_id"],
            }
        )
        merged.append(expanded)
    return merged


async def _fill_document_name(results: List[dict]) -> None:
    """Adds the document name to the search results.

    The vector table has redundancies but no redundant document names because the documents can be renamed,
    Redundancy would be inconsistent, so press document_id to check back when displayed.
    """
    if not results:
        return
    from models import KnowledgeDocument

    document_ids = {item["document_id"] for item in results if item.get("document_id")}
    if not document_ids:
        return
    documents = await KnowledgeDocument.filter(id__in=list(document_ids))
    names = {doc.id: doc.name for doc in documents}
    for item in results:
        item["document_name"] = names.get(item.get("document_id"))


async def kb_options_with_chunks() -> List[dict]:
    """The knowledge base of the tests is retrieved on the page, with segments that can be easily retrieved."""
    bases = await KnowledgeBase.filter(status="Active").order_by("-id")
    return [
        {"id": kb.id, "name": kb.name, "chunk_count": kb.chunk_count}
        for kb in bases
    ]


async def chunk_strategy_of(kb_id: int) -> dict | None:
    """Check the splitting policy attached to the knowledge base, and show on the page whether it is a parent-son split."""
    kb = await KnowledgeBase.get_or_none(id=kb_id)
    if kb is None or not kb.chunk_strategy_id:
        return None
    strategy = await ChunkStrategy.get_or_none(id=kb.chunk_strategy_id)
    if strategy is None:
        return None
    return {"id": strategy.id, "name": strategy.name, "strategy_type": strategy.strategy_type}
