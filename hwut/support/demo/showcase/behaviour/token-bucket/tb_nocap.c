/* tb_nocap.c -- BROKEN FIXTURE: the refill without the cap. Nobody notices
 * under steady load; after a quiet spell the bucket holds everything the
 * quiet time earned, and the next storm goes through unthrottled.       */
#include "tb.h"

void tb_init(tb_t* me, uint32_t rate, uint32_t burst, uint32_t now_ms)
{ me->rate = rate; me->burst = burst; me->milli = burst * 1000u; me->last_ms = now_ms; }

int tb_allow(tb_t* me, uint32_t now_ms)
{
    me->milli  += (now_ms - me->last_ms) * me->rate;   /* <-- no cap */
    me->last_ms = now_ms;
    if( me->milli < 1000u ) return 0;
    me->milli -= 1000u;
    return 1;
}

uint32_t tb_peek_milli(tb_t* me, uint32_t now_ms)
{ me->milli += (now_ms - me->last_ms) * me->rate; me->last_ms = now_ms; return me->milli; }
