import random

import numpy as np

from backend.app import ml
from backend.app.data import generate_demo_records, group_engines, training_examples


class NegativeEstimator:
    def __init__(self, fit_sizes):
        self.fit_sizes = fit_sizes

    def fit(self, _features, _targets):
        self.fit_sizes.append(len(_features))
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
    fit_sizes = []
    monkeypatch.setattr(ml, "make_estimator", lambda _algorithm, _seed=41: NegativeEstimator(fit_sizes))
    monkeypatch.setattr(ml.db, "one", lambda *_args: None)
    monkeypatch.setattr(ml.db, "execute", lambda *_args: None)
    monkeypatch.setattr(ml, "log_mlflow", lambda *_args: {"warning": "disabled for test"})
    records = generate_demo_records(6, 81)
    engine_ids = sorted(group_engines(records))
    shuffled = engine_ids[:]
    random.Random(41).shuffle(shuffled)
    validation_ids = set(shuffled[:max(1, round(len(engine_ids) * 0.2))])
    validation_rows = [row for row in records if row["engine_id"] in validation_ids]
    _, validation_targets = ml.censored_validation_examples(validation_rows, validation_ids)
    train_rows = [row for row in records if row["engine_id"] not in validation_ids]
    train_X, _, _ = training_examples(train_rows)
    all_X, _, _ = training_examples(records)

    result = ml.fit_candidate(records, "HistGradientBoostingRegressor")

    expected = ml.metrics_for(validation_targets, [0.0] * len(validation_targets))
    assert result["metrics"]["mae"] == expected["mae"]
    assert result["metrics"]["bias"] == expected["bias"]
    assert result["metrics"]["validation_samples"] == len(validation_ids)
    assert "80% of each held-out training trajectory" in result["metrics"]["validation_protocol"]
    assert fit_sizes == [len(train_X), len(all_X)]


def test_repeated_validation_is_seeded_and_reports_the_split():
    records = generate_demo_records(12, 81)

    first = ml.validation_metrics(records, "MeanBaseline", 43)
    repeated = ml.validation_metrics(records, "MeanBaseline", 43)

    assert first == repeated
    assert first["validation_seed"] == 43
    assert first["validation_engines"] == 2
    assert first["training_engines"] == 10


def test_condition_features_expand_model_inputs_and_stay_finite():
    records = generate_demo_records(8, 81)
    features, _, _ = training_examples(records)
    transformer = ml.OperatingConditionFeatures(seed=41)

    transformed = transformer.fit_transform(np.asarray(features, dtype=np.float32))

    assert transformed.shape == (len(features), len(features[0]) + transformer.cluster_count_ + 63)
    assert np.isfinite(transformed).all()
