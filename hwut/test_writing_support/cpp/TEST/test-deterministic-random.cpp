/* @hwut {
 *     title      = "DeterministicStream RNG and SelectionMarker spread"
 *     build      { framework = "make", executable = "%.exe" }
 *     choices {
 *         gauss      { features = ["cpp-random"] }
 *         primitives { features = ["cpp-random"] }
 *         ranges     { features = ["cpp-random"] }
 *         sample     { features = ["cpp-random"] }
 *         seed_sweep { features = ["cpp-random"] }
 *         select     { features = ["cpp-random"] }
 *         unchosen   { features = ["cpp-random"] }
 *     }
 *     interactive = true
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The C++ port of 'python/TEST/test-deterministic-random.py', choice
 *          for choice, held against its GOOD files by '.link'.
 * _____________________________________________________________________________
 */
#include <array>
#include <cstdio>
#include <string>
#include <vector>
#include "hwut_runner.hpp"
#include "hwut_pytext.hpp"
#include "deterministic_random.hpp"

using hwut::DeterministicStream;
using hwut::SelectionMarker;
using hwut::pytext::repr;

static const int64_t SEED = 0x42;
static const char*   TOLERANCE_REGION_BEGIN = "##! table numeric={1:1e-12}";
static const char*   REGION_END             = "####";

static void banner(const std::string& label) { std::printf("\n--- %s ---\n", label.c_str()); }

template <class T>
static void
print_joined(const std::vector<T>& list)
/* RETURN: nothing; the elements were printed, blank-separated, a newline. */
{
    for(size_t i = 0; i < list.size(); ++i) std::printf("%s%s", i ? " " : "", std::string(list[i]).c_str());
    std::printf("\n");
}

static void
run_primitives()
{
    banner("next_int(0, 1000000) -- first 20");
    DeterministicStream s(SEED);
    for(int i = 0; i < 20; ++i) std::printf("[%02d] %lld\n", i, (long long)s.next_int(0, 1000000));
    banner("next_float -- first 10 (full precision)");
    s = DeterministicStream(SEED);
    for(int i = 0; i < 10; ++i) std::printf("[%02d] %s\n", i, repr(s.next_float()).c_str());
    banner("coin(0.5) -- 40 draws");
    s = DeterministicStream(SEED);
    for(int i = 0; i < 40; ++i) std::printf("%s%s", i ? " " : "", s.coin(0.5) ? "T" : "F");
    std::printf("\n");
}

static void
run_ranges()
{
    banner("next_int(0, 9) -- 30 draws");
    DeterministicStream s(SEED);
    for(int i = 0; i < 30; ++i) std::printf("%s%lld", i ? " " : "", (long long)s.next_int(0, 9));
    std::printf("\n");
    banner("next_int(5, 5) -- degenerate range returns the bound");
    s = DeterministicStream(SEED);
    for(int i = 0; i < 5; ++i) std::printf("%s%lld", i ? " " : "", (long long)s.next_int(5, 5));
    std::printf("\n");
    banner("next_int(-3, 3) -- spanning zero");
    s = DeterministicStream(SEED);
    for(int i = 0; i < 20; ++i) std::printf("%s%+lld", i ? " " : "", (long long)s.next_int(-3, 3));
    std::printf("\n");
}

static void
run_gauss()
{
    banner("gauss(0, 1) -- 10 draws (full precision)");
    DeterministicStream s(SEED);
    std::printf("%s\n", TOLERANCE_REGION_BEGIN);
    for(int i = 0; i < 10; ++i) std::printf("[%02d] %s\n", i, repr(s.gauss(0.0, 1.0)).c_str());
    std::printf("%s\n", REGION_END);
    banner("gauss(0, 1) clamped to [-1, 1]");
    s = DeterministicStream(SEED);
    std::printf("%s\n", TOLERANCE_REGION_BEGIN);
    for(int i = 0; i < 10; ++i) std::printf("[%02d] %s\n", i, repr(s.gauss(0.0, 1.0, -1.0, 1.0)).c_str());
    std::printf("%s\n", REGION_END);
    banner("gauss_int(100, 15) -- 20 draws");
    s = DeterministicStream(SEED);
    for(int i = 0; i < 20; ++i) std::printf("%s%lld", i ? " " : "", (long long)s.gauss_int(100.0, 15.0));
    std::printf("\n");
}

