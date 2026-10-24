/* sim.c -- argv: seconds to run; stdin: the seconds at which a car arrives
 * on EW. Prints '<t> <road> <RED|YELLOW|GREEN>' whenever a lamp changes, and
 * '<t> car EW' when the sensor sees a car.                                */
#include <stdio.h>
#include <stdlib.h>
#include "lights.h"

static void show(int t, const char* road, int c)
{ printf("%d s %s %s\n", t, road, c == RED ? "RED" : c == YELLOW ? "YELLOW" : "GREEN"); }

int main(int argc, char** argv)
{
    int end = atoi(argv[1]), t, next, have = scanf("%d", &next) == 1;
    lights_init(show);
    for( t = 1; t <= end; ++t ) {
        int car = 0;
        while( have && next == t ) { car = 1; have = scanf("%d", &next) == 1; }
        if( car ) printf("%d s car EW\n", t);
        lights_tick(t, car);
    }
    return 0;
}
