#!/usr/bin/env python3
"""Summarize completed overdue JSON runs without importing the simulator."""
from __future__ import annotations

import json
import hashlib
import math
from pathlib import Path


VALIDATION = Path("/private/tmp/cinta-collection-validation")
OUTPUT = VALIDATION / "overdue-summary.json"
SEEDS = (17, 31)
TARGETS = {17: (319,), 31: (353, 841)}


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def norm(vector) -> float:
    return math.sqrt(sum(float(x) * float(x) for x in vector))


def subtract(left, right):
    return [float(a) - float(b) for a, b in zip(left, right)]


def add(left, right):
    return [float(a) + float(b) for a, b in zip(left, right)]


def scale(vector, factor):
    return [float(factor) * float(x) for x in vector]


def quat_multiply(a, b):
    aw, ax, ay, az = map(float, a)
    bw, bx, by, bz = map(float, b)
    return [
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    ]


def quat_rotate(q, vector):
    pure = [0.0, *map(float, vector)]
    inverse = [float(q[0]), -float(q[1]), -float(q[2]), -float(q[3])]
    return quat_multiply(quat_multiply(q, pure), inverse)[1:]


def quat_normalize(q):
    length = norm(q)
    return [float(x) / length for x in q]


def splitter_normal(surface: dict) -> list[float]:
    return quat_rotate(surface["quaternion_wxyz"], [0.0, 0.0, 1.0])


def splitter_contacts(sample: dict) -> list[dict]:
    return [item for item in sample.get("positive_native_contacts", [])
            if item.get("surface") == "splitter"]


def target_oriented_normal(item: dict) -> list[float]:
    normal = [float(x) for x in item.get("normal", [])]
    geom_ids = item.get("geom_ids", [])
    target_geom_id = item.get("target_geom_id")
    if len(geom_ids) == 2 and target_geom_id == geom_ids[0]:
        return scale(normal, -1.0)
    return normal


def contact_groups(items: list[dict], reference_normal: list[float] | None = None) -> list[dict]:
    groups = {}
    for item in items:
        oriented = target_oriented_normal(item)
        key = (item.get("surface"), tuple(oriented))
        group = groups.setdefault(key, {
            "surface": item.get("surface"),
            "normal_toward_target": list(key[1]),
            "samples": 0,
            "unsigned_normal_force_total_n": 0.0,
            "unsigned_normal_force_max_n": 0.0,
            "target_directed_signed_force_n": 0.0,
        })
        group["samples"] += 1
        force = float(item.get("normal_force_n", 0.0))
        group["unsigned_normal_force_total_n"] += abs(force)
        group["unsigned_normal_force_max_n"] = max(group["unsigned_normal_force_max_n"], abs(force))
        if reference_normal is not None:
            group["target_directed_signed_force_n"] += force * sum(a * b for a, b in zip(oriented, reference_normal))
    return list(groups.values())


def current_summary(snapshot: dict, reference_normal: list[float]) -> dict:
    current = snapshot.get("current") or {}
    physical = current.get("physical_state") or {}
    contacts = current.get("positive_native_contacts") or []
    return {
        "time_s": current.get("time_s"),
        "contact_solve_time_s": current.get("solve_time_s"),
        "contact_observation_time_s": current.get("observation_time_s"),
        "position_m": physical.get("position_m"),
        "speed_m_s": norm(physical.get("velocity_m_s", [])),
        "applied_force_n": physical.get("xfrc_applied_n"),
        "contacts": contact_groups(contacts, reference_normal),
        "contact_count": len(contacts),
        "retirement": snapshot.get("retirement"),
        "engine_record": snapshot.get("engine_record"),
    }


