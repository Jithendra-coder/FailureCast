from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import numpy as np

from . import db
from .data import MAX_IMPORT_FILE_BYTES, MAX_IMPORT_TOTAL_BYTES, feature_vector, make_dataset_engines, parse_cmapss, parse_rul, sha256, validate_records
from .ml import _fit_with_validation, fit_candidate, metrics_for, validation_metrics


def main() -> None:
    parser = argparse.ArgumentParser(prog="failurecast", description="Validate and train on NASA C-MAPSS files.")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Validate train, test and final-cycle RUL files.")
    train = commands.add_parser("train", help="Train a candidate with an engine-level holdout split.")
    benchmark = commands.add_parser("benchmark", help="Compare fixed baselines and estimators on the official final-cycle test protocol.")
    for command in (validate, train, benchmark):
        command.add_argument("--subset", required=True, choices=["FD001", "FD002", "FD003", "FD004"])
        command.add_argument("--train", type=Path, required=True, help="Path to train_FD00x.txt")
        command.add_argument("--test", type=Path, required=True, help="Path to test_FD00x.txt")
        command.add_argument("--rul", type=Path, required=True, help="Path to RUL_FD00x.txt")
    train.add_argument("--algorithm", choices=["MeanBaseline", "HistGradientBoostingRegressor", "ConditionAwareHistGradientBoostingRegressor", "RandomForestRegressor"], default="HistGradientBoostingRegressor")
    args = parser.parse_args()
    expected_names = {"train": f"train_{args.subset}.txt", "test": f"test_{args.subset}.txt", "rul": f"RUL_{args.subset}.txt"}
    paths = {"train": args.train, "test": args.test, "rul": args.rul}
    for kind, path in paths.items():
        if path.name != expected_names[kind]:
            parser.error(f"--{kind} must point to {expected_names[kind]} for subset {args.subset}.")
    contents = {}
    total = 0
    try:
        for kind, path in paths.items():
            with path.open("rb") as source:
                content = source.read(MAX_IMPORT_FILE_BYTES + 1)
            if len(content) > MAX_IMPORT_FILE_BYTES:
                parser.error(f"{expected_names[kind]} exceeds the {MAX_IMPORT_FILE_BYTES // (1024 * 1024)} MB file limit.")
            total += len(content)
            if total > MAX_IMPORT_TOTAL_BYTES:
                parser.error(f"Dataset import exceeds the {MAX_IMPORT_TOTAL_BYTES // (1024 * 1024)} MB total limit.")
            contents[kind] = content
    except OSError as exc:
        parser.error(f"Could not read dataset files: {exc}")
    train_bytes, test_bytes, rul_bytes = contents["train"], contents["test"], contents["rul"]
    try:
        train_rows = parse_cmapss(train_bytes, args.train.name)
        test_rows = parse_cmapss(test_bytes, args.test.name)
        rul_values = parse_rul(rul_bytes, args.rul.name)
        report = {"subset": args.subset, "train": validate_records(train_rows, args.train.name),
                  "test": validate_records(test_rows, args.test.name), "rul_labels": len(rul_values),
                  "sha256": {"train": sha256(train_bytes), "test": sha256(test_bytes), "rul": sha256(rul_bytes)}}
    except (UnicodeDecodeError, ValueError) as exc:
        parser.error(str(exc))
    if report["test"]["engines"] != len(rul_values):
        parser.error(f"test has {report['test']['engines']} engines but RUL has {len(rul_values)} labels")
    file_hashes = {args.train.name: report["sha256"]["train"], args.test.name: report["sha256"]["test"], args.rul.name: report["sha256"]["rul"]}
    fingerprint = sha256("".join(file_hashes[name] for name in sorted(file_hashes)).encode())
    dataset_id = f"ds-{args.subset.lower()}-{fingerprint[:10]}"
    if args.command == "train":
        db.init_db()
        report["candidate"] = fit_candidate(train_rows, args.algorithm, dataset_id)
    elif args.command == "benchmark":
        engines = make_dataset_engines(test_rows, rul_values)
        reports = []
        validation_seeds = (41, 42, 43, 44, 45)
        for algorithm in ("MeanBaseline", "HistGradientBoostingRegressor", "ConditionAwareHistGradientBoostingRegressor", "RandomForestRegressor"):
            estimator, _, primary_validation = _fit_with_validation(train_rows, algorithm, validation_seeds[0])
            validation_runs = [primary_validation] + [
                validation_metrics(train_rows, algorithm, seed) for seed in validation_seeds[1:]
            ]
            features = [feature_vector(engine["history"][-1], engine["history"][:-1]) for engine in engines]
            predictions = np.clip(estimator.predict(np.asarray(features, dtype=np.float32)), 0, None).tolist()
            metric_names = ("mae", "rmse", "bias", "nasa_score")
            validation_summary = {
                name: {"mean": round(statistics.mean(run[name] for run in validation_runs), 3),
                       "stddev": round(statistics.pstdev(run[name] for run in validation_runs), 3)}
                for name in metric_names
            }
            reports.append({"algorithm": algorithm, "validation": primary_validation,
                            "repeated_validation": {"seeds": list(validation_seeds), "runs": validation_runs,
                                                     "summary": validation_summary},
                            "final_cycle_test": metrics_for(rul_values, predictions)})
        report["benchmark"] = {"dataset_id": dataset_id,
                                "protocol": "fixed MeanBaseline, HistGradientBoosting, train-fitted operating-condition-aware HistGradientBoosting and RandomForest comparison; five predeclared train-only engine holdouts (seeds 41-45); final models fit using all official training engines; official supplied RUL labels are used only for final-cycle reporting after model choices are fixed",
                                "models": reports}
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
