# Candidate 4 Keep-loss audit

Generated from existing traces only. No simulation or source edit ran.

## Exact method

- Match within each seed by exact `class`, `spawn_s`, `mass_kg`, and `axes_m`.
- Require unique keys. All inputs satisfy this requirement.
- Use the recorded inclusive cohort boundaries.
- Define Keep as `required_reject=false`.
- Count only Reject and Spill as Keep loss, matching the existing gate.
- Treat Unresolved separately.

## Legacy baseline versus Candidate 4

- All objects: 7,184 matched and 816 were unmatched on each side.
- Mature cohort: 3,697 matched and 503 were unmatched on each side.
- Keep cohort: 3,174 matched. Baseline has 408 unmatched Keep samples. Candidate 4 has 405.
- Matched transitions: 66 entered loss, 111 remained losses, and 17 recovered.
- The 66 new losses comprise 61 Accept-to-Reject and five Accept-to-Spill transitions.
- Unmatched Keep losses are 17 baseline and 17 Candidate 4.
- The matched net increase is 49. Unmatched losses add zero net change.

The baseline scorer retires objects early and records no target attribution. Its transitions cannot establish physical contacts or classifier causes.

## Candidate 2 versus Candidate 4

- All 3,579 Candidate 4 Keep samples match Candidate 2 on the required physical key.
- Thirty-three samples entered the Keep-loss set. This includes 32 Accept transitions and one Unresolved transition.
- The new losses comprise 26 Accept-to-Reject, six Accept-to-Spill, and one Unresolved-to-Reject transition.
- Another 161 samples remained losses, and 15 recovered.
- Net Keep losses increase by 18, from 176 to 194.
- All 33 new losses record nonzero Candidate 4 jet hits.
- Nine retain the same reported hit count. Twenty-four have a changed hit count.

Twenty Candidate 4 samples have associated rejection tracks. Nineteen map to changed same-numbered Candidate 2 track cores.
One sample retains the same-numbered track core, but its jet hits change from zero to four.
Thirteen samples have no Candidate 4 associated rejection. All 13 record hits from other pulses.
Eight of those 13 retain the same hit count. Six change from Accept to Spill.

Candidate 2 lacks `target_uids`. A same-numbered track does not prove identical object association.
The feed runs also omit per-object contact histories for these samples.

## Causal assessment

The traces do not isolate the raised top as the Keep-loss cause.
Decision streams differ. Candidate 4 records 11 more Reject decisions than Candidate 2.
Nineteen new losses also map to changed same-numbered track cores, subject to the target-attribution limit.

Eight transitions provide the strongest physical evidence because association is absent and hit counts match.
Six move from the Accept floor near `z=0.432-0.434 m` to ground Spill near `z=0.001-0.004 m`.
These paths support changed downstream routing. They do not separate top height, friction, or unrecorded initial and contact state.

Separate overdue traces reproduce the exact physical samples for UIDs 319, 353, and 841.
Candidate 4 resolves all three and removes UID 841 opposing contacts.
The overdue claim does not depend on feed track identity.

## Verdict and later work

**No tested candidate passes every unchanged release gate. Candidate 4 remains unaccepted.**

Candidate 4 increases Keep loss by `1.37249065` percentage points against a `1.0` point limit.
The result exceeds the limit by `0.37249065` percentage points.
Current traces do not justify a new candidate design.

If sorting resumes, collect paired object-bound decisions, pulse records, initial states, and splitter contacts for the 33 transitions.
Separate decision-stream changes from downstream physical routing before selecting another geometry.
Keep every existing release gate unchanged.

## Earlier candidates

- Candidate 1 failed native terminal support.
- Candidate 2 passed Keep loss but failed unresolved and deadline gates.
- Candidate 3 failed one Stone route and support case.
- Candidate 4 fails the Keep-loss delta gate.

## Artifacts

- Derived JSON: `keep-loss-audit.json`
- Input and supporting evidence SHA256 values are in the JSON.
