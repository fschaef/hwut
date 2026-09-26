#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE NUMBERS OF INTEND 19's PHASE TWO, MEASURED -- the margin and
         the n of o-6, the base measure and the context width k of o-7.

    benchmark-anchoring.py --build-corpus    (inside the git repository)
    benchmark-anchoring.py                    the tables
    benchmark-anchoring.py --knee             search time by element work

Phase two is a PROTOTYPE here, parameterised, and enters the engine only
once its numbers are ruled. Phase one is the engine's own
('line_sequence.anchor_list_of').

TWO CORPORA, TWO QUESTIONS.
    REAL     old/new versions of GOOD files from git history: what the
             settings COST on changes that happened. History says a file
             changed, not which line became which: no correctness here.
    MUTATED  the larger GOODs, edited by known operations (delete,
             insert, small and heavy change, near-duplicate): the true
             pairing is known, so wrong and missed anchors are counted.

THE PROTOTYPE. A section phase one leaves is costed pair by pair: the base
measure on the two lines, averaged with k lines of context either side.
The alternative to pairing is DELETE + INSERT, 1.0; so a pair's runner-up
is the cheapest competitor in its row or column, or 1.0. First every pair
OUTLIERLY CLOSE -- the minimum of its row and its column, the runner-up
clear by 'margin' -- anchors; where none is, the n cheapest pairs below
1.0 do; non-crossing, and the act recurses into what they leave.

