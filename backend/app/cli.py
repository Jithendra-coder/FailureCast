from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import db
from .data import parse_cmapss, parse_rul, sha256, validate_records
from .ml import fit_candidate


def main() -> None:
    parser = argparse.ArgumentParser(prog="failurecast", description="Validate and train on NASA C-MAPSS files.")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Validate train, test and final-cycle RUL files.")
    train = commands.add_parser("train", help="Train a candidate with an engine-level holdout split.")
    for command in (validate, train):
        command.add_argument("--subset", required=True, choices=["FD001", "FD002", "FD003", "FD004"])
        command.add_argument("--train", type=Path, required=True, help="Path to train_FD00x.txt")
        command.add_argument("--test", type=Path, required=True, help="Path to test_FD00x.txt")
        command.add_argument("--rul", type=Path, required=True, help="Path to RUL_FD00x.txt")
    train.add_argument("--algorithm", choices=["MeanBaseline", "HistGradientBoostingRegressor", "RandomForestRegressor"], default="HistGradientBoostingRegressor")
    args = parser.parse_args()
    train_bytes, test_bytes, rul_bytes = args.train.read_bytes(), args.test.read_bytes(), args.rul.read_bytes()
    train_rows = parse_cmapss(train_bytes, args.train.name)
    test_rows = parse_cmapss(test_bytes, args.test.name)
    rul_values = parse_rul(rul_bytes, args.rul.name)
    report = {"subset": args.subset, "train": validate_records(train_rows, args.train.name),
              "test": validate_records(test_rows, args.test.name), "rul_labels": len(rul_values),
              "sha256": {"train": sha256(train_bytes), "test": sha256(test_bytes), "rul": sha256(rul_bytes)}}
    if report["test"]["engines"] != len(rul_values):
        parser.error(f"test has {report['test']['engines']} engines but RUL has {len(rul_values)} labels")
    if args.command == "train":
        db.init_db()
        fingerprint = sha256(train_bytes + test_bytes + rul_bytes)
        report["candidate"] = fit_candidate(train_rows, args.algorithm, f"cli-{args.subset.lower()}-{fingerprint[:10]}")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
