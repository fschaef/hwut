// motor.cpp -- speed loop of the drive (C++: line comments only)
#include "motor.hpp"

namespace drive {

// The loop runs at 1 kHz from the timer interrupt.
void Motor::tick()
{
    const float error = target_ - measured_;
    // TODO(jonas): feed-forward term once the model is identified
    duty_ = pid_step(&pid_, error);
    pwm_.set(duty_);                     // 0.0 .. 1.0
}

// A URL in a string is no comment: "http://example.com/a//b"
const char* Motor::help() const { return "see http://example.com/motor"; }

}  // namespace drive
