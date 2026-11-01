/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: Every combination of a parameter basis -- see 'space_iterator.h'.
 * _____________________________________________________________________________
 */
#include "space_iterator.h"

void
SpaceIterator_init(SpaceIterator* self, const size_t* size, size_t dimension_n)
/* RETURN: nothing; the iterator stands before the first point.             */
{
    size_t i;
    self->dimension_n = dimension_n < SPACE_ITERATOR_DIMENSION_MAX ? dimension_n : SPACE_ITERATOR_DIMENSION_MAX;
    self->done_f      = 0;
    for(i = 0; i < self->dimension_n; ++i) {
        self->size[i]  = size[i];
        self->index[i] = 0;
        if( size[i] == 0 ) self->done_f = 1;           /* an empty dimension */
    }
}

int
SpaceIterator_next(SpaceIterator* self, size_t* at)
/* RETURN: 1, 'at' holds the next point -- one index per dimension; 0, every
 *         point was given.                                                 */
{
    size_t i;
    if( self->done_f ) return 0;
    for(i = 0; i < self->dimension_n; ++i) at[i] = self->index[i];
    /* THE ODOMETER: the rightmost index steps; one that wraps carries left. */
    for(i = self->dimension_n; i > 0; --i) {
        if( ++self->index[i - 1] < self->size[i - 1] ) return 1;
        self->index[i - 1] = 0;
    }
    self->done_f = 1;
    return 1;
}
