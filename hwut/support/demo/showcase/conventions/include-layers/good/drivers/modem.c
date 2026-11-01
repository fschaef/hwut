#include <string.h>
#include "drivers/modem.h"
#include "hal/uart.h"
int modem_send(const char* at) { uart_send(at, strlen(at)); return 0; }
