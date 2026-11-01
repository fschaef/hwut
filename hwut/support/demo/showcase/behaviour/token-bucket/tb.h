/* tb.h -- token-bucket rate limiter for firmware log messages:
 * 'rate' tokens per second, at most 'burst' tokens saved up.            */
#ifndef TB_H
#define TB_H
#include <stdint.h>

typedef struct {
    uint32_t rate;        /* tokens per second               */
    uint32_t burst;       /* bucket size, tokens             */
    uint32_t milli;       /* level, in 1/1000 token          */
    uint32_t last_ms;     /* time of the last refill         */
} tb_t;

void tb_init(tb_t* me, uint32_t rate, uint32_t burst, uint32_t now_ms);
int  tb_allow(tb_t* me, uint32_t now_ms);          /* 1: send, 0: drop  */
uint32_t tb_peek_milli(tb_t* me, uint32_t now_ms);  /* level now, for observers */
#endif
