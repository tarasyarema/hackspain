#ifndef HOST_ARDUINO_H
#define HOST_ARDUINO_H

#include <stdint.h>
#include <deque>
#include <sstream>
#include <string>

struct __FlashStringHelper;
#define F(value) (reinterpret_cast<const __FlashStringHelper *>(value))

const uint8_t OUTPUT = 1;
const uint8_t LOW = 0;

extern uint32_t hostMillis;
extern uint8_t hostPinModes[20];
extern uint8_t hostPinValues[20];

inline unsigned long millis() { return hostMillis; }
inline void pinMode(uint8_t pin, uint8_t mode) { hostPinModes[pin] = mode; }
inline void digitalWrite(uint8_t pin, uint8_t value) { hostPinValues[pin] = value; }

class MockSerial {
 public:
  std::deque<char> input;
  std::string output;

  void begin(unsigned long) {}
  int available() const { return (int)input.size(); }
  int read() {
    char value = input.front();
    input.pop_front();
    return value;
  }
  void feed(const std::string &value) {
    input.insert(input.end(), value.begin(), value.end());
  }
  void print(const __FlashStringHelper *value) {
    output += reinterpret_cast<const char *>(value);
  }
  void print(const char *value) { output += value; }
  void print(char value) { output += value; }
  template <typename T>
  void print(T value) {
    std::ostringstream stream;
    stream << value;
    output += stream.str();
  }
  template <typename T>
  void println(T value) {
    print(value);
    output += '\n';
  }
  void println() { output += '\n'; }
};

extern MockSerial Serial;

#endif
