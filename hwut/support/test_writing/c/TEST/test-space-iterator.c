/* @hwut {
 *     title      = "space_iterator: every combination of a parameter basis"
 *     build      { framework = "make", executable = "%.exe" }
 *     choices {
 *         product { features = ["c-space"] }
 *         edges   { features = ["c-space"] }
 *     }
 *     interactive = true
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The C port of 'python/TEST/test-space-iterator.py', held against its
 *          GOOD files by '.link'. A basis is printed from string arrays; the
 *          iterator yields the indices.
 * _____________________________________________________________________________
 */
#include <stdio.h>
#include "hwut_runner.h"
#include "space_iterator.h"

static void banner(const char* label) { printf("\n--- %s ---\n", label); }

static void
points(const char* const* const* basis, const size_t* size, size_t dimension_n)
{
    SpaceIterator it; size_t at[SPACE_ITERATOR_DIMENSION_MAX], i; int n = 0;
    SpaceIterator_init(&it, size, dimension_n);
    while( SpaceIterator_next(&it, at) ) {
        printf("  (");
        for(i = 0; i < dimension_n; ++i) printf("%s%s", i ? ", " : "", basis[i][at[i]]);
        printf(")\n");
        n += 1;
    }
    printf("  %d point(s)\n", n);
}

static void
run_product(void)
{
    static const char* x[] = { "0", "2", "4" }, *name[] = { "otto", "heinz" }, *number[] = { "1", "2" };
    static const char* const* basis[] = { x, name, number };
    static const size_t size[] = { 3, 2, 2 };
    banner("[0, 2, 4] x [otto, heinz] x [1, 2] -- 3 * 2 * 2 points");
    points(basis, size, 3);
}

static void
run_edges(void)
{
    static const char* a[] = { "1", "2" }, *c[] = { "3" }, *letter[] = { "a", "b", "c" };
    static const char* const* with_empty[] = { a, NULL, c };
    static const char* const* one[]        = { letter };
    static const size_t size_empty[] = { 2, 0, 1 }, size_one[] = { 3 };
    banner("an EMPTY basis -- one point, the empty one");
    points(NULL, NULL, 0);
    banner("a basis with an EMPTY dimension -- nothing");
    points(with_empty, size_empty, 3);
    banner("ONE dimension -- its values one by one");
    points(one, size_one, 1);
}

int
main(int argc, char** argv)
{
    static const HwutRunner_Choice choice_list[] = {
        { "product", run_product }, { "edges", run_edges }, { NULL, NULL }
    };
    HwutRunner runner;
    HwutRunner_init(&runner, argc, argv, "space_iterator: every combination of a parameter basis",
                    choice_list);
    return HwutRunner_run(&runner);
}
