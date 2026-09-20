# Unverified end-wall candidate

Status: UNVERIFIED. No candidate physics run occurred before the release cutoff.
Production remains unchanged. Native collector-floor scoring remains unchanged.

Geometry commit: `07490d0afeff7a77ef08d336df6593366b91a67d`.
Branch: `codex/cinta-end-wall-experiment`.
The application diff changes two lines in `sim/coffee_sorter/scene.py`.

Both collector end walls grow from 6 mm to 30 mm total x thickness.
Their centers move outward by 12 mm. Their inner faces and vertical extents remain fixed.
The escape boundary moves outward by 24 mm because it follows the outer wall.

Thirty millimeters exceeds the observed 2.3-2.5 mm median wall penetration and the roughly 10 mm nominal bean length.
The thicker wall places its center farther from the inward contact face.
This is a test choice, not an established optimum or verified improvement.

The baseline has 315 overdue objects contacting these walls, including simultaneous opposing contact normals for UID 548.
See `2026-09-20-cinta-paired-score-audit.md` for complete baseline evidence.

## Continuation

This command runs one seed-8 diagnostic for 16 simulated seconds on `hackspain`:

```sh
python3 thoughts/taras/qa/evidence/cinta_end_wall_continue.py
```

It uses the accepted immutable image with two read-only overlays: the committed candidate scene and its source revision.
It verifies all source, model, preset, runner, and transferred-file hashes.
It uses two CPUs, no network, no ports, and separate input, output, and lock mounts.
It refuses to reuse its remote run directory.
The command itself has only passed syntax and static checks. It has not executed.

The image remains identified as baseline `c95a10a`.
The expected manifest explicitly identifies candidate source `07490d0` and both overlays.
Only the scene hash changes among the checked application files.
The model remains `d793e25a3662585eda545cbe0dc84796d9fdd2e0787bdd89a10bfb441ed861ad`.
Policy, preset, and scorer remain unchanged.

Captured-case checks for baseline UIDs 1 and 44 remain required.
They must preserve captured initial states and resolve through native floor contact or a real Spill condition.
The continuation command runs only the continuous diagnostic. It does not perform those case checks.

Acceptance requires substantial reductions in persistent wall retention and escaped spills.
Require zero wall-held objects older than five seconds and fewer than 2,934 starved requests.
Require no regression in native accuracy, Reject capture, or Keep loss relative to the same-seed baseline.
Keep all existing release gates.

Any release needs a rebuilt image and refreshed evaluation and provenance artifacts for the candidate source.
Existing model bytes permit a controlled geometry comparison. They do not certify a refreshed training result.
Generated-catalog training remains a separate CI task.
