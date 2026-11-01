/* drive.c -- argv: rate burst; stdin: 'R <ms>' a request, 'P <ms>' a look
 * at the level, times ascending. Prints 'R <ms> <1|0>' or 'P <ms> <milli>'. */
#include <stdio.h>
#include <stdlib.h>
#include "tb.h"

int main(int argc, char** argv)
{
    tb_t tb; long t; char what;
    tb_init(&tb, (uint32_t)atol(argv[1]), (uint32_t)atol(argv[2]), 0);
    while( scanf(" %c %ld", &what, &t) == 2 ) {
        if( what == 'R' ) printf("R %ld %d\n", t, tb_allow(&tb, (uint32_t)t));
        else              printf("P %ld %u\n", t, tb_peek_milli(&tb, (uint32_t)t));
    }
    return 0;
}
