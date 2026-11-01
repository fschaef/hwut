/* range_gate.c -- MODEL of the Patriot's time base (GAO/IMTEC-92-26).
 *
 * The system clock counts tenths of a second in an integer. To get seconds,
 * the count is multiplied by 1/10 held in a 24-bit fixed-point register: 0.1
 * has no finite binary expansion and is CHOPPED to the register's 23
 * fraction bits, 0.00011001100110011001100 (binary) = 838860 / 2^23.
 * Each tenth is short by 0.8 / 2^23 s = 9.5e-8 s, and the shortfall grows
 * with the count: the calculated time drifts behind the true time.
 *
 * The RANGE GATE -- where the radar looks for the target next -- is placed
 * from the target's velocity times the time between two radar times. If
 * both times are converted the same way, their drifts cancel in the
 * difference. GATE selects (-DGATE=...):
 *   GATE_MIXED       one time through the improved conversion, the other
 *                    through the 24-bit one (the software at Dhahran, as
 *                    Skeel explains): the drift does NOT cancel
 *   GATE_CONSISTENT  both times through the same conversion
 *
 * stdin: lines '<uptime hours> <interval tenths>'.
 * stdout: '<hours> <true s> <calculated s> <inaccuracy s> <interval error s>' */
#include <stdio.h>
#include <stdint.h>

#define GATE_MIXED      1
#define GATE_CONSISTENT 2

#define TENTH_24 838860u                  /* 0.1 * 2^23, chopped           */

static double time_24(uint64_t tenths)    /* the 24-bit conversion          */
{
    return (double)(tenths * TENTH_24) / 8388608.0;     /* exact in double */
}

static double __attribute__((unused)) time_improved(uint64_t tenths)
{
    return (double)tenths / 10.0;
}

int main(void)
{
    unsigned hours, interval;
    while (scanf("%u %u", &hours, &interval) == 2) {
        uint64_t now  = (uint64_t)hours * 36000u;        /* tenths of uptime */
        uint64_t last = now >= interval ? now - interval : 0;  /* previous sighting */
        interval = (unsigned)(now - last);
#if   GATE == GATE_MIXED
        double dt = time_24(now) - time_improved(last);
#elif GATE == GATE_CONSISTENT
        double dt = time_24(now) - time_24(last);
#endif
        printf("%u %.4f %.4f %.4f %.7f\n", hours, now / 10.0, time_24(now),
               now / 10.0 - time_24(now), dt - interval / 10.0);
    }
    return 0;
}
