/*
  Bounded one-servo repeatability bench for an Arduino Uno.

  D9 remains low and Servo stays detached at boot. Select POSITIONAL or
  CONTINUOUS in servo_repeatability_config.h only after identifying the unit.
  All pulse widths are commands, not position or speed measurements.

  Exact, newline-terminated commands:
    T                 run the configured finite repeatability test
    P <pulse_us>      positional single-target calibration command
    C <pulse_us> <ms> continuous bounded calibration command
    X                 cancel: positional holds; continuous commands neutral
    D                 disable the D9 signal
*/

#include <Arduino.h>
#include <Servo.h>
#include <stdint.h>
#include <string.h>

#include "servo_repeatability_config.h"

const uint8_t SERVO_PIN = 9;
const uint8_t LINE_CAPACITY = 48;
const uint32_t MAX_SETTLE_MS = 60000UL;
const uint32_t MAX_MOTION_MS = 10000UL;
const uint8_t MAX_REPETITIONS = 10;

enum Operation {
  IDLE,
  POSITIONAL_TEST,
  CONTINUOUS_TEST,
  CONTINUOUS_CALIBRATION
};

enum Step {
  POS_LOW,
  POS_TARGET_FROM_LOW,
  POS_HIGH,
  POS_TARGET_FROM_HIGH,
  CONT_LOW,
  CONT_NEUTRAL_AFTER_LOW,
  CONT_HIGH,
  CONT_NEUTRAL_AFTER_HIGH,
  CONT_CALIBRATION_PULSE
};

Servo servo;
Operation operation = IDLE;
Step step;
uint8_t repetition = 0;
uint16_t commandedPulseUs = 0;
uint32_t deadlineMs = 0;
char line[LINE_CAPACITY];
uint8_t lineLength = 0;
bool discardingLine = false;
bool invalidLine = false;

bool configurationValid() {
  const bool modeValid = SERVO_REPEATABILITY_MODE == SERVO_MODE_POSITIONAL ||
                         SERVO_REPEATABILITY_MODE == SERVO_MODE_CONTINUOUS;
  const bool envelopeValid = SERVO_REPEATABILITY_MIN_US >= MIN_PULSE_WIDTH &&
                             SERVO_REPEATABILITY_MIN_US < SERVO_REPEATABILITY_MAX_US &&
                             SERVO_REPEATABILITY_MAX_US <= MAX_PULSE_WIDTH;
  const bool endpointsValid = SERVO_REPEATABILITY_MIN_US <= SERVO_REPEATABILITY_LOW_US &&
                              SERVO_REPEATABILITY_LOW_US < SERVO_REPEATABILITY_HIGH_US &&
                              SERVO_REPEATABILITY_HIGH_US <= SERVO_REPEATABILITY_MAX_US;
  const bool modePulseValid =
      (SERVO_REPEATABILITY_MODE == SERVO_MODE_POSITIONAL &&
       SERVO_REPEATABILITY_LOW_US < SERVO_REPEATABILITY_TARGET_US &&
       SERVO_REPEATABILITY_TARGET_US < SERVO_REPEATABILITY_HIGH_US) ||
      (SERVO_REPEATABILITY_MODE == SERVO_MODE_CONTINUOUS &&
       SERVO_REPEATABILITY_LOW_US < SERVO_REPEATABILITY_STOP_US &&
       SERVO_REPEATABILITY_STOP_US < SERVO_REPEATABILITY_HIGH_US);
  const bool timingValid = SERVO_REPEATABILITY_SETTLE_MS > 0 &&
                           SERVO_REPEATABILITY_SETTLE_MS <= MAX_SETTLE_MS &&
                           SERVO_REPEATABILITY_MOTION_MS > 0 &&
                           SERVO_REPEATABILITY_MOTION_MS <= MAX_MOTION_MS;
  const bool repetitionsValid = SERVO_REPEATABILITY_REPETITIONS > 0 &&
                                SERVO_REPEATABILITY_REPETITIONS <= MAX_REPETITIONS;
  return modeValid && envelopeValid && endpointsValid && modePulseValid && timingValid &&
         repetitionsValid;
}

