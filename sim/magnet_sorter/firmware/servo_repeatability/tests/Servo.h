#ifndef HOST_SERVO_H
#define HOST_SERVO_H

#include <stdint.h>
#include <vector>

#define MIN_PULSE_WIDTH 544
#define MAX_PULSE_WIDTH 2400

struct ServoEvent {
  uint8_t pin;
  uint16_t pulseUs;
};

extern std::vector<ServoEvent> hostServoEvents;

class Servo {
 public:
  Servo() : isAttached(false), pin(0), pulseUs(1500) {}

  uint8_t attach(int nextPin) {
    pin = (uint8_t)nextPin;
    isAttached = true;
    hostServoEvents.push_back({pin, pulseUs});
    return 1;
  }
  void detach() { isAttached = false; }
  bool attached() const { return isAttached; }
  void writeMicroseconds(int value) {
    if (value < MIN_PULSE_WIDTH) value = MIN_PULSE_WIDTH;
    if (value > MAX_PULSE_WIDTH) value = MAX_PULSE_WIDTH;
    pulseUs = (uint16_t)value;
    if (isAttached) hostServoEvents.push_back({pin, pulseUs});
  }

 private:
  bool isAttached;
  uint8_t pin;
  uint16_t pulseUs;
};

#endif
