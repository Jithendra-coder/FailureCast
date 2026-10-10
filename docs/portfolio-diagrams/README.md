# FailureCast — Portfolio Diagrams

A local-first platform for predictive-maintenance remaining-useful-life workflows using C-MAPSS data. These diagrams explain its single-host architecture and trace a validated dataset through model training, approval, and prediction.

## Files

| Asset | Purpose |
| --- | --- |
| [`system-architecture.svg`](system-architecture.svg) | Editable vector master for Diagram 01 |
| [`system-architecture.png`](system-architecture.png) | 2400 px wide portfolio export |
| [`system-architecture.mmd`](system-architecture.mmd) | Editable topology source for Diagram 01 |
| [`execution-flow.svg`](execution-flow.svg) | Editable vector master for Diagram 02 |
| [`execution-flow.png`](execution-flow.png) | 2400 px wide portfolio export |
| [`execution-flow.mmd`](execution-flow.mmd) | Editable workflow source for Diagram 02 |

The SVG files are the presentation masters; each PNG is a 1.25× browser render of its SVG. The Mermaid files preserve the corresponding component and decision topology as diagram-as-code. Keep both representations aligned when changing the implementation. Mermaid auto-layout output is useful for topology checks, but it should not overwrite the hand-laid SVG presentation masters.

## 01 — System Architecture

The diagram shows a browser client, the single FastAPI application process, the separate training worker, optional local MLflow UI, and the shared single-host data stores. The React build is served by FastAPI in the Docker deployment; in development Vite proxies `/api` to the API. Browser calls use same-origin REST/JSON in production.

### Component responsibilities

- **React / TypeScript / Vite:** eight workspace views for overview, engine health, replay, datasets, experiments, explainability, monitoring, and model registry. Recharts renders charts; Lucide supplies interface icons.
- **FastAPI:** serves the production frontend bundle and exposes `/api/v1` routes. Pydantic request schemas, the C-MAPSS parser, prediction/replay logic, alerts, model promotion/rollback, drift review, and audit endpoints live in the API process.
- **Security middleware:** production Compose requires an administrator password and session secret. The API uses a signed, expiring, HttpOnly, SameSite=Strict cookie; checks allowed origins for mutations; limits request bodies; and adds security headers. Login attempts are throttled. Development can run without authentication when credentials are not configured.
- **Training worker:** a separate Compose service polls durable job rows in SQLite, claims work under `BEGIN IMMEDIATE`, and holds a file lock so a second worker does not train concurrently. It trains candidates outside prediction requests.
- **SQLite:** the local WAL-mode database stores dataset metadata, model registry rows, training jobs, predictions, alerts, audit events, auth sessions, login attempts, and replay state. It is also the training queue; there is no separate broker.
- **Local files:** `data/raw/` holds imported source bytes under content-derived dataset versions. `artifacts/models/` holds estimator files and `artifacts/experiments/` holds experiment JSON. The API and worker share the Compose `data/` and `artifacts/` volumes.
- **MLflow:** local tracking metadata uses `artifacts/mlflow.db`; run artifacts go under `artifacts/mlartifacts/`. The Compose UI is an optional service exposed on loopback. A tracking exception is recorded as a warning; it does not by itself fail a successful training run.

### Data and model path

The built-in demo trajectories are generated locally. Imported C-MAPSS data is supplied by the operator as the matching `train_FD00x.txt`, `test_FD00x.txt`, and `RUL_FD00x.txt` files; the application does not fetch a NASA service. The importer checks the subset, filenames, 26-column layout, finite values, engine/cycle integrity, cycle ordering, and RUL label count. It hashes each file with SHA-256, reuses an identical fingerprint, stages new files before an atomic directory rename and SQLite metadata insert, then recomputes file hashes and the combined fingerprint on restore.

Training is explicitly started by the user. The worker reads training trajectories, builds capped RUL labels and trailing features without crossing engine boundaries, and uses a seeded 80/20 engine-ID holdout. Validation evaluates one censored observation at 80% of each held-out full training trajectory; the final estimator is refit on every official training engine. CPU candidates include MeanBaseline, RandomForestRegressor, HistGradientBoostingRegressor, and a train-fitted operating-condition-aware HistGradientBoosting pipeline. PyTorch is an optional extra for the fixed 30-cycle LSTM. Validation records MAE, RMSE, bias, and the NASA score; the official test labels are reserved for a separate post-selection final-cycle evaluation. The read-only benchmark repeats the engine holdout over seeds 41–45.

The candidate artifact and registry row are separate from the active model. Promotion requires explicit approval, a valid engine-level validation report, and an exact match with the currently selected dataset version. The promotion transaction records an audit event and retains the previous active model as approved for rollback within that dataset version. The API process loads and caches the selected artifact for inference. When a different dataset is selected, forecasts pause until its own model version is active. It returns non-negative RUL in cycles; it does not return a calibrated uncertainty interval.

