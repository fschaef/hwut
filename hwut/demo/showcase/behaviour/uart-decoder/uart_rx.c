/* uart_rx.c -- 8N1 receiver, 4x oversampling, majority-free mid-bit look.
 *
 *   idle:  a falling edge (1 -> 0) starts a frame candidate.
 *   start: look again in the middle of the start bit; still low => a
 *          frame, else a glitch.
 *   data:  8 looks, one bit time apart, LSB first.
 *   stop:  one look; high => byte ok, low => framing error. Back to idle
 *          either way; a new frame needs a new falling edge.            */
#include "uart_rx.h"

enum { IDLE, START, DATA, STOP };

void uart_rx_init(uart_rx_t* me, const uart_sink_t* sink)
{ me->state = IDLE; me->tick = 0; me->bit_n = 0; me->shift = 0;
  me->start = 0; me->now = -1; me->prev = 1; me->sink = sink; }

void uart_rx_sample(uart_rx_t* me, int level)
{
    ++(me->now);
    switch( me->state ) {
    case IDLE:
        if( me->prev == 1 && level == 0 ) {
            me->state = START; me->start = me->now;
            me->tick  = UART_OVERSAMPLE / 2 - 1;     /* mid of start bit */
        }
        break;
    case START:
        if( me->tick-- ) break;
        me->sink->on_sample(me->now, 'S', level);
        if( level != 0 ) { me->sink->on_glitch(me->start); me->state = IDLE; break; }
        me->state = DATA; me->bit_n = 0; me->shift = 0; me->tick = UART_OVERSAMPLE - 1;
        break;
    case DATA:
        if( me->tick-- ) break;
        me->sink->on_sample(me->now, (char)('0' + me->bit_n), level);
        me->shift |= (uint8_t)(level << me->bit_n);
        me->tick = UART_OVERSAMPLE - 1;
        if( ++(me->bit_n) == 8 ) me->state = STOP;
        break;
    case STOP:
        if( me->tick-- ) break;
        me->sink->on_sample(me->now, 'T', level);
        me->sink->on_byte(me->start, me->shift, level == 1);
        me->state = IDLE;
        break;
    }
    me->prev = level;
}
