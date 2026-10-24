/* pid.h -- discrete PID controller */
#ifndef PID_H
#define PID_H

typedef struct {
    float kp, ki, kd;       /* gains */
    float integral;
    float last_error;
    float out_min, out_max; /* output clamp */
} pid_ctrl_t;

float pid_step(pid_ctrl_t* p, float error);

#endif /* PID_H */
