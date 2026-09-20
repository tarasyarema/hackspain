# Collection geometry validation

Candidate 4 corrects the observed collection failures but fails the unchanged mixed-feed Keep-loss gate.
Keep loss increases from 4.0480% to 5.4205%, exceeding the allowed one-percentage-point increase.
The candidate is not accepted for release.

All sixteen Stone routes retain their expected support, and all 80 isolated class cases resolve.
The three previously stuck physical samples resolve before the 1.1-second deadline.
The four feed runs contain no overdue objects, late resolutions, or pool starvation.
All 57 focused tests pass.

The current scene SHA256 is `116fbb854a877604308a3fbbc924c4b0733035cd5fe6e2ffd265ebf75418ce5b`.
Source commit `733bd15` extends the collector geometry in commit `696e36a68be7ec10c696d02aefbeae77791ffdf5`.
The following sections preserve each failed candidate and the evidence that motivated its successor.

## Candidate 1: failed retention

The first candidate exactly implements the four authorized box changes.
It emits eight Accept events for Keep and eight Reject events for Reject.
Every object resolves and retires once.
No object emits Spill or remains unresolved in the absorbing simulation.

The required unabsorbed continuation changes that conclusion.
All eight Keep objects retain Accept support.
Only four Reject objects retain Reject support.
Reject cases 7/1, 8/0, 8/1, and 9/1 reach the ground.

Each continuation copies native `MjData` immediately before retirement.
It advances 1.5 simulated seconds with the same model and no actuator force.
The observer preserves the original data and reproduces belt and roller updates.
Terminal support requires contact during 90% of the final 100 ms.
It also requires speed below 0.01 m/s and displacement below 1 mm.

The four failed objects penetrate the Reject floor while inside its footprint.
The floor spans z=0.177 through 0.183 m, with a midplane at z=0.180 m.
Their centers cross the midplane 2 through 4 ms after the contact solve timestamp.
This corresponds to 1 through 3 ms after the saved post-step observation.
Their x positions remain between 0.604 and 0.756 m.
Their absolute y positions remain below 0.150 m.
Those positions lie inside the floor footprint.
Their post-contact downward speeds remain between 1.86 and 2.20 m/s.

The observer stores contact solve pose and post-step pose separately.
Those poses must not be treated as identical.
The final ground contact covers all 100 terminal samples for each failed object.

The unchanged bean geometry has priority one and `solref="0.006 1"`.
The static floor has priority zero.
This gives the bean contact a 6 ms response time constant.

The failed candidate remains preserved under `evidence/2026-09-20-cinta-collection/geometry-stone-attempt-1`.
The directory contains source, runner, log, summary, and lossless compressed object traces.
Its manifest records each original JSON hash.

## Downward thickness proposal

The proposal keeps the Reject floor top at z=0.183 m.
Its center becomes `(split_x+0.20, 0, belt_z-0.447)`.
Its half-size becomes `(0.26, belt_w/2+0.02, 0.030)`.
Default vertical bounds become 0.123 through 0.183 m.
The footprint and other three boxes remain unchanged.

The recorded normal-force impulse and mass imply incoming downward speeds up to 3.184 m/s.
This incoming speed is inferred, since Candidate 1 did not save velocity before its contact step.
Travel over one 6 ms response period is approximately 19.1 mm.
The worst recorded initial penetration adds 2.9 mm.
The proposed 30 mm top-to-midplane distance leaves approximately 8 mm against that estimate.
This estimate does not guarantee solver retention.
The same sixteen unabsorbed continuations must verify the proposal before broader validation.

No timestep, force, friction, solver, or collection-semantic change is proposed.

## Candidate 2: sixteen routes pass

The coordinator approved the 30 mm half-height correction.
The implementation changes only the Reject floor's vertical center and half-height relative to Candidate 1.
Its top remains at 0.183 m.

All eight Keep cases produce Accept and retain stable Accept support.
All eight Reject cases produce Reject and retain stable Reject support.
Every case emits one outcome and retires once.
No case spills, remains unresolved, or skips pooled reuse.
The maximum collection age is 0.645 seconds.

Every continuation has 100% named-bin contact during the final 100 ms.
All speed, displacement, zero-force, roller-update, and original-data preservation checks pass.
The validator now returns nonzero if route and terminal-support agreement fails.

