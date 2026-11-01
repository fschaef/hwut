/* sri.c -- the conversion at the heart of Ariane 501: the horizontal bias BH,
 * a 64-bit float, is converted to a 16-bit signed integer for the telemetry
 * word of the inertial reference system (SRI).
 *
 * CONVERT selects how (-DCONVERT=...):
 *   ADA_UNPROTECTED  Ada semantics without a handler: a value outside
 *                    -32768..32767 raises Operand Error; nobody catches it,
 *                    the SRI declares itself failed and stops.   (flight 501)
 *   C_CAST           a WRAPPING conversion, on purpose: the value wraps
 *                    modulo 2^16, silently. Not what C 'does': a direct
 *                    out-of-range double -> int16 conversion is undefined
 *                    behaviour in C; the unit converts through int64 and
 *                    uint32, which is defined, to model a silent wrap.
 *   PROTECTED        the guard the other converted variables had: the
 *                    value is clamped to the limit and a flag is raised.
 * Rounding to nearest, as Ada converts float to integer.
 *
 * stdin: one value per line.  argv[1]: 'table' -- every line on its own;
 *                                       'flight' -- the SRI stops at the
 *                                       first unhandled error.
 * stdout: 'value <n>' | 'clamped <n> flag' | 'OPERAND_ERROR' | 'SRI_FAILED'  */
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <math.h>

#define ADA_UNPROTECTED 1
#define C_CAST          2
#define PROTECTED       3

int main(int argc, char** argv)
{
    int    flight = argc > 1 && strcmp(argv[1], "flight") == 0;
    double bh;
    (void)flight;                        /* only the unprotected SRI stops */
    while (scanf("%lf", &bh) == 1) {
        double r = round(bh);
#if   CONVERT == ADA_UNPROTECTED
        if (!(r >= -32768.0 && r <= 32767.0)) {
            puts("OPERAND_ERROR");
            if (flight) { puts("SRI_FAILED"); return 0; }   /* no handler   */
            continue;
        }
        printf("value %d\n", (int16_t)r);
#elif CONVERT == C_CAST
        printf("value %d\n", (int16_t)(uint16_t)(uint32_t)(int64_t)r);  /* wraps */
#elif CONVERT == PROTECTED
        if      (r >  32767.0) printf("clamped %d flag\n",  32767);
        else if (r < -32768.0) printf("clamped %d flag\n", -32768);
        else                   printf("value %d\n", (int16_t)r);
#endif
    }
    return 0;
}