### Communication and operational properties

- In production, the browser downloads the bundled UI from the FastAPI origin, then sends REST/JSON requests to that origin. The Vite development server instead proxies `/api` to FastAPI.
- A training request creates a SQLite job and returns `202`; the separate worker discovers it by polling. Job status and result return through SQLite and API reads, not through a message broker or streaming channel.
- The API uses the active model for engine estimates and replay steps. Explicit prediction writes and replay steps persist prediction rows; threshold alerts are created for non-normal severity, with duplicate open alerts suppressed for the same engine and severity.
- Replay sessions and their progress are persisted in SQLite. The browser advances replay through request/response calls; this is not a telemetry stream.
- `/api/v1/health` is liveness; `/api/v1/ready` checks the database, active model, and current dataset, and reports not-ready if an imported dataset could not be restored at startup. Compose restarts services unless stopped. Training exceptions are written to the job row and logged by the worker.
- Compose runs one API process and one worker on one host. The API and MLflow host ports bind to loopback. The containers run as non-root with a read-only root filesystem, dropped capabilities, `no-new-privileges`, a PID limit, and a restricted temporary filesystem. The README recommends a TLS reverse proxy before any remote access.

### Engineering trade-offs and limitations

Python hosts the data validation, feature generation, training, and inference path. scikit-learn supplies the baseline and tree models already used by the default environment; PyTorch is optional because its CPU package is substantially larger. React is the API-backed dashboard, and FastAPI is the REST/static-file host. The project documents no comparative rationale for those framework choices, so this describes their implemented roles rather than inventing a selection story.

SQLite plus local files keeps this deployment self-contained and makes the job queue durable, but the project explicitly does not support multi-host concurrent writes, multiple API replicas, network filesystems, or horizontal worker scaling. Scaling out would require shared transactional storage, a distributed queue, shared artifacts, and an external identity provider. Drift is a statistical review signal, not a retraining trigger. Explainability is local perturbation sensitivity, not causal attribution or confidence.

There is no LLM, agent framework, MCP server, vector database, external model provider, distributed cache, or tracing platform in the inspected implementation. NASA data enters as operator-selected files. The included MLflow service is local rather than a hosted integration.

## 02 — End-to-End Execution Flow

The flow traces an imported dataset through a user-started training job, human model approval, and a replay/prediction result. It keeps authorization denials, invalid requests, persistence failures, model errors, and worker recovery as separate outcomes.

1. The browser submits the three files for one FD001–FD004 subset. When authentication is enabled, middleware checks the request origin on mutations and requires an administrator session. A missing/expired session returns `401`; a disallowed origin returns `403`.
2. The importer enforces its 20 MB per-file and 40 MB total bounds. Invalid filenames, subset, schema, rows, or label count return `422`; oversize imports return `413`.
3. The API computes per-file checksums and a combined fingerprint. An identical dataset version is reused. A new version is written to a staging directory, atomically moved into `data/raw/`, and then recorded in SQLite. A file or database commit error returns `500` and cleans staged or moved files.
4. A user explicitly starts training. The API writes a queued job with `BEGIN IMMEDIATE` and returns `202`. A second queued/running job is rejected with `409`.
5. The worker claims the queued row and trains outside the HTTP request. It uses training trajectories only for labels/features and a seeded engine-ID holdout. Validation scores one censored observation at 80% of each held-out trajectory; the final estimator is refit on all official training engines. Validation metrics, experiment metadata, and the versioned artifact are saved; MLflow tracking is best-effort.
6. A training exception marks the job failed, stores a bounded error message, and writes a worker log. On worker startup, interrupted `running` jobs return to `queued`; if an artifact for the same training-job ID already exists, the worker reuses it instead of creating a duplicate candidate.
7. A reviewer checks the candidate’s engine-level validation and explicitly approves promotion. A candidate without a valid report or without approval is not activated. Successful promotion updates registry states and records an audit event; the prior active model remains approved for rollback.
8. Engine overview/history and replay use a model bound to the selected dataset version. The direct prediction endpoint validates required fields, finite numbers, increasing cycles, and the 120-row limit. A model from another dataset is rejected with `409`; an unavailable compatible artifact returns `503` without an estimate.
9. The overview returns current engine estimates. Direct prediction writes and replay steps record a prediction in SQLite and create a threshold alert when severity is not normal. An open alert of the same engine and severity is suppressed. The response is JSON; the React workspace refreshes data every 12 seconds. Replay advances through request/response step calls and persists its session state.

