#! /usr/bin/env python3
#
# @hwut {
#     title      = "DeterministicStream RNG and SelectionMarker spread"
#     choices    = ["gauss", "primitives", "ranges", "sample",
#                   "seed_sweep", "select", "unchosen"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Pin the DeterministicStream RNG and the SelectionMarker spread so any
         drift in the number stream -- the substrate the monkey fuzzer and every
         other reproducible walk stands on -- shows up as a binary diff.

CHOICES: primitives, ranges, gauss, sample, select, unchosen, seed_sweep;

DESCRIPTION:

The stream is a Park-Miller MINSTD generator: 'state = 48271 * state mod
(2^31 - 1)'. It is pure integer arithmetic with no platform-dependent floats in
the core, so the recorded numbers MUST be identical on every machine. The Gauss
path is the only one that touches libm (log/cos/sqrt); it is recorded too, so a
libm-induced last-ULP difference would surface here rather than silently in a
downstream walk.

    primitives   raw next_int stream, next_float, coin -- the bare generator.
    ranges       next_int over small and degenerate [v,v] ranges.
    gauss        gauss, gauss clamped to a band, gauss_int -- the libm path.
                 THE ONLY TOLERATED CHOICE: the two full-precision blocks
                 are framed as a 'table' region with 'numeric={1:1e-12}',
                 so a differing libm's last bits pass while real drift in
                 the Box-Muller path fails. The integer draws stay exact.
    sample       sample_indices (Fisher-Yates) and sample over a list.
    select       stateless select: same state + same pool -> same element.
    unchosen     select_unchosen with a caller-owned SelectionMarker: spread is
                 reproducible across FRESH containers and coherent across
                 differing sub-pools, because memory is keyed on candidate
                 identity (NOT container address). This is the property the
                 monkey fuzzer's per-ALT marker relies on.
    seed_sweep   the first draw for a range of seeds -- pins seed handling.
