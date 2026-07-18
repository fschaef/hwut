#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Generative consistency net for the comparison engine (Stage 0).

THE LAW (invariant under test):

    is_equivalent(subject, nominal) is True
        <=>  associate(subject, nominal) yields only equivalent pairs
             (no LinePair with cost > 0, no cell with a BAD_ relation).

The Judge (is_equivalent) is meant to be a fast-fail optimization of the
Lawyer (associate). This test hammers that equality with deterministically
generated inputs, so any divergence surfaces as a reproducible counterexample
rather than as a rare production surprise.

CHOICES:

    consistency  -- differential oracle: for many random stream pairs, assert
                    Judge verdict == Lawyer verdict. Needs no knowledge of the
                    'true' answer; it only requires the two engines to agree.

    reflexive    -- identity oracle: is_equivalent(s, s) must be True and the
                    association of s with itself must be perfectly clean, for
                    every generated stream s.

    metamorphic  -- transformation oracles on top of an equivalent pair:
                      * potpourri line permutation      preserves True
                      * consistent analogy renaming     preserves True
                      * in-tolerance numeric jitter     preserves True
                      * out-of-tolerance numeric jitter flips  to  False

DETERMINISM: all randomness comes from 'DeterministicStream' with fixed seeds,
so the output is stable across runs and machines and can serve as a golden.
______________________________________________________________________________
"""
import sys
import asyncio
from   io import StringIO

sys.path.insert(0, "../../../../")

from   vut.engine.compare.configuration import Configuration
import vut.engine.compare.main          as     main
from   vut.language_support.python.deterministic_random import DeterministicStream


# --- Configuration under test -------------------------------------------------
def make_config():
    c  = Configuration()
    pf = c.pattern_finder
    pf.analogy_f                    = True
    pf.whitespace_f                 = True
    pf.backslash_f                  = False
    pf.numeric_tolerance_ratio      = 0.1               # +/-10%
    pf.equivalent_pattern_list      = [r"happy|glad"]
    pf.visible_nothing_pattern_list = ["nothing", "nix"]
    return c

CONFIG    = make_config()
TOLERANCE = 0.1

STRINGS   = ["alpha", "beta", "gamma", "delta", "epsilon"]
ANALOGIES = ["A", "B", "C", "D"]
EQUIVS    = ["happy", "glad"]


# --- Structured stream model --------------------------------------------------
# A stream is a list of blocks. A block is a tuple:
#     ("seq", [line, ...])   ordered line sequence
#     ("pot", [line, ...])   unordered potpourri (rendered inside '||||')
# A line is a list of tokens; a token is a tuple (kind, value):
#     ("STR", str) ("NUM", float-as-str) ("ANA", symbol) ("EQV", str)

def gen_token(rng):
    kind = rng.select(["STR", "STR", "NUM", "ANA", "EQV"])
    if   kind == "STR": return ("STR", rng.select(STRINGS))
    elif kind == "NUM": return ("NUM", str(rng.next_int(100, 900)))
    elif kind == "ANA": return ("ANA", rng.select(ANALOGIES))
    else:               return ("EQV", rng.select(EQUIVS))

def gen_line(rng, min_tok=1, max_tok=4):
    return [gen_token(rng) for _ in range(rng.next_int(min_tok, max_tok))]

def gen_block(rng):
    kind    = rng.select(["seq", "seq", "pot"])
    n_lines = rng.next_int(1, 4)
    return (kind, [gen_line(rng) for _ in range(n_lines)])

def gen_stream(rng, min_blocks=1, max_blocks=3):
    return [gen_block(rng) for _ in range(rng.next_int(min_blocks, max_blocks))]

def render_token(tok):
    kind, val = tok
    if   kind == "ANA": return "((%s))" % val
    else:               return val

def render_line(line):
    return " ".join(render_token(t) for t in line)

def render_stream(stream):
    out = []
    for kind, lines in stream:
        if kind == "pot": out.append("||||")
        out.extend(render_line(l) for l in lines)
        if kind == "pot": out.append("||||")
    return "\n".join(out) + "\n"


# --- Engine access ------------------------------------------------------------
async def judge(subject_txt, nominal_txt):
    """RETURNS: bool, the verdict of 'is_equivalent' (the Judge)."""
    return await main.is_equivalent(CONFIG, StringIO(subject_txt),
                                            StringIO(nominal_txt))

async def lawyer(subject_txt, nominal_txt):
    """RETURNS: (bool, set), the association verdict (the Lawyer) and the set
                of BAD_ relation names that made it negative (empty if clean).

    Verdict is False as soon as any LinePair has cost > 0 or any cell carries
    a BAD_ relation -- the same criterion the display feeder uses to mark a
    line as non-matching.
    """
    verdict = True
    bad     = set()
    async for chunk in main.associate(CONFIG, StringIO(subject_txt),
                                              StringIO(nominal_txt)):
        st, nt = chunk.types()
        if st != nt:
            verdict = False
            bad.add("CHUNK_TYPE_%s_vs_%s" % (st.name, nt.name))
        for lp in chunk:
            if lp.cost > 0:
                verdict = False
            for c in lp.subject_list() + lp.nominal_list():
                if "BAD_" in c.relation_id.name:
                    verdict = False
                    bad.add(c.relation_id.name)
    return verdict, bad


# --- Metamorphic transformations (structured, on the nominal side) ------------
def permute_potpourri(stream, rng):
    """RETURNS: new stream with the lines of one potpourri block rotated.

    Rotation (not a random shuffle) keeps the transformation deterministic and
    guarantees a different order when the block has >= 2 lines.
    """
    pots = [i for i, (k, ls) in enumerate(stream) if k == "pot" and len(ls) > 1]
    if not pots:
        return None
    i = rng.select(pots)
    k, lines = stream[i]
    rotated  = lines[1:] + lines[:1]
    return stream[:i] + [(k, rotated)] + stream[i+1:]

def rename_analogies(stream):
    """RETURNS: new stream with every analogy symbol mapped through a fixed
                bijection. A consistent renaming must preserve equivalence.
    """
    bijection = {"A": "W", "B": "X", "C": "Y", "D": "Z"}
    def fix_token(t):
        return ("ANA", bijection[t[1]]) if t[0] == "ANA" else t
    return [(k, [[fix_token(t) for t in line] for line in lines])
            for k, lines in stream]

def jitter_numeric(stream, factor, rng):
    """RETURNS: (new stream, changed_f). Multiplies ONE numeric token by
                'factor'. 'changed_f' is False if the stream has no numeric.
    """
    sites = [(bi, li, ti)
             for bi, (k, lines) in enumerate(stream)
             for li, line in enumerate(lines)
             for ti, tok in enumerate(line) if tok[0] == "NUM"]
    if not sites:
        return stream, False
    bi, li, ti = rng.select(sites)
    new = [(k, [list(line) for line in lines]) for k, lines in stream]
    old = float(new[bi][1][li][ti][1])
    new[bi][1][li][ti] = ("NUM", str(round(old * factor, 4)))
    return new, True


# --- Check families -----------------------------------------------------------
async def run_consistency(seed, cases):
    rng      = DeterministicStream(seed=seed)
    agree    = 0
    failures = []
    for i in range(cases):
        s = gen_stream(rng)
        # Build nominal by one of four strategies, but assert only agreement.
        strategy = rng.select(["copy", "preserve", "break", "independent"])
        if   strategy == "copy":
            n = s
        elif strategy == "preserve":
            n = rename_analogies(s)
        elif strategy == "break":
            n, _ = jitter_numeric(s, 2.0, rng)   # 2x is far out of tolerance
        else:
            n = gen_stream(rng)
        s_txt, n_txt = render_stream(s), render_stream(n)
        jv        = await judge(s_txt, n_txt)
        lv, bad   = await lawyer(s_txt, n_txt)
        if jv == lv:
            agree += 1
        else:
            failures.append((i, strategy, jv, lv, sorted(bad), s_txt, n_txt))
    print("=== CONSISTENCY (seed=%d, cases=%d) ===" % (seed, cases))
    print("Judge == Lawyer: %d/%d agree" % (agree, cases))
    _report_failures(failures)
    print("result: %s" % ("PASS" if not failures else "FAIL"))

async def run_reflexive(seed, cases):
    rng      = DeterministicStream(seed=seed)
    ok       = 0
    failures = []
    for i in range(cases):
        s     = gen_stream(rng)
        s_txt = render_stream(s)
        jv        = await judge(s_txt, s_txt)
        lv, bad   = await lawyer(s_txt, s_txt)
        if jv is True and lv is True:
            ok += 1
        else:
            failures.append((i, "identity", jv, lv, sorted(bad), s_txt, s_txt))
    print("=== REFLEXIVE (seed=%d, cases=%d) ===" % (seed, cases))
    print("is_equivalent(s, s) is True and association clean: %d/%d" % (ok, cases))
    _report_failures(failures)
    print("result: %s" % ("PASS" if not failures else "FAIL"))

async def run_metamorphic(seed, cases):
    rng      = DeterministicStream(seed=seed)
    checks   = {"permute": [0, 0], "rename": [0, 0],
                "in_tol": [0, 0], "out_tol": [0, 0]}   # [pass, total]
    failures = []
    for i in range(cases):
        s     = gen_stream(rng)
        s_txt = render_stream(s)

        # permutation of a potpourri block preserves equivalence with itself
        perm = permute_potpourri(s, rng)
        if perm is not None:
            checks["permute"][1] += 1
            v = await judge(s_txt, render_stream(perm))
            if v is True: checks["permute"][0] += 1
            else: failures.append((i, "permute", True, v, [], s_txt, render_stream(perm)))

        # consistent analogy renaming preserves equivalence
        ren = rename_analogies(s)
        if render_stream(ren) != s_txt:
            checks["rename"][1] += 1
            v = await judge(s_txt, render_stream(ren))
            if v is True: checks["rename"][0] += 1
            else: failures.append((i, "rename", True, v, [], s_txt, render_stream(ren)))

        # in-tolerance jitter (+5% with ratio 10%) preserves equivalence
        jin, ch = jitter_numeric(s, 1.05, rng)
        if ch:
            checks["in_tol"][1] += 1
            v = await judge(s_txt, render_stream(jin))
            if v is True: checks["in_tol"][0] += 1
            else: failures.append((i, "in_tol", True, v, [], s_txt, render_stream(jin)))

        # out-of-tolerance jitter (+50%) flips to non-equivalent
        jout, ch = jitter_numeric(s, 1.5, rng)
        if ch:
            checks["out_tol"][1] += 1
            v = await judge(s_txt, render_stream(jout))
            if v is False: checks["out_tol"][0] += 1
            else: failures.append((i, "out_tol", False, v, [], s_txt, render_stream(jout)))

    print("=== METAMORPHIC (seed=%d, cases=%d) ===" % (seed, cases))
    for name in ("permute", "rename", "in_tol", "out_tol"):
        p, t = checks[name]
        print("  %-8s preserved/flipped: %d/%d" % (name, p, t))
    _report_failures(failures)
    print("result: %s" % ("PASS" if not failures else "FAIL"))


def _report_failures(failures):
    if not failures:
        return
    print("  COUNTEREXAMPLES: %d" % len(failures))
    for idx, tag, expect, got, bad, s_txt, n_txt in failures[:5]:
        print("  ---- case %d [%s] expected=%s got=%s bad=%s"
              % (idx, tag, expect, got, bad))
        print("       SUBJECT: %r" % s_txt)
        print("       NOMINAL: %r" % n_txt)


# --- HWUT entry ---------------------------------------------------------------
if "--hwut-info" in sys.argv:
    print("Generative Judge/Lawyer consistency net;")
    print("CHOICES: consistency, reflexive, metamorphic;")
    sys.exit()

CHOICE = sys.argv[1] if len(sys.argv) > 1 else "consistency"
if   CHOICE == "consistency": asyncio.run(run_consistency(seed=0x51EED, cases=400))
elif CHOICE == "reflexive":   asyncio.run(run_reflexive(seed=0xBEEF,   cases=300))
elif CHOICE == "metamorphic": asyncio.run(run_metamorphic(seed=0xC0FFEE, cases=300))
else:
    print("unknown choice: %s" % CHOICE)
    sys.exit(1)
