#ifndef MOTOR_H
#define MOTOR_H

typedef enum {
    MOTOR_OFF,
    MOTOR_STARTING,
    MOTOR_RUNNING,
    MOTOR_STOPPING,
    MOTOR_FAULT
} motor_state_t;

motor_state_t motor_step(motor_state_t s, int cmd, int ok);
const char*   state_name(motor_state_t s);
int           state_code(motor_state_t s);

#endif