bool configuredFor(uint8_t requiredMode) {
  if (SERVO_REPEATABILITY_MODE == SERVO_MODE_UNCONFIRMED) {
    Serial.println(F("ERR MODE_UNCONFIRMED"));
    return false;
  }
  if (SERVO_REPEATABILITY_MODE != requiredMode) {
    Serial.println(F("ERR WRONG_MODE"));
    return false;
  }
  if (!configurationValid()) {
    Serial.println(F("ERR CONFIG_INVALID"));
    return false;
  }
  return true;
}

bool pulseInEnvelope(uint32_t pulseUs) {
  return pulseUs >= SERVO_REPEATABILITY_MIN_US && pulseUs <= SERVO_REPEATABILITY_MAX_US;
}

void commandPulse(uint16_t pulseUs) {
  commandedPulseUs = pulseUs;
  if (!servo.attached()) {
    // Servo retains a pre-attach write, avoiding its default-centre transient.
    servo.writeMicroseconds(pulseUs);
    // The AVR Servo library stores custom attach bounds as int8_t quarter-us offsets;
    // the conservative 1400..1600 envelope would overflow those fields.
    servo.attach(SERVO_PIN);
  } else {
    servo.writeMicroseconds(pulseUs);
  }
}

void printPositionalCommand(uint16_t pulseUs, const __FlashStringHelper *role,
                            const __FlashStringHelper *approach) {
  Serial.print(F("CMD POSITIONAL pulse_us="));
  Serial.print(pulseUs);
  Serial.print(F(" target_us="));
  Serial.print(pulseUs);
  Serial.print(F(" role="));
  Serial.print(role);
  Serial.print(F(" approach="));
  Serial.print(approach);
  Serial.print(F(" settle_ms="));
  Serial.println((unsigned long)SERVO_REPEATABILITY_SETTLE_MS);
}

void setPositionalStep(Step next, uint32_t now) {
  step = next;
  deadlineMs = now + (uint32_t)SERVO_REPEATABILITY_SETTLE_MS;
  if (next == POS_LOW) {
    commandPulse(SERVO_REPEATABILITY_LOW_US);
    printPositionalCommand(SERVO_REPEATABILITY_LOW_US, F("approach"), F("preposition"));
  } else if (next == POS_TARGET_FROM_LOW) {
    commandPulse(SERVO_REPEATABILITY_TARGET_US);
    printPositionalCommand(SERVO_REPEATABILITY_TARGET_US, F("target"), F("below"));
  } else if (next == POS_HIGH) {
    commandPulse(SERVO_REPEATABILITY_HIGH_US);
    printPositionalCommand(SERVO_REPEATABILITY_HIGH_US, F("approach"), F("preposition"));
  } else {
    commandPulse(SERVO_REPEATABILITY_TARGET_US);
    printPositionalCommand(SERVO_REPEATABILITY_TARGET_US, F("target"), F("above"));
  }
}

void printContinuousCommand(uint16_t pulseUs, const __FlashStringHelper *direction,
                            uint32_t durationMs) {
  Serial.print(F("CMD CONTINUOUS pulse_us="));
  Serial.print(pulseUs);
  Serial.print(F(" requested_position_us=NA"));
  Serial.print(F(" direction="));
  Serial.print(direction);
  Serial.print(F(" motion_ms="));
  Serial.println((unsigned long)durationMs);
}

void commandNeutral(const __FlashStringHelper *reason, uint32_t dwellMs) {
  commandPulse(SERVO_REPEATABILITY_STOP_US);
  Serial.print(F("CMD STOP pulse_us="));
  Serial.print(SERVO_REPEATABILITY_STOP_US);
  Serial.print(F(" reason="));
  Serial.print(reason);
  Serial.print(F(" dwell_ms="));
  Serial.println((unsigned long)dwellMs);
}

void setContinuousDirection(Step next, uint32_t now) {
  step = next;
  deadlineMs = now + (uint32_t)SERVO_REPEATABILITY_MOTION_MS;
  if (next == CONT_LOW) {
    commandPulse(SERVO_REPEATABILITY_LOW_US);
    printContinuousCommand(SERVO_REPEATABILITY_LOW_US, F("low"),
                           SERVO_REPEATABILITY_MOTION_MS);
  } else {
    commandPulse(SERVO_REPEATABILITY_HIGH_US);
    printContinuousCommand(SERVO_REPEATABILITY_HIGH_US, F("high"),
                           SERVO_REPEATABILITY_MOTION_MS);
  }
}

