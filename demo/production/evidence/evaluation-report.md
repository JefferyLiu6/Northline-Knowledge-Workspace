> Recorded demo evidence: this report describes the earlier capture, before the source-document refresh.

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

- 214 backend regression tests passed, including permission checks, duplicate filenames, path traversal, model binding, stale vectors, password hashing, token revocation, and concurrent parse requests.
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
| Required technical evidence in top 3 (18 cases) | 72.2% | 83.3% | 88.9% |
| Critical fact checks: pass rate (18 cases) | 83.3% | 94.4% | 94.4% |
| Answerable cases with explicit no-content refusal | 21.4% | 11.9% | 11.9% |
| Judge-rated correctness (known false positives) | 82.0% | 86.0% | 90.0% |
| Judge-rated supported citations (answerable cases) | 69.0% | 71.4% | 66.7% |
| Judge-rated unsupported-answer rate (unreliable) | 0.0% | 0.0% | 0.0% |
| Unanswerable explicit no-content refusal | 100.0% | 100.0% | 100.0% |
| Median retrieval latency | 0.05 s | 0.12 s | 7.65 s |
| Median answer generation | 4.32 s | 3.49 s | 2.77 s |

## What this run suggests

Technical fact pass rates were 83.3% for vector, 94.4% for hybrid, and 94.4% for hybrid with reranking. Compare those gains with the measured latency above. This experiment reranks the same five candidates and returns all five, so top-5 evidence coverage is necessarily unchanged by reranking; the top-3 evidence metric tests ordering. A larger candidate pool followed by a smaller reranked output is needed to evaluate candidate selection before drawing a general conclusion about reranking.

## How to interpret the numbers

The main retrieval metric is exact expected-source-document recall@5, using source filenames labeled in cases.json. It is deliberately coarse: retrieving an unrelated chunk from the right document still counts. The separate technical-evidence check verifies required facts in the retrieved passages for 18 cases. Neither metric alone proves the answer is correct.

The raw run also contains provisional chunk labels: expected chunks come from reference passages using the documented word-overlap rule. The benchmark reports recall of those canonical chunks, not an exhaustive human relevance assessment. For example, the frequent-restart question can retrieve a useful alternate source while missing the labeled FAQ chunk. Hit@5 and the raw evidence should be reviewed together.

**Observed judge failures:** case-023 confuses recommended deployment sizes (500/3000 points) with maximum limits (2000/5000/20000), but the judge approves it. It also approves a refusal on the answerable ERR-5022 case. The judge also inconsistently marks explicit refusals as non-abstentions. The main refusal metrics therefore count the actual no-content response text independently. The 18-case deterministic fact checks were added after discovering these false positives and expose selected technical errors independently; they are pattern-based checks, not full semantic grading.

Answer correctness, unsupported claims, citation support, and abstention are automatic estimates from the same model that generated the answer. These are not independently verified accuracy or hallucination rates. In particular, a judge-reported zero unsupported-answer rate is not evidence of zero unsupported answers: the wrong maximum-limit answers are a retained counterexample. The set includes 22 questions copied from the source FAQ, so it is easier than an independent held-out user-query set.

Latency comes from a single local development run, including cold starts/model switching and occasional verification activity on the same machine. It excludes judge time and is not a production throughput measurement.

## Follow-up work

1. Have a reviewer check the reference passages, alternate valid sources, and every judge-marked failure. Expand the relevance labels before using recall as a release gate.
2. Add independent paraphrases and multi-document questions in a held-out set. Keep tuning cases separate from the final evaluation.
3. Tune candidate depth, abstention thresholds, and reranker configuration on the development set; rerun all strategies before claiming an improvement.
4. Review answer citations and unsupported claims manually, especially the eight unanswerable cases. Add confidence intervals and repeated latency runs.

## Reproduce and inspect

See [the evaluation guide](../README.md) for commands and scoring definitions. [Cases](../cases.json), [raw model outputs](runs.jsonl), [derived citation scores](scored.jsonl), [summary](summary.json), [run metadata](metadata.json), and [local model digests/corpus fingerprint](environment.json) are retained.

The raw log is preserved. Citation syntax is scored separately to accept both bracketed source numbers and explicit prose references; no answers or judge decisions are rewritten.
