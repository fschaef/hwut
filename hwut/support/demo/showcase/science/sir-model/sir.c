/* sir.c -- the Kermack-McKendrick SIR epidemic:
 *     dS/dt = -beta S I / N      dI/dt = beta S I / N - gamma I      dR/dt = gamma I
 * usage: sir N I0 BETA GAMMA DAYS DT rk4|euler EVERY
 * prints 't S I R' every EVERY days (t %.6f, S I R %.9f).                         */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

static double N, beta, gamma_;

static void deriv(const double y[3], double d[3])
{
    double infect = beta * y[0] * y[1] / N, recover = gamma_ * y[1];
    d[0] = -infect;
    d[1] = infect - recover;
    d[2] = recover;
}

static void step_euler(double y[3], double h)
{
    double d[3];
    int i;
    deriv(y, d);
    for(i = 0; i < 3; ++i) y[i] += h * d[i];
}

static void step_rk4(double y[3], double h)
{
    double k1[3], k2[3], k3[3], k4[3], t[3];
    int i;
    deriv(y, k1);
    for(i = 0; i < 3; ++i) t[i] = y[i] + h / 2 * k1[i];
    deriv(t, k2);
    for(i = 0; i < 3; ++i) t[i] = y[i] + h / 2 * k2[i];
    deriv(t, k3);
    for(i = 0; i < 3; ++i) t[i] = y[i] + h * k3[i];
    deriv(t, k4);
    for(i = 0; i < 3; ++i) y[i] += h / 6 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]);
}

int main(int argc, char** argv)
{
    if( argc != 9 ) { fprintf(stderr, "usage: sir N I0 BETA GAMMA DAYS DT rk4|euler EVERY\n"); return 2; }
    N = atof(argv[1]); beta = atof(argv[3]); gamma_ = atof(argv[4]);
    double y[3] = { N - atof(argv[2]), atof(argv[2]), 0 };
    double days = atof(argv[5]), h = atof(argv[6]), every = atof(argv[8]);
    long   steps = lround(days / h), per_print = lround(every / h), k;
    void (*step)(double*, double) = strcmp(argv[7], "euler") == 0 ? step_euler : step_rk4;

    for(k = 0; k <= steps; ++k) {
        if( k % per_print == 0 ) printf("%.6f %.9f %.9f %.9f\n", k * h, y[0], y[1], y[2]);
        step(y, h);
    }
    return 0;
}
