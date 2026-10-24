#include <string.h>
#include "drivers/modem.h"
#include "hal/uart.h"
#include <app/app_config.h>
int modem_send(const char* at) { uart_send(at, strlen(at)); return APP_TELEMETRY_PERIOD_MS > 0 ? 0 : -1; }
