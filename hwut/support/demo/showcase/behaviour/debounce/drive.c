/* drive.c -- feeds a raw waveform ('_' low, '-' high, one char per 1 ms
 * tick) from stdin through the debouncer and prints the output waveform. */
#include <stdio.h>
#include <stdlib.h>
#include "debounce.h"

int main(int argc, char** argv)
{
    deb_t deb;
    int   c;
    deb_init(&deb, (uint8_t)(argc > 1 ? atoi(argv[1]) : 5));
    while( (c = getchar()) != EOF ) {
        if( c != '_' && c != '-' ) continue;
        putchar(deb_sample(&deb, c == '-') ? '-' : '_');
    }
    putchar('\n');
    return 0;
}
