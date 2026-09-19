#include <stdint.h>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

#include "Arduino.h"
#include "Servo.h"

uint32_t hostMillis = 0;
uint8_t hostPinModes[20] = {};
uint8_t hostPinValues[20] = {};
MockSerial Serial;
std::vector<ServoEvent> hostServoEvents;

#include "../servo_repeatability.ino"

static int checks = 0;

void expect(bool condition, const char *message) {
  ++checks;
  if (!condition) {
    std::cerr << "FAIL: " << message << '\n';
    std::exit(1);
  }
}

bool outputContains(const char *text) {
  return Serial.output.find(text) != std::string::npos;
}

void clearOutput() { Serial.output.clear(); }

void runLoops(size_t count) {
  for (size_t i = 0; i < count; ++i) loop();
}

void send(const std::string &command) {
  Serial.feed(command + "\n");
  while (Serial.available()) loop();
}

void advance(uint32_t milliseconds) {
  hostMillis += milliseconds;
  loop();
}

void expectPulse(size_t index, uint16_t pulseUs, const char *message) {
  expect(index < hostServoEvents.size(), message);
  expect(hostServoEvents[index].pin == 9 && hostServoEvents[index].pulseUs == pulseUs,
         message);
}

void testStrictParser() {
  clearOutput();
  send("P 1500 extra");
  send("P -1");
  send("C 1500");
  send("T extra");
  expect(outputContains("ERR COMMAND"), "malformed commands are rejected");

  clearOutput();
  send(std::string(60, 'A'));
  expect(outputContains("ERR LINE_TOO_LONG"), "overlong line is rejected in full");

  clearOutput();
  const size_t eventsBeforeNul = hostServoEvents.size();
  send(std::string("T\0garbage", 9));
  expect(outputContains("ERR LINE_INVALID"), "embedded NUL rejects the complete line");
  expect(hostServoEvents.size() == eventsBeforeNul, "embedded NUL cannot execute a prefix");
}

