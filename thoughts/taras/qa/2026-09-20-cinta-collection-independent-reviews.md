# Independent collection reviews

## Scorer: Spec

Reviewer: `collection_scorer_spec_review`, GPT-5.6 Sol, high effort.
Scope: production scorer and duration changes through `0f4dc05`.
Final verdict: clean.

The reviewer confirmed positive named-bin contact, one outcome, one retirement, and removal of the early height and retirement rules.
The reviewer confirmed ground and bounded downstream Spill behavior, shared duration use, and the sixteen preserved diagnostic cases.
The review required restoration of the existing lateral guard and a fresh test beyond the old strict cutoff.
Both findings were resolved before the scorer commit.

The review records one integration dependency outside this branch's ownership.
The Engine owner must copy `Bean.last_quat` into retained object history.
The coordinator accepted that dependency and owns its integration.

## Scorer: Standards

Reviewer: `collection_scorer_standards_review`, GPT-5.6 Terra, high effort.
Final verdict: pass.

The first review rejected anonymous selection of the last wall by geometry properties.
The revised implementation names both walls and derives the escape boundary from their exterior coordinates.
The reviewer found no remaining standards issue.

## Exact four-box candidate: static Spec

Reviewer: `collection_scorer_spec_review`, GPT-5.6 Sol, high effort.
Scope: four geometry lines after `0f4dc05`.
Final static verdict: clean.

The reviewer verified every authorized center and half-size.
The reviewer confirmed unchanged splitter, widths, friction, force, model, and lead.
This verdict covers source conformance only.
It does not establish physical retention or runtime acceptance.

## Exact four-box candidate: Standards

Reviewer: `collection_scorer_standards_review`, GPT-5.6 Terra, high effort.
Final verdict: pass.

The reviewer verified that the diff changes only four named colliders.
The reviewer accepted the use of `L.split_z` for the raised Accept surfaces.
The reviewer confirmed unchanged unrelated settings and a clean whitespace check.

## Physical validation remains separate

The first exact geometry candidate emits eight correct Accept and eight correct Reject events.
Its unabsorbed continuation retains all eight Keep objects and only four Reject objects.
The other four Reject objects penetrate the thin floor and reach the ground.
This failed physical check overrides the clean static reviews for geometry acceptance.
The scorer verdict remains accepted independently.

## Revised thickness: Standards

Reviewer: `collection_scorer_standards_review`, GPT-5.6 Terra, high effort.
Final verdict: pass.

The reviewer compared the revision with `0f4dc05` and the preserved failed candidate.
Only the Reject floor's vertical center and half-height differ from Candidate 1.
The other three geometry changes match the preserved source.
The complete application diff still contains only four collider lines.
The whitespace check passes.

## Revised thickness: Spec

Reviewer: `collection_scorer_spec_review`, GPT-5.6 Sol, high effort.
Final verdict: pass, with no actionable finding.

The reviewer verified the exact four authorized boxes and every frozen setting.
The reviewer inspected all sixteen executed Stone records and verified their source hashes.
Every expected route, first named contact, and stable terminal support agrees.
Every case emits one outcome and retires once.
No continuation contains ground contact.
Maximum terminal speed is 8.13e-6 m/s.
Maximum final-window displacement is 2.10e-7 m.
The direct impact velocities and effective solver reference match the reported values.

This independent physical review covers isolated Stone only.
The broader all-class and feed measurements are reported separately.
## Bounded continuation Spec review

The independent Spec reviewer examined both completed overdue traces and the diagnostic runner.
The reviewer found no observer defect that explains the unresolved objects.
All target samples match the original feed records.
Native force timestamps correctly refer to the pre-integration solve.

Stone 319 and Good 353 have ordinary friction-supported contact on the splitter top.
Good 353 continues slow translation and rotation.
Good 841 straddles the plate and receives opposing forces near 1.4 N each.
Final support comes from the splitter, with zero applied actuator force.

