#!/usr/bin/env python3
"""Aggregate the four-seed feed gate from completed JSON inputs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SEEDS = (11, 17, 23, 31)
BRANCHES = ("baseline", "candidate4")
QUALITY_START_S = 0.8
RUN_SECONDS = 4.0
DEADLINE_SECONDS = 1.1


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs(directory: Path) -> tuple[dict, dict, list[dict]]:
    values = {}
    identities = []
    for branch in BRANCHES:
        values[branch] = {}
        for seed in SEEDS:
            path = directory / f"{branch}-feed-{seed}-attempt-1.json"
            if not path.is_file():
                raise FileNotFoundError(f"missing required input: {path}")
            data = json.loads(path.read_text())
            if int(data.get("seed")) != seed:
                raise ValueError(f"{path} reports seed {data.get('seed')}, expected {seed}")
            if bool(data.get("lock_released")) is not True:
                raise ValueError(f"{path} did not report lock release")
            if data.get("errors"):
                raise ValueError(f"{path} reports run errors")
            if int(data.get("timing", {}).get("physics_steps", -1)) != 4000:
                raise ValueError(f"{path} does not contain a four-second run")
            if abs(float(data["cohort"]["end_s"]) + DEADLINE_SECONDS - RUN_SECONDS) > 1e-9:
                raise ValueError(f"{path} cohort timing does not cover four simulated seconds")
            expected_settling = 0.6 if branch == "baseline" else DEADLINE_SECONDS
            if float(data["settling_seconds"]) != expected_settling:
                raise ValueError(f"{path} has unexpected settling deadline")
            values[branch][seed] = data
            identities.append({
                "branch": branch,
                "seed": seed,
                "path": str(path),
                "sha256": sha256(path),
                "embedded_hashes": {
                    key: data.get(key) for key in
                    ("source_sha256", "model_sha256", "preset_sha256", "runner_sha256")
                    if key in data
                },
            })
    return values["baseline"], values["candidate4"], identities


def validate_consistent_identities(branch: dict[int, dict], label: str) -> None:
    keys = ("source_sha256", "model_sha256", "preset_sha256", "runner_sha256")
    reference = {key: branch[SEEDS[0]].get(key) for key in keys}
    for seed in SEEDS[1:]:
        current = {key: branch[seed].get(key) for key in keys}
        if current != reference:
            raise ValueError(f"{label} input identities differ at seed {seed}")


def cohort_metrics(data: dict) -> dict:
    cohort = data["cohort"]
    outcomes = cohort["outcomes"]
    objects = cohort["objects"]
    reject_required = cohort["required_reject"]
    keep_required = cohort["required_keep"]
    return {
        "spawned": int(data["capacity"]["spawned"]),
        "admitted": int(data["capacity"]["spawned"]),
        "starved": int(data["capacity"]["starved"]),
        "resolved": sum(int(row.get("outcome") is not None) for row in data["objects"]),
        "cohort_objects": int(objects),
        "reject_required": int(reject_required),
        "reject_captured": int(cohort["captured_reject"]),
        "reject_capture_rate": cohort["captured_reject"] / reject_required if reject_required else None,
        "keep_required": int(keep_required),
        "keep_lost": int(cohort["keep_lost"]),
        "keep_loss_rate": cohort["keep_lost"] / keep_required if keep_required else None,
        "spill": int(outcomes.get("spilled", 0)),
        "spill_rate": outcomes.get("spilled", 0) / objects if objects else None,
        "unresolved": int(outcomes.get("unresolved", 0)),
        "unresolved_rate": outcomes.get("unresolved", 0) / objects if objects else None,
        "overdue_unresolved": sum(
            row.get("outcome") is None and
            float(data["rolling_scores"]["as_of_sim_time_s"]) - float(row["spawn_s"]) > DEADLINE_SECONDS
            for row in data["objects"]
        ),
        "late_resolution_count": sum(
            row.get("resolved_s") is not None and
            float(row["resolved_s"]) - float(row["spawn_s"]) > DEADLINE_SECONDS
            for row in data["objects"]
        ),
        "max_resolution_age_s": data["timing"]["maximum_resolution_age_s"],
        "wall_s": float(data["execution"]["run_wall_s"]),
        "cpu_s": float(data["execution"]["run_cpu_s"]),
        "peak_rss_bytes": int(data["execution"]["peak_rss_bytes"]),
        "max_active": int(data["capacity"]["peak_active"]),
    }


def aggregate(branch: dict[int, dict]) -> dict:
    per_seed = {str(seed): cohort_metrics(branch[seed]) for seed in SEEDS}
    additive = ("spawned", "admitted", "starved", "resolved", "cohort_objects", "reject_required",
                "reject_captured", "keep_required", "keep_lost", "spill", "unresolved",
                "overdue_unresolved", "late_resolution_count")
    total = {key: sum(per_seed[str(seed)][key] for seed in SEEDS) for key in additive}
    total.update({
        "max_resolution_age_s": max(per_seed[str(seed)]["max_resolution_age_s"] for seed in SEEDS),
        "wall_s": sum(per_seed[str(seed)]["wall_s"] for seed in SEEDS),
        "cpu_s": sum(per_seed[str(seed)]["cpu_s"] for seed in SEEDS),
        "peak_rss_bytes": max(per_seed[str(seed)]["peak_rss_bytes"] for seed in SEEDS),
        "max_active": max(per_seed[str(seed)]["max_active"] for seed in SEEDS),
    })
    total["reject_capture_rate"] = total["reject_captured"] / total["reject_required"]
    total["keep_loss_rate"] = total["keep_lost"] / total["keep_required"]
    total["spill_rate"] = total["spill"] / total["cohort_objects"]
    total["unresolved_rate"] = total["unresolved"] / total["cohort_objects"]
    return {"per_seed": per_seed, "aggregate": total}


def pct_change(candidate, baseline):
    return None if baseline == 0 else (candidate - baseline) / baseline


def compare(baseline: dict, candidate: dict) -> dict:
    b, c = baseline["aggregate"], candidate["aggregate"]
    keep_pp = (c["keep_loss_rate"] - b["keep_loss_rate"]) * 100
    spill_pp = (c["spill_rate"] - b["spill_rate"]) * 100
    changes = {
        key: {"baseline": b[key], "candidate": c[key], "relative_change": pct_change(c[key], b[key])}
        for key in ("spawned", "admitted", "resolved", "starved", "wall_s", "cpu_s", "peak_rss_bytes", "max_active", "late_resolution_count")
    }
    changes.update({
        "reject_capture_rate": {"baseline": b["reject_capture_rate"], "candidate": c["reject_capture_rate"],
                                 "change_percentage_points": (c["reject_capture_rate"] - b["reject_capture_rate"]) * 100},
        "keep_loss_rate": {"baseline": b["keep_loss_rate"], "candidate": c["keep_loss_rate"], "change_percentage_points": keep_pp},
        "spill_rate": {"baseline": b["spill_rate"], "candidate": c["spill_rate"], "change_percentage_points": spill_pp},
        "overdue_unresolved": {"baseline": b["overdue_unresolved"], "candidate": c["overdue_unresolved"],
                               "change": c["overdue_unresolved"] - b["overdue_unresolved"]},
        "late_resolution_count": {"baseline": b["late_resolution_count"], "candidate": c["late_resolution_count"],
                                   "change": c["late_resolution_count"] - b["late_resolution_count"]},
    })
    thresholds = {
        "reject_capture_no_regression": "candidate >= baseline",
        "keep_loss_change_max_percentage_points": 1.0,
        "spill_change_max_percentage_points": 0.5,
        "admitted_relative_change_max": 0.05,
        "resolved_relative_change_max": 0.05,
        "starvation": "candidate <= baseline",
        "wall_relative_change_max": 0.05,
        "peak_rss_relative_change_max": 0.05,
        "overdue_unresolved": 0,
        "late_resolution_count": 0,
        "cpu_gate": None,
    }
    gates = {
        "reject_capture_no_regression": c["reject_capture_rate"] >= b["reject_capture_rate"],
        "keep_loss": keep_pp <= 1.0,
        "spill": spill_pp <= 0.5,
        "admitted_within_5_percent": abs(pct_change(c["admitted"], b["admitted"])) <= 0.05,
        "resolved_within_5_percent": abs(pct_change(c["resolved"], b["resolved"])) <= 0.05,
        "starvation_no_increase": c["starved"] <= b["starved"],
        "wall_within_5_percent": pct_change(c["wall_s"], b["wall_s"]) <= 0.05,
        "rss_within_5_percent": pct_change(c["peak_rss_bytes"], b["peak_rss_bytes"]) <= 0.05,
        "no_overdue_unresolved": c["overdue_unresolved"] == 0,
        "no_late_resolutions": c["late_resolution_count"] == 0,
    }
    return {"changes": changes, "thresholds": thresholds, "gates": gates}


def targeted_good(candidate31: dict) -> dict:
    result = {}
    for uid in (353, 841):
        row = next(item for item in candidate31["objects"] if item["uid"] == uid)
        result[str(uid)] = {
            "expectedAccept": not bool(row["required_reject"]),
            "actual_outcome": row["outcome"],
            "actualReject": row["outcome"] == "reject",
            "jet_hits": row["jet_hits"],
            "own_pulse_hit": row["own_pulse_hit"],
            "associated_rejection_tracks": row["associated_rejection_tracks"],
            "activated_rejection_tracks": row["activated_rejection_tracks"],
            "spawn_s": row["spawn_s"],
            "quality_cohort_included": row["spawn_s"] >= QUALITY_START_S,
            "warmup_note": (
                "before 0.8 seconds, excluded from quality cohort"
                if row["spawn_s"] < QUALITY_START_S else "included in quality cohort"
            ),
            "target_decisions": candidate31.get("target_decisions", {}).get(str(uid), []),
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    directory = args.directory.resolve()
    baseline, candidate, identities = load_inputs(directory)
    validate_consistent_identities(baseline, "baseline")
    validate_consistent_identities(candidate, "candidate4")
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {args.output}")
    baseline_summary = aggregate(baseline)
    candidate_summary = aggregate(candidate)
    output = {
        "schema_version": 1,
        "seeds": list(SEEDS),
        "aggregator_sha256": sha256(Path(__file__).resolve()),
        "output_path": str(args.output.resolve()),
        "existing_output_paths_rejected": True,
        "input_identities": identities,
        "baseline": baseline_summary,
        "candidate4": candidate_summary,
        "comparison": compare(baseline_summary, candidate_summary),
        "targeted_good_seed31": targeted_good(candidate[31]),
        "interpretation": {
            "baseline_definition": "The baseline uses the old invalid early scorer.",
            "comparison_limit": "This compares changed outcome definitions. It does not prove physical accuracy.",
            "performance_limit": "Baseline performance was measured earlier, not in a contemporary paired execution.",
            "quality_limit": "Quality success is not inferred from resolution.",
            "warmup": "UID353 spawned before 0.8 seconds and is excluded. UID841 is included.",
            "cpu": "CPU time is reported separately and has no gate.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
