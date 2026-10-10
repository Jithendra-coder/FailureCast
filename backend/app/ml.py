from __future__ import annotations

import json
import math
import os
import random
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from . import db
from .data import group_engines, training_examples, feature_vector

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "artifacts" / "models"
EXPERIMENT_DIR = ROOT / "artifacts" / "experiments"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)
MODEL_CACHE: dict[str, object] = {}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_mlflow(experiment: dict, artifact: Path) -> dict:
    try:
        import mlflow
        tracking_uri = os.getenv("MLFLOW_TRACKING_URI", f"sqlite:///{(ROOT / 'artifacts' / 'mlflow.db').as_posix()}")
        mlflow.set_tracking_uri(tracking_uri)
        mlflow_experiment = mlflow.get_experiment_by_name("FailureCast")
        if mlflow_experiment is None:
            try:
                experiment_id = mlflow.create_experiment("FailureCast", artifact_location=(ROOT / "artifacts" / "mlartifacts").resolve().as_uri())
            except mlflow.exceptions.MlflowException:
                mlflow_experiment = mlflow.get_experiment_by_name("FailureCast")
                if mlflow_experiment is None:
                    raise
                experiment_id = mlflow_experiment.experiment_id
        else:
            experiment_id = mlflow_experiment.experiment_id
        mlflow.set_experiment(experiment_id=experiment_id)
        with mlflow.start_run(run_name=experiment["model_id"]) as run:
            mlflow.log_params({"algorithm": experiment["algorithm"], "seed": experiment["seed"],
                               "feature_version": experiment["feature_version"], "dataset_id": experiment.get("dataset_id") or "demo-fd001-v1"})
            mlflow.log_metrics({key: float(value) for key, value in experiment["metrics"].items()
                                if isinstance(value, (int, float)) and math.isfinite(value)})
            mlflow.set_tags({"model_version": experiment["model_id"], "validation_split": experiment["metrics"].get("validation_split", "engine_id holdout")})
            mlflow.log_artifact(str(artifact))
            mlflow.log_dict(experiment, "experiment.json")
            return {"run_id": run.info.run_id}
    except Exception as exc:
        return {"warning": f"MLflow tracking unavailable: {str(exc)[:240]}"}


def metrics_for(y_true: list[float], y_pred: list[float]) -> dict:
    errors = np.asarray(y_pred, dtype=float) - np.asarray(y_true, dtype=float)
    score = sum(math.exp(min(50, float(-err) / 13)) - 1 if err < 0 else math.exp(min(50, float(err) / 10)) - 1 for err in errors)
    actual = np.asarray(y_true, dtype=float)
    by_range = {}
    for name, low, high in (("0_30", 0, 30), ("30_60", 30, 60), ("60_plus", 60, np.inf)):
        mask = (actual >= low) & (actual < high)
        if mask.any():
            by_range[name] = round(float(np.mean(np.abs(errors[mask]))), 3)
    return {"mae": round(float(mean_absolute_error(y_true, y_pred)), 3),
            "rmse": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 3),
            "bias": round(float(np.mean(errors)), 3), "nasa_score": round(float(score), 2), "mae_by_rul_range": by_range,
            "samples": len(y_true), "validation_engines": 0}


def make_estimator(algorithm: str):
    if algorithm == "MeanBaseline":
        return DummyRegressor(strategy="mean")
    if algorithm == "RandomForestRegressor":
        return RandomForestRegressor(n_estimators=60, min_samples_leaf=2, max_features=0.8, n_jobs=min(4, os.cpu_count() or 1), random_state=41)
    if algorithm == "HistGradientBoostingRegressor":
        return HistGradientBoostingRegressor(max_iter=90, max_leaf_nodes=20, l2_regularization=0.1, random_state=41)
    raise ValueError("Choose MeanBaseline, HistGradientBoostingRegressor or RandomForestRegressor.")


