/* counters.c -- three counters of fixed width, as deployed, and widened.
 *
 * Reads lines '<kind> <true value>' from stdin, stores the true value into
 * the counter as the device does, and prints what the device decodes from
 * the counter:
 *
 *   gcu  <centiseconds of power>   Boeing 787 generator control unit:
 *                                  a signed 32-bit centisecond counter
 *                                  (WIDE: 64-bit). Decoded: seconds of
 *                                  power; a negative counter is a fault.
 *   gps  <weeks since 1980-01-06>  GPS week number: 10 bits on the wire
 *                                  (WIDE: 13 bits, as in CNAV). Decoded:
 *                                  the week the receiver believes it is.
 *   y2k  <year>                    a two-digit year field (WIDE: four
 *                                  digits). Decoded: the year.
 *
 * Output: '<kind> <raw counter> <decoded>' per line.
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#ifndef WIDE
#   define WIDE 0
#endif

int
main(void)
{
    char    kind[8];
    int64_t value;

    while( scanf("%7s %lld", kind, (long long*)&value) == 2 ) {
        if( strcmp(kind, "gcu") == 0 ) {
#           if WIDE
            int64_t counter = value;
#           else
            int32_t counter = (int32_t)(uint32_t)value;   /* wraps at 2^31 */
#           endif
            printf("gcu %lld %lld\n", (long long)counter, (long long)(counter / 100));
        }
        else if( strcmp(kind, "gps") == 0 ) {
#           if WIDE
            int64_t week = value & 0x1FFF;
#           else
            int64_t week = value & 0x3FF;                   /* 10 bits */
#           endif
            printf("gps %lld %lld\n", (long long)week, (long long)week);
        }
        else if( strcmp(kind, "y2k") == 0 ) {
#           if WIDE
            int64_t field = value;
            int64_t year  = field;
#           else
            int64_t field = value % 100;                    /* two digits */
            int64_t year  = 1900 + field;
#           endif
            printf("y2k %lld %lld\n", (long long)field, (long long)year);
        }
    }
    return 0;
}
