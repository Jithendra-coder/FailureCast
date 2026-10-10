# FailureCast

FailureCast is a local-first predictive-maintenance research platform for NASA C-MAPSS remaining-useful-life (RUL) work. It includes a responsive operations dashboard, a FastAPI service, validated dataset import, reproducible classical-model training, optional PyTorch LSTM training, inference, replay, alerts, drift review, experiment records, and a model registry with explicit promotion and rollback.

**Use boundary:** this is an engineering demonstration. The included dashboard data is synthetic; NASA C-MAPSS itself is simulated turbofan data. RUL estimates are not guaranteed service life, maintenance instructions, or a connection to real equipment.

## Start locally

Requirements: Python 3.10+, Node.js 20+, and npm. Docker Compose is optional.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Set-Location frontend
npm install
npm run dev
```

In a second terminal, from the repository root with the same virtual environment active:

```powershell
python -m uvicorn backend.app.main:app --reload --port 8000
```

In another terminal from the repository root, start the persistent training worker:

```powershell
python -m backend.app.worker
```

Open the Vite URL (usually `http://127.0.0.1:5173`). The dashboard starts in **simulated demo mode**, so it is usable before NASA data is imported. Development API documentation is at `http://127.0.0.1:8000/api/docs`.

## Production deployment

The self-hosted Compose deployment enables password authentication, serves the UI and API from one origin, runs the API as a non-root user, and separates model training into a restartable worker. The API and optional MLflow UI ports bind to loopback. Do not expose them directly to the internet; put them behind a TLS reverse proxy with an access policy and set `FAILURECAST_COOKIE_SECURE=true`.

1. Copy `.env.example` to `.env` and replace both example credentials. Use a unique administrator passphrase (at least 14 characters) and generate a session secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
2. On Linux, set `FAILURECAST_UID` and `FAILURECAST_GID` in `.env` to the owner of the `data` and `artifacts` directories (`id -u` and `id -g`). This lets the non-root containers persist files without changing directory permissions.
3. For a reverse-proxy hostname, add its exact origin to `FAILURECAST_ALLOWED_ORIGINS`, such as `https://failurecast.example.com`.
4. Run `docker compose up --build -d`, then open `http://127.0.0.1:8000` and sign in with the configured administrator passphrase.

`GET /api/v1/health` is a liveness check. `/api/v1/ready` checks the database and restored dataset, and reports `model_status` separately as `ready`, `training_required`, or `unavailable`; the API and worker remain ready to train when the selected data version has no usable model. Production disables Swagger and OpenAPI routes. Compose runs one API process and one training worker over local SQLite and shared local files. Keep one worker; multiple API replicas, network filesystems, and concurrent cross-host writes are not supported. Back up `artifacts/` and `data/` together while the services are stopped so the registry, model files, experiment tracking, and imported source data stay consistent. Keep `.env` out of source control and store production secrets in the deployment platform's secret manager.

The MLflow tracking UI is not started by default. To run it locally when needed, use `docker compose --profile tracking up -d mlflow`; it is available on `http://127.0.0.1:5000`.

## NASA C-MAPSS data

Download a subset from the NASA Prognostics Center of Excellence repository and keep the original files unchanged. Import the matching `train_FD00x.txt`, `test_FD00x.txt`, and `RUL_FD00x.txt` files together from **Dataset explorer**. Imports are restricted to FD001–FD004 and validate numeric schema, engine/cycle integrity, duplicates, ordering, finite values, and the final-cycle RUL label count. Raw files are stored under `data/raw/<version>/`, with per-file SHA-256 checksums; they are ignored by Git.

The CLI applies the same file checks and can train a candidate associated with the same content-derived dataset version used by the UI importer:

```powershell
python -m backend.app.cli validate --subset FD001 --train .\train_FD001.txt --test .\test_FD001.txt --rul .\RUL_FD001.txt
python -m backend.app.cli train --subset FD001 --train .\train_FD001.txt --test .\test_FD001.txt --rul .\RUL_FD001.txt --algorithm ConditionAwareHistGradientBoostingRegressor
python -m backend.app.cli benchmark --subset FD001 --train .\train_FD001.txt --test .\test_FD001.txt --rul .\RUL_FD001.txt
```