def fit_candidate(records: list[dict], algorithm: str, dataset_id: str | None = None, training_job_id: str | None = None) -> dict:
    started = time.perf_counter()
    grouped = group_engines(records)
    engine_ids = sorted(grouped)
    if len(engine_ids) < 3:
        raise ValueError("At least three complete engines are required for an engine-level training split.")
    shuffled = engine_ids[:]
    random.Random(41).shuffle(shuffled)
    validation_ids = set(shuffled[: max(1, round(len(shuffled) * 0.2))])
    train_rows = [row for row in records if row["engine_id"] not in validation_ids]
    train_X, train_y, _ = training_examples(train_rows)
    estimator = make_estimator(algorithm)
    estimator.fit(np.asarray(train_X, dtype=np.float32), np.asarray(train_y, dtype=np.float32))
    val_X, val_y, _ = training_examples([row for row in records if row["engine_id"] in validation_ids])
    val_pred = np.clip(estimator.predict(np.asarray(val_X, dtype=np.float32)), 0, None).tolist()
    metrics = metrics_for(val_y, val_pred)
    metrics["validation_engines"] = len(validation_ids)
    metrics["training_engines"] = len(engine_ids) - len(validation_ids)
    metrics["duration_seconds"] = round(time.perf_counter() - started, 2)
    metrics["validation_split"] = "engine_id holdout (80/20)"

    model_id = f"fc-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
    artifact = MODEL_DIR / f"{model_id}.joblib"
    bundle = {"estimator": estimator, "medians": np.median(np.asarray(train_X, dtype=np.float32), axis=0).tolist()}
    joblib.dump(bundle, artifact)
    MODEL_CACHE[model_id] = bundle
    db.execute("INSERT INTO models (id, algorithm, status, created_at, metrics, artifact_path, dataset_id, parent_id, training_job_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
               (model_id, algorithm, "candidate", utcnow(), json.dumps(metrics), str(artifact.relative_to(ROOT)), dataset_id,
                (db.one("SELECT id FROM models WHERE status='active' ORDER BY created_at DESC LIMIT 1") or {}).get("id"), training_job_id))
    experiment = {"model_id": model_id, "algorithm": algorithm, "dataset_id": dataset_id, "metrics": metrics,
                  "created_at": utcnow(), "seed": 41, "feature_version": "raw-plus-trailing-5-v1"}
    tracking = log_mlflow(experiment, artifact)
    if tracking.get("run_id"):
        metrics["mlflow_run_id"] = tracking["run_id"]
        db.execute("UPDATE models SET metrics=? WHERE id=?", (json.dumps(metrics), model_id))
    experiment.update({"mlflow_run_id": tracking.get("run_id"), "tracking_warning": tracking.get("warning")})
    (EXPERIMENT_DIR / f"{model_id}.json").write_text(json.dumps(experiment, indent=2), encoding="utf-8")
    return {"model_id": model_id, "algorithm": algorithm, "metrics": metrics, "artifact": str(artifact.relative_to(ROOT)), **tracking}


def load_estimator(model: dict):
    model_id = model["id"]
    if model_id not in MODEL_CACHE:
        path = (ROOT / model["artifact_path"]).resolve()
        if not path.is_relative_to(MODEL_DIR.resolve()) or not path.is_file():
            raise ValueError("Model artifact is missing or outside the managed model directory.")
        if model["algorithm"] == "LSTM":
            try:
                import torch
                from torch import nn
            except ImportError as exc:
                raise ValueError("This model requires the optional PyTorch dependency.") from exc
            class LSTMRegressor(nn.Module):
                def __init__(self, input_size: int):
                    super().__init__()
                    self.lstm = nn.LSTM(input_size, 32, batch_first=True)
                    self.head = nn.Sequential(nn.Linear(32, 16), nn.ReLU(), nn.Linear(16, 1))
                def forward(self, values):
                    return self.head(self.lstm(values)[0][:, -1, :])
            saved = torch.load(path, map_location="cpu", weights_only=True)
            estimator = LSTMRegressor(saved["input_size"])
            estimator.load_state_dict(saved["state_dict"])
            estimator.eval()
            MODEL_CACHE[model_id] = {"estimator": estimator, "mean": np.asarray(saved["mean"], dtype=np.float32),
                                     "std": np.asarray(saved["std"], dtype=np.float32)}
        else:
            MODEL_CACHE[model_id] = joblib.load(path)
    return MODEL_CACHE[model_id]


