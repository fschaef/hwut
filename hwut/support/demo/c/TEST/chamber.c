/* @hwut {
 *     title     = "Demo: a climate chamber's step response -- regions, units, a string law"
 *     build     { framework = "make", target = "%.exe" }
 *     tolerance { constraints = ["overshoot <= 0.5 K",
 *                                "settle <= 4 min",
 *                                "verdict == 'settled'"] }
 *     choices {
 *         heat { features = ["region-verbatim", "region-table", "region-point-cloud",
 *                            "region-ignore", "laws-in-units", "string-binding",
 *                            "test-level-tolerance", "annotation-lines"] }
 *         cool { features = ["region-verbatim", "region-table", "region-point-cloud",
 *                            "region-ignore", "laws-in-units", "string-binding",
 *                            "test-level-tolerance", "annotation-lines"] }
 *     }
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * SUBJECT  a climate chamber driven from one temperature to another by a PI
 *          controller: its configuration, its sensors at the end, its step
 *          response, and the three numbers its requirement names.
 * REQUIREMENT  The chamber reaches the setpoint within 4 minutes, overshoots
 *              it by no more than 0.5 K, and reports itself 'settled'.
 *
 * Every run is seeded by the clock: the sensors are noisy, the four sensor
 * rows come out in a different order, the calibration stamps are today's.
 * Both choices pass on every run anyway; each part of the output says how:
 *
 * '##' lines     notes for the reader. The comparison skips them on both
 *                sides, anywhere -- even inside a region.
 *
 * verbatim       '##! verbatim' ... '####': the configuration as loaded. It is
 *                YAML, where indentation is meaning, so nothing is tolerated:
 *                no whitespace folding, no numeric band.
 *
 * table          '##! table key=0 ignore=1 numeric={2:0.0005}': one row per
 *                sensor, matched by its NAME (column 0) whatever the order;
 *                column 1, the calibration stamp, is not compared; column 2,
 *                the reading in K, within 0.05 %.
 *
 * point-cloud    '##! point-cloud limit=0.5 constraint={...}': the step
 *                response as points (t, T). Every point lies within 0.5 of a
 *                point of the GOOD file ('limit'), AND every point keeps the
 *                envelope stated in the region ('constraint') -- the GOOD's
 *                points, too, so a GOOD that breaks its envelope is refused.
 *
 * ignore         '##! ignore': a picture for the human eye. One noisy sample
 *                moves a star; the picture's presence is compared, its
 *                contents are not.
 *
 * units          '((settle: 150 s))' is a quantity; the law says 'settle <= 4
 *                min' and the comparison converts. A temperature DIFFERENCE is
 *                printed in K, never in degC (an offset unit).
 *
 * string law     '((verdict: "settled"))' binds a string; 'verdict ==
 *                'settled'' judges it.
 *
 * test-level     the three laws stand ONCE, in the header's own 'tolerance',
 * tolerance      and hold for both choices.
 *
 * The configuration's numbers are printed as Python prints them ('%s' of a
 * float) by the C support's 'pytext_float_repr': the GOOD is the Python
 * demo's.
 *
 * CHOICES  heat  20 degC -> 40 degC.
 *          cool  40 degC -> 20 degC.
 * _____________________________________________________________________________
 */
#define _POSIX_C_SOURCE 200809L
#define _DEFAULT_SOURCE
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "hwut_pytext.h"

#define DT_S          1.0            /* simulation step                       */
#define DURATION_S    400            /* simulated time                        */
#define SAMPLE_S      20             /* one point of the cloud every 20 s     */
#define BAND_K        0.3            /* 'settled' = within 0.3 K of setpoint  */
#define NOISE_K       0.02           /* sensor noise, one sigma               */
#define SAMPLE_N      (DURATION_S + 1)
static const double TAU_S = 300.0, RATE_K_PER_S = 0.15;   /* the plant      */
static const double KP    = 0.6,   KI           = 0.01;   /* the controller */

/* Offset of each sensor against the air in the middle of the chamber. */
static const char* const SENSOR_NAME[4]   = { "top", "middle", "bottom", "door" };
static const double      SENSOR_OFFSET[4] = { +0.10, 0.00, -0.10, -0.40 };

typedef struct { double t_s, measured_C; } Sample;

static uint64_t random_state;

