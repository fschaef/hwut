#include <stddef.h>
#include "hal/uart.h"
#include "logger.h"
void uart_send(const char* data, size_t n) { (void)data; if (n > 256) log_line("uart: long frame"); }
