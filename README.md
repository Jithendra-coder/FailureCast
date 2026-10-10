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

`GET /api/v1/health` is a liveness check and `/api/v1/ready` checks the database, active model, and restored dataset. Production disables Swagger and OpenAPI routes. Compose runs one API process and one training worker over local SQLite and shared local files. Keep one worker; multiple API replicas, network filesystems, and concurrent cross-host writes are not supported. Back up `artifacts/` and `data/` together while the services are stopped so the registry, model files, experiment tracking, and imported source data stay consistent. Keep `.env` out of source control and store production secrets in the deployment platform's secret manager.

The MLflow tracking UI is not started by default. To run it locally when needed, use `docker compose --profile tracking up -d mlflow`; it is available on `http://127.0.0.1:5000`.

## NASA C-MAPSS data

Download a subset from the NASA Prognostics Center of Excellence repository and keep the original files unchanged. Import the matching `train_FD00x.txt`, `test_FD00x.txt`, and `RUL_FD00x.txt` files together from **Dataset explorer**. Imports are restricted to FD001–FD004 and validate numeric schema, engine/cycle integrity, duplicates, ordering, finite values, and the final-cycle RUL label count. Raw files are stored under `data/raw/<version>/`, with per-file SHA-256 checksums; they are ignored by Git.

The CLI applies the same file checks and can train a registered candidate:

```powershell
python -m backend.app.cli validate --subset FD001 --train .\train_FD001.txt --test .\test_FD001.txt --rul .\RUL_FD001.txt
python -m backend.app.cli train --subset FD001 --train .\train_FD001.txt --test .\test_FD001.txt --rul .\RUL_FD001.txt --algorithm HistGradientBoostingRegressor
```

Training constructs capped RUL labels (cap 125) from run-to-failure **training trajectories**. Features use current and trailing sensor readings only. Validation engines are held out before feature/model fitting; official test labels are not used in candidate training or validation. After explicitly selecting and activating a version, run its official final-cycle test protocol from the model registry. No score should be described as a model improvement unless compared on the same held-out protocol and data version.

## Deep learning and experiment tracking

The default environment trains a mean baseline, HistGradientBoosting, or Random Forest candidates on CPU and records run configuration, metrics, and model metadata in `artifacts/experiments/`. A separate worker claims each durable SQLite job; worker restarts re-queue an interrupted run. MLflow stores run metadata in the local SQLite database `artifacts/mlflow.db` and artifacts under `artifacts/mlartifacts/` by default. Set `MLFLOW_TRACKING_URI` to select another MLflow store. Inspect local runs from the repository root with `mlflow ui --backend-store-uri sqlite:///artifacts/mlflow.db --host 127.0.0.1 --port 5000`, or start the optional Compose UI with the `tracking` profile. The built-in demonstration model is trained from generated trajectories and must not be reported as NASA evaluation.

PyTorch is optional because its CPU wheel is substantially larger. Install it to enable the fixed-window LSTM option:

```powershell
python -m pip install -r requirements-deep-learning.txt
```

LSTM training is CPU-compatible, fixed-seed, held out by engine, and early-stopped on its validation loss. Feature normalization is fit on training windows only. Set `FAILURECAST_TRAIN_DEVICE=cpu`, `cuda`, or `auto` (default) to select its training device. It is not selected or activated automatically.

## Product flow

1. Import and inspect a dataset version.
2. Train a baseline or LSTM candidate; poll the job under Experiments.
3. Review validation MAE, RMSE, bias, NASA score, split, and validation-engine count.
4. Explicitly approve a candidate in Model registry.
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

## Local persistence and reproducibility

- SQLite registry, alerts, predictions, training jobs, and audit events: `artifacts/failurecast.sqlite3`.
- Signed session records, throttled login attempts, and replay progress share the same SQLite database.
- Model artifacts and experiment metadata: `artifacts/models/`, `artifacts/experiments/`.
- MLflow run metadata and artifacts: `artifacts/mlflow.db`, `artifacts/mlartifacts/`.
- Immutable imported source files and checksums: `data/raw/`.
- Feature version: `raw-plus-trailing-5-v1`; random seed: `41`.
- Generated datasets, model artifacts, databases, and secrets are excluded from Git.

See [architecture](docs/architecture.md), [data governance](docs/data-governance.md), and the [model card](docs/model-card.md).

## Checks

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
Set-Location frontend
npm ci
npm run build
```
