# Overdue collection evidence

The two compressed traces reproduce seeds 17 and 31 through 5.5 simulated seconds.
They preserve the original feed through four seconds and continue the same feed afterward.
Both runs use application geometry commit `696e36a` without changes.
The shared runtime lock protects each run separately.

`overdue-summary.json` contains the corrected analysis.
`overdue-summary-attempt-1.json` is an invalid earlier analysis, preserved for audit only.
That earlier analysis incorrectly applies capsule geometry to the Stone box and aggregates forces across two objects.
It also labels an observation timestamp without its separate solve timestamp.
Do not use that earlier analysis for conclusions.

`runner.py` records the native traces.
`summary-runner.py` analyzes the traces without simulation.
`clearance-runner.py` evaluates proposed splitter boxes against stored Stone poses without simulation.
The verified clearance files record script and input hashes.
The earlier clearance files preserve matching calculations made before the durable script existed.

The 6 mm half-thickness is a pending proposal.
The 10 mm half-thickness was rejected during calculation because it affects more saved Reject paths.
Neither proposal was implemented or simulated when this evidence was captured.

`uncompressed-sha256.json` verifies each original trace after gzip decompression.
The trace metadata records the executed model, preset, runner, and application source hashes.
The corrected summary records its own script and input hashes.