Training constructs capped RUL labels (cap 125) from run-to-failure **training trajectories**. A seeded 80/20 engine-ID split evaluates one censored observation at 80% of each held-out training trajectory; the final artifact is then refit on all official training engines. `ConditionAwareHistGradientBoostingRegressor` is an optional comparison: its operating-setting clusters and sensor normalization are fit on training rows only, and raw features remain available to the estimator. The read-only `benchmark` compares a mean baseline, default HistGradientBoosting, condition-aware HistGradientBoosting, and Random Forest on five predeclared train-only engine splits (seeds 41–45), then reports official test labels once at final observed cycles. It writes no registry or MLflow records. See the [reproducible NASA benchmark](docs/evaluation/nasa-cmapss-benchmark-2026-10.md) for results and limitations. No score should be described as a model improvement unless compared on the same held-out protocol and data version.

## Deep learning and experiment tracking

The default environment trains a mean baseline, HistGradientBoosting, condition-aware HistGradientBoosting, or Random Forest candidates on CPU and records run configuration, metrics, and model metadata in `artifacts/experiments/`. A separate worker claims each durable SQLite job; worker restarts re-queue an interrupted run. MLflow stores run metadata in the local SQLite database `artifacts/mlflow.db` and artifacts under `artifacts/mlartifacts/` by default. Set `MLFLOW_TRACKING_URI` to select another MLflow store. Inspect local runs from the repository root with `mlflow ui --backend-store-uri sqlite:///artifacts/mlflow.db --host 127.0.0.1 --port 5000`, or start the optional Compose UI with the `tracking` profile. The built-in demonstration model is trained from generated trajectories and must not be reported as NASA evaluation.

PyTorch is optional because its CPU wheel is substantially larger. Install it to enable the fixed-window LSTM option:

```powershell
python -m pip install -r requirements-deep-learning.txt
```

LSTM training is CPU-compatible, fixed-seed, held out by engine, and early-stopped on its validation loss. Feature normalization is fit on training windows only. Set `FAILURECAST_TRAIN_DEVICE=cpu`, `cuda`, or `auto` (default) to select its training device. It is not selected or activated automatically.

## Product flow

1. Import and inspect a dataset version.
2. Train a baseline or LSTM candidate; poll the job under Experiments.
3. Review validation MAE, RMSE, bias, NASA score, split, and validation-engine count.
4. Explicitly approve a candidate in Model registry. Models can only be activated for the exact dataset version used for training; changing datasets pauses forecasts until a compatible version is activated.
5. Evaluate the active version on final observed test cycles and the supplied RUL labels.
6. Replay an engine trajectory to store cycle-ordered predictions and create threshold alerts.
7. Acknowledge alerts, inspect local sensor sensitivity and distribution shift, and roll back to an approved version when needed.

Default alert thresholds are configurable with `FAILURECAST_WATCH_CYCLES`, `FAILURECAST_WARNING_CYCLES`, and `FAILURECAST_CRITICAL_CYCLES` (60, 30, and 15 cycles). Values must satisfy critical < warning < watch. An open alert of the same engine and severity is suppressed until acknowledged. Drift review never trains or promotes a model. The monitoring screen has a reversible 4σ in-memory shift demonstration; it does not modify source data.

## API surface

All routes are under `/api/v1`. OpenAPI is available only in development at `/api/openapi.json`.

- `GET /health`, `/ready`, `/auth/session`, `/overview`, `/datasets`, `/engines`, `/models`, `/alerts`, `/monitoring/drift`, `/replay/sessions`
- `POST /auth/login`, `/auth/logout`, `/datasets/import`, `/training/jobs`, `/predictions`, `/replay/sessions`
- Engine history, dataset quality, training job status, model metrics, model promotion/evaluation/rollback, replay controls, alert acknowledgment, explainability, audit history, and drift simulation are documented in Swagger.

The prediction endpoint rejects malformed feature sets, non-finite values, non-increasing cycles, and sequences longer than 120 rows. Request bodies are bounded even when sent without a content-length header; dataset uploads are bounded to 20 MB per file and 40 MB total. Model loading accepts only artifacts inside the application-managed model directory. Production uses one administrator account with an expiring, signed, HttpOnly session cookie, login throttling, same-site cookies, and origin checks on state-changing requests. There are no user roles or external identity provider integrations.

