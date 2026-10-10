from __future__ import annotations

import hashlib
import math
import random
from collections import defaultdict
from typing import Iterable

SETTINGS = [f"setting_{i}" for i in range(1, 4)]
SENSORS = [f"sensor_{i}" for i in range(1, 22)]
FEATURES = SETTINGS + SENSORS + ["cycle"] + [f"sensor_{i}_{suffix}" for i in range(1, 22) for suffix in ("mean5", "delta5")]
CMAPSS_COLUMNS = ["engine_id", "cycle", *SETTINGS, *SENSORS]
MAX_IMPORT_FILE_BYTES = 20 * 1024 * 1024
MAX_IMPORT_TOTAL_BYTES = 40 * 1024 * 1024


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_cmapss(data: bytes, filename: str) -> list[dict]:
    """Parse the official whitespace-delimited C-MAPSS format without trusting filenames or rows."""
    if len(data) > MAX_IMPORT_FILE_BYTES:
        raise ValueError(f"{filename} exceeds the {MAX_IMPORT_FILE_BYTES // (1024 * 1024)} MB file limit.")
    rows: list[dict] = []
    text = data.decode("utf-8-sig")
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != len(CMAPSS_COLUMNS):
            raise ValueError(f"{filename}:{line_no} has {len(parts)} values; expected {len(CMAPSS_COLUMNS)}.")
        try:
            values = [float(value) for value in parts]
        except ValueError as exc:
            raise ValueError(f"{filename}:{line_no} contains a non-numeric value.") from exc
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"{filename}:{line_no} contains a missing or non-finite value.")
        if values[0] < 1 or values[1] < 1 or not values[0].is_integer() or not values[1].is_integer():
            raise ValueError(f"{filename}:{line_no} has an invalid engine ID or cycle.")
        rows.append(dict(zip(CMAPSS_COLUMNS, [int(values[0]), int(values[1]), *values[2:]])))
        if len(rows) > 250_000:
            raise ValueError("Dataset file exceeds the 250,000 row import limit.")
    if not rows:
        raise ValueError(f"{filename} is empty.")
    return rows


def parse_rul(data: bytes, filename: str) -> list[int]:
    if len(data) > MAX_IMPORT_FILE_BYTES:
        raise ValueError(f"{filename} exceeds the {MAX_IMPORT_FILE_BYTES // (1024 * 1024)} MB file limit.")
    values = []
    for line_no, line in enumerate(data.decode("utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = float(line.strip())
        except ValueError as exc:
            raise ValueError(f"{filename}:{line_no} is not a number.") from exc
        if not math.isfinite(value) or value < 0 or not value.is_integer():
            raise ValueError(f"{filename}:{line_no} must be a non-negative whole number.")
        values.append(int(value))
    if not values:
        raise ValueError(f"{filename} is empty.")
    return values


def validate_records(records: list[dict], filename: str) -> dict:
    by_engine: dict[int, list[int]] = defaultdict(list)
    seen = set()
    duplicates = 0
    for row in records:
        key = (row["engine_id"], row["cycle"])
        duplicates += key in seen
        seen.add(key)
        by_engine[row["engine_id"]].append(row["cycle"])
    unordered = [engine_id for engine_id, cycles in by_engine.items() if cycles != sorted(set(cycles))]
    if duplicates:
        raise ValueError(f"{filename} contains {duplicates} duplicate engine-cycle rows.")
    if unordered:
        raise ValueError(f"{filename} has non-increasing cycles for engine {unordered[0]}.")
    return {
        "file": filename,
        "rows": len(records),
        "engines": len(by_engine),
        "cycle_min": min(min(cycles) for cycles in by_engine.values()),
        "cycle_max": max(max(cycles) for cycles in by_engine.values()),
        "missing_values": 0,
        "duplicate_engine_cycles": 0,
        "ordered_cycles": True,
        "sensors": len(SENSORS),
    }


def group_engines(records: Iterable[dict]) -> dict[int, list[dict]]:
    result: dict[int, list[dict]] = defaultdict(list)
    for row in records:
        result[int(row["engine_id"])].append(row)
    for rows in result.values():
        rows.sort(key=lambda row: row["cycle"])
    return dict(result)


def feature_vector(row: dict, previous: list[dict]) -> list[float]:
    window = [*previous[-4:], row]
    values = [float(row[name]) for name in SETTINGS + SENSORS]
    values.append(float(row["cycle"]))
    for name in SENSORS:
        sensor_values = [float(item[name]) for item in window]
        values.extend((sum(sensor_values) / len(sensor_values), sensor_values[-1] - sensor_values[0]))
    return values


def training_examples(records: list[dict], cap_rul: int | None = 125) -> tuple[list[list[float]], list[float], list[int]]:
    X, y, engine_ids = [], [], []
    for engine_id, rows in group_engines(records).items():
        end = rows[-1]["cycle"]
        for index, row in enumerate(rows):
            rul = end - row["cycle"]
            X.append(feature_vector(row, rows[max(0, index - 4):index]))
            y.append(float(min(rul, cap_rul)) if cap_rul is not None else float(rul))
            engine_ids.append(engine_id)
    return X, y, engine_ids


def generate_demo_records(engine_count: int = 48, seed: int = 81) -> list[dict]:
    """Create visibly simulated C-MAPSS-shaped trajectories for local product exploration."""
    records: list[dict] = []
    for engine_id in range(1, engine_count + 1):
        local = random.Random(seed * 1000 + engine_id)
        life = 95 + ((engine_id * 19) % 61)
        offsets = [local.uniform(-0.08, 0.08) for _ in SENSORS]
        phase = local.random() * math.tau
        for cycle in range(1, life + 1):
            progress = cycle / life
            row = {"engine_id": engine_id, "cycle": cycle}
            row.update({"setting_1": round(0.001 * math.sin(phase) + local.uniform(-0.002, 0.002), 5),
                        "setting_2": round(0.0003 + local.uniform(-0.0001, 0.0001), 6),
                        "setting_3": round(100.0 + local.uniform(-0.08, 0.08), 4)})
            for sensor_index, name in enumerate(SENSORS, 1):
                direction = 1 if sensor_index in (2, 3, 4, 7, 11, 12, 15, 20, 21) else -1 if sensor_index in (1, 6, 10, 13, 16, 18, 19) else 0
                noise = local.gauss(0, 0.025 if sensor_index in (2, 3, 4, 7, 11, 12, 15, 20, 21) else 0.045)
                base = 0.7 + sensor_index * 0.12 + offsets[sensor_index - 1]
                degradation = direction * progress * (0.7 + sensor_index * 0.025)
                row[name] = round(base + degradation + noise, 6)
            records.append(row)
    return records


def make_dataset_engines(records: list[dict], rul_values: list[int] | None = None, *, demo: bool = False) -> list[dict]:
    grouped = group_engines(records)
    result = []
    for position, (engine_id, rows) in enumerate(sorted(grouped.items())):
        last_index = max(1, int(len(rows) * (0.56 + ((position * 17) % 29) / 100))) - 1 if demo else len(rows) - 1
        current = rows[: last_index + 1]
        truth = (rows[-1]["cycle"] - current[-1]["cycle"]) if demo else (rul_values[position] if rul_values and position < len(rul_values) else None)
        result.append({"id": f"ENG-{engine_id:03d}", "engine_id": engine_id, "subset": "FD001", "cycle": current[-1]["cycle"],
                       "total_cycles": rows[-1]["cycle"], "rul": truth, "health": "—", "history": current})
    return result