Candidate 2 records velocity immediately before the contact step.
Direct Reject impact velocities range from -3.183573 to -2.970766 m/s vertically.
The native contact's effective solver reference is `(0.006, 1.0)` in every Reject case.
These measurements confirm the inferred velocity range and time constant used for the thickness proposal.

The exact source and complete traces are preserved under `evidence/2026-09-20-cinta-collection/geometry-stone-attempt-2`.
The saved scene and runner hashes match the identities recorded during execution.
Broader class and paired feed validation follows this passing sixteen-case check.

## Candidate 2: all-class validation

The same four seeds and two sequential reuses cover all ten built-in classes.
All 80 objects resolve without Spill or skipped reuse.
The maximum resolution age is 0.610 seconds, below the unchanged 1.1-second deadline.
Every object emits one outcome and retires once.

The frozen classifier predicts 78 of 80 classes correctly.
It predicts one Good object as Insect and rejects it.
It predicts one Faded object as Good and accepts it.
The other 78 physical outcomes match the class policy.
This balanced isolated sample does not measure production feed accuracy.
These all-class runs verify absorbing collection, rather than unabsorbed terminal support.

All 57 focused tests pass with Candidate 2 geometry.
Both independent geometry reviews pass.
The Candidate 2 `scene.py` SHA256 is `c4f945fcf1047c505c8e9850151c5e26d01386639f5d02dcccfa2c2614a72e53`.

## Candidate 2: seed-paired feed validation

Seeds 11, 17, 23, and 31 each run for four simulated seconds at 500 objects/s.
Both branches use the frozen model, preset, and 488-slot pool.
Each run holds the shared lock independently.
The common quality cohort spans spawn times 0.8 through 2.9 seconds.

| Measure | Legacy baseline | Revised collection |
| --- | ---: | ---: |
| Admitted objects | 8,000 | 8,000 |
| Pool starvation | 0 | 0 |
| Peak active objects | 261 | 302 |
| Mature cohort objects | 4,200 | 4,200 |
| Reject capture | 563/618, 91.10% | 588/621, 94.69% |
| Keep loss | 145/3,582, 4.05% | 176/3,579, 4.92% |
| Mature cohort Spill | 8 | 1 |
| Mature cohort unresolved | 0 | 1 |
| All objects resolved by endpoint | 7,096 | 6,831 |
| Active objects past deadline | 0 | 3 |
| Summed wall time | 99.937 s | 101.051 s |
| Summed CPU time | 98.010 s | 104.138 s |
| Maximum peak RSS | 307.99 MB | 313.26 MB |

The legacy baseline uses the invalid early scorer.
Its quality numbers provide regression comparisons, rather than proof of a physical accuracy gain.
The same seeds also produce slightly different realized class counts after collection timing changes.
No seed, policy, model, sampling algorithm, or injection mechanism changed.

Aggregate wall cost rises 1.11%, peak memory rises 1.71%, and endpoint resolution count falls 3.73%.
Those measurements remain within the existing 5% limits.
CPU cost rises 6.25% and remains reported separately.
Keep loss rises 0.870 percentage points, within the existing one-point limit.
Spill frequency falls, and pool starvation remains zero.
Per-seed timing varies with host load.
Seeds 23 and 31 use opposite execution orders for their adjacent branch comparisons.

The deadline check has three exceptions.
Seed 17 leaves Stone UID 319 unresolved after 3.361 seconds of age.
Seed 31 leaves Good UIDs 353 and 841 unresolved after 3.293 and 2.317 seconds of age.
Only UID 841 belongs to the post-warmup quality cohort.
No resolved object exceeds the 1.1-second deadline.
The longest completed collection takes 0.819 seconds.
These unresolved exceptions require a physical continuation before geometry acceptance.
The deadline and all operational thresholds remain unchanged.

The complete eight runs and source identities are preserved under `evidence/2026-09-20-cinta-collection/paired-feed`.

## Bounded continuation: three splitter failures

Seeds 17 and 31 reproduce the same four-second feed and continue that feed until 5.5 seconds.
Each run holds the shared simulation lock independently.
All three target samples exactly match their original class, spawn time, mass, axes, and jet-hit count.
The runner records native positive contacts, their solve timestamps, and the separate post-step states.
It changes no physical parameter, collection rule, deadline, or feed behavior.

