# Verification record

This directory records checks performed for the reproducibility and recovery work. The current 50-case retrieval experiment is in evaluations/results/. The recorded demo’s earlier aggregate measurements are retained separately in evaluations/recorded-demo/.

## Automated checks

- Backend suite: 222 passing tests, with five dependency deprecation warnings.
- Fresh Compose import: three knowledge bases, 11 documents, and successful authenticated source download.
- Model connectivity from the backend container: chat, embeddings, and local reranking passed.
- Python dependencies are recorded in requirements.lock.txt; runtime/build images use multi-platform digests.
- [Recovery results](recovery.json) record interruption and retry outcomes for parsing, splitting, and embedding.
- [Installation and browser results](installation-and-ui.json) record the clean-source setup and final UI checks.

## Clean-source installation

A temporary source copy excluded local configuration, signing keys, installed dependencies, build output, and caches. A separate Compose project generated fresh credentials and initialized empty database/upload volumes. Building and starting it passed, followed by downloads of all 11 documents, pgvector health, all three model modes, and the saved Ollama digest checks. The test reused the host's Docker engine/cache and downloaded Ollama models; it was not an empty-machine test.

## Browser verification

Chrome through Playwright exercised administrator login, an actual empty-file parse failure, source replacement, processing history, a simulated network outage with automatic reconnection, and successful retry. Both the original failure and the new completed attempt remained visible, with progress totals. Parsed text and cookie-authenticated downloads matched the replacement file. Desktop and mobile layouts were inspected; no uncaught JavaScript errors occurred.

[Desktop history](retry-desktop.png) · [Mobile history](retry-mobile.png)

The browser fixture was removed afterward. A final smoke check confirmed the normal local deployment retained three knowledge bases and 11 documents. Disposable clean-install and crash-test stacks were removed; the normal application remains running separately.

Run the regression suite against dedicated test databases. Run scripts/smoke.py against an installed stack. Run scripts/verify_recovery.py to repeat the crash tests in a disposable Compose project.

The recovery tests deliberately pause background operations using deploy/recovery.compose.yaml, kill the backend with SIGKILL, restart the normal backend, and verify failure history, cleanup, and a successful new attempt. The embedding test waits until at least one batch has been stored before interruption. The fault-injection module is not used by the normal startup command.

## Environment and limits

The verified host is Apple Silicon with Docker Desktop; containers run Linux/arm64. Host Ollama supplies the models. Other operating systems and architectures have not been validated in this session. These checks establish local behavior, not production load capacity or independent answer-quality certification.

## Source refresh

[Content refresh verification](content-refresh.json) records the source-file hashes, matching raw-document archives, regenerated embeddings, updated sample accounts, regression tests, and fresh-install checks. The refreshed corpus was evaluated across all 50 questions and three retrieval strategies; see the [current report](../../evaluations/results/REPORT.md).
