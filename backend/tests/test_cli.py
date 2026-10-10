import sys

import pytest

from backend.app import cli
from backend.app.cli import main


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
