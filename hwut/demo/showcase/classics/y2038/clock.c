/* clock.c -- a device clock: seconds since 1970-01-01 00:00:00 UTC in a
 * variable of type TIME_T (-DTIME_T=int32_t, as 32-bit Unix time_t was, or
 * int64_t), advanced by 'delta' seconds and shown as UTC.
 * Compile with -fwrapv: the int32_t addition then wraps as the CPU does.
 *
 * stdin:  lines 'start delta'   stdout: lines '<seconds> <YYYY-MM-DD hh:mm:ss>'
 * The calendar is computed here (days -> civil date, proleptic Gregorian),
 * not by the C library, so the result does not depend on the libc's gmtime. */
#include <stdio.h>
#include <stdint.h>

static void civil(int64_t t, char out[128])
{
    int64_t days = t >= 0 ? t / 86400 : -((-t + 86399) / 86400);
    int64_t sec  = t - days * 86400;
    int64_t z = days + 719468;                    /* H. Hinnant's algorithm */
    int64_t era = (z >= 0 ? z : z - 146096) / 146097;
    int64_t doe = z - era * 146097;
    int64_t yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    int64_t y   = yoe + era * 400;
    int64_t doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    int64_t mp  = (5 * doy + 2) / 153;
    int64_t d   = doy - (153 * mp + 2) / 5 + 1;
    int64_t m   = mp < 10 ? mp + 3 : mp - 9;
    snprintf(out, 128, "%04lld-%02lld-%02lld %02lld:%02lld:%02lld",
            (long long)(y + (m <= 2)), (long long)m, (long long)d,
            (long long)(sec / 3600), (long long)(sec / 60 % 60), (long long)(sec % 60));
}

int main(void)
{
    long long start, delta;
    char text[128];
    while (scanf("%lld %lld", &start, &delta) == 2) {
        TIME_T now = (TIME_T)start;
        now = now + (TIME_T)delta;               /* the clock ticks on       */
        civil((int64_t)now, text);
        printf("%lld %s\n", (long long)now, text);
    }
    return 0;
}
