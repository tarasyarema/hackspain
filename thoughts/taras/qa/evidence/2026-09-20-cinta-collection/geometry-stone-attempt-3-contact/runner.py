#!/usr/bin/env python3
"""Wrap the existing seed 8 Reject route with a UID 0 contact trace."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
import traceback

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cinta_collection_routes as routes
import cinta_collection_overdue as overdue


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--preset", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing output directory: {args.output_dir}")

    repo, model, preset = args.repo.resolve(), args.model.resolve(), args.preset.resolve()
    source_preset, coffee = routes.validate_inputs(repo, model, preset)
    source_preset["_preset_path"] = str(preset)
    args.output_dir.parent.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir()
    original_install = routes.install_observers

    def traced_install(sim, capture, observe_support_enabled):
        original_install(sim, capture, observe_support_enabled)
        original_step = sim.step
        capture["contact_trace"] = []
        capture["contact_trace_errors"] = []

        def traced_step():
            bean = sim.bean_by_uid.get(0)
            body = None if bean is None else bean.body
            before = None if body is None else routes.state(sim, sim.data, body)
            try:
                result = original_step()
            except Exception as exc:
                capture["contact_trace_errors"].append({"message": str(exc), "traceback": traceback.format_exc()})
                raise
            if body is None:
                return result
            active = sim.bean_by_uid.get(0)
            park = next((item for item in reversed(capture["parks"])
                         if item["object_id"] == 0), None)
            after = routes.state(sim, sim.data, body) if active is not None else None
            if after is None and park is not None:
                after = {
                    "time_s": park["sim_time_s"],
                    "pose": park["final_pose_before_park"],
                    "velocity": park["final_velocity_before_park"],
                }
            capture["contact_trace"].append({
                "object_id": 0,
                "body_id": int(body),
                "pre_step": before,
                "post_step": after,
                "retired": active is None,
                "contacts": overdue.contacts(sim, body),
            })
            return result

        sim.step = traced_step
        traced_install.capture = capture

    routes.install_observers = traced_install
    run_path = args.output_dir / "stone-reject-seed-8.json"
    trace_path = args.output_dir / "stone-reject-seed-8-contact-trace.json"
    errors = []
    try:
        run = routes.run_case(
            repo, model, source_preset, coffee, run_path,
            "stone-reject", 8, ["stone"], "reject", False,
        )
    except Exception as exc:
        run = None
        errors.append({"message": str(exc), "traceback": traceback.format_exc()})
    trace = {
        "schema_version": 1,
        "seed": 8,
        "label": "stone-reject",
        "model_sha256": routes.file_hash(model),
        "preset_sha256": routes.file_hash(preset),
        "source_hashes": routes.source_hashes(coffee),
        "runner_sha256": routes.file_hash(Path(__file__).resolve()),
        "overdue_contact_helper_sha256": routes.file_hash(Path(overdue.__file__).resolve()),
        "run": run,
        "errors": errors,
    }
    capture = getattr(traced_install, "capture", None)
    if capture is not None:
        trace["trajectory"] = copy.deepcopy(capture.get("contact_trace", []))
        trace["errors"].extend(capture.get("contact_trace_errors", []))
    trace_path.write_text(json.dumps(trace, indent=2, allow_nan=False) + "\n")
    return 1 if errors or (run is not None and run.get("status") != "ok") else 0


if __name__ == "__main__":
    raise SystemExit(main())
