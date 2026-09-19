# SG90 repeatability investigation and bench test

Use this single-servo sketch for the unknown 9 g unit before connecting it to the sorting mechanism. The repository does **not** establish whether that particular unit is positional or continuous rotation. An SG90 label is not sufficient evidence. The default build is unconfirmed and emits no servo pulses. No physical servo was available during this change.

## What the repository controls

The documented board is an Arduino Uno R3 (ATmega328P). `magnet_arm/magnet_arm.ino` uses Arduino `Servo.h`: D9 base/coffee gate, D10 shoulder, D11 elbow, optional D6 continuous conveyor. The installed program and actual wiring still need checking on the bench.

The coffee path is `sim/line/panel.py` → `Gate.pulse()` in `sim/line/gate.py` → `S base shoulder elbow` through `arduino_link.py` → the serial bridge in `conveyor_button.py` (or direct serial) → `magnet_arm.ino` → `Servo.write(degrees)`. The separate magnet arm controller also sends `S` through `hardware.SerialArduino`. Close all other command owners during a bench run: serial locks serialize bytes, not the intent of multiple panels or scripts.

| Setting | Meaning |
| --- | --- |
| `Gate.pulse(delay_s, dwell_s)` | Seconds until an OPEN command, then scheduled open interval; not a pulse generator or an angle command |
| `gate.settle_ms` | Estimated mechanical travel allowance in milliseconds, used by line timing; not measured settling |
| `TICK_MS = 20` in arm firmware | Trajectory update cadence, with `20 / 1000.0 = 0.020 s` integration step |
| Browser conveyor “run for” | Seconds before JavaScript sends another `C 0` command |
| `S` / `Servo.write()` | Requested nominal position in degrees; no shaft feedback |
| `writeMicroseconds()` in this bench sketch | Requested high-pulse width in microseconds; `1500 us = 1.5 ms` |

No milliseconds/microseconds conversion defect was found in these paths. Their names refer to different quantities. The legacy arm firmware rounds its generated profile to whole degrees. Its default Servo mapping is 544–2400 us, approximately 10.3 us per nominal degree; this is library mapping, not a calibrated shaft-angle relationship. This bench test uses explicit microsecond targets and avoids angle-map rounding.

