/* kalman.c -- barometric altitude: a constant-velocity Kalman filter.
 *
 *     kalman <tuning-file> <p0[Pa]> < samples     samples: "t[s] pressure[Pa]"
 *
 * Prints one line per sample: "t raw_altitude estimate" in metres.
 * The tuning file holds two numbers: q (process noise, acceleration
 * spectral density, m^2/s^3) and r (measurement noise variance, m^2).
 * State x = (h, v); h is the altitude above the reference pressure p0. */
#include <math.h>
#include <stdio.h>

static double altitude_m(double p, double p0)
{ return 44330.0 * (1.0 - pow(p / p0, 1.0 / 5.255)); }

int main(int argc, char** argv)
{
    double q, r, t, p, p0 = 0.0, t_prev = 0.0;
    double h = 0.0, v = 0.0;                      /* state            */
    double P00 = 10.0, P01 = 0.0, P11 = 10.0;     /* covariance       */
    int    first = 1;
    FILE*  fh = argc > 1 ? fopen(argv[1], "r") : NULL;

    if (!fh || fscanf(fh, " q = %lf r = %lf", &q, &r) != 2) {
        fprintf(stderr, "kalman: cannot read tuning file\n");
        return 2;
    }
    fclose(fh);
    if (argc < 3 || sscanf(argv[2], "%lf", &p0) != 1) {
        fprintf(stderr, "kalman: no reference pressure p0\n");
        return 2;
    }
    while (scanf("%lf %lf", &t, &p) == 2) {
        if (first) { t_prev = t; first = 0; }
        double z  = altitude_m(p, p0);
        double dt = t - t_prev;  t_prev = t;
        /* predict */
        h += v * dt;
        double dt2 = dt * dt, dt3 = dt2 * dt, dt4 = dt3 * dt;
        P00 += dt * (2.0 * P01 + dt * P11) + q * dt4 / 4.0;
        P01 += dt * P11 + q * dt3 / 2.0;
        P11 += q * dt2;
        /* update */
        double S  = P00 + r;
        double K0 = P00 / S, K1 = P01 / S;
        double y  = z - h;
        h += K0 * y;  v += K1 * y;
        P11 -= K1 * P01;  P01 -= K0 * P01;  P00 -= K0 * P00;
        printf("%.3f %.4f %.4f\n", t, z, h);
    }
    return 0;
}
