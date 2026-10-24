/* rtc.c -- MODEL of ConvertDays() from the real-time-clock driver of the
 * Microsoft Zune 30 (Freescale MC13783 PMIC code), the routine that froze
 * every Zune 30 on 31 December 2008. The year loop is the original's; the
 * month part is written out plainly.
 *
 * FIXED=0: the loop as shipped.  FIXED=1: a leap year with days == 366
 * ends the loop (the year is complete).
 *
 * argv[1] = 'trace': print every iteration of the year loop as
 *     'loop <n> year <y> days <d>'   (stdout is flushed per line)
 * stdin: day numbers, 1 = 1980-01-01.  stdout: 'date YYYY-MM-DD' per day. */
#include <stdio.h>
#include <string.h>

#define ORIGINYEAR 1980

static int IsLeapYear(int year)
{
    return (year % 4 == 0 && year % 100 != 0) || year % 400 == 0;
}

static void ConvertDays(unsigned days, int trace, int* y, int* m, int* d)
{
    static const int month_tab[2][12] = {
        { 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31 },
        { 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31 } };
    int year = ORIGINYEAR, month = 0;
    unsigned long loop = 0;

    while (days > 365)
    {
        if (trace) { printf("loop %lu year %d days %u\n", ++loop, year, days); fflush(stdout); }
        if (IsLeapYear(year))
        {
            if (days > 366)
            {
                days -= 366;
                year += 1;
            }
#if FIXED
            else break;                 /* day 366 of a leap year: done   */
#endif
        }
        else
        {
            days -= 365;
            year += 1;
        }
    }
    while (days > (unsigned)month_tab[IsLeapYear(year)][month])
        days -= month_tab[IsLeapYear(year)][month++];
    *y = year; *m = month + 1; *d = (int)days;
}

int main(int argc, char** argv)
{
    int      trace = argc > 1 && strcmp(argv[1], "trace") == 0;
    unsigned days;
    int      y, m, d;
    while (scanf("%u", &days) == 1) {
        ConvertDays(days, trace, &y, &m, &d);
        printf("date %04d-%02d-%02d\n", y, m, d);
        fflush(stdout);
    }
    return 0;
}
