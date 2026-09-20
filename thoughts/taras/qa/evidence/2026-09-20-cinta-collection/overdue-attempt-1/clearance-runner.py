"""Check proposed splitter boxes against saved Stone poses without simulation."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np


def rotation(quaternion):
    w, x, y, z = quaternion
    return np.array([
        [1 - 2 * (y*y + z*z), 2 * (x*y - z*w), 2 * (x*z + y*w)],
        [2 * (x*y + z*w), 1 - 2 * (x*x + z*z), 2 * (y*z - x*w)],
        [2 * (x*z - y*w), 2 * (y*z + x*w), 1 - 2 * (x*x + y*y)],
    ])


def separating_gap(pose, axes, center, half_size, plate_rotation):
    body_rotation = rotation(pose[3:])
    tests = np.array([
        *plate_rotation.T, *body_rotation.T,
        *[np.cross(a, b) for a in plate_rotation.T for b in body_rotation.T],
    ])
    norms = np.linalg.norm(tests, axis=1)
    tests = tests[norms > 1e-10] / norms[norms > 1e-10, None]
    return float(np.max(
        np.abs(tests @ (np.array(pose[:3]) - center))
        - np.abs(tests @ plate_rotation) @ half_size
        - np.abs(tests @ body_rotation) @ axes
    ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--half-thickness", type=float, choices=(.006, .010), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    normal = np.array([math.sin(.25), 0, math.cos(.25)])
    plate_rotation = np.array([[math.cos(.25), 0, -math.sin(.25)], [0, 1, 0], normal]).T
    center = np.array([.48, 0, .475])
    proposed_center = center - normal * (args.half_thickness - .002)
    proposed_half_size = np.array([.14, .27, args.half_thickness])
    result = {
        "method": "15-axis box separation at stored poses. Negative gaps indicate overlap. No modified physics ran.",
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "old_center_m": center.tolist(),
        "proposed_center_m": proposed_center.tolist(),
        "proposed_half_size_m": proposed_half_size.tolist(),
        "preserved_top_center_m": (proposed_center + normal * args.half_thickness).tolist(),
        "reject_clearance": [],
    }
    for path in sorted(args.traces.glob("reject-seed-*-reuse-*.json.gz")):
        raw = gzip.decompress(path.read_bytes())
        case = json.loads(raw)
        old_gaps, new_gaps, added = [], [], []
        for sample in case["trajectory"] + case["continuation"]:
            if not .32 < sample["pose"][0] < .64:
                continue
            old = separating_gap(sample["pose"], case["axes_m"], center, [.14, .27, .002], plate_rotation)
            new = separating_gap(sample["pose"], case["axes_m"], proposed_center, proposed_half_size, plate_rotation)
            old_gaps.append(old)
            new_gaps.append(new)
            if new <= 0 < old:
                added.append({"time_s": sample["time_s"], "position_m": sample["pose"][:3]})
        result["reject_clearance"].append({
            "source": path.name, "uncompressed_sha256": hashlib.sha256(raw).hexdigest(),
            "seed": case["seed"], "reuse": case["reuse"],
            "minimum_old_separating_gap_m": min(old_gaps),
            "minimum_proposed_separating_gap_m": min(new_gaps),
            "new_overlap_steps": len(added),
            "first_new_overlap": added[0] if added else None,
            "last_new_overlap": added[-1] if added else None,
        })
    assert len(result["reject_clearance"]) == 8
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