Models are bound to the exact content-derived dataset version used for training. If a different version is selected, prediction, engine, replay, and test-evaluation requests cannot use the old model; the workspace keeps dataset and experiment management available and guides the reviewer to train, approve, or restore a compatible version. Alerts and replay sessions are scoped to their source dataset; each replay also retains the model version used for its predictions.

## Local persistence and reproducibility

- SQLite registry, alerts, predictions, training jobs, and audit events: `artifacts/failurecast.sqlite3`.
- Signed session records, throttled login attempts, and replay progress share the same SQLite database.
- Model artifacts and experiment metadata: `artifacts/models/`, `artifacts/experiments/`.
- MLflow run metadata and artifacts: `artifacts/mlflow.db`, `artifacts/mlartifacts/`.
- Immutable imported source files and checksums: `data/raw/`.
- Feature version: `raw-plus-trailing-5-v1` (or `raw-plus-trailing-5+condition-clusters-v1`); candidate seed: `41`; repeated benchmark seeds: `41`–`45`.
- Generated datasets, model artifacts, databases, and secrets are excluded from Git.

## Backup and restore

Stop the API and worker before creating a recovery point so the SQLite registry, model files, experiment records, and imported source files describe one consistent application state. The backup command snapshots SQLite databases with SQLite's online backup API, writes a SHA-256 manifest, and refuses to overwrite an existing archive. It includes only `data/` and `artifacts/`; it never includes `.env` credentials.

```powershell
python -m backend.app.backup create --source . --output D:\FailureCastBackups\failurecast-2026-10-10.tar.gz
python -m backend.app.backup verify --archive D:\FailureCastBackups\failurecast-2026-10-10.tar.gz
python -m backend.app.backup restore --archive D:\FailureCastBackups\failurecast-2026-10-10.tar.gz --destination D:\FailureCastRestore
```

Restore requires a path that does not already exist. The command verifies every path and checksum, checks restored SQLite integrity, and then atomically publishes the restored directory. To start a restored copy, point `FAILURECAST_DATA_DIR` and `FAILURECAST_ARTIFACT_DIR` at its `data` and `artifacts` subdirectories, set ownership for the configured container UID/GID, and use a separately configured `.env` with new credentials. Keep encrypted copies and credentials in an access-controlled backup location.

## Browser acceptance tests

The Playwright suite covers the welcome-to-workspace path, engine inspection, historical replay, model training, explicit approval, simulated test-set evaluation, and rollback. It expects a running, isolated Docker Compose instance and never seeds or clears a user's workspace. The CI workflow creates its own credentials and storage directories before starting the test deployment.

```powershell
Set-Location frontend
npm ci
npx playwright install chromium
$env:FAILURECAST_E2E_URL = "http://127.0.0.1:8000"
$env:FAILURECAST_E2E_PASSWORD = "<the test deployment administrator password>"
npm run test:e2e
```

For a local run, first start Compose with separate `FAILURECAST_DATA_DIR`, `FAILURECAST_ARTIFACT_DIR`, and `FAILURECAST_PORT` values so browser actions cannot affect a working workspace. CI checks runtime, development, and optional deep-learning Python dependencies with `pip-audit -r requirements-dev.txt -r requirements-deep-learning.txt --strict`, and all frontend dependencies with `npm audit --audit-level=moderate`.

With the same isolated workspace and credentials loaded into the environment, run `npm run demo:record` from `frontend` to create the captioned 1080p silent recording at `docs/demo-video/failurecast-demo.webm`. The recording queues training and changes model lifecycle state, so never target a user's workspace. The accompanying [demo narration script](docs/demo-video-script.md) is optional voiceover copy.

See the [captioned demo video](docs/demo-video/failurecast-demo.webm), [engineering readiness report](docs/readiness-report.md), [reproducible NASA benchmark](docs/evaluation/nasa-cmapss-benchmark-2026-10.md), [architecture](docs/architecture.md), [data governance](docs/data-governance.md), and the [model card](docs/model-card.md).

## Checks

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
Set-Location frontend
npm ci
npm audit --audit-level=moderate
npm run build
```
