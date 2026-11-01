/* filter.c -- first-order low-pass, "Grenzfrequenz" in comments is fine: ä ö ü */
#include "filter.h"

float filter_step(filter_t* f, float x)
{
    f->y += f->alpha * (x - f->y);
    return f->y;
}
