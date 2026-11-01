/* wdt_u8.c -- BROKEN FIXTURE: the same watchdog after a 'RAM diet' that made
 * the counter 8 bits wide. Fine for timeouts below 256 ms; with 300 ms the
 * count wraps from 255 to 0 and the timeout is never reached.              */
#include "wdt.h"

static uint16_t timeout, window;
static uint8_t  since_kick;                     /* <-- was uint16_t */

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
