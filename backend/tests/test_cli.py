import json
import sys

import pytest

from backend.app import cli
from backend.app.cli import main


def cmapss_bytes(*engine_ids):
    lines = []
    for engine_id in engine_ids:
        for cycle in range(1, 4):
            values = [engine_id, cycle, .1, .2, .3, *[float(cycle)] * 21]
            lines.append(" ".join(map(str, values)))
    return ("\n".join(lines) + "\n").encode()


def test_cli_rejects_files_that_do_not_match_the_selected_subset(tmp_path, monkeypatch):
    paths = [tmp_path / name for name in ("train_FD002.txt", "test_FD002.txt", "RUL_FD002.txt")]
    monkeypatch.setattr(sys, "argv", ["failurecast", "validate", "--subset", "FD001",
                                      "--train", str(paths[0]), "--test", str(paths[1]), "--rul", str(paths[2])])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


def test_cli_enforces_the_total_dataset_size_limit(tmp_path, monkeypatch):
    paths = [tmp_path / name for name in ("train_FD001.txt", "test_FD001.txt", "RUL_FD001.txt")]
    for path in paths:
        path.write_bytes(b"123")
    monkeypatch.setattr(cli, "MAX_IMPORT_FILE_BYTES", 4)
    monkeypatch.setattr(cli, "MAX_IMPORT_TOTAL_BYTES", 8)
    monkeypatch.setattr(sys, "argv", ["failurecast", "validate", "--subset", "FD001",
                                      "--train", str(paths[0]), "--test", str(paths[1]), "--rul", str(paths[2])])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


def test_cli_benchmark_reports_fixed_final_cycle_comparison_without_registry_writes(tmp_path, monkeypatch, capsys):
    contents = {
        "train_FD001.txt": cmapss_bytes(1, 2, 3, 4),
        "test_FD001.txt": cmapss_bytes(10, 11),
        "RUL_FD001.txt": b"5\n7\n",
    }
    paths = {name: tmp_path / name for name in contents}
    for name, content in contents.items():
        paths[name].write_bytes(content)
    monkeypatch.setattr(cli.db, "init_db", lambda: pytest.fail("benchmark must not write to the model registry"))
    monkeypatch.setattr(sys, "argv", ["failurecast", "benchmark", "--subset", "FD001", "--train", str(paths["train_FD001.txt"]),
                                      "--test", str(paths["test_FD001.txt"]), "--rul", str(paths["RUL_FD001.txt"])])

    main()

    output = json.loads(capsys.readouterr().out)
    assert output["benchmark"]["protocol"].startswith("fixed MeanBaseline, HistGradientBoosting, train-fitted")
    assert [item["algorithm"] for item in output["benchmark"]["models"]] == [
        "MeanBaseline", "HistGradientBoostingRegressor", "ConditionAwareHistGradientBoostingRegressor", "RandomForestRegressor"
    ]
    assert all(item["final_cycle_test"]["samples"] == 2 for item in output["benchmark"]["models"])
    assert all(item["repeated_validation"]["seeds"] == [41, 42, 43, 44, 45]
               for item in output["benchmark"]["models"])
    assert all(set(item["repeated_validation"]["summary"]) == {"mae", "rmse", "bias", "nasa_score"}
               for item in output["benchmark"]["models"])
