# Reliability and retrieval evaluation

This report concerns the fictional Northline demo corpus. It records engineering checks and a development benchmark; it does not claim customer outcomes.

## Implementation verified

- Replacement, reparsing, direct chunk editing, and deletion remove obsolete vectors. Source replacement also clears parsed text and MySQL chunks.
- Document commands lock the knowledge-base/document rows and reject conflicting processing jobs. A concurrent parse regression checks that only one task is created.
- Bound embedding configurations cannot change identity or be deleted. Queries reject a mismatched active embedding model.
- Uploads require authentication, use immutable storage keys, reject traversal and unsupported types, validate images, and enforce a 50 MB file limit. Downloads require an administrator or an authorized avatar session.
- User directories and raw chunks are restricted to administrators. Passwords use salted PBKDF2-SHA256; seeded and existing users are hashed. Signing keys are private per installation, and password changes invalidate existing tokens.
- Frontend upload headers, file cookies, logout, avatar previews, and local CORS are integrated. Legacy Office formats require conversion; moving an existing document to another knowledge base requires a new upload.

## Verification

- 222 backend regression tests passed, including permission checks, duplicate filenames, path traversal, model binding, stale vectors, password hashing, token revocation, and concurrent parse requests.
- Frontend production build passed. Existing large-bundle warnings remain.
- A disposable end-to-end test with real Ollama embeddings passed: upload, parse, split, embed, replace, retrieve only current text, reparse, and delete.
- Live-index reconciliation inspected 110 vectors and found no orphaned or stale entries.
- Chrome checks passed: administrator login, upload and registration, authenticated download, logout denial, standard-user avatar preview, Q&A navigation, and document preview. Desktop 1440×960 and mobile 390×844 were checked; no JavaScript page errors were observed.

## Experiment

50 questions: 42 answerable and 8 unanswerable, across five source formats. The generator and judge are llama3.1:8b; embeddings use mxbai-embed-large:latest (1024 dimensions). Reranking uses the local llama3.1:8b scorer. Each retrieval provides at most five chunks; query rewriting and parent expansion are disabled.

All 150 case/strategy comparisons completed without request errors.

| Metric | Vector | Hybrid | Hybrid + reranking |
| --- | ---: | ---: | ---: |
| Completed cases | 50 | 50 | 50 |
| Request errors | 0 | 0 | 0 |
| Expected-source-document recall@5 | 100.0% | 100.0% | 100.0% |
| Required technical evidence in top 5 (18 cases) | 83.3% | 94.4% | 94.4% |
| Required technical evidence in top 3 (18 cases) | 72.2% | 83.3% | 94.4% |
| Critical fact checks: pass rate (18 cases) | 83.3% | 94.4% | 94.4% |
| Answerable cases with explicit no-content refusal | 21.4% | 11.9% | 14.3% |
| Judge-rated correctness (known false positives) | 84.0% | 86.0% | 88.0% |
| Judge-rated supported citations (answerable cases) | 66.7% | 81.0% | 76.2% |
| Judge-rated unsupported-answer rate (unreliable) | 0.0% | 0.0% | 0.0% |
| Unanswerable explicit no-content refusal | 100.0% | 100.0% | 100.0% |
| Median retrieval latency | 0.09 s | 0.18 s | 7.62 s |
| Median answer generation | 4.51 s | 3.48 s | 3.16 s |

## What this run suggests

Technical fact pass rates were 83.3% for vector, 94.4% for hybrid, and 94.4% for hybrid with reranking. Compare those rates with the measured latency above. This experiment reranks the same five candidates and returns all five, so top-5 evidence coverage is necessarily unchanged by reranking; the top-3 evidence metric tests ordering. A larger candidate pool followed by a smaller reranked output is needed to evaluate candidate selection before drawing a general conclusion about reranking.

## How to interpret the numbers

The main retrieval metric is exact expected-source-document recall@5, using source filenames labeled in cases.json. It is deliberately coarse: retrieving an unrelated chunk from the right document still counts. The separate technical-evidence check verifies required facts in the retrieved passages for 18 cases. Neither metric alone proves the answer is correct.

The raw run also contains provisional chunk labels: expected chunks come from reference passages using the documented word-overlap rule. The benchmark reports recall of those canonical chunks, not an exhaustive human relevance assessment. For example, the frequent-restart question can retrieve a useful alternate source while missing the labeled FAQ chunk. Hit@5 and the raw evidence should be reviewed together.

**Judge/fact-check disagreements in this run:** case-023 (vector), case-023 (hybrid), case-023 (hybrid_rerank), case-034 (vector), case-035 (vector). The same-model judge marked these answers correct even though they failed a selected technical fact pattern. Inspect the raw answers and evidence before interpreting either score.

Earlier development runs exposed confusion between recommended deployment sizes and maximum limits, and judge approval of refusals on answerable questions. These findings motivated the deterministic checks. Refusal rates now count the actual no-content response text independently. The 18-case checks remain diagnostic and pattern-based, not full semantic grading.

Answer correctness, unsupported claims, citation support, and abstention are automatic estimates from the same model that generated the answer. These are not independently verified accuracy or hallucination rates. In particular, a judge-reported zero unsupported-answer rate is not evidence of zero unsupported answers: earlier maximum-limit errors showed why this judge cannot be a release gate. The set includes 22 questions copied from the source FAQ, so it is easier than an independent held-out user-query set.

Latency comes from a single local development run, including cold starts/model switching and occasional verification activity on the same machine. It excludes judge time and is not a production throughput measurement.

## Follow-up work

1. Have a reviewer check the reference passages, alternate valid sources, and every judge-marked failure. Expand the relevance labels before using recall as a release gate.
2. Add independent paraphrases and multi-document questions in a held-out set. Keep tuning cases separate from the final evaluation.
3. Tune candidate depth, abstention thresholds, and reranker configuration on the development set; rerun all strategies before claiming an improvement.
4. Review answer citations and unsupported claims manually, especially the eight unanswerable cases. Add confidence intervals and repeated latency runs.

## Reproduce and inspect

See [the evaluation guide](../README.md) for commands and scoring definitions. [Cases](../cases.json), [raw model outputs](runs.jsonl), [derived citation scores](scored.jsonl), [summary](summary.json), [run metadata](metadata.json), and [local model digests/corpus fingerprint](environment.json) are retained.

The raw log is preserved. Citation syntax is scored separately to accept both bracketed source numbers and explicit prose references; no answers or judge decisions are rewritten.
