/* @hwut {
 *     title      = "DeterministicStream RNG and SelectionMarker spread"
 *     build      { framework = "make", executable = "%.exe" }
 *     choices {
 *         gauss      { features = ["c-random"] }
 *         primitives { features = ["c-random"] }
 *         ranges     { features = ["c-random"] }
 *         sample     { features = ["c-random"] }
 *         seed_sweep { features = ["c-random"] }
 *         select     { features = ["c-random"] }
 *         unchosen   { features = ["c-random"] }
 *     }
 *     interactive = true
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The C port of 'python/TEST/test-deterministic-random.py', choice
 *          for choice, held against its GOOD files by '.link'.
 * _____________________________________________________________________________
 */
#include <math.h>
#include <stdio.h>
#include "hwut_runner.h"
#include "hwut_pytext.h"
#include "deterministic_random.h"

#define SEED 0x42
static const char* TOLERANCE_REGION_BEGIN = "##! table numeric={1:1e-12}";
static const char* REGION_END             = "####";

static void banner(const char* label) { printf("\n--- %s ---\n", label); }

static DeterministicStream stream(void)
{ DeterministicStream s; DeterministicStream_init(&s, SEED); return s; }

static void
print_index_list(const size_t* index, size_t n)
{
    size_t i;
    printf("[");
    for(i = 0; i < n; ++i) printf("%s%zu", i ? ", " : "", index[i]);
    printf("]\n");
}

static void
run_primitives(void)
{
    DeterministicStream s; char text[64]; int i;
    banner("next_int(0, 1000000) -- first 20");
    s = stream();
    for(i = 0; i < 20; ++i) printf("[%02d] %lld\n", i, (long long)DeterministicStream_next_int(&s, 0, 1000000));
    banner("next_float -- first 10 (full precision)");
    s = stream();
    for(i = 0; i < 10; ++i)
        printf("[%02d] %s\n", i, pytext_float_repr(text, sizeof(text), DeterministicStream_next_float(&s)));
    banner("coin(0.5) -- 40 draws");
    s = stream();
    for(i = 0; i < 40; ++i) printf("%s%s", i ? " " : "", DeterministicStream_coin(&s, 0.5) ? "T" : "F");
    printf("\n");
}

static void
run_ranges(void)
{
    DeterministicStream s; int i;
    banner("next_int(0, 9) -- 30 draws");
    s = stream();
    for(i = 0; i < 30; ++i) printf("%s%lld", i ? " " : "", (long long)DeterministicStream_next_int(&s, 0, 9));
    printf("\n");
    banner("next_int(5, 5) -- degenerate range returns the bound");
    s = stream();
    for(i = 0; i < 5; ++i) printf("%s%lld", i ? " " : "", (long long)DeterministicStream_next_int(&s, 5, 5));
    printf("\n");
    banner("next_int(-3, 3) -- spanning zero");
    s = stream();
    for(i = 0; i < 20; ++i) printf("%s%+lld", i ? " " : "", (long long)DeterministicStream_next_int(&s, -3, 3));
    printf("\n");
}

static void
run_gauss(void)
{
    DeterministicStream s; char text[64]; int i;
    banner("gauss(0, 1) -- 10 draws (full precision)");
    s = stream();
    printf("%s\n", TOLERANCE_REGION_BEGIN);
    for(i = 0; i < 10; ++i)
        printf("[%02d] %s\n", i, pytext_float_repr(text, sizeof(text),
               DeterministicStream_gauss(&s, 0.0, 1.0, -INFINITY, INFINITY)));
    printf("%s\n", REGION_END);
    banner("gauss(0, 1) clamped to [-1, 1]");
    s = stream();
    printf("%s\n", TOLERANCE_REGION_BEGIN);
    for(i = 0; i < 10; ++i)
        printf("[%02d] %s\n", i, pytext_float_repr(text, sizeof(text),
               DeterministicStream_gauss(&s, 0.0, 1.0, -1.0, 1.0)));
    printf("%s\n", REGION_END);
    banner("gauss_int(100, 15) -- 20 draws");
    s = stream();
    for(i = 0; i < 20; ++i)
        printf("%s%lld", i ? " " : "",
               (long long)DeterministicStream_gauss_int(&s, 100.0, 15.0, -INFINITY, INFINITY));
    printf("\n");
}

