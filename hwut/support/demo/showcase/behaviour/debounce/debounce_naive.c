/* debounce_naive.c -- BROKEN FIXTURE: the 'two samples agree' filter from
 * an old code base. It rejects a one-sample spike and nothing longer:
 * contact bounce of two or three milliseconds goes straight through.     */
#include "debounce.h"

void deb_init(deb_t* me, uint8_t threshold)
{ me->out = 0; me->count = 0; me->aux = 0; me->threshold = threshold; }

uint8_t deb_sample(deb_t* me, uint8_t raw)
{
    if( raw == me->aux ) me->out = raw;   /* aux: the previous raw sample */
    me->aux = raw;
    return me->out;
}
