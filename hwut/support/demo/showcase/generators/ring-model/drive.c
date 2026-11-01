/* drive.c -- script on stdin: 'cap N' starts a fresh FIFO, '+ v' pushes,
 * '-' pops. Prints one answer per operation: 'ok', 'full', 'v' or 'empty'. */
#include <stdio.h>
#include "rb.h"
int main(void)
{
    rb_t rb; char op[8]; unsigned v; unsigned char b;
    while (scanf("%7s", op) == 1) {
        if (op[0] == 'c')      { if (scanf("%u", &v) != 1) return 1; rb_init(&rb, v); }
        else if (op[0] == '+') { if (scanf("%u", &v) != 1) return 1; puts(rb_push(&rb, (unsigned char)v) ? "full" : "ok"); }
        else                   { if (rb_pop(&rb, &b)) puts("empty"); else printf("%u\n", b); }
    }
    return 0;
}
