#include "motor.h"

int state_code(motor_state_t s)
{
    int code = -1;
    switch (s) {
    case MOTOR_OFF:
    case MOTOR_STOPPING: code = 0; break;
    case MOTOR_STARTING: code = 1; break;
    case MOTOR_RUNNING:  code = 2; break;
    case MOTOR_FAULT:    code = 9; break;
    }
    return code;
}
