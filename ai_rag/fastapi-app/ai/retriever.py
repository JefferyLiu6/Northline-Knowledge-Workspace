"""Retrieval.

The first failure point discussed in Chapter 13: vector retrieval cannot recognize proper nouns like GTE-3000,
Keyword retrieval can recognize the model number but does not understand that "warranty" and "quality assurance" are the same thing.
This module runs both methods together, then uses RRF to merge the two rankings into one.

    Vector Retrieval Semantic Matching, cannot recognize exact characters
    BM25 Retrieval Character Matching, does not understand synonyms
    RRF Fusion Only looks at rank, not score, merges the two rankings into one
"""

import re

import jieba

from rank_bm25 import BM25Okapi

# Snippets written by letters and numbers, such as gte 3000, v2, err 5021
ALNUM_MIXED = re.compile(r"^(?=.*[a-z])(?=.*\d)[a-z\d]+$")
# Break the serial clips into letters and numbers.
ALNUM_PARTS = re.compile(r"[a-z]+|\d+")

# Words to be dropped after word breaks. These words are available almost every time, and keeping them will cause BM25's distinction to decline.
STOP_WORDS = {
    "the", "the", "and", "Yes", "in", "have", "for", "and", "and", "or", "Yes", "From",
    "With", "By", "Each", "Me", "You", "Him", "It", "This", "That", "?", "?", "?",
    "What", "How", "How", "How much", "Which", "Can", "Need", "Please ask",
    " ", "\n", "\t",
    ",", ".", "?", "!", ";", ":", "(", ")", "-", "_",
}


def tokenize(text: str) -> list[str]:
    """Tokenize text for keyword retrieval.

    BM25 accepts a token list. Segment text and normalize model identifiers before scoring.

    Here, we do an extra step on top of jieba: split words that are concatenated letters and numbers into separate terms.
    The document writes GTE-3000, jieba splits it into gte, -, 3000;
    The user input is GTE3000, jieba splits it into one term gte3000.
    If not split, neither side matches, and the model can't retrieve the model number—this is exactly the problem this chapter aims to solve.
    After splitting, both sides contain gte and 3000, and they can match.
    """
    tokens = []
    for word in jieba.lcut(text.lower()):
        word = word.strip()
        if not word or word in STOP_WORDS:
            continue
        tokens.append(word)
        # The letter is a serial number, the word is added to an unbundled form and the original word is retained.
        if ALNUM_MIXED.match(word):
            tokens.extend(ALNUM_PARTS.findall(word))
    return tokens


def bm25_search(query: str, candidates: list[dict], top_k: int) -> list[dict]:
    """Perform BM25 keyword retrieval on the given candidate fragments.

    Each item in candidates must have at least two keys: chunk_id and content,
    which are retrieved by the caller from the MySQL knowledge_chunk table.

    BM25 builds an index in memory and scores it all at once. When the number of knowledge chunks is large, this step can be slow,
    so the caller first narrows down the candidate range based on the knowledge base and documents.
    """
    if not candidates:
        return []
    corpus = [tokenize(item["content"]) for item in candidates]
    # When all the pieces are empty, you can't index them. You go straight back to empty results.
    if not any(corpus):
        return []
    bm25 = BM25Okapi(corpus)
    query_tokens = tokenize(query)
    if not query_tokens:
        return []
    scores = bm25.get_scores(query_tokens)
    ranked = sorted(zip(candidates, scores), key=lambda pair: pair[1], reverse=True)
    results = []
    for item, score in ranked[:top_k]:
        # The BM25 score is above bounds, and there's no comparison between the different issues.
        # So just by sorting it out, and then when you're in the process, you don't have to score.
        if score <= 0:
            continue
        merged = dict(item)
        merged["score"] = round(float(score), 6)
        merged["source"] = "BM25 search"
        results.append(merged)
    return results


def rrf_fuse(rankings: list[list[dict]], k: int = 60, top_k: int = 10) -> list[dict]:
    """Use RRF to merge the rankings from multiple retrieval sources into one.

    The formula for RRF is: the total score of a result = the sum of 1 / (k + rank) from each source.

    It only considers the rank, not the original score, which is key:
    The score from vector retrieval is a similarity between 0 and 1, while BM25 scores have no upper bound,
    the two have completely different dimensions, and directly weighted summation is adding two incomparable numbers.
    After converting to rank, both sources become "1st place, 2nd place", and they can be calculated together.

    k is a smoothing constant that controls how much difference there is between ranks:
    the larger k is, the closer the contributions of each rank are, and the more favorable the results that are recalled by multiple sources;
    the smaller k is, the more the top ranks are amplified, and the easier it is for a result ranked first by a single source to appear.
    60 is the empirical value given in the algorithm paper, and this project defaults to using it.
    """
    scores: dict[int, float] = {}
    payloads: dict[int, dict] = {}
    sources: dict[int, set] = {}
    for ranking in rankings:
        for index, item in enumerate(ranking):
            chunk_id = item["chunk_id"]
            # First name counts from 1, so it's index + 1
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + index + 1)
            sources.setdefault(chunk_id, set()).add(item.get("source", ""))
            # The same footage may be recalled on both sides, just like the one you left first.
            payloads.setdefault(chunk_id, item)
    fused = []
    for chunk_id, score in sorted(scores.items(), key=lambda pair: pair[1], reverse=True)[:top_k]:
        item = dict(payloads[chunk_id])
        item["score"] = round(score, 6)
        # It's more credible to point out which way this was recalled.
        item["source"] = "+".join(sorted(source for source in sources[chunk_id] if source))
        fused.append(item)
    return fused
