/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: EVERY COMBINATION OF A PARAMETER BASIS -- the port of
 *          'python/space_iterator.py': the cartesian product, the RIGHTMOST
 *          dimension changing fastest. The iterator yields INDICES, one per
 *          dimension, into the caller's own value arrays:
 *
 *     static const int   x[]    = { 0, 2, 4 };
 *     static const char* name[] = { "otto", "heinz" };
 *     size_t size[] = { 3, 2 }, at[2];
 *     SpaceIterator it;
 *     SpaceIterator_init(&it, size, 2);
 *     while( SpaceIterator_next(&it, at) ) run_test(x[at[0]], name[at[1]]);
 *
 * An empty basis (dimension_n 0) yields exactly one point, the empty one; a
 * basis with an empty dimension yields nothing -- as 'itertools.product'.
 * _____________________________________________________________________________
 */
#ifndef HWUT_SPACE_ITERATOR_H
#define HWUT_SPACE_ITERATOR_H

#include <stddef.h>

#define SPACE_ITERATOR_DIMENSION_MAX 32

typedef struct {
    size_t size[SPACE_ITERATOR_DIMENSION_MAX];
    size_t index[SPACE_ITERATOR_DIMENSION_MAX];
    size_t dimension_n;
    int    done_f;
} SpaceIterator;

void SpaceIterator_init(SpaceIterator* self, const size_t* size, size_t dimension_n);
int  SpaceIterator_next(SpaceIterator* self, size_t* at);

#endif
