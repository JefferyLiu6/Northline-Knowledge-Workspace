# Reproducible local setup

## Prerequisites

Install Docker with Compose v2 or later, Python 3 for the setup/check scripts, and Ollama. The verified host is Apple Silicon with Docker Desktop; the application containers run Linux/arm64. Other architectures have not been validated in this session.

Start Ollama and download the models:

    ollama serve
    ollama pull llama3.1:8b
    ollama pull mxbai-embed-large:latest

Run ollama serve in a separate terminal only if Ollama is not already running. Downloads require network access and several gigabytes of disk space. Host memory and acceleration affect inference speed.

From a fresh source checkout:

    python3 scripts/configure.py
    python3 scripts/check_models.py
    docker compose up --build -d --wait
    python3 scripts/smoke.py --models

Open http://127.0.0.1:8080 and sign in with the public demo account admin / admin. Use the administrator sidebar to open Document Management or choose Open Q&A.

configure.py creates a private .env with random database passwords and preserves an existing file. Use --port 8088 when creating a configuration if port 8080 is occupied, or edit APP_PORT in an existing .env. Pass the matching --url to smoke.py.

## Configuration and network

The default model endpoint inside the backend is http://host.docker.internal:11434/v1. The Docker host-gateway mapping is included. Docker Desktop on macOS was verified against the host Ollama service. On Linux, make Ollama reachable from the Docker bridge and set OLLAMA_BASE_URL accordingly; a host service bound only to loopback may be unreachable from containers. Keep Ollama restricted to trusted local interfaces.

The backend translates seeded loopback model URLs to OLLAMA_BASE_URL. This leaves database configuration portable while preserving model identities. The browser uses /api on the frontend origin.

Only the frontend port is published, and it binds to 127.0.0.1. Databases and the backend are internal services. The signing key is generated privately in the app-state volume; database credentials are read from .env. Neither is committed or copied into the images.

## First boot and persistence

On empty volumes, database entrypoints import ai_rag.sql and ai_rag_vector.sql. The demo includes three knowledge bases, 11 source documents, 121 chunks (110 searchable plus 11 parents), and 110 vectors. The uploads volume is initially populated from the image's seed files.

Existing volumes are not reseeded on restart or rebuild. Startup applies the small task-context schema migration where needed, converts any legacy plaintext passwords, and recovers interrupted document jobs before readiness succeeds.

Persistent volumes hold MySQL data, PostgreSQL data, uploads, and the signing key. To stop while keeping data:

    docker compose down

To rebuild after a source change:

    docker compose up --build -d --wait

Deleting volumes destroys the corresponding local data. The verification scripts use their own isolated project names and remove only their generated test volumes.

## Processing recovery

Open Document Management → More → Processing history. An interrupted attempt appears as Failed with an explanation. Choose Retry failed step to create a new attempt; the original failure stays in history. The dialog refreshes every three seconds while processing.

Parse recovery clears partial parsed text/chunks/vectors. Split recovery preserves parsed text and removes partial chunks/vectors. Embedding recovery preserves chunks and removes partial vectors. Split retries reuse saved parameters; older tasks without a snapshot require choosing a strategy again using Split into chunks.

The app intentionally supports one backend worker per database. A second instance fails startup with an ownership error. If the ownership connection is lost, the backend stops; the next startup performs recovery. Do not add workers or replicas without changing this design.

## Verification

Read-only installed-stack checks:

    python3 scripts/smoke.py --models

Deterministic crash/restart verification in a separate disposable stack:

    python3 scripts/verify_recovery.py

The recovery check uses port 8091 by default, pauses real background processing through a test-only override, kills the backend, restarts it normally, and retries each stage. It exercises a partially written chunk set and at least one completed embedding batch. It removes its test stack/volumes afterward. The normal Compose command never mounts the fault-injection module.

For the backend suite, import seeds into dedicated databases ending in _test or _check, configure MYSQL_* and PG* environment variables as described in Database Setup.md, and run pytest from ai_rag/fastapi-app. It refuses ordinary database names.

The original manual Python/npm setup remains available in Database Setup.md. Docker uses requirements.lock.txt; requirements.txt documents the direct dependencies. Update the lock and reverify after changing dependencies.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Compose cannot connect to Docker | Start Docker Desktop or the Docker daemon. |
| Port already allocated | Change APP_PORT in .env and rerun Compose. |
| Model requests fail | Run check_models.py and smoke.py --models; verify host reachability and OLLAMA_BASE_URL. |
| Model digest differs | Use the recorded model version, or intentionally rebuild embeddings and rerun evaluation for the new model. |
| Backend is unhealthy | Inspect docker compose logs backend mysql postgres. Recovery waits for both databases to be available. |
| Another backend owns the database | Stop the other instance; this deployment uses one worker per database. |
| Fresh seed changes are not visible | Existing volumes are retained deliberately; use a separate new project for fresh-import testing. |
| Session expired after setup | Sign in again. Different installations have different signing keys. |
