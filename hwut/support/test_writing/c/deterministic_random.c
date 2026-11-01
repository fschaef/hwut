/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The deterministic random stream -- see 'deterministic_random.h'.
 * _____________________________________________________________________________
 */
#include "deterministic_random.h"

#include <assert.h>
#include <math.h>
#include <stdlib.h>

#ifndef M_PI
#   define M_PI 3.14159265358979323846
#endif

void
SelectionMarker_init(SelectionMarker* self)
/* RETURN: nothing; nothing is chosen yet.                                  */
{ self->chosen_n = 0; }

void
SelectionMarker_reset(SelectionMarker* self)
/* RETURN: nothing; every chosen candidate is forgotten.                    */
{ self->chosen_n = 0; }

int
SelectionMarker_seen_f(const SelectionMarker* self, const void* candidate)
/* RETURN: 1 where 'candidate' (by address) was chosen; 0 else.             */
{
    size_t i;
    for(i = 0; i < self->chosen_n; ++i) if( self->chosen[i] == candidate ) return 1;
    return 0;
}

void
DeterministicStream_init(DeterministicStream* self, int64_t seed)
/* RETURN: nothing; the stream stands at 'seed'.                            */
{ self->state = seed & 0x7FFFFFFF; }

int64_t
DeterministicStream_next_int(DeterministicStream* self, int64_t v_min, int64_t v_max)
/* RETURN: an integer uniform in [v_min, v_max]; the state steps even where
 *         the range is one value.                                          */
{
    self->state = (48271 * self->state) % 2147483647;
    if( v_min == v_max ) return v_min;
    return v_min + (self->state % (v_max - v_min + 1));
}

double
DeterministicStream_next_float(DeterministicStream* self)
/* RETURN: a number in [0, 1): 'next_int(0, 1000000) / 1000001'.           */
{ return (double)DeterministicStream_next_int(self, 0, 1000000) / 1000001.0; }

int
DeterministicStream_coin(DeterministicStream* self, double probability_of_true)
/* RETURN: 1 with 'probability_of_true', 0 else.                            */
{ return DeterministicStream_next_float(self) < probability_of_true; }

size_t
DeterministicStream_select(DeterministicStream* self, size_t candidate_n)
/* RETURN: an index into 'candidate_n' candidates, uniformly drawn.         */
{ return (size_t)DeterministicStream_next_int(self, 0, (int64_t)candidate_n - 1); }

size_t
DeterministicStream_choice(DeterministicStream* self, size_t candidate_n)
/* RETURN: an index into 'candidate_n' elements, uniformly drawn.           */
{ return DeterministicStream_select(self, candidate_n); }

const void*
DeterministicStream_select_unchosen(DeterministicStream* self, const void* const* candidate,
                                    size_t candidate_n, SelectionMarker* marker)
/* RETURN: a candidate the marker has not seen, uniformly drawn among those,
 *         recorded in the marker; where every one was seen, the marker is
 *         reset and the draw is over all.                                  */
{
    const void* unchosen[SELECTION_MARKER_MAX];
    size_t      n = 0, i;
    const void* choice;
    for(i = 0; i < candidate_n; ++i)
        if( ! SelectionMarker_seen_f(marker, candidate[i]) ) unchosen[n++] = candidate[i];
    if( n == 0 ) {
        SelectionMarker_reset(marker);
        for(i = 0; i < candidate_n; ++i) unchosen[n++] = candidate[i];
    }
    choice = unchosen[DeterministicStream_next_int(self, 0, (int64_t)n - 1)];
    if( marker->chosen_n < SELECTION_MARKER_MAX ) marker->chosen[marker->chosen_n++] = choice;
    return choice;
}

double
DeterministicStream_gauss(DeterministicStream* self, double mu, double sigma,
                          double lower, double upper)
/* RETURN: a draw of the normal distribution (mu, sigma) by Box-Muller,
 *         clipped to [lower, upper] (-INFINITY, INFINITY for none).        */
{
    double u1 = DeterministicStream_next_float(self) + 1e-9;
    double u2 = DeterministicStream_next_float(self);
    double z0 = sqrt(-2.0 * log(u1)) * cos(2.0 * M_PI * u2);
    double result = z0 * sigma + mu;
    if( result < lower ) return lower;
    if( result > upper ) return upper;
    return result;
}

int64_t
DeterministicStream_gauss_int(DeterministicStream* self, double mu, double sigma,
                              double lower, double upper)
/* RETURN: 'gauss' rounded to the nearest integer, a half to the even one --
 *         as Python's 'round'.                                             */
{ return (int64_t)nearbyint(DeterministicStream_gauss(self, mu, sigma, lower, upper)); }

void
DeterministicStream_sample_indices(DeterministicStream* self, size_t population_size,
                                   size_t k, size_t* out)
/* RETURN: nothing; 'out' holds 'k' distinct indices of 0 .. population_size-1,
 *         drawn by Fisher-Yates.                                           */
{
    size_t* index = malloc(sizeof(size_t) * population_size);
    size_t  i;
    assert(population_size >= k);
    for(i = 0; i < population_size; ++i) index[i] = i;
    for(i = 0; i < k; ++i) {
        size_t j = (size_t)DeterministicStream_next_int(self, (int64_t)i, (int64_t)population_size - 1);
        size_t t = index[i]; index[i] = index[j]; index[j] = t;
        out[i] = index[i];
    }
    free(index);
}
