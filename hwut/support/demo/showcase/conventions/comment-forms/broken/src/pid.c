/* pid.c -- discrete PID controller (C: block comments are the house form) */
#include "pid.h"

static const char* const PID_UNITS = "error in mV /* not a comment */";

/* Anti-windup: the integral is clamped to the output range. */
float pid_step(pid_ctrl_t* p, float error)
{
    p->integral += p->ki * error;               /* I term */
    if (p->integral > p->out_max) p->integral = p->out_max;
    if (p->integral < p->out_min) p->integral = p->out_min;
    /* TODO: derivative on measurement */
    float d = p->kd * (error - p->last_error);
    p->last_error = error;
    /* p->integral = 0.0f; */
    return p->kp * error + p->integral + d;
}
