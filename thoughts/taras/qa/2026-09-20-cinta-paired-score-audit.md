# Paired score audit

The same current trajectories score 95.72% under the old crossing rule and 74.77% under native collector contact.
The 20.95 percentage-point gap comes from score semantics within this run.
It does not measure the separate effect of historical physics changes.

## Run identity

- Source: `c95a10a78a568a9580e54b1a18bc27bd9e64f737`.
- Image: `sha256:4bf6d623015cc92655d880a3563e8904a5467a082034fb8e3f14d19dccea120a`.
- Initial model: `d793e25a3662585eda545cbe0dc84796d9fdd2e0787bdd89a10bfb441ed861ad`.
- Observer commit: `1608056`.
- Seed: 8. Duration: 16 simulated seconds. Requested rate: 500/s.
- Two CPUs, 2 GiB memory, no network, no published ports, read-only image, separate state mounts.
- Runtime: 221.87 wall seconds. Exit status: 0. Source hashes matched before and after execution.
- Local port 8899 and production state remained untouched.

Exact approved command:

```sh
ssh hackspain 'sh /srv/hackspain-coffee/diagnostics/c95a10a-shadow16s-attempt1/input/cinta_shadow_score_remote.sh > /srv/hackspain-coffee/diagnostics/c95a10a-shadow16s-attempt1/output/runner.log 2>&1'
```

The frozen shell script and manifest are in `evidence/`.
The remote files remain under `/srv/hackspain-coffee/diagnostics/c95a10a-shadow16s-attempt1`.

## Same-cohort scores

Both columns use the same 4,902 objects older than the 1.1-second settling interval.
The cohort includes initial warmup, matching the live rolling score at this time.

| Metric | Old crossing rule | Native collection |
|---|---:|---:|
| Accuracy | 4,692/4,902 = 95.72% | 3,665/4,902 = 74.77% |
| Reject capture | 721/807 = 89.34% | 378/807 = 46.84% |
| Keep loss | 121/4,095 = 2.95% | 528/4,095 = 12.89% |
| Spill | 4/4,902 = 0.08% | 606/4,902 = 12.36% |
| Unresolved | 5/4,902 = 0.10% | 316/4,902 = 6.45% |

The outcome labels disagree for 1,155 objects.
Old successes become native wrong or unresolved outcomes for 1,063 objects.
The reverse happens for 36 objects. Their net difference is 1,027 correct outcomes.

| Old label | Native Accept | Native Reject | Native Spill | Native unresolved |
|---|---:|---:|---:|---:|
| Accept | 3,299 | 2 | 470 | 280 |
| Reject | 230 | 444 | 132 | 36 |
| Spill | 0 | 0 | 4 | 0 |
| Unresolved | 0 | 5 | 0 | 0 |

Native failures comprise 606 spills, 315 wrong-bin outcomes, and 316 unresolved objects.
Of the spills, 470 have final positions beyond the furthest end-wall exterior.
The remaining 136 have final positions near the ground.
These rounded positions identify regions. They do not establish each triggering contact or escape predicate.

## Pool pressure and physical location

The run admitted 5,066 objects and recorded 2,934 starved requests, totaling 8,000 completed feed attempts.
Admission averaged 316.63/s. Admission during the final four seconds averaged 177.25/s.
Placement retries are excluded from the attempted count.

Peak occupancy was 427. Final occupancy was 423, including all 400 ellipsoid slots.
At the end, 346 active objects already met an old retirement rule.
This count cannot predict historical throughput because earlier recycling changes subsequent dynamics.

There were 316 overdue objects:

- 16 aged between 1.1 and 2 seconds.
- 52 aged between 2 and 5 seconds.
- 248 aged above 5 seconds.
- The oldest was UID 1, aged 15.997 seconds.

Positive native contacts locate 315 overdue objects at collector end walls:

| Contact surface | Overdue objects | Median penetration | Desired Accept / Reject |
|---|---:|---:|---:|
| `bin_accept_end` | 279 | 2.46 mm | 270 / 9 |
| `bin_reject_end` | 36 | 2.30 mm | 10 / 26 |
| `splitter` | 1 | 0.0022 mm | 0 / 1 |

Three Accept-wall objects also contact other objects.
The oldest object's center is at x=0.75983, inside the 6 mm Accept end wall.
UID 548 has simultaneous opposing x normals against the same Reject end wall.
This snapshot supports a thin-wall contact problem. It cannot establish motion oscillation over time.

## Recommended bounded experiment

Keep native collector-floor scoring.
Test 30 mm end walls by moving only their outer faces outward.
Preserve inner faces, vertical extents, floors, splitter, contact parameters, force, timing, model, and policy.

The two centers move from x=0.760/0.520 to x=0.772/0.532.
The existing escape boundary moves outward by 24 mm because it follows the outer wall.
Report that movement separately. Longer survival is not collection.

Replay captured Accept UID 1 and Reject UID 44, then repeat this seed-8 run for 16 seconds.
Require zero end-wall-held objects older than five seconds and fewer starved requests than 2,934.
Require no regression in native accuracy, capture, or Keep loss. Preserve existing release gates.
Also require a substantial decrease in escaped spills before accepting the candidate.

This experiment addresses retention. It does not promise to fix the 606 spills or 315 wrong-bin outcomes.
Never convert an old predicted success or an end-wall contact into actual collection.

## Evidence and verification

`evidence/c95a10a-shadow16s-attempt1/run.json.gz` contains the complete raw observer output.
Its decompressed SHA256 is `230a2acd89f5bf53973c911cf9788e7b51c3dcfb6a5330988f690a116e22aac6`.
`inspection.json` contains an independent recomputation and contact attribution.
`runner.log` contains every half-second sample and the successful completion record.
`runtime-inspection.txt` records the live container limits and mounts.

The independent checker confirmed every score numerator and denominator against raw rows and the Engine rolling score.
It also confirmed unique UIDs and conservation of admitted, resolved, and active objects.

```sh
python3 thoughts/taras/qa/evidence/cinta_shadow_score_inspect.py thoughts/taras/qa/evidence/c95a10a-shadow16s-attempt1/run.json.gz
git diff --check
```

Only one continuous diagnostic ran. No geometry, policy, model, or production scorer changed during this audit.