def predict(model: dict, history: list[dict]) -> float:
    estimator = load_estimator(model)
    if model["algorithm"] == "LSTM":
        import torch
        bundle = estimator
        offset = max(0, len(history) - 30)
        sequence = [feature_vector(row, history[max(0, index - 4):index]) for index, row in enumerate(history[offset:], offset)]
        sequence = [sequence[0]] * (30 - len(sequence)) + sequence
        values = (np.asarray(sequence, dtype=np.float32) - bundle["mean"]) / bundle["std"]
        with torch.no_grad():
            return max(0.0, float(bundle["estimator"](torch.tensor([values], dtype=torch.float32)).item()))
    if isinstance(estimator, dict):
        estimator = estimator["estimator"]
    row = history[-1]
    vector = feature_vector(row, history[:-1])
    return max(0.0, float(estimator.predict(np.asarray([vector], dtype=np.float32))[0]))


def bootstrap_model(records: list[dict]) -> dict:
    existing = db.one("SELECT * FROM models WHERE status='active' ORDER BY created_at DESC LIMIT 1")
    if existing:
        try:
            load_estimator(existing)
            return db.decode(existing, "metrics")
        except (OSError, ValueError, KeyError):
            db.execute("UPDATE models SET status='retired' WHERE id=?", (existing["id"],))
    result = fit_candidate(records, "HistGradientBoostingRegressor")
    db.execute("UPDATE models SET status='active' WHERE id=?", (result["model_id"],))
    return db.decode(db.one("SELECT * FROM models WHERE id=?", (result["model_id"],)), "metrics")