bool deadlineReached(uint32_t now, uint32_t deadline) {
  return (int32_t)(now - deadline) >= 0;
}

void serviceMotion(uint32_t now) {
  if (operation == IDLE || !deadlineReached(now, deadlineMs)) return;

  if (operation == POSITIONAL_TEST) {
    if (step == POS_LOW) {
      setPositionalStep(POS_TARGET_FROM_LOW, now);
    } else if (step == POS_TARGET_FROM_LOW && ++repetition < SERVO_REPEATABILITY_REPETITIONS) {
      setPositionalStep(POS_LOW, now);
    } else if (step == POS_TARGET_FROM_LOW) {
      repetition = 0;
      setPositionalStep(POS_HIGH, now);
    } else if (step == POS_HIGH) {
      setPositionalStep(POS_TARGET_FROM_HIGH, now);
    } else if (++repetition < SERVO_REPEATABILITY_REPETITIONS) {
      setPositionalStep(POS_HIGH, now);
    } else {
      operation = IDLE;
      Serial.print(F("CMD TEST_DONE mode=POSITIONAL hold_us="));
      Serial.println(commandedPulseUs);
    }
    return;
  }

  if (operation == CONTINUOUS_CALIBRATION) {
    commandNeutral(F("calibration_complete"), 0);
    operation = IDLE;
    return;
  }

  if (step == CONT_LOW) {
    commandNeutral(F("between_runs"), SERVO_REPEATABILITY_SETTLE_MS);
    step = CONT_NEUTRAL_AFTER_LOW;
    deadlineMs = now + (uint32_t)SERVO_REPEATABILITY_SETTLE_MS;
  } else if (step == CONT_NEUTRAL_AFTER_LOW) {
    if (++repetition < SERVO_REPEATABILITY_REPETITIONS) {
      setContinuousDirection(CONT_LOW, now);
    } else {
      repetition = 0;
      setContinuousDirection(CONT_HIGH, now);
    }
  } else if (step == CONT_HIGH) {
    commandNeutral(F("between_runs"), SERVO_REPEATABILITY_SETTLE_MS);
    step = CONT_NEUTRAL_AFTER_HIGH;
    deadlineMs = now + (uint32_t)SERVO_REPEATABILITY_SETTLE_MS;
  } else if (++repetition < SERVO_REPEATABILITY_REPETITIONS) {
    setContinuousDirection(CONT_HIGH, now);
  } else {
    operation = IDLE;
    Serial.println(F("CMD TEST_DONE mode=CONTINUOUS stop=neutral"));
  }
}

bool parseUnsigned(const char *&cursor, uint32_t &value) {
  if (*cursor < '0' || *cursor > '9') return false;
  value = 0;
  do {
    const uint8_t digit = (uint8_t)(*cursor - '0');
    if (value > (UINT32_MAX - digit) / 10UL) return false;
    value = value * 10UL + digit;
    ++cursor;
  } while (*cursor >= '0' && *cursor <= '9');
  return true;
}

bool parseOneArgument(const char *command, char prefix, uint32_t &first) {
  if (command[0] != prefix || command[1] != ' ') return false;
  const char *cursor = command + 2;
  return parseUnsigned(cursor, first) && *cursor == '\0';
}

bool parseTwoArguments(const char *command, char prefix, uint32_t &first,
                       uint32_t &second) {
  if (command[0] != prefix || command[1] != ' ') return false;
  const char *cursor = command + 2;
  if (!parseUnsigned(cursor, first) || *cursor++ != ' ') return false;
  return parseUnsigned(cursor, second) && *cursor == '\0';
}

void cancelOperation() {
  if (operation == IDLE) {
    Serial.println(F("ERR IDLE"));
    return;
  }
  if (operation == POSITIONAL_TEST) {
    operation = IDLE;
    Serial.print(F("CMD CANCEL mode=POSITIONAL hold_us="));
    Serial.println(commandedPulseUs);
  } else {
    commandNeutral(F("cancel"), 0);
    operation = IDLE;
  }
}

void disableSignal() {
  operation = IDLE;
  if (servo.attached()) servo.detach();
  pinMode(SERVO_PIN, OUTPUT);
  digitalWrite(SERVO_PIN, LOW);
  Serial.println(F("CMD SIGNAL_DISABLED pin=D9"));
}