static void
run_sample(void)
{
    static const char* pool[] = { "alpha", "beta", "gamma", "delta", "epsilon" };
    static const char  letter[] = "ABCDEFGH";
    DeterministicStream s; size_t index[20]; char text[16]; int i;
    banner("sample_indices(10, 10) -- full permutation");
    s = stream(); DeterministicStream_sample_indices(&s, 10, 10, index); print_index_list(index, 10);
    banner("sample_indices(20, 5) -- partial draw");
    s = stream(); DeterministicStream_sample_indices(&s, 20, 5, index); print_index_list(index, 5);
    banner("choice from a list -- 20 draws");
    s = stream();
    for(i = 0; i < 20; ++i) printf("%s%s", i ? " " : "", pool[DeterministicStream_choice(&s, 5)]);
    printf("\n");
    banner("sample(list, 4) -- unique elements");
    s = stream(); DeterministicStream_sample_indices(&s, 8, 4, index);
    printf("[");
    for(i = 0; i < 4; ++i) {
        char one[2] = { letter[index[i]], '\0' };
        printf("%s%s", i ? ", " : "", pytext_str_repr(text, sizeof(text), one));
    }
    printf("]\n");
}

static void
run_select(void)
{
    static const char* pool[]   = { "a", "b", "c", "d" };
    static const char* branch[] = { "p", "q", "r" };
    DeterministicStream s; int i;
    banner("select over a list -- 20 draws");
    s = stream();
    for(i = 0; i < 20; ++i) printf("%s%s", i ? " " : "", pool[DeterministicStream_select(&s, 4)]);
    printf("\n");
    banner("select over a tuple -- 12 draws");
    s = stream();
    for(i = 0; i < 12; ++i) printf("%s%s", i ? " " : "", branch[DeterministicStream_select(&s, 3)]);
    printf("\n");
}

static const char* A = "a"; static const char* B = "b";
static const char* C = "c"; static const char* D = "d";

static const char*
unchosen(DeterministicStream* s, const char** pool, size_t n, SelectionMarker* m)
{ return (const char*)DeterministicStream_select_unchosen(s, (const void* const*)pool, n, m); }

static void
run_unchosen(void)
{
    DeterministicStream s; SelectionMarker m; int i;
    const char* pool[] = { A, B, C, D };
    banner("stable pool -- three full cycles of 4 elements");
    s = stream(); SelectionMarker_init(&m);
    for(i = 0; i < 12; ++i) printf("%s%s", i ? " " : "", unchosen(&s, pool, 4, &m));
    printf("\n");

    banner("FRESH container each call -- identical to the stable pool above");
    s = stream(); SelectionMarker_init(&m);
    for(i = 0; i < 12; ++i) {
        const char* fresh[] = { A, B, C, D };          /* a new array every call */
        printf("%s%s", i ? " " : "", unchosen(&s, fresh, 4, &m));
    }
    printf("\n");

    banner("sub-pool coherence -- draw from [a,b] then the full [a,b,c,d]");
    s = stream(); SelectionMarker_init(&m);
    {
        const char* full[] = { A, B, C, D };
        const char* sub[]  = { A, B };
        const char* first  = unchosen(&s, sub, 2, &m);
        printf("first(from sub): %s  then(from full):", first);
        for(i = 0; i < 3; ++i) printf(" %s", unchosen(&s, full, 4, &m));
        printf("\n");
    }

    banner("reset() restarts the cycle");
    s = stream(); SelectionMarker_init(&m);
    {
        const char* before[4]; const char* after[4];
        for(i = 0; i < 4; ++i) before[i] = unchosen(&s, pool, 4, &m);
        SelectionMarker_reset(&m);
        for(i = 0; i < 4; ++i) after[i] = unchosen(&s, pool, 4, &m);
        printf("before reset:"); for(i = 0; i < 4; ++i) printf(" %s", before[i]); printf("\n");
        printf("after  reset:"); for(i = 0; i < 4; ++i) printf(" %s", after[i]);  printf("\n");
    }
}

static void
run_seed_sweep(void)
{
    int seed;
    banner("first next_int(0, 1000000) per seed 0..15");
    for(seed = 0; seed < 16; ++seed) {
        DeterministicStream s; DeterministicStream_init(&s, seed);
        printf("seed=%2d -> %lld\n", seed, (long long)DeterministicStream_next_int(&s, 0, 1000000));
    }
}

int
main(int argc, char** argv)
{
    static const HwutRunner_Choice choice_list[] = {
        { "primitives", run_primitives }, { "ranges",   run_ranges },
        { "gauss",      run_gauss },      { "sample",   run_sample },
        { "select",     run_select },     { "unchosen", run_unchosen },
        { "seed_sweep", run_seed_sweep }, { NULL, NULL }
    };
    HwutRunner runner;
    HwutRunner_init(&runner, argc, argv, "DeterministicStream RNG and SelectionMarker spread",
                    choice_list);
    return HwutRunner_run(&runner);
}
