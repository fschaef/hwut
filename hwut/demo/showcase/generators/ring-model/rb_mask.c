/* rb_mask.c -- the "fast" rb.c: wraps the index with a mask instead of %. */
#include "rb.h"

void rb_init(rb_t *rb, unsigned cap) { rb->cap = cap; rb->head = rb->tail = rb->n = 0; }

int rb_push(rb_t *rb, unsigned char b)
{
    if (rb->n == rb->cap) return -1;
    rb->buf[rb->head] = b;
    rb->head = (rb->head + 1) & (rb->cap - 1);
    ++rb->n;
    return 0;
}

int rb_pop(rb_t *rb, unsigned char *b)
{
    if (rb->n == 0) return -1;
    *b = rb->buf[rb->tail];
    rb->tail = (rb->tail + 1) & (rb->cap - 1);
    --rb->n;
    return 0;
}
