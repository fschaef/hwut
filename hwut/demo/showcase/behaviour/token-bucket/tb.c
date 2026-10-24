/* tb.c -- refill by elapsed time, capped at the bucket size; a message
 * costs one token. Integer arithmetic only (milli-tokens).               */
#include "tb.h"

void tb_init(tb_t* me, uint32_t rate, uint32_t burst, uint32_t now_ms)
{ me->rate = rate; me->burst = burst; me->milli = burst * 1000u; me->last_ms = now_ms; }

static void refill(tb_t* me, uint32_t now_ms)
{
    uint32_t add = (now_ms - me->last_ms) * me->rate;      /* milli-tokens */
    me->milli    = me->milli + add > me->burst * 1000u ? me->burst * 1000u : me->milli + add;
    me->last_ms  = now_ms;
}

int tb_allow(tb_t* me, uint32_t now_ms)
{
    refill(me, now_ms);
    if( me->milli < 1000u ) return 0;
    me->milli -= 1000u;
    return 1;
}

uint32_t tb_peek_milli(tb_t* me, uint32_t now_ms)
{ refill(me, now_ms); return me->milli; }
