import pytest

from backend.app.data import CMAPSS_COLUMNS, MAX_IMPORT_FILE_BYTES, feature_vector, make_dataset_engines, parse_cmapss, parse_rul, training_examples, validate_records


def rows_for(*engine_ids: int) -> bytes:
    lines = []
    for engine_id in engine_ids:
        for cycle in range(1, 4):
            values = [engine_id, cycle, .1, .2, .3, *[cycle * 1.0 for _ in range(21)]]
            lines.append(" ".join(map(str, values)))
    return ("\n".join(lines) + "\n").encode()


def test_cmapss_schema_and_quality_report():
    parsed = parse_cmapss(rows_for(1), "train_FD001.txt")
    report = validate_records(parsed, "train_FD001.txt")
    assert len(CMAPSS_COLUMNS) == 26
    assert report["rows"] == 3
    assert report["engines"] == 1
    assert report["ordered_cycles"] is True


def test_rejects_bad_width_duplicate_cycles_and_non_finite_data():
    with pytest.raises(ValueError, match="expected 26"):
        parse_cmapss(b"1 1 2", "bad.txt")
    with pytest.raises(ValueError, match="non-finite"):
        parse_cmapss(("1 1 " + " ".join(["nan"] * 24)).encode(), "bad.txt")
    duplicate = parse_cmapss(rows_for(1), "train.txt")
    with pytest.raises(ValueError, match="duplicate"):
        validate_records(duplicate + [duplicate[-1]], "train.txt")
    unordered = parse_cmapss(rows_for(1), "train.txt")
    unordered[0], unordered[1] = unordered[1], unordered[0]
    with pytest.raises(ValueError, match="non-increasing"):
        validate_records(unordered, "train.txt")


def test_rul_labels_are_non_negative_whole_cycles():
    assert parse_rul(b"5\n0\n", "RUL_FD001.txt") == [5, 0]
    with pytest.raises(ValueError, match="non-negative whole"):
        parse_rul(b"-1\n", "RUL_FD001.txt")


def test_source_parsers_reject_files_over_the_import_limit():
    oversized = bytes(MAX_IMPORT_FILE_BYTES + 1)
    with pytest.raises(ValueError, match="20 MB file limit"):
        parse_cmapss(oversized, "train_FD001.txt")
    with pytest.raises(ValueError, match="20 MB file limit"):
        parse_rul(oversized, "RUL_FD001.txt")


def test_trailing_features_and_targets_stay_within_engine():
    records = parse_cmapss(rows_for(1, 2), "train.txt")
    latest = records[2]
    vector = feature_vector(latest, records[0:2])
    # sensor_1 is the first sensor; its five-cycle window contains cycles 1..3 from engine 1 only.
    assert vector[25] == pytest.approx(2.0)
    assert vector[26] == pytest.approx(2.0)
    _, targets, engine_ids = training_examples(records)
    assert targets[:3] == [2, 1, 0]
    assert targets[3:] == [2, 1, 0]
    assert engine_ids[:3] == [1, 1, 1]
    assert engine_ids[3:] == [2, 2, 2]


def test_test_rul_labels_follow_file_engine_order_even_when_ids_are_not_sorted():
    records = parse_cmapss(rows_for(20, 10), "test_FD001.txt")

    engines = make_dataset_engines(records, [5, 7])

    assert [(engine["id"], engine["rul"]) for engine in engines] == [("ENG-010", 7), ("ENG-020", 5)]
