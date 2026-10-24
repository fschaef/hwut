/* sat_add.c -- saturating 32-bit addition, as used in a fixed-point DSP path.
 * The overflow test is done BEFORE the addition: no signed overflow, no UB. */
#include <stdint.h>

int32_t sat_add(int32_t a, int32_t b)
{
    if (b > 0 && a > INT32_MAX - b) return INT32_MAX;
    if (b < 0 && a < INT32_MIN - b) return INT32_MIN;
    return a + b;
}
