/* sat_add_wrapcheck.c -- the "add first, look at the sign afterwards"
 * variant found in an older DSP library: the sum is computed with wrap-around
 * and overflow is guessed from the sign of the result. */
#include <stdint.h>

int32_t sat_add(int32_t a, int32_t b)
{
    int32_t s = (int32_t)((uint32_t)a + (uint32_t)b);
    if (a > 0 && b > 0 && s < 0) return INT32_MAX;
    if (a < 0 && b < 0 && s > 0) return INT32_MIN;
    return s;
}