On the Uno, the established Servo library uses Timer1 compare interrupts and a nominal minimum 20,000 us refresh period. It keeps producing the last commanded pulse independently of the application loop. This is timer-driven interrupt output, not proof of zero jitter or direct hardware PWM. No competing Timer1 user was found in the inspected sketch; adding Timer1 users or PWM on its associated pins can conflict. See the official [Servo interface](https://github.com/arduino-libraries/Servo/blob/master/src/Servo.h), [AVR implementation](https://github.com/arduino-libraries/Servo/blob/master/src/avr/Servo.cpp), and [AVR timer selection](https://github.com/arduino-libraries/Servo/blob/master/src/avr/ServoTimers.h).

## Confirmed software findings

- The gate worker selected an OPEN under its condition lock but sent it after releasing that lock. A manual FLUSH could finish in between, followed by the stale OPEN. Command selection and delivery now share ordering with manual actions. Focused tests force this interleaving.
- Gate motion commands previously ignored non-`ok` replies and recorded the requested state before command success. Rejected commands now surface as errors. Acknowledgement still means command acceptance, not measured movement.
- Line stop previously left scheduled gate work active, and switching to dry mode could suppress the final FLUSH. Stop/dry now disable new classification-driven actuation and cancel/flush scheduled work. Shutdown closes the gate before closing its Arduino link. A flush remains a configured position request, not a hardware emergency stop.
- The previous SG90 guide directed users to arm firmware that boots D9 to 150 degrees and permits the broad default Servo endpoint range. This is unsuitable as an unqualified test for an unknown unit. The new bench path starts without output, requires explicit type configuration, validates a narrow configurable pulse envelope, and never performs a full-range sweep.
- Browser conveyor timing starts before its asynchronous send completes. Browser scheduling, serial latency, and later slider/raw commands can change actual run duration. The repeatability sketch owns timed-motion deadlines on the Uno and rejects overlapping motion commands. The general conveyor panel remains a manual control panel, not a precision rotation test.
- Existing conveyor stop detaches the signal and assumes that stops rotation. That behavior is not proven for this unit. The bench path provides calibrated neutral and explicit signal-disable controls; neither constitutes a guaranteed mechanical emergency stop.

These are confirmed code behaviors and failure modes, **not proof that any one caused the reported SG90 movement**. The multi-axis arm's calibration and general raw protocol are not rewritten by this bench test. Its status `P ... B 0` describes the generated profile, not actual position or settling.

## Configuration and use

Protocol and build instructions are below; identify the unit before enabling a mode. Confirm the pin, board, loaded sketch, supply, and whether the servo has been modified. Manufacturer documentation for the exact unit is preferable. If identification remains uncertain, an unloaded, very small supervised step near nominal center can help distinguish “moves and holds” from “keeps rotating”; stop and remove power immediately if motion is unexpected. Do not force the shaft or use endpoint sweeps to identify it.

Use an external regulated supply suitable for the actual servo, with a common ground to the Uno. The legacy guide's USB-powered arrangement is not a controlled power baseline. Verify voltage at the servo connector during motion; a supply's label alone does not establish transient performance. Arduino's [servo troubleshooting guidance](https://support.arduino.cc/hc/en-us/articles/360017053760-Troubleshoot-servo-motors) discusses external supplies, grounding, and current demand. Do not connect the separate supply's positive output to the USB-powered Uno's 5 V pin.

Initial proposed limits are 1400–1600 us, with test targets at 1450, 1500, and 1550 us and 1000 ms settling. These are conservative starting proposals, **not verified safe endpoints for this unit or linkage**. Remove the load/horn as appropriate and verify each point individually before a repeated run. Configure limits and targets together; expand only from bench evidence. Position here is specified by a target pulse, not a claimed number of shaft degrees. Do not add correction offsets to conceal scatter.

Edit `servo_repeatability_config.h`. Every setting has the prefix `SERVO_REPEATABILITY_`:

| Suffix | Default | Meaning |
| --- | --- | --- |
| `MODE` | `SERVO_MODE_UNCONFIRMED` | Change to `SERVO_MODE_POSITIONAL` or `SERVO_MODE_CONTINUOUS` only after identification |
| `MIN_US`, `MAX_US` | 1400, 1600 | Software-enforced pulse envelope, not measured travel limits |
| `LOW_US`, `TARGET_US`, `HIGH_US` | 1450, 1500, 1550 | Positional test points; target is approached repeatedly from each side |
| `STOP_US` | 1500 | Continuous neutral; must be calibrated for the actual unit |
| `SETTLE_MS` | 1000 | Positional settling interval or continuous neutral dwell |
| `MOTION_MS` | 500 | Continuous test's commanded motion duration |
| `REPETITIONS` | 2 | Repeats per direction group; increase after individual point checks |

Validation requires an envelope inside the library's 544–2400 us representable range, ordered low/target/high (or low/stop/high), settling of 1–60,000 ms, motion of 1–10,000 ms, and 1–10 repetitions. Those maximum bounds are software constraints, not permission to try broad travel or long motion on unverified hardware. The sketch enforces the narrower configured envelope itself: the AVR library's compact `attach(pin, min, max)` offsets cannot represent a 1400–1600 us attachment range correctly. The actual pulse is preloaded before ordinary attachment.

Install Arduino AVR core and the Servo library, then compile from the repository root:

```sh
arduino-cli core install arduino:avr@1.8.8
arduino-cli lib install Servo@1.3.0
arduino-cli compile --fqbn arduino:avr:uno sim/magnet_sorter/firmware/servo_repeatability
```

Upload the configured sketch to the verified Uno using the Arduino IDE or CLI. Uploading replaces the arm program. Open one serial terminal at **115200 baud** with newline line endings. Opening the connection can reset the Uno; wait for `READY`. Boot never starts motion, even with a configured type. Reflash the arm program only when returning to the calibrated multi-actuator setup.

| Command | Behavior |
| --- | --- |
| `P 1500` | Positional: request and hold that pulse target; wait the settling interval before judging movement |
| `C 1500 500` | Continuous: command this pulse for 500 ms, then configured neutral; use to check a candidate neutral before testing speed |
| `T` | Run the configured finite test; repeated low→target then high→target for positional; low/neutral and high/neutral trials for continuous |
| `X` | Cancel active test/motion; positional holds current commanded target, continuous commands configured neutral |
| `D` | Cancel and disable D9 signal; this does not cut servo power or guarantee a mechanical stop |

Examples use proposed defaults; substitute individually verified values. Speed is calibrated by selecting low/high pulse widths around `STOP_US`, not by claiming a fixed RPM. Once a mode is configured, invalid configuration, out-of-envelope requests, malformed lines, and overlapping test/motion commands are rejected. `D` releases positional holding torque where the servo responds that way; account for any load before using it. Remove external servo power if unexpected movement persists.

The Uno owns test timing using rollover-safe `millis()` deadlines. These have millisecond resolution and loop/interrupt latency; they are not exact electrical pulse-duration measurements. Logs prefixed `CMD` report the requested target/pulse, approach group, and settling or motion interval. They are **commands only**, not encoder readings or scope traces. Holding and neutral remain commanded after normal completion. The loop does not detach a positional servo just because the settling interval elapsed.

## Before/after physical procedure

1. **Record the baseline without a new sweep.** Record servo markings/type evidence, wiring, exact flashed sketch/version, control path, target or speed, delay/dwell/settle settings, supply, load, and initial position. Capture the existing known-safe command sequence and corresponding scope/video observations. Avoid reproducing unsafe endpoints merely to obtain a baseline.
2. **Isolate control and power.** Stop the coffee panel, conveyor panel, serial monitors, and other scripts. Use only one serial connection. Disconnect other actuators. Start unloaded with controlled power. Keep a physical way to remove servo power available.
3. **Verify signal first.** Flash the explicit-type bench build only after inspection. Scope D9 relative to servo ground over at least 100 frames at each verified target, both idle and under serial traffic. Record high-time min/max, frame period, jitter, and startup/stop behavior. Software logs cannot supply these measurements.
4. **Positional repeatability.** Confirm low, target, and high individually within the safe envelope. Run repeated low→target approaches, then high→the same target approaches, allowing the full configured settling interval at every step. The same-direction scatter tests repeatability; the difference between direction groups can reveal backlash/hysteresis. A fiducial and fixed camera, protractor, or encoder must measure shaft position. Increase settling if motion remains visible; log the new interval and repeat the same trial.
5. **Continuous rotation.** Calibrate neutral unloaded until no rotation is observed over a specified dwell. Select small clockwise/counterclockwise pulse offsets and a bounded motion duration. Repeat identical timed moves with neutral dwell between them, recording actual angle externally. Supply voltage, load, deadband, temperature, and acceleration can change travel for equal durations. Precise angle requires position feedback.
6. **Change one physical variable at a time.** Repeat under the same supply/load, then with a verified supply and then representative mechanical load. Compare with a known-good servo if available. Retain raw electrical and shaft measurements alongside command logs.

## What still needs physical verification

| Question | Required measurement |
| --- | --- |
| Positional or continuous? | Exact-unit identification plus supervised unloaded behavior; currently unresolved |
| Electrical signal stable? | Scope/logic analyzer at servo connector: high width, period, startup/stop pulses and jitter under traffic |
| Supply stable? | Rail voltage at connector during motion, transient/current capability, wiring drop, common-ground integrity and Uno resets |
| Mechanical repeatability? | External shaft angle after settling, same-direction scatter and opposite-direction bias |
| Load/backlash/deadband/defect? | Unloaded versus loaded trials, small-step response, temperature, gear play, and known-good comparison |

The tests verify command ordering, requested pulse bounds, timing state transitions and error handling in software. Compilation verifies the Uno build. Neither verifies electrical waveform accuracy, actual settling, mechanical position, power adequacy, or the reported symptom on hardware.

Run the hardware-free checks from the repository root:

```sh
sim/magnet_sorter/firmware/servo_repeatability/tests/run_host_tests.sh
bash sim/line/run_tests.sh
```

The first command needs `g++` and executes the real sketch with small Arduino/Servo test doubles in unconfirmed, positional, continuous and invalid-configuration builds. It tests pulse bounds, grouped approaches, holding/neutral, cancellation, busy rejection, malformed lines, serial traffic and `millis()` rollover. These doubles do not simulate the timer ISR or motor. The second command is the existing line suite and expects its Python environment at `sim/.venv`.

The Uno sketch was also compiled in all three modes using Arduino AVR 1.8.8 and Servo 1.3.0. To compile enabled modes without editing the default configuration, add `--build-property compiler.cpp.extra_flags=-DSERVO_REPEATABILITY_MODE=1` for positional or `=2` for continuous to the compile command. Use separate build directories when comparing outputs. Compile success is not permission to flash an unidentified unit.
