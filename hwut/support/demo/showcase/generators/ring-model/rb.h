typedef struct { unsigned char buf[64]; unsigned cap, head, tail, n; } rb_t;
void rb_init(rb_t *rb, unsigned cap);
int  rb_push(rb_t *rb, unsigned char b);
int  rb_pop(rb_t *rb, unsigned char *b);