The reviewer supports downward thickness as a candidate for the straddling mechanism only.
The proposed center shift preserves the exact top plane, slope, and rectangular boundary.
The reviewer explicitly rejects treating that change as a complete feed correction.
It cannot release the two slow objects through a changed top surface because that surface remains fixed.
Reject routes require regression checks because the added underside occupies previously open space.
The coordinator must approve any splitter edit before implementation.

## Diagnostic Standards review

The Standards reviewer found two meaningful validation defects and several evidence metadata gaps.
The route validator now returns failure for any failed Stone collection gate, including runs without the unabsorbed observer.
The clearance script now explicitly rejects an incomplete set of eight source routes.
It no longer relies on assertions that optimized Python can disable.

Future route traces include both geom identifiers and the target geom identifier alongside raw contact normals.
Future overdue traces include the profile source hash and use structured error records consistently.
The corrected derived summary retains separate solve and observation timestamps for its contact groups.
It derives splitter face offsets from the geometry stored in each trace.
The summary compares force and weight per object, with separate signed and unsigned contact-force totals.
It applies capsule geometry only to the two Good objects.

All four diagnostic scripts pass syntax compilation.
The reviewer confirmed the final two summary corrections after the other fixes.
Saved executed runners remain unchanged beside their raw traces.
Metadata corrections do not justify repeating completed physical runs.

## Candidate 4: final Spec

Reviewer: `collection_scorer_spec_review`, GPT-5.6 Sol, high effort.
Final verdict: not accepted.

The source exactly matches the authorized underside-preserving splitter and explicit contact attributes.
All sixteen Stone routes retain their expected support.
All 80 isolated class cases resolve, with 78 outcomes matching class policy.
The three formerly stuck samples resolve within 0.653 seconds, and opposing splitter contacts disappear.
The two small Good-object force differences remain disclosed.

The unchanged mixed-feed Keep-loss gate fails.
Keep loss rises from 4.0480% to 5.4205%, an increase of 1.3725 percentage points.
The result exceeds the limit by 0.3725 percentage points.
This failure prevents acceptance despite the targeted physical corrections.

The reviewer distinguishes late resolutions from late controller decisions.
There are zero late resolutions.
The legacy baseline and Candidate 4 each contain one late controller decision.
The final report uses the precise resolution wording.

The legacy baseline uses different, invalid outcome semantics.
The baseline performance measurements also precede the final candidate runs.
These limitations prevent assigning the aggregate quality regression solely to geometry.
All 57 focused tests pass.
The test log does not independently record the parent process's lock acquisition.
The recorded invocation acquires the shared lock before starting the test process.

## Candidate 4: final Standards

Reviewer: `overdue_diagnostic_standards`, GPT-5.6 Terra, high effort.
Final verdict: pass after one diagnostic fix.

The reviewer confirms minimal application scope, unchanged frozen settings, and correctly isolated observers.
The aggregate summary uses summed numerators and their matching denominators.
All eight raw input hashes and the executed source identities are preserved.
The summary correctly reports Keep loss as the sole failed aggregate gate.

The initial review identified missing structured artifacts when the feed diagnostic fails.
The future runner now records construction, execution, collection, and close failures with available source hashes.
It retains both errors when execution and close fail together.
Explicit guards replace assertions and verify the exact `400/48/20/20` pool.
Existing outputs cannot be overwritten.

Three fake-Engine checks cover construction failure, execution failure, and simultaneous execution and close failures.
Each check also confirms that an existing output remains unchanged.
Those checks import no Engine or MuJoCo and execute no simulation.
Syntax compilation passes.
The executed Candidate 4 runner remains archived unchanged, with its original hash matching all four raw feeds.
The future diagnostic version has a different hash and was not used to repeat those feeds.

The reviewer withdrew an initial finding about the old top-preserving calculation.
That script intentionally preserves Candidate 2 diagnosis and the historical Candidate 3 proposal.
Changing its geometry would falsify the historical analysis.
Candidate 4 clearance calculations remain separate in `splitter-combined-proposal`.
