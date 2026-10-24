/* wdt.c -- the watchdog counts milliseconds since the last kick. A kick
 * restarts the count; a count that reaches the timeout resets the MCU. With
 * a window, a kick that comes sooner than 'window' ms after the previous one
 * resets too: a task stuck in a tight loop that kicks is not a healthy task. */
#include "wdt.h"

static uint16_t timeout, window, since_kick;

void wdt_start(uint16_t timeout_ms, uint16_t window_ms)
{ timeout = timeout_ms; window = window_ms; since_kick = 0; }

int wdt_kick(void)
{
    if( window && since_kick < window ) return WDT_EARLY_KICK;
    since_kick = 0;
    return WDT_OK;
}

int wdt_tick(void)
{
    if( ++since_kick >= timeout ) return WDT_TIMEOUT;
    return WDT_OK;
}
