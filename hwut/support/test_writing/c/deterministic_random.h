/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: A RANDOM STREAM THAT IS THE SAME EVERYWHERE -- the port of
 *          'python/deterministic_random.py'. The same seed gives the same
 *          numbers as the Python module, draw for draw: Park-Miller MINSTD,
 *          'state = 48271 * state mod (2^31 - 1)'.
 *
 *     DeterministicStream s;
 *     DeterministicStream_init(&s, 0x42);
 *     DeterministicStream_next_int(&s, 0, 9);
 *     DeterministicStream_next_float(&s);          DeterministicStream_coin(&s, 0.5);
 *     pool[DeterministicStream_select(&s, pool_n)];  -- an index
 *     DeterministicStream_gauss(&s, 0.0, 1.0, -INFINITY, INFINITY);
 *     DeterministicStream_sample_indices(&s, 10, 3, out);
 *
 *     SelectionMarker m;   SelectionMarker_init(&m);
 *     DeterministicStream_select_unchosen(&s, (const void**)pool, pool_n, &m);
 *
 * IDENTITY, AS IN PYTHON: a marker remembers a candidate by its ADDRESS --
 * what 'id()' is in Python. Two string literals of one text are commonly one
 * object in C, as two equal short strings are in Python.
 *
 * 'gauss' is the one path through libm: a last bit may differ between
 * platforms, so a GOOD that prints a draw tolerates the last digits.
 * _____________________________________________________________________________
 */
#ifndef HWUT_DETERMINISTIC_RANDOM_H
#define HWUT_DETERMINISTIC_RANDOM_H

#include <stdint.h>
#include <stddef.h>

#define SELECTION_MARKER_MAX 256

typedef struct {
    const void* chosen[SELECTION_MARKER_MAX];
    size_t      chosen_n;
} SelectionMarker;

void SelectionMarker_init(SelectionMarker* self);
void SelectionMarker_reset(SelectionMarker* self);
int  SelectionMarker_seen_f(const SelectionMarker* self, const void* candidate);

typedef struct {
    int64_t state;
} DeterministicStream;

void    DeterministicStream_init(DeterministicStream* self, int64_t seed);
int64_t DeterministicStream_next_int(DeterministicStream* self, int64_t v_min, int64_t v_max);
double  DeterministicStream_next_float(DeterministicStream* self);
int     DeterministicStream_coin(DeterministicStream* self, double probability_of_true);
size_t  DeterministicStream_select(DeterministicStream* self, size_t candidate_n);
size_t  DeterministicStream_choice(DeterministicStream* self, size_t candidate_n);
const void* DeterministicStream_select_unchosen(DeterministicStream* self, const void* const* candidate,
                                                size_t candidate_n, SelectionMarker* marker);
double  DeterministicStream_gauss(DeterministicStream* self, double mu, double sigma,
                                  double lower, double upper);
int64_t DeterministicStream_gauss_int(DeterministicStream* self, double mu, double sigma,
                                      double lower, double upper);
void    DeterministicStream_sample_indices(DeterministicStream* self, size_t population_size,
                                           size_t k, size_t* out);

#endif
