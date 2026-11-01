/* decode.c -- reads a capture ('-' high, '_' low, one char per sample;
 * lines starting with '#' are notes) and prints what the receiver did:
 *   LOOK <sample> <S|0..7|T> <level>    BYTE <start> <hex> <ok|FERR>
 *   GLITCH <start>                                                      */
#include <stdio.h>
#include "uart_rx.h"

static void look(long at, char what, int level) { printf("LOOK %ld %c %d\n", at, what, level); }
static void byte(long start, uint8_t v, int ok)  { printf("BYTE %ld %02x %s\n", start, v, ok ? "ok" : "FERR"); }
static void glitch(long start)                  { printf("GLITCH %ld\n", start); }

int main(void)
{
    static const uart_sink_t sink = { look, byte, glitch };
    uart_rx_t rx;
    int c, bol = 1, comment = 0;
    uart_rx_init(&rx, &sink);
    while( (c = getchar()) != EOF ) {
        if( bol ) comment = (c == '#');
        bol = (c == '\n');
        if( comment ) continue;
        if( c == '-' || c == '_' ) uart_rx_sample(&rx, c == '-');
    }
    return 0;
}
