/* uart.h -- UART driver, module prefix UART_ */
#ifndef UART_H
#define UART_H

#include <stdint.h>

#define UART_BAUD_DEFAULT   115200u
#define UART_FIFO_DEPTH     16u
#define UART_FLAG_OVERRUN   (1u << 3)
#define UART_IS_READY(u)    (((u)->status & 1u) != 0u)

void uart_init(uint32_t baud);

#endif /* UART_H */