______________________________________________________________________________
"""
import sys
import config                                                       # noqa: F401

from vut.test_writing_support.python.hwut_runner          import HwutRunner
from vut.test_writing_support.python.deterministic_random import (DeterministicStream,
                                                              SelectionMarker)

SEED = 0x42

#  THE ONE PLACE THE LIBM PATH IS TOLERATED. Every other choice compares
#  exactly: the generator is integer arithmetic and owes byte identity on
#  any machine. 'gauss' alone touches log/cos/sqrt, so its two
#  full-precision blocks carry a per-column band -- stated in the output
#  itself, since a region frames BOTH streams or neither.
TOLERANCE_REGION_BEGIN = "##! table numeric={1:1e-12}"
REGION_END             = "####"


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def run_primitives():
    """RETURN: None. The bare generator: next_int, next_float, coin."""
    banner("next_int(0, 1000000) -- first 20")
    s = DeterministicStream(SEED)
    for i in range(20):
        print("[%02d] %d" % (i, s.next_int(0, 1000000)))

    banner("next_float -- first 10 (full precision)")
    s = DeterministicStream(SEED)
    for i in range(10):
        print("[%02d] %r" % (i, s.next_float()))

    banner("coin(0.5) -- 40 draws")
    s = DeterministicStream(SEED)
    print(" ".join("T" if s.coin(0.5) else "F" for _ in range(40)))


def run_ranges():
    """RETURN: None. next_int over small and degenerate ranges."""
    banner("next_int(0, 9) -- 30 draws")
    s = DeterministicStream(SEED)
    print(" ".join(str(s.next_int(0, 9)) for _ in range(30)))

    banner("next_int(5, 5) -- degenerate range returns the bound")
    s = DeterministicStream(SEED)
    print(" ".join(str(s.next_int(5, 5)) for _ in range(5)))

    banner("next_int(-3, 3) -- spanning zero")
    s = DeterministicStream(SEED)
    print(" ".join("%+d" % s.next_int(-3, 3) for _ in range(20)))


def run_gauss():
    """RETURN: None. The libm path: gauss, clamped gauss, gauss_int.

    THE TWO FULL-PRECISION BLOCKS ARE FRAMED AS A 'table' REGION with a
    per-column numeric tolerance. Column 1 is the value; 1e-12 is some
    four thousand ULP at unit magnitude, so a libm that differs in the
    last bits is tolerated while any real drift in the Box-Muller path
    -- which moves a value in its leading digits -- still fails. The
    labels in column 0 and the integer draws below stay exact.
    """
    banner("gauss(0, 1) -- 10 draws (full precision)")
    s = DeterministicStream(SEED)
    print(TOLERANCE_REGION_BEGIN)
    for i in range(10):
        print("[%02d] %r" % (i, s.gauss(0.0, 1.0)))
    print(REGION_END)

    banner("gauss(0, 1) clamped to [-1, 1]")
    s = DeterministicStream(SEED)
    print(TOLERANCE_REGION_BEGIN)
    for i in range(10):
        print("[%02d] %r" % (i, s.gauss(0.0, 1.0, -1.0, 1.0)))
    print(REGION_END)

    banner("gauss_int(100, 15) -- 20 draws")
    s = DeterministicStream(SEED)
    print(" ".join(str(s.gauss_int(100.0, 15.0)) for _ in range(20)))


def run_sample():
    """RETURN: None. sample_indices (Fisher-Yates) and sample over a list."""
    banner("sample_indices(10, 10) -- full permutation")
    s = DeterministicStream(SEED)
    print(s.sample_indices(10, 10))

    banner("sample_indices(20, 5) -- partial draw")
    s = DeterministicStream(SEED)
    print(s.sample_indices(20, 5))

    banner("choice from a list -- 20 draws")
    s = DeterministicStream(SEED)
    pool = ["alpha", "beta", "gamma", "delta", "epsilon"]
    print(" ".join(s.choice(pool) for _ in range(20)))

    banner("sample(list, 4) -- unique elements")
    s = DeterministicStream(SEED)
    print(s.sample(list("ABCDEFGH"), 4))


def run_select():
    """RETURN: None. Stateless select: same state + same pool -> same element."""
    banner("select over a list -- 20 draws")
    s = DeterministicStream(SEED)
    pool = ["a", "b", "c", "d"]
    print(" ".join(s.select(pool) for _ in range(20)))

    banner("select over a tuple -- 12 draws")
    s = DeterministicStream(SEED)
    branches = ("p", "q", "r")
    print(" ".join(s.select(branches) for _ in range(12)))


def run_unchosen():
    """RETURN: None. select_unchosen spread is identity-keyed, not address-keyed.

    Records three properties the monkey fuzzer's per-ALT marker depends on:
    a clean cycle over a stable pool, the SAME cycle when the container is
    rebuilt fresh every call (proving memory is not keyed on container address),
    and coherence when the pool composition changes between calls (a candidate
    chosen via a sub-pool is remembered when the full pool is offered).
    """
    banner("stable pool -- three full cycles of 4 elements")
    s = DeterministicStream(SEED)
    pool = ["a", "b", "c", "d"]
    m = SelectionMarker()
    print(" ".join(s.select_unchosen(pool, m) for _ in range(12)))

    banner("FRESH container each call -- identical to the stable pool above")
    s = DeterministicStream(SEED)
    m = SelectionMarker()
    out = []
    for _ in range(12):
        fresh = ["a", "b", "c", "d"]      # new list object every call
        out.append(s.select_unchosen(fresh, m))
    print(" ".join(out))

    banner("sub-pool coherence -- draw from [a,b] then the full [a,b,c,d]")
    s = DeterministicStream(SEED)
    m = SelectionMarker()
    full = ["a", "b", "c", "d"]
    sub  = ["a", "b"]
    first = s.select_unchosen(sub, m)
    rest  = [s.select_unchosen(full, m) for _ in range(3)]
    print("first(from sub):", first, " then(from full):", " ".join(rest))

    banner("reset() restarts the cycle")
    s = DeterministicStream(SEED)
    pool = ["a", "b", "c", "d"]
    m = SelectionMarker()
    before = [s.select_unchosen(pool, m) for _ in range(4)]
    m.reset()
    after  = [s.select_unchosen(pool, m) for _ in range(4)]
    print("before reset:", " ".join(before))
    print("after  reset:", " ".join(after))


def run_seed_sweep():
    """RETURN: None. First next_int per seed -- pins seed handling."""
    banner("first next_int(0, 1000000) per seed 0..15")
    for seed in range(16):
        s = DeterministicStream(seed)
        print("seed=%2d -> %d" % (seed, s.next_int(0, 1000000)))


HwutRunner(
    argv       = sys.argv,
    title      = "DeterministicStream RNG and SelectionMarker spread",
    choice_map = {
        "primitives": run_primitives,
        "ranges":     run_ranges,
        "gauss":      run_gauss,
        "sample":     run_sample,
        "select":     run_select,
        "unchosen":   run_unchosen,
        "seed_sweep": run_seed_sweep,
    },
).run()