| Seed / UID | Class | Position at 5.5 s, meters | Final speed | Movement from 4 to 5.5 s |
| --- | --- | --- | ---: | ---: |
| 17 / 319 | Stone | `(0.380018, -0.065896, 0.506147)` | 0.155 mm/s | 0.226 mm |
| 31 / 353 | Good | `(0.537629, -0.139545, 0.464725)` | 3.067 mm/s | 4.598 mm |
| 31 / 841 | Good | `(0.354976, 0.231183, 0.506923)` | 0.063 mm/s | 0.089 mm |

Every target contacts the named `splitter` throughout the final 100 milliseconds.
No other collider supports a target at either saved endpoint.
All three have zero applied actuator force at those endpoints.
No target reaches a bin or emits an outcome during the continuation.
This bounded observation proves persistence through 5.5 seconds, not permanent immobility.

Stone 319 and Good 353 have ordinary top-surface support.
Their final normal forces total 0.007396 and 0.002340 N respectively.
Each total matches its weight component normal to the slope.
Their tangential forces approximately balance gravity down the slope.
The effective sliding friction is 0.8, while `tan(0.25)` is approximately 0.255.
The contact model therefore permits friction-supported equilibrium.
Good 353 continues slow movement and rotation, so it must remain distinct from the straddled object.

Good 841 contacts both splitter faces from the solve at 2.138 seconds onward.
Its final opposing normal forces are 1.399120 and 1.397005 N.
Each force exceeds its 0.002182 N weight by approximately 640 times.
The two penetrations remain approximately 1.187 mm.
The difference between those opposing forces balances gravity normal to the plate.
Raw contact normals reverse with geom ordering, which the analysis accounts for.

Good 841 uses the existing capsule collision approximation.
Its radius is 2.274 mm, and its central segment is 6.173 mm long.
Its complete maximum span is 10.720 mm.
At four seconds, its segment endpoints project to approximately +3.086 and -3.087 mm from the splitter midplane.
The current splitter faces lie at +2 and -2 mm.
This native straddling state explains its large opposing contact forces.

The independent Spec review confirms both mechanisms and the observer's timestamp semantics.
It does not claim that thickness corrects slow movement on the preserved top surface.
Complete traces, source hashes, logs, and the runner remain under `evidence/2026-09-20-cinta-collection/overdue-attempt-1`.

## Candidate 3: original thickness proposal

Change only the splitter's local normal half-thickness from 2 to 6 mm.
Shift its center by `-0.004 * (sin(0.25), 0, cos(0.25))` meters.
Keep its rotation and tangential dimensions unchanged.
This preserves the exact top plane and its rectangular boundary.
The default center becomes `(0.479010384163, 0, 0.471124350313)` meters.
The half-size becomes `(0.14, 0.27, 0.006)` meters.
Use sufficient decimal precision when generating MJCF to preserve that working surface.

The proposed total thickness is 12 mm, exceeding Good 841's complete 10.720 mm capsule span.
That dimension targets the observed two-face straddling mechanism.
It is a candidate requiring native validation, not a guarantee of solver retention.
The change leaves both slow objects' top support plane and contact parameters unchanged.
It therefore cannot establish complete feed readiness by itself.

The added underside changes the lower route's clearance.
A static 15-axis box test compares the proposed splitter with saved Stone poses.
It predicts added overlap for Reject seed 8/reuse 1 and longer overlap for seed 8/reuse 0.
The other six saved routes remain separated at their sampled poses.
Seed 7/reuse 1 has the smallest positive separating gap, approximately 0.190 mm.
The calculation uses actual oriented Stone boxes, rather than only center positions.
It does not predict the changed dynamic trajectories or contacts between sampled times.
The saved trajectories use the same original splitter and precede collection-floor changes near the implicated leading-edge contacts.

A 20 mm total thickness calculation affected five routes, so the proposal uses the narrower 12 mm candidate.
Neither calculated geometry has been implemented or simulated.
The calculation scripts and both results remain evidence, including the rejected wider candidate.