def train_lstm(records: list[dict], dataset_id: str | None = None, training_job_id: str | None = None) -> dict:
    """Optional sequence-model path; imports torch only when explicitly requested."""
    try:
        import torch
        from torch import nn
        from torch.utils.data import DataLoader, TensorDataset
    except ImportError as exc:
        raise ValueError("PyTorch is not installed. Install the optional deep-learning requirements to train an LSTM.") from exc

    started = time.perf_counter()
    torch.manual_seed(41)
    by_engine = group_engines(records)
    ids = sorted(by_engine)
    if len(ids) < 3:
        raise ValueError("At least three engines are required for an engine-level LSTM split.")
    shuffled = ids[:]
    random.Random(41).shuffle(shuffled)
    validation_ids = set(shuffled[: max(1, round(len(ids) * .2))])
    train_windows, train_targets, val_windows, val_targets = [], [], [], []
    for engine_id, rows in by_engine.items():
        end = rows[-1]["cycle"]
        for index, row in enumerate(rows):
            sequence = rows[max(0, index - 29):index + 1]
            window = [feature_vector(item, rows[max(0, j - 4):j]) for j, item in enumerate(sequence, max(0, index - 29))]
            if len(window) < 30:
                pad = [window[0]] * (30 - len(window))
                window = pad + window
            target = min(125, end - row["cycle"])
            group = (val_windows, val_targets) if engine_id in validation_ids else (train_windows, train_targets)
            group[0].append(window)
            group[1].append(target)
    device_name = os.getenv("FAILURECAST_TRAIN_DEVICE", "auto").lower()
    if device_name not in {"auto", "cpu", "cuda"}:
        raise ValueError("FAILURECAST_TRAIN_DEVICE must be auto, cpu, or cuda.")
    if device_name == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA was requested but is unavailable.")
    device = torch.device("cuda" if device_name == "cuda" or (device_name == "auto" and torch.cuda.is_available()) else "cpu")
    x_train = torch.tensor(np.asarray(train_windows), dtype=torch.float32)
    y_train = torch.tensor(np.asarray(train_targets), dtype=torch.float32).unsqueeze(1)
    x_val = torch.tensor(np.asarray(val_windows), dtype=torch.float32)
    y_val = np.asarray(val_targets, dtype=float)
    train_mean = x_train.mean(dim=(0, 1))
    train_std = x_train.std(dim=(0, 1)).clamp_min(1e-6)
    x_train = ((x_train - train_mean) / train_std).to(device)
    x_val = ((x_val - train_mean) / train_std).to(device)
    y_train, y_val_tensor = y_train.to(device), torch.tensor(y_val, dtype=torch.float32).unsqueeze(1).to(device)
    class LSTMRegressor(nn.Module):
        def __init__(self, input_size: int):
            super().__init__()
            self.lstm = nn.LSTM(input_size, 32, batch_first=True)
            self.head = nn.Sequential(nn.Linear(32, 16), nn.ReLU(), nn.Linear(16, 1))

        def forward(self, values):
            return self.head(self.lstm(values)[0][:, -1, :])
    model = LSTMRegressor(x_train.shape[-1]).to(device)
    loader = DataLoader(TensorDataset(x_train, y_train), batch_size=128, shuffle=True)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min", patience=1, factor=0.5)
    loss_fn = nn.SmoothL1Loss()
    best_loss, stale, best = float("inf"), 0, None
    for _ in range(12):
        model.train()
        for batch_x, batch_y in loader:
            optimizer.zero_grad()
            loss_fn(model(batch_x), batch_y).backward()
            optimizer.step()
        model.eval()
        with torch.no_grad():
            val_loss = float(loss_fn(model(x_val), y_val_tensor))
        scheduler.step(val_loss)
        if val_loss < best_loss:
            best_loss, stale = val_loss, 0
            best = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
        else:
            stale += 1
            if stale == 3:
                break
    model.load_state_dict(best)
    model_id = f"fc-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
    artifact = MODEL_DIR / f"{model_id}.pt"
    torch.save({"state_dict": {key: value.detach().cpu() for key, value in model.state_dict().items()},
                "input_size": x_train.shape[-1], "sequence_length": 30,
                "mean": train_mean.cpu().tolist(), "std": train_std.cpu().tolist()}, artifact)
    with torch.no_grad():
        val_pred = np.clip(model(x_val).squeeze(1).cpu().numpy(), 0, None).tolist()
    metrics = metrics_for(y_val.tolist(), val_pred)
    metrics.update({"validation_engines": len(validation_ids), "training_engines": len(ids) - len(validation_ids),
                    "duration_seconds": round(time.perf_counter() - started, 2), "validation_split": "engine_id holdout (80/20)",
                    "device": str(device)})
    db.execute("INSERT INTO models (id, algorithm, status, created_at, metrics, artifact_path, dataset_id, parent_id, training_job_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
               (model_id, "LSTM", "candidate", utcnow(), json.dumps(metrics), str(artifact.relative_to(ROOT)), dataset_id,
                (db.one("SELECT id FROM models WHERE status='active' ORDER BY created_at DESC LIMIT 1") or {}).get("id"), training_job_id))
    experiment = {"model_id": model_id, "algorithm": "LSTM", "dataset_id": dataset_id, "metrics": metrics,
                  "created_at": utcnow(), "seed": 41, "feature_version": "raw-plus-trailing-5-v1", "sequence_length": 30}
    tracking = log_mlflow(experiment, artifact)
    if tracking.get("run_id"):
        metrics["mlflow_run_id"] = tracking["run_id"]
        db.execute("UPDATE models SET metrics=? WHERE id=?", (json.dumps(metrics), model_id))
    experiment.update({"mlflow_run_id": tracking.get("run_id"), "tracking_warning": tracking.get("warning")})
    (EXPERIMENT_DIR / f"{model_id}.json").write_text(json.dumps(experiment, indent=2), encoding="utf-8")
    return {"model_id": model_id, "algorithm": "LSTM", "metrics": metrics, "artifact": str(artifact.relative_to(ROOT)), **tracking}
