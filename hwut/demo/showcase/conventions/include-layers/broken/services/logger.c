#include <string.h>
#include "services/logger.h"
#include <hal/uart.h>
void log_line(const char* text) { uart_send(text, strlen(text)); }