After explicit approval, all sixteen native and unabsorbed Stone checks must pass before broader runs.
Any persistent slow object still fails the physical collection gate.
No solver, friction, air, deadline, or outcome-rule change forms part of this proposal.

## Candidate 3: thicker splitter fails the route gate

The coordinator authorized the proposed 12 mm total thickness with the exact top surface preserved.
The candidate changes only the splitter center and normal half-thickness.
It preserves all Candidate 2 collectors and contact parameters.
The generated shifted coordinates use twelve decimal places.
Its scene SHA256 is `99a54cd548b29dc8f7612c081d04aeb65b0af99cc48bbd9525c64bfcf15feb9f`.

All sixteen isolated attempts complete, with one outcome and one retirement each.
All eight Keep cases reach Accept and retain stable Accept support.
Seven Reject cases reach Reject and retain stable Reject support.
Reject seed 8/reuse 0 spills, so the validator returns status one.
Broader class and feed validation stop at this failure.

The failed object makes native ground contact at solve time 0.791 seconds.
Its contact-step center is `(0.234055, -0.115167, 0.003193)` meters.
Its incoming velocity is `(-0.334929, 0.007462, -3.134823)` meters per second.
It lands upstream of the Reject floor's start at x=0.28 m.
The ground contact normal force is 0.368359 N.
No named collector contact occurs before Spill.
The runner records the failed object's unabsorbed observation as unavailable because no named collector contact exists.
The other fifteen unabsorbed continuations retain their expected support.

The added underside is the only physical change and was predicted to intersect this saved route.
An upstream deflection at the splitter is therefore the likely cause.
This runner records the native state at retirement, rather than the earlier splitter impulse.
The evidence does not directly measure that impulse.

The exact failed scene, runner, log, summary, and complete traces remain in `evidence/2026-09-20-cinta-collection/geometry-stone-attempt-3`.
The failed splitter change was not committed as application code.

The coordinator requested a bounded contact diagnosis using the same failed seed and physical sample.
That rerun reproduces the exact sample and the same 0.791-second Spill.
Thirteen contact solves occur from 0.453 through 0.465 seconds.
Every splitter contact normal points along its upstream face: `(-0.968912, 0, 0.247404)`.
Velocity changes from `(3.000683, 0.003289, -1.512500)` before contact to `(-0.334929, 0.007462, 0.053427)` meters per second afterward.
Forward velocity first becomes negative after the solve at 0.458 seconds.
The maximum summed normal force is 0.847804 N, and the deepest penetration is 6.052 mm.
These native contacts directly confirm that the splitter causes the upstream reversal.
The diagnostic preserves the original two sequential reuses and introduces no new seed.
Its exact source and trace remain under `evidence/2026-09-20-cinta-collection/geometry-stone-attempt-3-contact`.

## Candidate 4: preserve the underside and change splitter material

The coordinator authorized one combined candidate without further tuning.
It retains 12 mm total thickness and preserves the original underside instead of the original top.
The center becomes `C_original + 0.004 * (sin(0.25), 0, cos(0.25))` meters.
Its default position is `(0.480989615837, 0, 0.478875649687)` meters.
The half-size remains `(0.14, 0.27, 0.006)`, and the slope remains 0.25 radians.
The top moves 8 mm along the normal: 1.979 mm downstream and 7.751 mm upward.
The exact lower rectangle remains unchanged.

Only the splitter receives these explicit contact attributes:

```xml
priority="2" friction="0.10 0.01 0.0005" condim="3"
solref="0.006 1" solimp="0.95 0.99 0.001"
```

