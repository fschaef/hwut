/* sim.c -- runs the watchdog on a simulated 1 ms clock. argv: timeout,
 * window, end; stdin: the times (ms) at which the task kicks, ascending.
 * Prints KICK <t>, RESET <t> <timeout|early-kick>, END <t>.               */
#include <stdio.h>
#include <stdlib.h>
#include "wdt.h"

int main(int argc, char** argv)
{
    long timeout = atol(argv[1]), window = atol(argv[2]), end = atol(argv[3]);
    long next_kick, t;
    int  have = scanf("%ld", &next_kick) == 1;
    wdt_start((uint16_t)timeout, (uint16_t)window);
    for( t = 1; t <= end; ++t ) {
        if( wdt_tick() == WDT_TIMEOUT ) { printf("RESET %ld timeout\n", t); return 0; }
        while( have && next_kick == t ) {
            printf("KICK %ld\n", t);
            if( wdt_kick() == WDT_EARLY_KICK ) { printf("RESET %ld early-kick\n", t); return 0; }
            have = scanf("%ld", &next_kick) == 1;
        }
    }
    printf("END %ld\n", end);
    return 0;
}
