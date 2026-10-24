/* debounce.h -- a push-button debouncer for a 1 ms sampling tick. */
#ifndef DEBOUNCE_H
#define DEBOUNCE_H
#include <stdint.h>

typedef struct {
    uint8_t out;        /* the debounced level, 0 or 1            */
    uint8_t count;      /* samples in a row that disagree with it */
    uint8_t aux;        /* free for the implementation            */
    uint8_t threshold;  /* samples it takes to accept a new level */
} deb_t;

void    deb_init(deb_t* me, uint8_t threshold);
uint8_t deb_sample(deb_t* me, uint8_t raw);   /* call once per tick */
#endif
