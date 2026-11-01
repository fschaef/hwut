#include "motor.h"

motor_state_t motor_step(motor_state_t s, int cmd, int ok)
{
    switch (s) {
    case MOTOR_OFF:      return cmd > 0 ? MOTOR_STARTING : MOTOR_OFF;
    case MOTOR_STARTING: return ok ? MOTOR_RUNNING : MOTOR_FAULT;
    case MOTOR_RUNNING:  return cmd < 0 ? MOTOR_STOPPING : MOTOR_RUNNING;
    case MOTOR_STOPPING: return MOTOR_OFF;
    case MOTOR_FAULT:    return cmd == 0 ? MOTOR_OFF : MOTOR_FAULT;
    }
    return MOTOR_FAULT;
}