The monitoring endpoint compares the last 12 sensor observations with an evenly spaced sample of up to 2,000 rows across the ordered training history. A shift of at least three standard deviations is a prompt to investigate, not evidence of failure and not an automatic retraining or promotion action. The separate reversible drift demonstration changes in-memory monitoring state only. Local feature perturbation reports sensitivity; it is not a causal explanation.

## Interview preparation

### 30-second explanation

FailureCast is a local-first predictive-maintenance platform for C-MAPSS remaining-useful-life workflows. A React dashboard calls a FastAPI service that validates dataset imports, serves predictions, and manages model releases. Training runs in a separate worker from durable SQLite jobs, records engine-held-out validation, and produces a candidate that needs explicit human approval. The self-hosted Compose deployment keeps the database, model files, and MLflow tracking on one host.

### 2-minute explanation

The project has two different runtime paths. Dataset import is synchronous: the API validates the three C-MAPSS files, checks their rows and labels, fingerprints the bytes, and commits a new version with staged files plus SQLite metadata. Training is asynchronous: the user explicitly queues one job, and a separate lock-protected worker claims it from SQLite. It creates labels and trailing features only from training trajectories, evaluates an 80%-life censored observation per held-out engine, refits the artifact on all training engines, and records metrics, a versioned model artifact, and experiment metadata. MLflow is local and best-effort.

The worker registers a candidate; it never silently replaces the active model. A reviewer must approve a candidate with a valid engine-level report. Promotion and rollback update the registry and write audit events. The FastAPI process then uses the active model to estimate RUL. Replay evaluates one history prefix per step and persists progress; prediction writes and replay steps can create threshold alerts. Monitoring compares a short recent window with training sensor distributions and raises a review signal, not an automatic model action. SQLite WAL and a single-host Compose layout make the service self-contained, while intentionally limiting horizontal scale.

### Five likely interview questions

1. **Why is training outside the request handler?** Training duration should not hold an HTTP request open. The API commits a durable SQLite job and the separate worker claims it; the UI reads job state through API requests.
2. **How do you prevent leakage between train and validation?** Engine IDs are shuffled with a fixed seed and split 80/20 before fitting. Validation scores one 80%-life censored observation per held-out engine; feature windows stay inside each engine. The final estimator is then refit on all training engines, while official test labels remain reserved for explicit post-selection evaluation.
3. **What happens if the worker restarts?** Startup moves interrupted `running` jobs back to `queued`. A candidate tied to the same training-job ID is checked and reused when present. Training exceptions instead mark the job `failed`; the app does not automatically retry every failed job.
4. **How is a model made active?** A candidate must have a valid engine-level validation report and a reviewer must send explicit approval. One SQLite transaction changes the statuses and inserts an audit event; the old active model remains approved for rollback.
5. **What would have to change to scale to multiple hosts?** The current SQLite WAL and shared local filesystem design is single-host. The architecture notes call for shared transactional storage, a distributed job queue, shared artifact storage, and an external identity provider before multi-host deployment.

## Validation summary

- **Sources inspected:** app source, tests, frontend, dependencies, Compose deployment, data/model boundaries, evaluation code, CI, documentation, and diagrams; see the full [readiness report](../readiness-report.md).
- **Automated checks:** all 35 backend tests, Python compilation, strict `pip-audit`, full `npm audit`, and the frontend TypeScript/Vite production build passed. CI also passed the isolated Compose browser and backup/restore recovery journeys.
- **ML evaluation:** fixed baseline, HGB, condition-aware HGB, and RandomForest protocols ran on all four official C-MAPSS subsets; reproducible commands, archive checksum, repeated-seed metrics, and limitations are in the [benchmark report](../evaluation/nasa-cmapss-benchmark-2026-10.md).
- **Compose runtime:** an isolated Podman stack built, served the UI with HTTP 200, passed readiness and admin login, completed a default HGB worker job, promoted/evaluated/rolled back the candidate, and marked the generated-data evaluation simulation-only.
- **Browser verification:** two Playwright journeys passed in CI against an isolated Docker Compose deployment, covering welcome/sign-in, engine inspection and replay, candidate training and promotion, simulated test evaluation, and rollback. Dataset upload remains covered by backend/API tests rather than a browser upload fixture.
- **Not verified:** optional LSTM benchmark quality, reverse-proxy/TLS deployment, multi-host behavior, long-duration soak, and real-equipment use.
- **Excluded:** systems not implemented in the inspected project, including hosted databases, Redis/message brokers, distributed tracing, NASA APIs, LLMs/agents, and vector search.
- **Diagram rendering:** both SVG masters were updated, re-rendered as 2400 px PNGs, XML-parsed, dimension-checked, and visually inspected for clipping and overlap.
