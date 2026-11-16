# Local RAG evaluation

This is a development benchmark for the fictional Northline corpus, not a customer acceptance study.

The 50 cases contain 42 answerable questions and eight deliberately unanswerable questions. They cover the FAQ, model limits, fault-code tables, warranty, installation, and spare parts. All five source formats are represented. Twenty-two FAQ questions are extracted from the source itself; this makes them easier than independent user questions. Reference passages in cases.json should receive a domain-owner review.

## Reproduce

Use the backend Python environment, import the databases, start Ollama, and run from the repository root:

    python evaluations/run.py
    python evaluations/write_report.py

The script reads backend settings. MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE, MYSQL_USER, MYSQL_PASSWORD and PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD can override connection settings. It does not alter corpus records. Use dedicated databases for regression tests, which create disposable records.

Results are checkpointed in results/runs.jsonl. Re-running skips successful case/strategy pairs and retries errors. To start a fresh experiment, move the results directory aside. Do not resume after changing the corpus, cases, prompt, models, or retrieval settings. Metadata records model names, prompt and case hashes, and parameters.

## Controlled comparison

Compare vector-only, hybrid vector/BM25, and hybrid with the configured local Ollama reranker. Each recall retrieves five candidates; hybrid uses reciprocal-rank fusion and reranks the fused five. All three provide at most five passages to the same answer model and database RAG_ANSWER prompt. Query rewriting and parent expansion are disabled to isolate retrieval changes. Thresholds are zero; this exposes generator behavior on irrelevant evidence rather than tuning an abstention threshold on the evaluation set.

Answers are capped at 220 output tokens; automated judgments at 180. These caps can truncate output and are limitations. Latency is one local sequential run, including cold starts and model switching, not a load test.

## Scoring

- Recall@5: fraction of canonical source chunks returned. A chunk in the expected document is selected if unique-word overlap with the reference is at least 65%, otherwise the best-matching chunk is used. This is a provisional labeling heuristic, not a fully human-labeled relevance set. Equivalent answers in another document may be penalized.
- Hit@5: at least one expected chunk appears.
- Answer correctness, unsupported-answer rate, and citation support: estimated by the same local model acting as judge in a separate call, with the reference, retrieved evidence, question, and answer. Same-model bias remains; inspect answers and judge reasons.
- Citation correctness additionally requires a citation and an in-range source number. Missing citations count as failures for answerable cases.
- Unanswerable abstention: fraction of the eight negative cases where the judge finds explicit refusal to invent an answer.
- Median retrieval and answer-generation latency are separate; judge latency is excluded.
- Failed requests remain in the raw log and error counts. Quality metrics use completed cases only; compare completion counts first.

The final summary is recomputed by report.py into scored.jsonl, leaving runs.jsonl unchanged. This deterministic scoring accepts bracketed source numbers and explicit prose citations such as “Source 2”; the original run-time flags only recognized brackets. No answers or judge decisions are changed.

The log preserves questions, expected/retrieved chunk IDs, answers, timings, judge decisions, and errors. A separate held-out set, human citation review, and repeated latency runs remain necessary before deployment.

## Deterministic technical checks

The same-model judge was observed to approve wrong model limits and refusals of answerable questions. Its correctness percentages must not be used as acceptance criteria.

fact_checks.json contains required fact patterns for 18 numeric/technical cases, authored from the source references. report.py checks these independently after removing thousands separators and Markdown bold markers. These checks cover selected facts, not complete answer semantics; alternative wording can fail a pattern, and mentioning the right numbers does not prove every statement is correct. Failures require inspection. The report also counts the exact standard “No relevant content/information…” refusal on answerable cases. Raw model outputs and original judge responses remain unchanged.

Examples from earlier development runs: case-023 substitutes recommended deployment sizes (500/3000 points) for maximum limits (2000/5000/20000), while the judge approves it. On case-034, vector retrieval leads to an explicit refusal despite an answerable reference; the judge also approves this. These findings motivated the separate fact checks; inspect the current report for this run’s disagreements.

## Final retrieval metrics

The final report uses expected-source-document recall@5 from the explicitly labeled source filenames, plus required-technical-evidence coverage for the 18 fact-checked cases. The saved corpus.json maps each retrieved chunk to its source and evidence text, allowing offline reproduction.

Document recall is coarse: the right document with the wrong passage still counts. Technical-evidence coverage requires every listed fact pattern somewhere in the retrieved five passages; it does not establish semantic relevance or resolve contradictions. Use both alongside answer fact checks.

The initial chunk-overlap labels were found to admit a neighboring passage in case-023 that mentions exceeding limits without stating the limits. Therefore those provisional chunk-recall numbers are retained in the raw/summary JSON for transparency but are not the report's headline retrieval metric. The fact checks were added after this run began; this is diagnostic development evaluation, not a preregistered held-out benchmark.

The final table also uses deterministic exact-template refusal rates for answerable and unanswerable questions. The original judge abstention field is retained in JSON but was observed to misclassify obvious refusals. A zero judge-rated unsupported-answer rate must not be interpreted as zero errors; case-023 is an explicit counterexample to treating that judge as a release gate.

Reranking preserves the five-candidate set in this run, so top-5 coverage cannot improve by design. Top-3 technical-evidence coverage measures ordering changes separately. The next comparison should recall a larger pool and rerank down to a smaller set before making claims about candidate-selection benefits.

Read the [completed report](results/REPORT.md) for measured results and failure analysis.
