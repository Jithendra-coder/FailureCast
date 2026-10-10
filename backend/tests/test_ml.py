import random

import numpy as np

from backend.app import ml
from backend.app.data import generate_demo_records, group_engines, training_examples


class NegativeEstimator:
    def fit(self, _features, _targets):
        return self

    def predict(self, features):
        return np.full(len(features), -5.0)


def test_validation_metrics_match_non_negative_inference_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(ml, "ROOT", tmp_path)
    monkeypatch.setattr(ml, "MODEL_DIR", tmp_path / "models")
    monkeypatch.setattr(ml, "EXPERIMENT_DIR", tmp_path / "experiments")
    ml.MODEL_DIR.mkdir()
    ml.EXPERIMENT_DIR.mkdir()
    monkeypatch.setattr(ml, "MODEL_CACHE", {})
    monkeypatch.setattr(ml, "make_estimator", lambda _algorithm: NegativeEstimator())
    monkeypatch.setattr(ml.db, "one", lambda *_args: None)
    monkeypatch.setattr(ml.db, "execute", lambda *_args: None)
    monkeypatch.setattr(ml, "log_mlflow", lambda *_args: {"warning": "disabled for test"})
    records = generate_demo_records(6, 81)
    engine_ids = sorted(group_engines(records))
    shuffled = engine_ids[:]
    random.Random(41).shuffle(shuffled)
    validation_ids = set(shuffled[:max(1, round(len(engine_ids) * 0.2))])
    validation_rows = [row for row in records if row["engine_id"] in validation_ids]
    _, validation_targets, _ = training_examples(validation_rows)

    result = ml.fit_candidate(records, "HistGradientBoostingRegressor")

    expected = ml.metrics_for(validation_targets, [0.0] * len(validation_targets))
    assert result["metrics"]["mae"] == expected["mae"]
    assert result["metrics"]["bias"] == expected["bias"]