static void
run_sample()
{
    const std::vector<std::string> pool   = { "alpha", "beta", "gamma", "delta", "epsilon" };
    const std::vector<std::string> letter = { "A", "B", "C", "D", "E", "F", "G", "H" };
    banner("sample_indices(10, 10) -- full permutation");
    DeterministicStream s(SEED);
    std::printf("%s\n", repr(s.sample_indices(10, 10)).c_str());
    banner("sample_indices(20, 5) -- partial draw");
    s = DeterministicStream(SEED);
    std::printf("%s\n", repr(s.sample_indices(20, 5)).c_str());
    banner("choice from a list -- 20 draws");
    s = DeterministicStream(SEED);
    std::vector<std::string> drawn;
    for(int i = 0; i < 20; ++i) drawn.push_back(s.choice(pool));
    print_joined(drawn);
    banner("sample(list, 4) -- unique elements");
    s = DeterministicStream(SEED);
    std::printf("%s\n", repr(s.sample(letter, 4)).c_str());
}

static void
run_select()
{
    const std::vector<std::string>   pool   = { "a", "b", "c", "d" };
    const std::array<std::string, 3> branch = { { "p", "q", "r" } };
    banner("select over a list -- 20 draws");
    DeterministicStream      s(SEED);
    std::vector<std::string> drawn;
    for(int i = 0; i < 20; ++i) drawn.push_back(s.select(pool));
    print_joined(drawn);
    banner("select over a tuple -- 12 draws");
    s = DeterministicStream(SEED);
    drawn.clear();
    for(int i = 0; i < 12; ++i) drawn.push_back(s.select(branch));
    print_joined(drawn);
}

/* THE CANDIDATES ARE OBJECTS, their identity what the marker remembers: four
 * texts, pointed to by every pool below -- as Python's four strings are.  */
static const char* const A = "a";
static const char* const B = "b";
static const char* const C = "c";
static const char* const D = "d";

static void
run_unchosen()
{
    using Pool = std::vector<const char*>;
    const Pool pool = { A, B, C, D };
    banner("stable pool -- three full cycles of 4 elements");
    DeterministicStream s(SEED);
    SelectionMarker     m;
    Pool                drawn;
    for(int i = 0; i < 12; ++i) drawn.push_back(s.select_unchosen(pool, m));
    print_joined(drawn);

    banner("FRESH container each call -- identical to the stable pool above");
    s = DeterministicStream(SEED); m = SelectionMarker(); drawn.clear();
    for(int i = 0; i < 12; ++i) drawn.push_back(s.select_unchosen(Pool{ A, B, C, D }, m));
    print_joined(drawn);

    banner("sub-pool coherence -- draw from [a,b] then the full [a,b,c,d]");
    s = DeterministicStream(SEED); m = SelectionMarker();
    std::printf("first(from sub): %s  then(from full):", s.select_unchosen(Pool{ A, B }, m));
    for(int i = 0; i < 3; ++i) std::printf(" %s", s.select_unchosen(pool, m));
    std::printf("\n");

    banner("reset() restarts the cycle");
    s = DeterministicStream(SEED); m = SelectionMarker();
    Pool before, after;
    for(int i = 0; i < 4; ++i) before.push_back(s.select_unchosen(pool, m));
    m.reset();
    for(int i = 0; i < 4; ++i) after.push_back(s.select_unchosen(pool, m));
    std::printf("before reset:"); for(const char* x : before) std::printf(" %s", x); std::printf("\n");
    std::printf("after  reset:"); for(const char* x : after)  std::printf(" %s", x); std::printf("\n");
}

static void
run_seed_sweep()
{
    banner("first next_int(0, 1000000) per seed 0..15");
    for(int seed = 0; seed < 16; ++seed)
        std::printf("seed=%2d -> %lld\n", seed, (long long)DeterministicStream(seed).next_int(0, 1000000));
}

int
main(int argc, char** argv)
{
    hwut::HwutRunner runner(argc, argv, "DeterministicStream RNG and SelectionMarker spread", {
        { "primitives", run_primitives }, { "ranges",   run_ranges },
        { "gauss",      run_gauss },      { "sample",   run_sample },
        { "select",     run_select },     { "unchosen", run_unchosen },
        { "seed_sweep", run_seed_sweep },
    });
    return runner.run();
}