#if SERVO_REPEATABILITY_MODE == SERVO_MODE_UNCONFIRMED
void runModeTests() {
  expect(hostServoEvents.empty(), "boot emits no servo pulse");
  expect(!servo.attached(), "boot leaves Servo detached");
  expect(hostPinModes[9] == OUTPUT && hostPinValues[9] == LOW, "boot holds D9 low");
  expect(outputContains("READY mode=UNCONFIRMED output=disabled"),
         "boot reports unconfirmed mode");

  clearOutput();
  send("T");
  send("P 1500");
  send("C 1450 100");
  expect(hostServoEvents.empty(), "unconfirmed commands emit no servo pulse");
  expect(outputContains("ERR MODE_UNCONFIRMED"), "unconfirmed commands explain rejection");
  testStrictParser();
}
#elif defined(TEST_INVALID_CONFIGURATION)
void runModeTests() {
  expect(hostServoEvents.empty(), "invalid configuration emits no boot pulse");
  expect(outputContains("READY config=INVALID output=disabled"),
         "invalid configuration is reported at boot");
  clearOutput();
  send("T");
  send("P 1500");
  expect(hostServoEvents.empty(), "invalid configuration never attaches");
  expect(outputContains("ERR CONFIG_INVALID"), "invalid configuration blocks commands");
}
#elif SERVO_REPEATABILITY_MODE == SERVO_MODE_POSITIONAL
void runModeTests() {
  expect(hostServoEvents.empty(), "positional boot emits no servo pulse");
  expect(outputContains("READY mode=POSITIONAL output=disabled"),
         "positional mode is explicit at boot");

  clearOutput();
  send("P 1399");
  send("P 1601");
  expect(hostServoEvents.empty(), "out-of-envelope positional pulses are rejected");
  expect(outputContains("ERR PULSE_RANGE"), "positional range rejection is reported");

  clearOutput();
  send("P 1500");
  expectPulse(0, 1500, "preloaded first positional pulse is commanded at attach");
  expect(outputContains("role=calibration approach=direct settle_ms=1000"),
         "positional calibration log labels commanded units");

  hostServoEvents.clear();
  clearOutput();
  send("T");
  send("P 1500");
  expect(outputContains("ERR BUSY"), "overlapping positional motion is rejected");
  for (int i = 0; i < 8; ++i) advance(SERVO_REPEATABILITY_SETTLE_MS);
  const uint16_t expected[] = {1450, 1500, 1450, 1500, 1550, 1500, 1550, 1500};
  expect(hostServoEvents.size() == 8, "positional test has a finite bounded sequence");
  for (size_t i = 0; i < 8; ++i) expectPulse(i, expected[i], "positional approach sequence");
  expect(operation == IDLE && servo.attached(), "positional completion holds its target");
  expect(outputContains("CMD TEST_DONE mode=POSITIONAL hold_us=1500"),
         "positional completion logs commanded hold");

  clearOutput();
  send("T");
  const size_t beforeCancel = hostServoEvents.size();
  send("X");
  expect(operation == IDLE && servo.attached(), "positional cancellation holds output active");
  expect(hostServoEvents.size() == beforeCancel, "positional cancellation does not jump target");
  expect(outputContains("CMD CANCEL mode=POSITIONAL hold_us=1450"),
         "positional cancellation logs hold pulse");

  hostMillis = UINT32_MAX - 500UL;
  hostServoEvents.clear();
  send("T");
  advance(1000);
  expectPulse(1, 1500, "positional deadline survives millis rollover");
  send("X");

  hostServoEvents.clear();
  send("T");
  Serial.feed(std::string(100, 'Z'));
  for (int i = 0; i < 100; ++i) {
    hostMillis += 10;
    loop();
  }
  expect(hostServoEvents.size() >= 2, "motion timing is serviced during sustained serial input");
  Serial.feed("\n");
  runLoops(1);
  send("X");

  clearOutput();
  send("D");
  expect(!servo.attached() && hostPinValues[9] == LOW, "D disables the pulse signal");
  expect(outputContains("CMD SIGNAL_DISABLED pin=D9"), "signal disable is logged");
  testStrictParser();
}
#elif SERVO_REPEATABILITY_MODE == SERVO_MODE_CONTINUOUS
void runModeTests() {
  expect(hostServoEvents.empty(), "continuous boot emits no servo pulse");
  expect(outputContains("READY mode=CONTINUOUS output=disabled"),
         "continuous mode is explicit at boot");

  clearOutput();
  send("C 1399 100");
  send("C 1450 0");
  send("C 1450 10001");
  expect(hostServoEvents.empty(), "continuous units and limits are enforced before attach");
  expect(outputContains("ERR PULSE_RANGE") && outputContains("ERR DURATION_RANGE"),
         "continuous unit/range errors are reported");

  clearOutput();
  send("C 1450 250");
  expectPulse(0, 1450, "preloaded first continuous pulse is commanded at attach");
  send("T");
  expect(outputContains("ERR BUSY"), "overlapping continuous motion is rejected");
  advance(249);
  expect(hostServoEvents.size() == 1, "continuous calibration remains active before deadline");
  advance(1);
  expectPulse(1, 1500, "continuous deadline commands configured neutral");
  expect(operation == IDLE && servo.attached(), "continuous completion keeps neutral active");
  expect(outputContains("reason=calibration_complete"), "continuous stop is logged");

  clearOutput();
  send("C 1550 300");
  send("X");
  expectPulse(hostServoEvents.size() - 1, 1500, "continuous cancellation commands neutral");
  expect(operation == IDLE && servo.attached(), "continuous cancellation keeps neutral active");
  expect(outputContains("reason=cancel"), "continuous cancellation log names the stop");

  hostServoEvents.clear();
  clearOutput();
  send("T");
  for (int i = 0; i < 8; ++i) {
    advance((i % 2 == 0) ? SERVO_REPEATABILITY_MOTION_MS : SERVO_REPEATABILITY_SETTLE_MS);
  }
  const uint16_t expected[] = {1450, 1500, 1450, 1500, 1550, 1500, 1550, 1500};
  expect(hostServoEvents.size() == 8, "continuous test has a finite bounded sequence");
  for (size_t i = 0; i < 8; ++i) expectPulse(i, expected[i], "continuous pulse/neutral sequence");
  expect(operation == IDLE && servo.attached(), "continuous test finishes at active neutral");
  expect(outputContains("CMD TEST_DONE mode=CONTINUOUS stop=neutral"),
         "continuous completion logs commanded stop");

  hostMillis = UINT32_MAX - 100UL;
  hostServoEvents.clear();
  send("C 1450 250");
  advance(250);
  expectPulse(1, 1500, "continuous deadline survives millis rollover");

  clearOutput();
  send("D");
  expect(!servo.attached() && hostPinValues[9] == LOW, "D disables continuous pulse signal");
  testStrictParser();
}
#else
#error Unsupported test mode
#endif

int main() {
  setup();
  runModeTests();
  std::cout << "PASS mode=" << SERVO_REPEATABILITY_MODE << " checks=" << checks << '\n';
  return 0;
}