static double
uniform01(void)
/* RETURN: double, drawn evenly from [0, 1) (splitmix64). */
{
    uint64_t z = (random_state += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return (double)((z ^ (z >> 31)) >> 11) / 9007199254740992.0;
}

static double
gauss(double mu, double sigma)
/* RETURN: double, drawn from the normal distribution (mu, sigma); Box-Muller. */
{ return mu + sigma * sqrt(-2.0 * log(1.0 - uniform01())) * cos(2.0 * M_PI * uniform01()); }

static void
step_response(double start_C, double setpoint_C, Sample* sample)
/* RETURN: nothing; 'sample' holds SAMPLE_N samples (t_s, measured_C), one per
 *         simulation step, of the chamber driven from 'start_C' to
 *         'setpoint_C' by the PI controller, with sensor noise.             */
{
    double ambient = 20.0, temp = start_C, integral = 0.0, t = 0.0;
    double measured, error, output;
    int    i = 0;
    while( t <= DURATION_S ) {
        measured = temp + gauss(0.0, NOISE_K);
        sample[i].t_s = t; sample[i].measured_C = measured; ++i;
        error  = setpoint_C - measured;
        output = KP * error + KI * integral;
        if( -1.0 < output && output < 1.0 )         /* anti-windup: integrate */
            integral += error * DT_S;               /* only while unsaturated */
        output = output < -1.0 ? -1.0 : output > 1.0 ? 1.0 : output;
        temp += DT_S * ((ambient - temp) / TAU_S + RATE_K_PER_S * output);
        t += DT_S;
    }
}

static double
overshoot_K(const Sample* sample, double start_C, double setpoint_C)
/* RETURN: double, how far in K the chamber went past 'setpoint_C' in the
 *         direction of travel from 'start_C'; 0.0 where it never did.       */
{
    double sign = setpoint_C > start_C ? 1.0 : -1.0, most = 0.0, d;
    int    i;
    for(i = 0; i < SAMPLE_N; ++i) {
        d = sign * (sample[i].measured_C - setpoint_C);
        if( d > most ) most = d;
    }
    return most;
}

static double
settle_s(const Sample* sample, double setpoint_C)
/* RETURN: double, the time in s after which every sample stays within BAND_K
 *         of 'setpoint_C' (the step after the last one outside); 0.0 where
 *         none was outside.                                                 */
{
    int i;
    for(i = SAMPLE_N - 1; i >= 0; --i)
        if( fabs(sample[i].measured_C - setpoint_C) > BAND_K ) return sample[i].t_s + DT_S;
    return 0.0;
}

static void
print_config(void)
/* RETURN: nothing. Prints the configuration as loaded, byte for byte. */
{
    char rate[32], kp[32], ki[32];
    printf("configuration, as loaded (YAML: whitespace is meaning):\n");
    printf("##! verbatim\n");
    printf("chamber:\n"
           "  plant:\n"
           "    time_constant_s: %.0f\n"
           "    heater_rate_K_per_s: %s\n"
           "  controller:\n"
           "    kind: PI\n"
           "    kp: %s\n"
           "    ki: %s\n"
           "    output: [-1.0, 1.0]\n"
           "  sensors: [top, middle, bottom, door]\n",
           TAU_S, pytext_float_repr(rate, sizeof(rate), RATE_K_PER_S),
           pytext_float_repr(kp, sizeof(kp), KP), pytext_float_repr(ki, sizeof(ki), KI));
    printf("####\n");
}

static void
print_sensors(double setpoint_C)
/* RETURN: nothing. Prints one row per sensor, in a random order, with
 *         today's calibration stamp and the reading at the end in K.        */
{
    int       order[4] = { 0, 1, 2, 3 }, i, k, swap;
    char      stamp[32];
    time_t    now = time(NULL);
    struct tm local;
    printf("sensors at the end, in K (the order is the bus's):\n");
    printf("    sensor  calibrated           reading_K\n");
    printf("##! table key=0 ignore=1 numeric={2:0.0005}\n");
    for(i = 3; i > 0; --i) {
        k = (int)(uniform01() * (i + 1));
        swap = order[i]; order[i] = order[k]; order[k] = swap;
    }
    localtime_r(&now, &local);
    strftime(stamp, sizeof(stamp), "%Y-%m-%dT%H:%M:%S", &local);
    for(i = 0; i < 4; ++i)
        printf("    %-6s  %s  %9.2f\n", SENSOR_NAME[order[i]], stamp,
               setpoint_C + SENSOR_OFFSET[order[i]] + gauss(0.0, NOISE_K) + 273.15);
    printf("####\n");
}

static void
print_cloud(const Sample* sample, double start_C, double setpoint_C)
/* RETURN: nothing. Prints the step response, one point (t_s, T_degC) every
 *         SAMPLE_S, framed with the envelope the requirement allows.        */
{
    double low  = start_C < setpoint_C ? start_C : setpoint_C;
    double high = start_C < setpoint_C ? setpoint_C : start_C;
    int    i;
    if( setpoint_C > start_C ) high += 0.5;
    else                       low  -= 0.5;
    /* 0.1 K beyond the envelope on either side: the sensor's noise. */
    printf("step response, t in s against T in degC; envelope %.1f .. %.1f:\n", low, high);
    printf("##! point-cloud limit=0.5 constraint={y >= %.1f and y <= %.1f}\n", low - 0.1, high + 0.1);
    for(i = 0; i < SAMPLE_N; ++i)
        if( fmod(sample[i].t_s, SAMPLE_S) == 0.0 )
            printf("    %5.0f  %6.2f\n", sample[i].t_s, sample[i].measured_C);
    printf("####\n");
}

static void
print_picture(const Sample* sample, double start_C, double setpoint_C)
/* RETURN: nothing. Prints the step response as stars, for the human eye
 *         only: one row per 40 s, one column per 0.5 K.                     */
{
    double low = (start_C < setpoint_C ? start_C : setpoint_C) - 1.0;
    char   row[47];
    int    i, at, end;
    printf("the same, as a picture ('|' the setpoint):\n");
    printf("##! ignore\n");
    for(i = 0; i < SAMPLE_N; ++i) {
        if( fmod(sample[i].t_s, 40.0) != 0.0 ) continue;
        memset(row, ' ', 46); row[46] = '\0';
        row[(int)nearbyint((setpoint_C - low) / 0.5)] = '|';
        at = (int)nearbyint((sample[i].measured_C - low) / 0.5);
        row[at < 0 ? 0 : at > 45 ? 45 : at] = '*';
        for(end = 46; end > 0 && row[end - 1] == ' '; --end) row[end - 1] = '\0';
        printf("    %4.0f s  %s\n", sample[i].t_s, row);
    }
    printf("####\n");
}

static void
run(double start_C, double setpoint_C)
/* RETURN: nothing. Drives the chamber and prints every part of the report. */
{
    static Sample   sample[SAMPLE_N];
    struct timespec now;
    double          over, settle;
    clock_gettime(CLOCK_REALTIME, &now);
    random_state = (uint64_t)now.tv_sec * 1000000000ULL + (uint64_t)now.tv_nsec;
    step_response(start_C, setpoint_C, sample);
    printf("## climate chamber, %.0f degC -> %.0f degC, one sample per second\n", start_C, setpoint_C);
    printf("## '##' lines are for the reader: the comparison skips them.\n");
    print_config();
    print_sensors(setpoint_C);
    print_cloud(sample, start_C, setpoint_C);
    print_picture(sample, start_C, setpoint_C);
    over   = overshoot_K(sample, start_C, setpoint_C);
    settle = settle_s(sample, setpoint_C);
    printf("overshoot  ((overshoot: %.2f K))          law <= 0.5 K\n", over);
    printf("settled    ((settle: %.0f s))             law <= 4 min\n", settle);
    printf("chamber    ((verdict: \"%s\"))\n",
           fabs(sample[SAMPLE_N - 1].measured_C - setpoint_C) <= BAND_K ? "settled" : "drifting");
}

int
main(int argc, char** argv)
/* RETURN: int, 0 -- the choice ran and '<hwut-end>' closed its output;
 *         1, the choice is neither 'heat' nor 'cool' (both are named).      */
{
    const char* choice = argc > 1 ? argv[1] : "";
    if     ( strcmp(choice, "heat") == 0 ) run(20.0, 40.0);
    else if( strcmp(choice, "cool") == 0 ) run(40.0, 20.0);
    else { printf("choices: heat, cool\n"); return 1; }
    printf("<hwut-end>\n");
    return 0;
}
