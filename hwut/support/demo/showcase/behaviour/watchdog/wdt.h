/* wdt.h -- a software model of a windowed watchdog, as it runs on the MCU:
 * wdt_tick() from the 1 ms timer interrupt, wdt_kick() from the task.     */
#ifndef WDT_H
#define WDT_H
#include <stdint.h>

enum { WDT_OK = 0, WDT_TIMEOUT = 1, WDT_EARLY_KICK = 2 };

void wdt_start(uint16_t timeout_ms, uint16_t window_ms); /* window 0: off */
int  wdt_kick(void);   /* returns WDT_EARLY_KICK inside the closed window */
int  wdt_tick(void);   /* returns WDT_TIMEOUT when the time is up        */
#endif