def exact_sample_comparison(overdue: dict, candidate: dict, uid: int) -> dict:
    observed = overdue["targets"][str(uid)]["sample"]
    baseline = next(item for item in candidate["objects"] if item["uid"] == uid)
    fields = {
        "class": observed["class"] == baseline["class"],
        "mass_kg": observed["mass_kg"] == baseline["mass_kg"],
        "axes_m": observed["axes_m"] == baseline["axes_m"],
        "spawn_time_s": observed["spawn_time_s"] == baseline["spawn_s"],
    }
    return {
        "exact_fields_equal": fields,
        "exact_sample_equal": all(fields.values()),
        "jet_hits_equal": overdue["targets"][str(uid)]["engine_record"]["jet_hits"] == baseline["jet_hits"],
        "overdue": {
            "class": observed["class"],
            "mass_kg": observed["mass_kg"],
            "axes_m": observed["axes_m"],
            "spawn_time_s": observed["spawn_time_s"],
            "jet_hits": overdue["targets"][str(uid)]["engine_record"]["jet_hits"],
        },
        "candidate": {
            "class": baseline["class"],
            "mass_kg": baseline["mass_kg"],
            "axes_m": baseline["axes_m"],
            "spawn_time_s": baseline["spawn_s"],
            "jet_hits": baseline["jet_hits"],
        },
    }


def final_100_metrics(row: dict) -> dict:
    samples = [item for item in row["trajectory"] if item.get("phase") == "step"][-100:]
    splitter_count = sum(bool(splitter_contacts(item)) for item in samples)
    zero_force = all(norm(item["physical_state"].get("xfrc_applied_n", [])) == 0.0 for item in samples)
    return {
        "sample_count": len(samples),
        "splitter_contact_samples": splitter_count,
        "splitter_contact_fraction": splitter_count / len(samples) if samples else None,
        "all_applied_force_zero": zero_force,
    }


def first_opposed_normal_time(row: dict, normal: list[float]):
    for sample in row["trajectory"]:
        contacts = splitter_contacts(sample)
        signs = {1 if sum(a * b for a, b in zip(target_oriented_normal(item), normal)) > 0 else -1
                 for item in contacts
                 if abs(sum(a * b for a, b in zip(target_oriented_normal(item), normal))) > 1e-9}
        if signs == {-1, 1}:
            return {
                "solve_time_s": sample.get("solve_time_s"),
                "observation_time_s": sample.get("observation_time_s"),
            }
    return None


def capsule_geometry(sample: dict, pre_step: dict, splitter: dict) -> dict:
    axes = [float(x) for x in sample["axes_m"]]
    radius = axes[2]
    half_segment = max(axes[0] - axes[2], 1e-4)
    center = pre_step["state"]["position_m"]
    body_quat = quat_normalize(pre_step["state"]["pose_quat_wxyz"])
    # sim.py uses a capsule collision geom whose local z axis is rotated to x.
    geom_quat = quat_normalize([0.7071068, 0.0, 0.7071068, 0.0])
    axis_world = quat_rotate(quat_multiply(body_quat, geom_quat), [0.0, 0.0, 1.0])
    endpoints = [
        subtract(center, scale(axis_world, half_segment)),
        add(center, scale(axis_world, half_segment)),
    ]
    normal = splitter_normal(splitter)
    splitter_center = splitter["center_m"]
    offsets = [sum(a * b for a, b in zip(subtract(point, splitter_center), normal)) for point in endpoints]
    return {
        "radius_m": radius,
        "half_segment_m": half_segment,
        "full_segment_length_m": 2.0 * half_segment,
        "center_m": center,
        "axis_world": axis_world,
        "endpoints_m": endpoints,
        "endpoint_normal_offsets_m": offsets,
        "old_splitter_face_offsets_m": [splitter["half_size_m"][2], -splitter["half_size_m"][2]],
    }


def proposed_splitter_box(splitter: dict, normal: list[float]) -> dict:
    center = subtract(splitter["center_m"], scale(normal, 0.004))
    half = list(splitter["half_size_m"])
    half[2] = 0.006
    return {
        "center_m": center,
        "half_size_m": half,
        "quaternion_wxyz": splitter["quaternion_wxyz"],
        "center_shift_m": -0.004,
        "preserves_top_rectangle_and_slope": True,
    }


