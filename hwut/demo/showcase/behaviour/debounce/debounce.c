/* debounce.c -- integrating debouncer: the output follows the raw level
 * only after 'threshold' consecutive samples agree on the new level. Any
 * sample of the old level in between starts the count again.            */
#include "debounce.h"

void deb_init(deb_t* me, uint8_t threshold)
{ me->out = 0; me->count = 0; me->aux = 0; me->threshold = threshold; }

uint8_t deb_sample(deb_t* me, uint8_t raw)
{
    if( raw == me->out ) {
        me->count = 0;
    } else if( ++(me->count) >= me->threshold ) {
        me->out   = raw;
        me->count = 0;
    }
    return me->out;
}
