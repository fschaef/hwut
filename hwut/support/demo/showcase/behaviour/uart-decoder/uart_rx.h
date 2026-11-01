/* uart_rx.h -- a UART receiver as it runs in a timer interrupt: one call
 * per sample of the RX pin, 4 samples per bit, 8 data bits, no parity,
 * 1 stop bit (8N1). Results are reported through three callbacks.       */
#ifndef UART_RX_H
#define UART_RX_H
#include <stdint.h>

#define UART_OVERSAMPLE 4

typedef struct {
    void (*on_sample)(long at, char what, int level); /* where it looked  */
    void (*on_byte)(long start, uint8_t value, int stop_ok);
    void (*on_glitch)(long start);                    /* start not confirmed */
} uart_sink_t;

typedef struct {
    int      state;      /* 0 idle, 1 start, 2 data, 3 stop */
    int      tick;       /* samples until the next look      */
    int      bit_n;
    uint8_t  shift;
    long     start;
    long     now;
    int      prev;
    const uart_sink_t* sink;
} uart_rx_t;

void uart_rx_init(uart_rx_t* me, const uart_sink_t* sink);
void uart_rx_sample(uart_rx_t* me, int level);
#endif