def summarize_seed(seed: int) -> dict:
    overdue = load(VALIDATION / f"overdue-seed-{seed}-attempt-1.json")
    candidate = load(VALIDATION / f"candidate-feed-{seed}-attempt-1.json")
    splitter = overdue["named_surfaces"]["splitter"]
    normal = splitter_normal(splitter)
    targets = {}
    for uid in TARGETS[seed]:
        key = str(uid)
        row = overdue["targets"][key]
        at_4 = overdue["snapshot_at_4_s"][key]
        at_55 = overdue["endpoint_at_5_5_s"][key]
        position_4 = at_4["current"]["physical_state"]["position_m"]
        position_55 = at_55["current"]["physical_state"]["position_m"]
        displacement = subtract(position_55, position_4)
        target = {
            "sample_and_jet_hit_comparison": exact_sample_comparison(overdue, candidate, uid),
            "at_4_s": current_summary(at_4, normal),
            "at_5_5_s": current_summary(at_55, normal),
            "displacement_m": displacement,
            "displacement_norm_m": norm(displacement),
            "final_100": final_100_metrics(row),
            "first_opposed_splitter_normal_time_s": first_opposed_normal_time(row, normal),
        }
        if row["sample"]["class"] == "good":
            target["capsule_geometry_at_4_s"] = capsule_geometry(
                row["sample"], at_4["current"]["pre_step"], splitter
            )
        targets[key] = target

    force_by_uid = {}
    for uid in TARGETS[seed]:
        at_4_contacts = overdue["snapshot_at_4_s"][str(uid)]["current"].get("positive_native_contacts", [])
        at_55_contacts = overdue["endpoint_at_5_5_s"][str(uid)]["current"].get("positive_native_contacts", [])
        force_by_uid[str(uid)] = {
            "mg_n": overdue["targets"][str(uid)]["sample"]["mass_kg"] * 9.81,
            "unsigned_normal_force_n_at_4_s": sum(abs(float(item.get("normal_force_n", 0.0))) for item in at_4_contacts),
            "unsigned_normal_force_n_at_5_5_s": sum(abs(float(item.get("normal_force_n", 0.0))) for item in at_55_contacts),
            "target_directed_signed_splitter_force_n_at_4_s": sum(
                float(item.get("normal_force_n", 0.0)) * sum(a * b for a, b in zip(target_oriented_normal(item), normal))
                for item in at_4_contacts if item.get("surface") == "splitter"
            ),
            "target_directed_signed_splitter_force_n_at_5_5_s": sum(
                float(item.get("normal_force_n", 0.0)) * sum(a * b for a, b in zip(target_oriented_normal(item), normal))
                for item in at_55_contacts if item.get("surface") == "splitter"
            ),
            "contact_groups_at_5_5_s": contact_groups(at_55_contacts, normal),
        }
    return {
        "seed": seed,
        "splitter_normal": normal,
        "targets": targets,
        "mg_vs_total_endpoint_normal_force": {
            "by_uid": force_by_uid,
        },
        "proposed_splitter_box": proposed_splitter_box(splitter, normal),
    }


def main() -> None:
    input_paths = [
        *(VALIDATION / f"overdue-seed-{seed}-attempt-1.json" for seed in SEEDS),
        *(VALIDATION / f"candidate-feed-{seed}-attempt-1.json" for seed in SEEDS),
    ]
    summary = {
        "schema_version": 1,
        "inputs": [str(path) for path in input_paths],
        "identities": {
            "script_sha256": sha256(Path(__file__).resolve()),
            "input_sha256": {str(path): sha256(path) for path in input_paths},
        },
        "seeds": {str(seed): summarize_seed(seed) for seed in SEEDS},
    }
    OUTPUT.write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
