#include "motor.h"

const char* state_name(motor_state_t s)
{
    switch (s) {
    case MOTOR_OFF:      return "off";
    case MOTOR_STARTING: return "starting";
    case MOTOR_RUNNING:  return "running";
    case MOTOR_STOPPING: return "stopping";
    case MOTOR_FAULT:    return "FAULT";
    default:             return "?";
    }
    return "?";
}