The coefficient 0.10 is a simulator material assumption, not a measured material property.
Higher priority makes that coefficient effective instead of the bean's 0.8.
The explicit solver attributes preserve the current effective `condim`, `solref`, and `solimp`.
MuJoCo copies these parameters from the higher-priority geom. [MuJoCo 3.13.0 implementation](https://github.com/google-deepmind/mujoco/blob/3.13.0/src/engine/engine_collision_driver.c#L1635-L1648)

No object property, collector, global solver, air setting, pool size, outcome rule, or deadline changes.
Static overlap checks find no added intersection across the eight saved Reject trajectories.
All eight saved Keep trajectories encounter the raised top earlier.
Those calculations compare stored poses, rather than predicting changed contact dynamics.
The results remain under `evidence/2026-09-20-cinta-collection/splitter-combined-proposal`.

The thicker plate targets the capsule's two-face straddling.
The lower friction targets the ordinary top support, since 0.10 is below `tan(0.25)`.
A slope change would require more than 0.675 radians merely to overcome friction 0.8.
That alternative would substantially move both working surfaces.
The selected material change preserves the established slope and lower route geometry.

The ideal downhill acceleration is 1.477 meters per second squared.
A 280 mm traverse from rest plus the new 20 mm drop takes approximately 0.680 seconds.
Only approximately 0.637 seconds can remain after the original first impact.
The analytic estimate therefore does not certify collection before the deadline.
Retained incoming motion and impact duration require native validation.

Independent Spec and Standards reviews confirm the exact approved source changes.
The source SHA256 is `116fbb854a877604308a3fbbc924c4b0733035cd5fe6e2ffd265ebf75418ce5b`.
All sixteen native and unabsorbed Stone checks pass.
Eight Keep cases reach Accept, and eight Reject cases reach Reject.
Every object resolves once, retires once, and retains its expected terminal support.
The maximum collection age is 0.672 seconds.
Reject seed 8/reuse 0 now reaches Reject at 0.598 seconds.
The full evidence remains under `evidence/2026-09-20-cinta-collection/geometry-stone-attempt-4`.
### Previously stuck physical samples

Both original feed seeds continue to 5.5 seconds with the combined candidate.
All three targets match their original class, mass, axes, spawn time, initial pose, velocity, and angular velocity exactly.
Stone 319 also retains the same pool body.
The two Good samples use different pool bodies with the same recorded physical initial conditions.
No target exhibits opposing splitter-face contacts in the corrected trace.

| Seed / UID | Class policy | Actual collector | Collection age | Original / current pool body |
| --- | --- | --- | ---: | --- |
| 17 / 319 | Reject | Reject | 0.653 s | 471 / 471 |
| 31 / 353 | Accept | Reject | 0.622 s | 349 / 342 |
| 31 / 841 | Accept | Reject | 0.624 s | 132 / 146 |

Stone 319 receives the exact original five-step force history.
Both Good samples retain the original three force-step times.
Their actual controller forces differ by at most `9.60e-8 N` and `1.04e-8 N` respectively.
Those differences are approximately 3.49 and 0.38 parts per million.
A strict assertion of identical force histories fails on those two values.
The physical-sample comparison passes, and no air configuration changes.
The evidence therefore establishes matching physical samples, rather than identical actuation.

Both Good samples retain a shared detection classified as Stick, a scheduled Reject decision, and contact from their associated pulse.
They remain sorting losses because the class policy requires Accept.
The earlier overdue runner did not retain separate anomaly scores.
The required feed validation adds targeted classifier, anomaly, and command evidence without repeating those overdue runs.
Good 353 spawns before the 0.8-second quality warmup boundary.
Good 841 belongs to the measured quality cohort.

Native splitter contacts use effective friction `(0.10, 0.10, 0.01, 0.0005, 0.0005)` and `solref=(0.006, 1)`.
The complete traces and strict comparison failure remain under `evidence/2026-09-20-cinta-collection/overdue-attempt-2`.

### All-class gate

All 80 isolated class cases resolve with one outcome and one retirement each.
No case spills, remains unresolved, or exceeds the 1.1-second deadline.
The maximum collection age is 0.599 seconds.
The same two classifier errors remain: one Good sample goes to Reject, and one Faded sample goes to Accept.
The other 78 outcomes match their class policy.
The complete results remain under `evidence/2026-09-20-cinta-collection/geometry-classes-attempt-2`.

### Mixed-feed gate: Keep loss fails

The final candidate runs the existing seeds 11, 17, 23, and 31 for four seconds each.
The model, preset, 500 objects/s feed, and 488-slot pool remain frozen.
Each run holds the shared simulation lock separately.
The unchanged quality cohort contains spawn times from 0.8 through 2.9 seconds.

| Measure | Legacy baseline | Candidate 4 | Existing gate |
| --- | ---: | ---: | --- |
| Admitted objects | 8,000 | 8,000 | Pass, within 5% |
| Pool starvation | 0 | 0 | Pass, no increase |
| Peak active objects | 261 | 287 | Informational |
| Mature cohort objects | 4,200 | 4,200 | Same cohort duration |
| Reject capture | 563/618, 91.1003% | 591/621, 95.1691% | Pass, no regression |
| Keep loss | 145/3,582, 4.0480% | 194/3,579, 5.4205% | **Fail, +1.3725 percentage points** |
| Mature cohort Spill | 8, 0.1905% | 7, 0.1667% | Pass, below +0.5 percentage points |
| Mature cohort unresolved | 0 | 0 | Pass |
| All objects resolved by endpoint | 7,096 | 6,879 | Pass, -3.0581% |
| Active objects past deadline | 0 | 0 | Pass |
| Resolutions after deadline | 0 | 0 | Pass |
| Maximum collection age | 0.480 s | 0.843 s | Pass, below 1.1 s |
| Summed wall time | 99.937 s | 103.669 s | Pass, +3.7347% |
| Summed CPU time | 98.010 s | 101.763 s | Informational, +3.8288% |
| Maximum peak RSS | 307.99 MB | 308.76 MB | Pass, +0.2500% |

The Keep-loss limit remains a maximum increase of one percentage point.
The measured increase exceeds that limit by 0.3725 percentage points.
Correct collection does not override this failed sorting-quality gate.
No further tuning or broad rerun follows the failure.

The baseline uses the invalid early scorer, so these rates compare different outcome definitions.
They do not prove that the corrected physics improves sorting accuracy.
Collection timing and pool reuse also change the realized class counts under the same seeds.
The candidate retains the exact three physical samples checked separately above.

The performance baseline was measured earlier, rather than in a contemporary paired execution.
The recorded wall and memory measurements meet the numeric limits, but host-load differences limit that comparison.
CPU time remains separate and has no acceptance threshold.

### Good 353 and Good 841: collection succeeds, sorting fails

The final seed-31 run preserves each target's decision probabilities, anomaly score, scheduled commands, and physical pulse attribution.
Both objects have class policy Accept and actual outcome Reject.
Both have `actualReject=true`, `own_pulse_hit=true`, and three jet-hit steps.

| Evidence | Good 353 | Good 841 |
| --- | --- | --- |
| Shared detection targets | Good 343 and Good 353 | Good 841 and Faded 843 |
| Track | 346 | 835 |
| Predicted class | Stick | Stick |
| Stick probability | 0.9999724174 | 0.9999917118 |
| Reject probability | 0.9999904827 | 0.9999989092 |
| Reject threshold | 0.8 | 0.8 |
| Anomaly score | 146.9074396 | 199.5965061 |
| Anomaly threshold | 14.9606219 | 14.9606219 |
| Anomaly enabled and triggered | Yes | Yes |
| Scheduled / late | Yes / no | Yes / no |
| Nominal pulse duration | 2.4 ms | 2.4 ms |
| Command interval | 1.0713564254 to 1.0747564254 s | 2.0493999265 to 2.0527999265 s |
| Nozzles | 12 and 11 | 61 and 62 |
| Command force per nozzle | 0.0275085128 N | 0.0275074519 N |
| Observed jet-hit step times | 1.073, 1.074, 1.075 s | 2.051, 2.052, 2.053 s |
| Quality cohort | Excluded, spawn 0.707 s | Included, spawn 1.683 s |

Both shared detections trigger the class threshold and the anomaly threshold.
The evidence therefore does not isolate either trigger as the sole cause.
The shared detections also prevent treating either prediction as an isolated-object classification result.
Good 353 is an observed loss outside the quality cohort.
Good 841 contributes to the reported 194 Keep losses.
The earlier strict force-history comparison still fails on the two small differences reported above.

### Final focused checks and preserved evidence

All 57 tests pass across lifecycle, pooled physics, continuous Engine, metrics, and open-set behavior.
The test process holds `/private/tmp/hackspain-coffee-runtime.lock` for the complete invocation.
No model, reserved seed, policy, air setting, global solver, or deadline changes during validation.

The final evidence directory is `evidence/2026-09-20-cinta-collection/candidate4-feed`.
It contains four compressed raw runs, logs, the exact scene and runner, the aggregate summary, and the focused-test log.
Its manifest records the uncompressed hashes.
The four baseline inputs remain in the earlier `paired-feed` directory.
The aggregate summary records all eight input hashes and both comparison limitations.
Separate final Spec and Standards findings are recorded in `2026-09-20-cinta-collection-independent-reviews.md`.
Standards review improved failure recording in the future diagnostic runner after the successful runs.
The archived executed runner retains its original hash and remains the source for this evidence.

No tested replacement candidate passes every unchanged release gate.
Candidate 1 fails floor retention, Candidate 2 leaves overdue objects, Candidate 3 fails a Stone route, and Candidate 4 fails Keep loss.

## Existing-trace audit and later work

This audit uses existing traces only and performs no simulation.
It matches records within each seed by exact class, spawn time, mass, and axes.
Those fields identify samples but do not establish identical initial pose or actuation for every feed object.

| Keep comparison | Matched samples | New losses | Persistent losses | Recovered losses | Net additional losses |
| --- | ---: | ---: | ---: | ---: | ---: |
| Legacy baseline to Candidate 4 | 3,174 | 66 | 111 | 17 | 49 |
| Candidate 2 to Candidate 4 | 3,579 | 33 | 161 | 15 | 18 |

The legacy comparison also contains 408 unmatched baseline Keep samples and 405 unmatched Candidate 4 Keep samples.
Each unmatched group contributes 17 losses, so matched transitions explain the full increase of 49 losses.
The 66 new matched losses comprise 61 Accept-to-Reject and five Accept-to-Spill transitions.
The invalid baseline scorer and missing contact records prevent direct contact attribution for that comparison.

Candidate 2 provides a narrower comparison because every measured Keep sample matches and both candidates use the accepted collection scorer.
The 33 new losses comprise 26 Accept-to-Reject, six Accept-to-Spill, and one Unresolved-to-Reject transition.
All 33 receive physical jet contact under Candidate 4.
Nine retain the same hit count, while 24 have different hit counts.
Twenty have associated rejection tracks, and thirteen receive only contact from other pulses.

The frozen model still produces different decision streams: Candidate 4 records eleven more Reject decisions than Candidate 2.
Nineteen new losses map to changed, same-numbered track records.
Candidate 2 lacks object-to-track attribution, so matching track numbers cannot establish matching detections.
The evidence cannot assign those nineteen transitions solely to classifier behavior.

Eight transitions have no Candidate 4 rejection association and retain one jet-hit step in both runs.
They provide the strongest evidence of changed physical routing.
Every one previously contacted Accept near z=0.432 through 0.434 m.

| Seed / UID | Candidate 2 | Candidate 4 | Candidate 4 final position, meters |
| --- | --- | --- | --- |
| 11 / 788 | Accept | Reject | `(0.361, 0.022, 0.185)` |
| 11 / 562 | Accept | Ground Spill | `(0.239, -0.167, 0.002)` |
| 17 / 921 | Accept | Ground Spill | `(0.230, 0.107, 0.001)` |
| 17 / 1029 | Accept | Ground Spill | `(0.231, 0.169, 0.004)` |
| 17 / 846 | Accept | Ground Spill | `(0.210, -0.104, 0.001)` |
| 17 / 446 | Accept | Reject | `(0.380, 0.114, 0.185)` |
| 23 / 1384 | Accept | Ground Spill | `(0.240, 0.221, 0.002)` |
| 31 / 899 | Accept | Ground Spill | `(0.207, -0.266, 0.002)` |

The six Spill endpoints lie upstream of the Reject floor's x=0.28 m boundary.
This is consistent with an upstream deflection near the changed splitter.
The raised top is a plausible mechanism, but these feeds did not record its contact normals or incoming velocities.
Equal hit counts also do not prove equal forces or pulse times.
The existing traces cannot separate the 7.75 mm top increase from friction, changed actuation, or unrecorded contact state.

Sorting work stops with Candidate 4 failed and unaccepted.
For later work, first capture matching decisions, forces, initial states, and native splitter contacts for these eight cases.
Use those records to separate physical deflection from decision changes across the 33 transitions before selecting another geometry.
Keep every existing release gate unchanged.
The complete audit and all input hashes remain in `candidate4-feed/keep-loss-audit.json` and `candidate4-feed/keep-loss-audit.md`.