void handleCommand(char *command, uint32_t now) {
  if (strcmp(command, "X") == 0) {
    cancelOperation();
    return;
  }
  if (strcmp(command, "D") == 0) {
    disableSignal();
    return;
  }

  if (operation != IDLE) {
    Serial.println(F("ERR BUSY"));
    return;
  }

  if (strcmp(command, "T") == 0) {
    if (SERVO_REPEATABILITY_MODE == SERVO_MODE_POSITIONAL) {
      if (!configuredFor(SERVO_MODE_POSITIONAL)) return;
      repetition = 0;
      operation = POSITIONAL_TEST;
      setPositionalStep(POS_LOW, now);
    } else {
      if (!configuredFor(SERVO_MODE_CONTINUOUS)) return;
      repetition = 0;
      operation = CONTINUOUS_TEST;
      setContinuousDirection(CONT_LOW, now);
    }
    return;
  }

  uint32_t pulseUs;
  if (command[0] == 'P') {
    if (!parseOneArgument(command, 'P', pulseUs)) {
      Serial.println(F("ERR COMMAND"));
    } else if (!configuredFor(SERVO_MODE_POSITIONAL)) {
      return;
    } else if (!pulseInEnvelope(pulseUs)) {
      Serial.println(F("ERR PULSE_RANGE"));
    } else {
      commandPulse((uint16_t)pulseUs);
      printPositionalCommand((uint16_t)pulseUs, F("calibration"), F("direct"));
    }
    return;
  }

  uint32_t durationMs;
  if (command[0] == 'C') {
    if (!parseTwoArguments(command, 'C', pulseUs, durationMs)) {
      Serial.println(F("ERR COMMAND"));
    } else if (!configuredFor(SERVO_MODE_CONTINUOUS)) {
      return;
    } else if (!pulseInEnvelope(pulseUs)) {
      Serial.println(F("ERR PULSE_RANGE"));
    } else if (durationMs == 0 || durationMs > MAX_MOTION_MS) {
      Serial.println(F("ERR DURATION_RANGE"));
    } else {
      commandPulse((uint16_t)pulseUs);
      printContinuousCommand((uint16_t)pulseUs, F("calibration"), durationMs);
      operation = CONTINUOUS_CALIBRATION;
      step = CONT_CALIBRATION_PULSE;
      deadlineMs = now + durationMs;
    }
    return;
  }

  Serial.println(F("ERR COMMAND"));
}

void receiveByte(char incoming, uint32_t now) {
  if (incoming == '\n' || incoming == '\r') {
    if (discardingLine) {
      Serial.println(F("ERR LINE_TOO_LONG"));
    } else if (invalidLine) {
      Serial.println(F("ERR LINE_INVALID"));
    } else if (lineLength > 0) {
      line[lineLength] = '\0';
      handleCommand(line, now);
    }
    lineLength = 0;
    discardingLine = false;
    invalidLine = false;
    return;
  }

  if (discardingLine || invalidLine) return;
  const uint8_t byteValue = (uint8_t)incoming;
  if (byteValue < 0x20 || byteValue > 0x7e) {
    lineLength = 0;
    invalidLine = true;
    return;
  }
  if (lineLength >= LINE_CAPACITY - 1) {
    lineLength = 0;
    discardingLine = true;
    return;
  }
  line[lineLength++] = incoming;
}

void setup() {
  pinMode(SERVO_PIN, OUTPUT);
  digitalWrite(SERVO_PIN, LOW);
  Serial.begin(115200);
  if (SERVO_REPEATABILITY_MODE == SERVO_MODE_UNCONFIRMED) {
    Serial.println(F("READY mode=UNCONFIRMED output=disabled"));
  } else if (!configurationValid()) {
    Serial.println(F("READY config=INVALID output=disabled"));
  } else if (SERVO_REPEATABILITY_MODE == SERVO_MODE_POSITIONAL) {
    Serial.println(F("READY mode=POSITIONAL output=disabled"));
  } else {
    Serial.println(F("READY mode=CONTINUOUS output=disabled"));
  }
}

void loop() {
  serviceMotion((uint32_t)millis());
  if (Serial.available()) receiveByte((char)Serial.read(), (uint32_t)millis());
  serviceMotion((uint32_t)millis());
}