Deterministic for a given corpus and seed; times are reported apart.
______________________________________________________________________________
"""
import bisect, json, os, random, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, *[".."] * 5)))

from vut.engine.compare.configuration                   import Configuration
from vut.engine.compare.reading.pattern_finder          import PatternFinder
from vut.engine.compare.engine.line                     import Line
from vut.engine.compare.core.edit_operations.line_sequence import anchor_list_of
from rapidfuzz import fuzz

CORPUS = os.path.join(HERE, "TMP", "anchoring-corpus.json")
SEED   = 20260925

# -- the corpora --------------------------------------------------------------
def build_corpus(real_n=300, big_min=2048):
    """RETURN: None. Writes CORPUS: real pairs from git history, seeded
    sample; the larger GOODs of the tree as mutation bases."""
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=HERE,
                         capture_output=True, text=True, check=True).stdout.strip()
    def git(*a):
        return subprocess.run(["git"] + list(a), cwd=top, capture_output=True,
                              text=True).stdout
    commit_list = git("log", "--no-renames", "--diff-filter=M", "--format=%H",
                      "--", "vut/*/TEST/GOOD/*.txt", "vut/**/TEST/GOOD/*.txt").split()
    pair_list = []
    for c in commit_list:
        for path in git("diff-tree", "-r", "--no-renames", "--diff-filter=M",
                        "--name-only", c + "^", c).split():
            if "/TEST/GOOD/" in path and path.endswith(".txt"):
                pair_list.append((c, path))
    rng = random.Random(SEED); rng.shuffle(pair_list)
    real = []
    for c, path in pair_list:
        old, new = git("show", "%s^:%s" % (c, path)), git("show", "%s:%s" % (c, path))
        if old and new and old != new and len(old) < 60000:
            real.append({"where": "%s %s" % (c[:8], path), "subject": new, "nominal": old})
        if len(real) >= real_n: break
    base = []
    for root, _d, files in os.walk(os.path.join(top, "vut")):
        if root.endswith("/TEST/GOOD"):
            for f in sorted(files):
                p = os.path.join(root, f)
                if f.endswith(".txt") and os.path.getsize(p) >= big_min:
                    base.append({"where": os.path.relpath(p, top),
                                 "text": open(p, errors="replace").read()})
    os.makedirs(os.path.dirname(CORPUS), exist_ok=True)
    json.dump({"real": real, "base": sorted(base, key=lambda b: b["where"])},
              open(CORPUS, "w"))
    print("corpus: %d real pairs, %d mutation bases -> %s"
          % (len(real), len(base), os.path.relpath(CORPUS, HERE)))

def mutated(text, rng, filler):
    """RETURN: (subject lines, nominal lines, truth) -- truth[si] is the
    nominal index subject line si came from, None where it was inserted."""
    nominal = text.splitlines()
    subject, truth = [], []
    for ni, line in enumerate(nominal):
        r = rng.random()
        if   r < 0.08: continue                                  # delete
        elif r < 0.16:                                           # small change
            w = line.split()
            if w: w[rng.randrange(len(w))] = "X%d" % rng.randrange(1000)
            subject.append(" ".join(w) or "x"); truth.append(ni)
        elif r < 0.20:                                           # heavy change
            w = line.split(); k = max(1, len(w) // 2)
            for _ in range(k):
                if w: w[rng.randrange(len(w))] = "Y%d" % rng.randrange(1000)
            subject.append(" ".join(w) or "y"); truth.append(ni)
        else:
            subject.append(line); truth.append(ni)
        if rng.random() < 0.05:                                  # insert
            subject.append(rng.choice(filler)); truth.append(None)
        if rng.random() < 0.03 and line.strip():                 # near-duplicate
            subject.append(line + " dup"); truth.append(None)
    return subject, nominal, truth

# -- the prototype --------------------------------------------------------------
class Pair:
    """ONE PAIR OF FILES, lexed once, with a base-cost cache per measure."""
    def __init__(self, subject, nominal, pf):
        self.S = [Line(i, t, pf) for i, t in enumerate(subject)]
        self.N = [Line(i, t, pf) for i, t in enumerate(nominal)]
        self.cache = {}; self.costed = 0
    def base(self, measure, i, j):
        """RETURN: float in [0,1], the base cost of pairing S[i] with N[j]."""
        key = (measure, i, j)
        self.costed += 1                   # asked, cached or not: the work
        c = self.cache.get(key)
        if c is None:
            if measure == "element":
                c = self.S[i].edit_operations(self.N[j], None).cost
            else:
                c = 1.0 - fuzz.ratio(self.S[i].uniform_string(),
                                     self.N[j].uniform_string()) / 100.0
            self.cache[key] = c
        return c
    def cost(self, measure, k, i, j):
        """RETURN: float, the base cost averaged with k context lines."""
        total, n = 0.0, 0
        for d in range(-k, k + 1):
            if 0 <= i + d < len(self.S) and 0 <= j + d < len(self.N):
                total += self.base(measure, i + d, j + d); n += 1
        return total / n

def noncrossing(pairs):
    """RETURN: list, the longest chain of pairs increasing in both."""
    pairs = sorted(pairs)
    top, idx, back = [], [], [None] * len(pairs)
    for x, (_i, j) in enumerate(pairs):
        p = bisect.bisect_left(top, j)
        back[x] = idx[p - 1] if p else None
        if p == len(top): top.append(j); idx.append(x)
        else:             top[p] = j;    idx[p] = x
    out, x = [], (idx[-1] if idx else None)
    while x is not None: out.append(pairs[x]); x = back[x]
    return out[::-1]

def phase_two(pair, s0, s1, n0, n1, measure, k, margin, n_low, stats):
    """RETURN: list[(i,j)], the anchors phase two sets in S[s0:s1] x N[n0:n1]."""
    if s0 >= s1 or n0 >= n1: return []
    C = {(i, j): pair.cost(measure, k, i, j)
         for i in range(s0, s1) for j in range(n0, n1)}
    #  THE TWO SMALLEST PER ROW AND PER COLUMN, once: a pair is outlierly
    #  close where it is the minimum of both and the next best of either
    #  -- or DELETE + INSERT, 1.0 -- stands 'margin' above it.
    def two_smallest(values):
        """RETURN: (float, float), the smallest and the next, 1.0-capped."""
        a = b = 1.0
        for v in values:
            if v < a: a, b = v, a
            elif v < b: b = v
        return a, b
    row = {i: two_smallest(C[i, j] for j in range(n0, n1)) for i in range(s0, s1)}
    col = {j: two_smallest(C[i, j] for i in range(s0, s1)) for j in range(n0, n1)}
    outlier = [(i, j) for (i, j), c in C.items()
               if c < 1.0 and c == row[i][0] and c == col[j][0]
               and min(row[i][1], col[j][1]) - c >= margin]
    if outlier:
        chosen = noncrossing(outlier); stats["outlier"] += len(chosen)
        origin = "o"
    else:
        cheap = sorted((c, i, j) for (i, j), c in C.items() if c < 1.0)
        chosen, taken = [], []
        for c, i, j in cheap:
            if all((i - a) * (j - b) > 0 for a, b in taken):
                taken.append((i, j))
                if len(taken) == n_low: break
        chosen = sorted(taken); stats["lowest"] += len(chosen)
        origin = "l"
    if not chosen: return []
    out, ps, pn = [], s0, n0
    for i, j in chosen + [(s1, n1)]:
        out += phase_two(pair, ps, i, pn, j, measure, k, margin, n_low, stats)
        if (i, j) != (s1, n1): out.append((i, j, origin))
        ps, pn = i + 1, j + 1
    return out

def anchored(pair, measure, k, margin, n_low, stats):
    """RETURN: list[(i,j)], phase one's anchors and phase two's between."""
    one = anchor_list_of(pair.S, pair.N)
    stats["phase_one"] += len(one)
    out, ps, pn = [], 0, 0
    for i, j in one + [(len(pair.S), len(pair.N))]:
        stats["sections"] += (ps < i and pn < j)
        stats["section_max"] = max(stats["section_max"], (i - ps) * (j - pn))
        out += phase_two(pair, ps, i, pn, j, measure, k, margin, n_low, stats)
        if (i, j) != (len(pair.S), len(pair.N)): out.append((i, j, "1"))
        ps, pn = i + 1, j + 1
    return out

# -- the tables ------------------------------------------------------------------
GRID = [(m, k, g, n) for m in ("fuzz", "element") for k in (0, 1, 2)
        for g in (0.05, 0.10, 0.20, 0.30) for n in (1, 2, 4)]
#  THE ELEMENT MEASURE COSTS ~3.6 ms A PAIR (measured, printed below), so it
#  runs on a seeded SUBSET -- and the fuzz measure on that same subset too,
#  so the two compare like for like.
SUBSET_MUT, SUBSET_REAL = 30, 50

def run():
    """RETURN: None. Prints one row per setting, per corpus."""
    corpus = json.load(open(CORPUS))
    pf     = PatternFinder(Configuration().pattern_finder)
    rng    = random.Random(SEED)
    filler = [l for b in corpus["base"] for l in b["text"].splitlines() if l.strip()]
    mut = []
    for b in corpus["base"]:
        for _rep in range(2):
            s, n, t = mutated(b["text"], rng, filler)
            mut.append((Pair(s, n, pf), t))
    real = [Pair(r["subject"].splitlines(), r["nominal"].splitlines(), pf)
            for r in corpus["real"]]
    print("corpus: %d real pairs, %d mutated pairs (from %d bases), seed %d"
          % (len(real), len(mut), len(corpus["base"]), SEED))
    #  THE PRICE OF ONE COSTING, per measure, timed once and apart.
    sample = [(p, i, j) for p, _ in mut[:20] for i in range(min(8, len(p.S)))
              for j in range(min(8, len(p.N)))]
    for m in ("element", "fuzz"):
        t0 = time.perf_counter()
        for p, i, j in sample: Pair.base(p, m + "-timing", i, j) if False else \
            (p.S[i].edit_operations(p.N[j], None).cost if m == "element" else
             fuzz.ratio(p.S[i].uniform_string(), p.N[j].uniform_string()))
        print("one costing, %-7s: %.1f us" % (m, 1e6 * (time.perf_counter() - t0)
                                               / len(sample)))
    table(mut, real, [g for g in GRID if g[0] == "fuzz"],
          "ALL PAIRS, fuzz measure")
    table(mut[:SUBSET_MUT], real[:SUBSET_REAL], GRID,
          "SUBSET (%d mutated, %d real), both measures" % (SUBSET_MUT, SUBSET_REAL))


def table(mut, real, grid, title):
    """RETURN: None. The two tables, for 'grid', over the given pairs."""
    print()
    print("== %s ==" % title)
    print("MUTATED -- correctness (true pairs known)")
    print("%-8s %2s %6s %2s | %6s %6s %6s %6s %6s | %6s %6s | %8s %6s"
          % ("measure", "k", "margin", "n", "wr-p1", "wr-out", "wr-low",
             "missed", "true", "outl", "lowest", "asked", "sec"))
    for m, k, g, n in grid:
        stats = dict(outlier=0, lowest=0, phase_one=0, sections=0, section_max=0)
        wrong = {"1": 0, "o": 0, "l": 0}; missed = true_n = 0
        costed0 = sum(p.costed for p, _ in mut)
        t0 = time.process_time()
        for p, truth in mut:
            a  = anchored(p, m, k, g, n, stats)
            tp = {(i, j) for i, j in enumerate(truth) if j is not None}
            true_n += len(tp)
            for i, j, o in a:
                if truth[i] != j: wrong[o] += 1
            missed += len(tp - {(i, j) for i, j, _o in a})
        print("%-8s %2d %6.2f %2d | %6d %6d %6d %6d %6d | %6d %6d | %8d %6.2f"
              % (m, k, g, n, wrong["1"], wrong["o"], wrong["l"], missed,
                 true_n, stats["outlier"],
                 stats["lowest"], sum(p.costed for p, _ in mut) - costed0,
                 time.process_time() - t0))
    print()
    print("REAL -- cost (history pairs, truth unknown)")
    print("%-8s %2s %6s %2s | %6s %8s %8s | %6s %6s | %8s %6s"
          % ("measure", "k", "margin", "n", "p1anc", "sections", "sect_max",
             "outl", "lowest", "asked", "sec"))
    for m, k, g, n in grid:
        stats = dict(outlier=0, lowest=0, phase_one=0, sections=0, section_max=0)
        costed0 = sum(p.costed for p in real); t0 = time.process_time()
        for p in real: anchored(p, m, k, g, n, stats)
        print("%-8s %2d %6.2f %2d | %6d %8d %8d | %6d %6d | %8d %6.2f"
              % (m, k, g, n, stats["phase_one"], stats["sections"],
                 stats["section_max"], stats["outlier"], stats["lowest"],
                 sum(p.costed for p in real) - costed0,
                 time.process_time() - t0))

def knee(cap_s=3.0):
    """RETURN: None. THE KNEE OF TODAY'S SEARCH: every section phase one
    leaves in the REAL pairs, searched alone (capped at 'cap_s'), classed
    by its ELEMENT WORK W = (elements of its subject lines) x (elements of
    its nominal lines) -- the most the search can touch. The pair count
    alone misses long lines: a 2x2 section of 3080-element lines ran out
    the cap."""
    import signal, statistics
    from vut.engine.compare.core.edit_operations import line_sequence as LS
    from vut.engine.compare.core.edit_operations.edit import EditSequence
    from vut.engine.compare.contract.frozen_analogy_db import FrozenAnalogyDb
    class Cap(Exception): pass
    def on_alarm(*_): raise Cap()
    signal.signal(signal.SIGALRM, on_alarm)
    corpus = json.load(open(CORPUS))
    pf = PatternFinder(Configuration().pattern_finder)
    row_list = []
    for r in corpus["real"]:
        p = Pair(r["subject"].splitlines(), r["nominal"].splitlines(), pf)
        ps = pn = 0
        for i, j in anchor_list_of(p.S, p.N) + [(len(p.S), len(p.N))]:
            if i > ps and j > pn:
                w = sum(max(1, len(l.sequence)) for l in p.S[ps:i]) \
                  * sum(max(1, len(l.sequence)) for l in p.N[pn:j])
                t0, capped = time.perf_counter(), 0
                signal.setitimer(signal.ITIMER_REAL, cap_s)
                try:
                    LS._aligned_by_sections(p.S[ps:i], p.N[pn:j], [],
                                            EditSequence(0, [], FrozenAnalogyDb()))
                except Cap: capped = 1
                finally: signal.setitimer(signal.ITIMER_REAL, 0)
                row_list.append((w, 1e3 * (time.perf_counter() - t0), capped))
            ps, pn = i + 1, j + 1
    print("sections: %d, capped at %.0f s: %d" % (len(row_list), cap_s,
                                                  sum(c for *_x, c in row_list)))
    print("%-18s %4s | %9s %9s %9s | %6s | %s" % ("element work W", "n",
          "median ms", "p90 ms", "max ms", "capped", "sections at or below"))
    lo = 1
    while lo < 2 ** 24:
        b = [x for x in row_list if lo <= x[0] < 2 * lo]
        if b:
            ms = sorted(x[1] for x in b)
            below = sum(1 for x in row_list if x[0] < 2 * lo)
            print("%8d-%-9d %4d | %9.1f %9.1f %9.1f | %6d | %.1f%%" % (
                  lo, 2 * lo - 1, len(b), statistics.median(ms),
                  ms[min(len(ms) - 1, int(.9 * len(ms)))], ms[-1],
                  sum(x[2] for x in b), 100.0 * below / len(row_list)))
        lo *= 2


if __name__ == "__main__":
    if   "--build-corpus" in sys.argv: build_corpus()
    elif "--knee"         in sys.argv: knee()
    else:                              run()
