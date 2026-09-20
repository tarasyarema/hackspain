#!/usr/bin/env python3
"""Summarize a paired old-retirement/native-outcome observer run.

This module only evaluates recorded rows. It does not import the simulator or
replay any physics.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
from typing import Any


OUTCOMES = ("accept", "reject", "spilled")
LABELS = ("accept", "reject", "spilled", "unresolved")
REQUIRED_ROW_FIELDS = {
    "uid", "class", "shape", "spawn_s", "required_reject", "old_label",
    "old_label_s", "old_retired_s", "native_outcome", "native_s", "retired_s",
    "jet_hits",
}
REQUIRED_SAMPLE_FIELDS = {
    "time_s", "spawned", "starved", "active", "active_by_shape", "free_by_shape",
    "old_retired_still_active", "overdue_active", "oldest_active_age",
}
REQUIRED_ACTIVE_FIELDS = {"uid", "age_s", "pos", "velocity", "contacts"}


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be an object")
    return value


def _required(mapping: dict[str, Any], fields: set[str], name: str) -> None:
    missing = sorted(fields - mapping.keys())
    if missing:
        raise ValueError(f"{name} is missing fields: {', '.join(missing)}")


def _outcome(value: Any, name: str) -> str | None:
    if value is not None and value not in OUTCOMES:
        raise ValueError(f"{name} must be null or one of {OUTCOMES}")
    return value


def _rate(numerator: int, denominator: int) -> dict[str, int | float | None]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else None,
    }


def _correct(required_reject: bool, outcome: str | None) -> bool:
    return (
        (required_reject and outcome == "reject")
        or (not required_reject and outcome == "accept")
    )


def _score(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, int | float | None]]:
    """Return the primary score rules for one outcome field."""
    eligible = len(rows)
    required = sum(bool(row["required_reject"]) for row in rows)
    keep = eligible - required
    correct = sum(_correct(row["required_reject"], row[field]) for row in rows)
    captured = sum(row["required_reject"] and row[field] == "reject" for row in rows)
    lost = sum((not row["required_reject"]) and row[field] in ("reject", "spilled") for row in rows)
    spilled = sum(row[field] == "spilled" for row in rows)
    unresolved = sum(row[field] is None for row in rows)
    return {
        "sorting_accuracy": _rate(correct, eligible),
        "reject_capture": _rate(captured, required),
        "keep_loss": _rate(lost, keep),
        "spill": _rate(spilled, eligible),
        "unresolved": _rate(unresolved, eligible),
    }


def _metric_delta(native: dict[str, Any], old: dict[str, Any]) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for name in ("sorting_accuracy", "reject_capture", "keep_loss", "spill", "unresolved"):
        native_rate = native[name]["rate"]
        old_rate = old[name]["rate"]
        result[name] = (
            native_rate - old_rate
            if native_rate is not None and old_rate is not None
            else None
        )
    return result


def _normal_label(value: str | None) -> str:
    return value if value is not None else "unresolved"


def _validate_and_copy(data: Any) -> dict[str, Any]:
    root = _mapping(data, "data")
    for name in ("configuration", "rows", "samples", "final_active", "rolling_scores", "final_time_s"):
        if name not in root:
            raise ValueError(f"data is missing field: {name}")
    config = _mapping(root["configuration"], "configuration")
    for name in ("duration_s", "settling_s", "seed"):
        if name not in config:
            raise ValueError(f"configuration is missing field: {name}")
    _number(config["duration_s"], "configuration.duration_s")
    _number(config["settling_s"], "configuration.settling_s")
    _integer(config["seed"], "configuration.seed")
    final_time = _number(root["final_time_s"], "final_time_s")

    rows = root["rows"]
    samples = root["samples"]
    active = root["final_active"]
    if not isinstance(rows, list):
        raise TypeError("rows must be a list")
    if not isinstance(samples, list):
        raise TypeError("samples must be a list")
    if not isinstance(active, list):
        raise TypeError("final_active must be a list")
    if not samples:
        raise ValueError("samples must not be empty")
    rolling = _mapping(root["rolling_scores"], "rolling_scores")
    capacity = root.get("capacity")
    if capacity is not None:
        capacity = _mapping(capacity, "capacity")
        for field in ("spawned", "starved", "active", "peak_active"):
            if field in capacity:
                _integer(capacity[field], f"capacity.{field}")
                if capacity[field] < 0:
                    raise ValueError(f"capacity.{field} must be non-negative")
    execution = root.get("execution")
    if execution is not None:
        execution = _mapping(execution, "execution")
        if "peak_active" in execution:
            _integer(execution["peak_active"], "execution.peak_active")
            if execution["peak_active"] < 0:
                raise ValueError("execution.peak_active must be non-negative")

    seen_uids: set[Any] = set()
    copied_rows: list[dict[str, Any]] = []
    for index, raw in enumerate(rows):
        row = _mapping(raw, f"rows[{index}]")
        _required(row, REQUIRED_ROW_FIELDS, f"rows[{index}]")
        uid = row["uid"]
        try:
            if uid in seen_uids:
                raise ValueError(f"duplicate uid: {uid!r}")
            seen_uids.add(uid)
        except TypeError as exc:
            raise TypeError(f"rows[{index}].uid must be hashable") from exc
        if not isinstance(row["class"], str) or not row["class"]:
            raise ValueError(f"rows[{index}].class must be a non-empty string")
        if not isinstance(row["shape"], str) or not row["shape"]:
            raise ValueError(f"rows[{index}].shape must be a non-empty string")
        _number(row["spawn_s"], f"rows[{index}].spawn_s")
        if not isinstance(row["required_reject"], bool):
            raise TypeError(f"rows[{index}].required_reject must be boolean")
        for field in ("old_label_s", "old_retired_s", "native_s", "retired_s"):
            if row[field] is not None:
                _number(row[field], f"rows[{index}].{field}")
        _outcome(row["old_label"], f"rows[{index}].old_label")
        _outcome(row["native_outcome"], f"rows[{index}].native_outcome")
        _integer(row["jet_hits"], f"rows[{index}].jet_hits")
        copied_rows.append(deepcopy(row))

    previous_time = float("-inf")
    for index, raw in enumerate(samples):
        sample = _mapping(raw, f"samples[{index}]")
        _required(sample, REQUIRED_SAMPLE_FIELDS, f"samples[{index}]")
        time_s = _number(sample["time_s"], f"samples[{index}].time_s")
        if time_s < previous_time:
            raise ValueError("samples must be ordered by time_s")
        previous_time = time_s
        for field in ("spawned", "starved", "active", "old_retired_still_active", "overdue_active"):
            _integer(sample[field], f"samples[{index}].{field}")
            if sample[field] < 0:
                raise ValueError(f"samples[{index}].{field} must be non-negative")
        if not isinstance(sample["active_by_shape"], dict) or not isinstance(sample["free_by_shape"], dict):
            raise TypeError(f"samples[{index}] shape counts must be objects")
        if sample["oldest_active_age"] is not None:
            _number(sample["oldest_active_age"], f"samples[{index}].oldest_active_age")

    active_uids: set[Any] = set()
    copied_active: list[dict[str, Any]] = []
    for index, raw in enumerate(active):
        item = _mapping(raw, f"final_active[{index}]")
        _required(item, REQUIRED_ACTIVE_FIELDS, f"final_active[{index}]")
        uid = item["uid"]
        if uid in active_uids:
            raise ValueError(f"duplicate final_active uid: {uid!r}")
        active_uids.add(uid)
        _number(item["age_s"], f"final_active[{index}].age_s")
        if item["age_s"] < 0:
            raise ValueError(f"final_active[{index}].age_s must be non-negative")
        for field in ("pos", "velocity", "contacts"):
            if not isinstance(item[field], list):
                raise TypeError(f"final_active[{index}].{field} must be a list")
        copied_active.append(deepcopy(item))

    return {
        "configuration": deepcopy(config),
        "final_time_s": final_time,
        "rows": copied_rows,
        "samples": deepcopy(samples),
        "final_active": copied_active,
        "rolling_scores": deepcopy(rolling),
        "capacity_observer": deepcopy(capacity),
        "execution_observer": deepcopy(execution),
    }


def _assert_rolling_matches(native: dict[str, Any], rolling: dict[str, Any]) -> None:
    if not isinstance(rolling.get("eligible_objects"), int):
        raise TypeError("rolling_scores.eligible_objects must be an integer")
    if rolling["eligible_objects"] != len(native["eligible_rows"]):
        raise ValueError(
            "rolling_scores eligible_objects does not match the native primary cohort"
        )
    mapping = {
        "sorting_accuracy": "sorting_accuracy",
        "reject_capture": "reject_capture",
        "keep_loss": "keep_loss",
        "unresolved": "unresolved",
    }
    for rolling_name, native_name in mapping.items():
        expected = native[native_name]
        actual = _mapping(rolling.get(rolling_name), f"rolling_scores.{rolling_name}")
        for field in ("numerator", "denominator"):
            if actual.get(field) != expected[field]:
                raise ValueError(
                    f"rolling_scores.{rolling_name}.{field} does not match native summary"
                )


def summarize(data: dict[str, Any]) -> dict[str, Any]:
    """Return score, pairing, capacity, and active-retention diagnostics."""
    source = _validate_and_copy(data)
    config = source["configuration"]
    final_time = source["final_time_s"]
    settling = float(config["settling_s"])
    cutoff = final_time - settling
    all_rows = source["rows"]
    eligible_rows = [row for row in all_rows if float(row["spawn_s"]) <= cutoff]

    old = _score(eligible_rows, "old_label")
    native = _score(eligible_rows, "native_outcome")
    old["eligible_objects"] = len(eligible_rows)
    native["eligible_objects"] = len(eligible_rows)
    native_for_compare = {
        **native,
        "eligible_rows": eligible_rows,
        "reject_capture": native["reject_capture"],
    }
    _assert_rolling_matches(native_for_compare, source["rolling_scores"])

    matrix = {old_label: {native_label: 0 for native_label in LABELS} for old_label in LABELS}
    old_correct_native_wrong: list[Any] = []
    native_correct_old_wrong: list[Any] = []
    for row in eligible_rows:
        old_label = _normal_label(row["old_label"])
        native_label = _normal_label(row["native_outcome"])
        matrix[old_label][native_label] += 1
        old_correct = _correct(row["required_reject"], row["old_label"])
        native_correct = _correct(row["required_reject"], row["native_outcome"])
        if old_correct and not native_correct:
            old_correct_native_wrong.append(row["uid"])
        if native_correct and not old_correct:
            native_correct_old_wrong.append(row["uid"])

    resolved_after = {
        "old": sum(
            row["old_label_s"] is not None and row["old_label_s"] - row["spawn_s"] > settling
            for row in eligible_rows
        ),
        "native": sum(
            row["native_s"] is not None and row["native_s"] - row["spawn_s"] > settling
            for row in eligible_rows
        ),
    }

    classes = sorted({row["class"] for row in all_rows})
    class_breakdown: dict[str, Any] = {}
    for class_name in classes:
        class_rows = [row for row in eligible_rows if row["class"] == class_name]
        class_breakdown[class_name] = {
            "eligible_objects": len(class_rows),
            "required_reject": sum(row["required_reject"] for row in class_rows),
            "old": _score(class_rows, "old_label"),
            "native": _score(class_rows, "native_outcome"),
        }

    final_by_uid = {item["uid"]: item for item in source["final_active"]}
    row_by_uid = {row["uid"]: row for row in all_rows}
    retired_under_old = [
        uid for uid in final_by_uid
        if uid in row_by_uid and row_by_uid[uid]["old_retired_s"] is not None
    ]
    buckets = {"1.1-2": 0, "2-5": 0, "5+": 0}
    for item in source["final_active"]:
        age = float(item["age_s"])
        if settling < age <= 2.0:
            buckets["1.1-2"] += 1
        elif 2.0 < age <= 5.0:
            buckets["2-5"] += 1
        elif age > 5.0:
            buckets["5+"] += 1
    latest_sample = source["samples"][-1]
    observed_capacity = source["capacity_observer"] or {}
    observed_execution = source["execution_observer"] or {}
    peak_active = int(observed_capacity.get("peak_active", observed_execution.get(
        "peak_active", max(sample["active"] for sample in source["samples"]))))
    peak_overdue = max(sample["overdue_active"] for sample in source["samples"])
    max_sample_age = max(
        (float(sample["oldest_active_age"]) for sample in source["samples"]
         if sample["oldest_active_age"] is not None),
        default=None,
    )
    admitted = len(all_rows)
    spawned = int(observed_capacity.get("spawned", latest_sample["spawned"]))
    starved = int(observed_capacity.get("starved", latest_sample["starved"]))
    occupancy_end = int(observed_capacity.get("active", latest_sample["active"]))
    native_delta = _metric_delta(native, old)

    return {
        "schema_version": 1,
        "configuration": source["configuration"],
        "final_time_s": final_time,
        "cohort": {
            "settling_s": settling,
            "cutoff_s": cutoff,
            "eligible_objects": len(eligible_rows),
            "includes_warmup": True,
            "basis": "same admitted rows with spawn_s <= final_time_s - settling_s",
        },
        "scores": {
            "old": old,
            "native": native,
            "native_minus_old_percentage_points": {
                name: (value * 100.0 if value is not None else None)
                for name, value in native_delta.items()
            },
        },
        "matrix_old_label_vs_native_outcome": matrix,
        "paired_false_successes": {
            "old_correct_native_wrong_or_unresolved": {
                "count": len(old_correct_native_wrong),
                "uids": old_correct_native_wrong,
            },
            "native_correct_old_wrong_or_unresolved": {
                "count": len(native_correct_old_wrong),
                "uids": native_correct_old_wrong,
            },
        },
        "class_breakdown": class_breakdown,
        "resolved_after_settling": resolved_after,
        "final_active": source["final_active"],
        "active": {
            "final_count": len(source["final_active"]),
            "final_overdue_count": sum(float(item["age_s"]) > settling for item in source["final_active"]),
            "final_oldest_age_s": max((float(item["age_s"]) for item in source["final_active"]), default=None),
            "final_age_buckets": buckets,
            "peak_overdue_count": peak_overdue,
            "maximum_sampled_oldest_active_age_s": max_sample_age,
        },
        "capacity": {
            "admitted": admitted,
            "spawned": spawned,
            "starved": starved,
            "inferred_requested_attempted": spawned + starved,
            "inferred_requested_attempted_note": "spawned + starved. Placement-retry attempts are excluded.",
            "admitted_rate_per_s": admitted / float(config["duration_s"]),
            "occupancy_peak": peak_active,
            "occupancy_end": occupancy_end,
            "pool": deepcopy(observed_capacity.get("pool")),
            "retired_under_old_but_active_at_end": {
                "count": len(retired_under_old),
                "uids": retired_under_old,
            },
            "sample_end": {
                "time_s": latest_sample["time_s"],
                "spawned": latest_sample["spawned"],
                "starved": latest_sample["starved"],
                "active": latest_sample["active"],
                "old_retired_still_active": latest_sample["old_retired_still_active"],
                "overdue_active": latest_sample["overdue_active"],
                "oldest_active_age": latest_sample["oldest_active_age"],
            },
        },
        "rolling_scores": source["rolling_scores"],
        "interpretation": {
            "trajectory_basis": "This compares outcomes on the same current trajectories. It does not replay historical pool, physics, or model behavior.",
            "throughput_caveat": "Old retirement observation does not estimate counterfactual throughput because recycling changes future dynamics.",
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {args.output}")
    result = summarize(json.loads(args.input.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
