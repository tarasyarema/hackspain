#!/usr/bin/env python3
"""Capture overdue collection targets from the frozen continuous feed.

This runner is intentionally diagnostic. It does not alter application code or
assert that a target reaches a particular outcome.
"""
from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback

# MuJoCo can load BLAS before the simulator imports NumPy.
for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_name] = "1"

import mujoco
import numpy as np

SCRIPT = Path(__file__).resolve()
REPO = SCRIPT.parents[4]
SIM_DIR = REPO / "sim" / "coffee_sorter"
sys.path.insert(0, str(SIM_DIR))

from engine import Engine  # noqa: E402
from profiles import PROFILES  # noqa: E402


LOCK_PATH = Path("/private/tmp/hackspain-coffee-runtime.lock")
PRESET = SIM_DIR / "configs" / "continuous_demo.json"
MODEL = SIM_DIR / "models" / "live_green_arabica.joblib"
EXPECTED_MODEL_SHA256 = "f5b26f26aed62db18fbef23b4df712b96b2946b1ae2fce699e1a2e85a20844a3"
EXPECTED_PRESET_SHA256 = "5fc5033ea62ceb4f640b4e642990d014d6de09ce706c20501eecd6c30d5c428b"
ENDPOINT_TIME = 4.0
FINAL_TIME = 5.5
TARGET_CLASSES = {17: {319: "stone"}, 31: {353: "good", 841: "good"}}
SOURCE_FILES = {
    "sim": SIM_DIR / "sim.py",
    "scene": SIM_DIR / "scene.py",
    "engine": SIM_DIR / "engine.py",
    "profiles": SIM_DIR / "profiles.py",
    "runner": SCRIPT,
}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def as_json(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def state(sim, body: int) -> dict:
    qa, va = sim.body_qpos[body], sim.body_qvel[body]
    return {
        "position_m": [float(x) for x in sim.data.qpos[qa:qa + 3]],
        "pose_quat_wxyz": [float(x) for x in sim.data.qpos[qa + 3:qa + 7]],
        "velocity_m_s": [float(x) for x in sim.data.qvel[va:va + 3]],
        "angular_velocity_rad_s": [float(x) for x in sim.data.qvel[va + 3:va + 6]],
        "xfrc_applied_n": [float(x) for x in sim.data.xfrc_applied[body, :3]],
    }


def contacts(sim, body: int) -> list[dict]:
    result = []
    solve_time = float(sim.data.time) - float(sim.dt)
    observation_time = float(sim.data.time)
    collision = sim.body_col[body]
    for index, contact in enumerate(sim.data.contact[:sim.data.ncon]):
        if collision not in (int(contact.geom1), int(contact.geom2)):
            continue
        force = np.zeros(6)
        mujoco.mj_contactForce(sim.model, sim.data, index, force)
        if force[0] <= 0:
            continue
        other = int(contact.geom2 if contact.geom1 == collision else contact.geom1)
        other_body = int(sim.model.geom_bodyid[other])
        other_bean = sim.bean_of.get(other_body)
        name = mujoco.mj_id2name(sim.model, mujoco.mjtObj.mjOBJ_GEOM, other)
        if other in sim.collection_geom:
            surface = sim.collection_geom[other]
        elif other == sim.ground_geom:
            surface = "floor"
        else:
            surface = name or f"geom_{other}"
        result.append({
            "surface": surface,
            "geom_name": name,
            "geom_ids": [int(contact.geom1), int(contact.geom2)],
            "target_geom_id": int(collision),
            "other_body_id": other_body,
            "other_object_uid": None if other_bean is None else int(other_bean.uid),
            "position_m": [float(x) for x in contact.pos],
            "distance_m": float(contact.dist),
            "friction": [float(x) for x in contact.friction],
            "solref": [float(x) for x in contact.solref],
            "normal": [float(x) for x in contact.frame[:3]],
            "normal_force_n": float(force[0]),
            "tangent_force_n": [float(x) for x in force[1:3]],
            "solve_time_s": solve_time,
            "observation_time_s": observation_time,
        })
    return result


def validate_preset(preset: dict, seed: int) -> None:
    layout = preset["layout"]
    policy = preset["policy"]
    expected_pool = layout["n_ellipsoid"] + layout["n_half"] + layout["n_box"] + layout["n_capsule"]
    checks = {
        "mode": preset.get("mode") == "continuous",
        "profile": preset.get("profile") == "green_arabica",
        "requested_rate": float(preset.get("requested_rate")) == 500.0,
        "jet_force_n": float(preset.get("jet_force_n")) == 0.06,
        "lead_s": float(policy.get("lead_s")) == 0.0015,
        "pool": expected_pool == 488,
        "timestep": float(layout.get("timestep")) == 0.001,
        "class_order": [item.name for item in PROFILES["green_arabica"].classes] == [
            "good", "faded", "black", "sour", "insect", "broken", "shell", "husk", "stone", "stick"
        ],
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise ValueError(f"frozen preset validation failed: {', '.join(failed)}")
    if seed not in TARGET_CLASSES:
        raise ValueError(f"unsupported diagnostic seed {seed}")


def make_runtime_preset(seed: int, directory: Path) -> Path:
    preset = json.loads(PRESET.read_text())
    preset["seed"] = seed
    path = directory / "continuous_overdue.json"
    path.write_text(json.dumps(preset, indent=2) + "\n")
    return path


def run(seed: int) -> dict:
    preset_source = json.loads(PRESET.read_text())
    validate_preset(preset_source, seed)
    if file_hash(MODEL) != EXPECTED_MODEL_SHA256:
        raise ValueError("model hash does not match the frozen artifact")
    if file_hash(PRESET) != EXPECTED_PRESET_SHA256:
        raise ValueError("preset hash does not match the frozen source")

    result = {
        "schema_version": 1,
        "seed": seed,
        "sim_endpoint_s": ENDPOINT_TIME,
        "sim_final_s": FINAL_TIME,
        "target_classes": {str(uid): cls for uid, cls in TARGET_CLASSES[seed].items()},
        "model_sha256": file_hash(MODEL),
        "preset_sha256": file_hash(PRESET),
        "source_sha256": {name: file_hash(path) for name, path in SOURCE_FILES.items() if path.exists()},
        "config": {
            "requested_rate_hz": 500.0,
            "pool_size": 488,
            "jet_force_n": 0.06,
            "lead_s": 0.0015,
            "dt_s": 0.001,
        },
        "targets": {str(uid): {"target_uid": uid, "expected_class": cls, "trajectory": [], "contacts": []}
                    for uid, cls in TARGET_CLASSES[seed].items()},
        "errors": [],
    }
    engine = None
    capture = result["targets"]
    with tempfile.TemporaryDirectory(prefix="cinta-overdue-") as temp_dir:
        runtime_preset = make_runtime_preset(seed, Path(temp_dir))
        lock_path = LOCK_PATH.open("a+")
        try:
            fcntl.flock(lock_path.fileno(), fcntl.LOCK_EX)
            engine = Engine(runtime_preset)
            if engine.model_path.resolve() != MODEL.resolve():
                raise ValueError("engine model path differs from the frozen artifact")
            if engine.model.classes != PROFILES["green_arabica"].names:
                raise ValueError("engine model classes differ from the frozen profile")
            sim = engine.sim
            result["named_surfaces"] = {
                name: {
                    "center_m": sim.model.geom_pos[gid].tolist(),
                    "half_size_m": sim.model.geom_size[gid].tolist(),
                    "quaternion_wxyz": sim.model.geom_quat[gid].tolist(),
                    "body_id": int(sim.model.geom_bodyid[gid]),
                }
                for name in ("splitter", "bin_accept", "bin_reject", "bin_accept_end", "bin_reject_end")
                for gid in [mujoco.mj_name2id(sim.model, mujoco.mjtObj.mjOBJ_GEOM, name)]
            }
            original_spawn = sim.spawn
            original_park = sim._park

            def target_row(uid: int):
                return capture.get(str(uid))

            def remember_initial(bean):
                row = target_row(bean.uid)
                if row is None or "sample" in row:
                    return
                row["sample"] = {
                    "class": bean.cls,
                    "mass_kg": float(bean.mass),
                    "axes_m": [float(x) for x in bean.axes],
                    "spawn_time_s": float(bean.spawn_t),
                    "body_id": int(bean.body),
                    "initial": state(sim, bean.body),
                }
                row["sampled_class_matches_expected"] = bean.cls == row["expected_class"]
                if bean.cls != row["expected_class"]:
                    result["errors"].append({
                        "type": "SampleMismatch",
                        "message": f"target {bean.uid} sampled class {bean.cls!r}, expected {row['expected_class']!r}",
                    })

            def append_trajectory(bean, phase: str, native_contacts=None, pre_step=None):
                row = target_row(bean.uid)
                if row is None:
                    return
                remember_initial(bean)
                after_step = native_contacts is not None
                row["trajectory"].append({
                    "phase": phase,
                    "time_s": float(sim.data.time),
                    "solve_time_s": (float(sim.data.time) - float(sim.dt) if after_step else None),
                    "observation_time_s": (float(sim.data.time) if after_step else None),
                    "pre_step": pre_step,
                    "physical_state": state(sim, bean.body),
                    "positive_native_contacts": native_contacts or [],
                })

            def wrapped_spawn(spec=None):
                bean = original_spawn(spec)
                if bean is not None and target_row(bean.uid) is not None:
                    remember_initial(bean)
                    append_trajectory(bean, "spawn")
                return bean

            def wrapped_park(body):
                bean = sim.bean_of.get(body)
                row = target_row(bean.uid) if bean is not None else None
                if row is not None:
                    remember_initial(bean)
                    native_contacts = contacts(sim, body)
                    append_trajectory(bean, "retirement_before_park", native_contacts=native_contacts)
                    row["contacts"].extend(native_contacts)
                    row["retirement"] = {
                        "outcome": bean.outcome,
                        "resolved_time_s": bean.resolved_t,
                        "last_position_m": None if bean.last_pos is None else list(bean.last_pos),
                        "pre_park_state": state(sim, body),
                    }
                original_park(body)

            sim.spawn = wrapped_spawn
            sim._park = wrapped_park

            def collect_after_step(pre_step_states):
                for uid, row in capture.items():
                    bean = sim.bean_by_uid.get(int(uid))
                    if bean is not None:
                        native_contacts = contacts(sim, bean.body)
                        append_trajectory(bean, "step", native_contacts=native_contacts,
                                          pre_step=pre_step_states.get(bean.uid))
                        row["contacts"].extend(native_contacts)
                    record = engine._object_records.get(int(uid))
                    if record is not None:
                        row["engine_record"] = {
                            "decisions": copy.deepcopy(record["decisions"]),
                            "associated_rejection_tracks": sorted(record["associated_rejection_tracks"]),
                            "activated_rejection_tracks": sorted(record["activated_rejection_tracks"]),
                            "own_pulse_hit": bool(record["own_pulse_hit"]),
                            "jet_hits": int(record["jet_hits"]),
                            "outcome": record["outcome"],
                            "resolved_time_s": record["resolved_time_s"],
                        }

            def snapshot_targets():
                snapshot = {}
                for uid, row in capture.items():
                    latest = row["trajectory"][-1] if row["trajectory"] else None
                    snapshot[uid] = {
                        "target_uid": int(uid),
                        "expected_class": row["expected_class"],
                        "sample": copy.deepcopy(row.get("sample")),
                        "current": copy.deepcopy(latest),
                        "contacts": copy.deepcopy([] if latest is None else latest["positive_native_contacts"]),
                        "retirement": copy.deepcopy(row.get("retirement")),
                        "engine_record": copy.deepcopy(row.get("engine_record")),
                    }
                return snapshot

            snapshot_done = False
            while float(sim.data.time) + 1e-12 < FINAL_TIME:
                pre_step_states = {
                    bean.uid: {"time_s": float(sim.data.time), "state": state(sim, bean.body)}
                    for bean in sim.bean_of.values()
                    if target_row(bean.uid) is not None
                }
                engine.step()
                collect_after_step(pre_step_states)
                if not snapshot_done and float(sim.data.time) + 1e-12 >= ENDPOINT_TIME:
                    result["snapshot_at_4_s"] = snapshot_targets()
                    snapshot_done = True
            result["endpoint_at_5_5_s"] = snapshot_targets()
            result["sim_time_observed_s"] = float(sim.data.time)
            if not snapshot_done:
                result["errors"].append({"type": "MissingEndpoint", "message": "4.0 second endpoint was not reached"})
            for uid, row in capture.items():
                if "sample" not in row:
                    result["errors"].append({"type": "MissingTarget", "message": f"target {uid} was not observed by 5.5 seconds"})
        except Exception as exc:
            result["errors"].append({
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            })
        finally:
            if engine is not None:
                try:
                    engine.close()
                except Exception as exc:
                    result["errors"].append({
                        "type": type(exc).__name__,
                        "message": f"engine close failed: {exc}",
                        "traceback": traceback.format_exc(),
                    })
            fcntl.flock(lock_path.fileno(), fcntl.LOCK_UN)
            lock_path.close()
    for uid, row in capture.items():
        row["resolved"] = bool(row.get("retirement"))
        row["unresolved_at_4_s"] = not bool(result.get("snapshot_at_4_s", {}).get(uid, {}).get("retirement"))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, choices=(17, 31), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")
    result = {"schema_version": 1, "seed": args.seed, "errors": []}
    try:
        result = run(args.seed)
    except Exception as exc:
        result["errors"].append({"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, default=as_json) + "\n")
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
