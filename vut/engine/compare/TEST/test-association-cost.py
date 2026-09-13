#! /usr/bin/env python3
#
# @hwut {
#     title      = "Association cost: how the search grows with the input"
#     choices    = ["fixture", "lines", "long_lines", "profile", "tokens",
#                   "unrelated"]
#     tolerance { regions = false  eq_pattern = ["SUCCESS.*", "BUDGET.*"] }
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ASSOCIATION SEARCH IS A*, AND IT IS UNBOUNDED. This test
         makes its cost VISIBLE, so that a blow-up is a number in a
         GOOD file rather than a face that never returns.

WHY IT EXISTS. 'hwut.accept.interactive' on a real pair was seen to sit
in 'WorkList.run()' without end -- 'line_sequence.do' deriving steps,
each calling a nested LINE-level 'edit_operations' of its own. Nothing
said it was searching; it simply did not come back.

WHAT IS MEASURED. Not wall time -- that is what THIS MACHINE SAW (B-11)
and a slow laptop must not fail a suite. What is measured is the NUMBER
OF NODES the search expands, which is a property of the algorithm and
the input, and the same on every machine.

    lines       n against n differing lines: how expansion grows
    tokens      one line, n differing tokens: the NESTED search
    unrelated   two streams with nothing in common -- the worst case,
                where no prefix match prunes anything
    profile     the growth side by side, for reading

HOW TO WORK WITH IT. Where a case is slow, the node count says whether
the search is exponential in that dimension or merely large. To step
through one, the places worth a 'breakpoint()' are named at the foot of
this file.
______________________________________________________________________________
"""
import sys
import io
import asyncio

from vut.engine.compare.configuration              import Configuration
from vut.engine.compare.core.edit_operations       import core as edit_core
from vut.engine.compare.api                        import feeder_ui


#  THE COUNTER. 'WorkList.produce_derived' is the one place a node is
#  expanded, so counting there counts the search and nothing else. The
#  original is put back afterwards: a test that leaves a component
#  patched has measured one thing and broken another.
#  WHERE THE BISECTION STOPS. Past this the search does not return in
#  any useful time, and walking into it turns a diagnostic into another
#  hang. The number is a STOPPING RULE, not a budget: it pins nothing.
KNEE_NODE_N = 60000

_original_produce_derived = edit_core.WorkListBase.produce_derived


class KneeReached(Exception):
    """The search passed 'KNEE_NODE_N' and was abandoned there."""


class Tally:
    """How many nodes the search expanded."""
    def __init__(self, limit_n=None):
        self.n       = 0
        self.limit_n = limit_n
    def __enter__(self):
        tally = self
        def counted(self, item):
            tally.n += 1
            #  THE KNEE BITES HERE, INSIDE THE SEARCH. Asked after the
            #  search returned, it cannot stop the one search that does
            #  not return -- and a test that reproduces a hang by
            #  hanging is no use to anybody.
            if tally.limit_n is not None and tally.n > tally.limit_n:
                raise KneeReached()
            return _original_produce_derived(self, item)
        edit_core.WorkListBase.produce_derived = counted
        return self
    def __exit__(self, *_):
        edit_core.WorkListBase.produce_derived = _original_produce_derived


def associate_n(subject_text, nominal_text, setup=None):
    """
    RETURN: (int, int), the nodes the search expanded and the line pairs
                        it yielded, for this pair of streams under 'setup'.
            (int, None), where the search passed 'KNEE_NODE_N' and was
                        abandoned there -- the node count is what it had
                        spent, and 'None' says no pairing was reached.

    THE SETUP IS NOT A DETAIL. A face builds compare's Configuration
    from the test's OWN '@hwut' block -- its eq_patterns, its analogy
    and numeric tolerances -- and those decide what the search may treat
    as equal. Measuring a captured pair under bare defaults compares the
    same bytes under DIFFERENT RULES, and answers a question nobody
    asked. 'None' means the defaults, and says so.
    """
    if setup is None: setup = Configuration()

    async def go():
        pair_n = 0
        async for item in feeder_ui.feed(setup,
                                         io.StringIO(subject_text),
                                         io.StringIO(nominal_text)):
            if type(item).__name__ == "LinePairInst": pair_n += 1
        return pair_n

    with Tally(KNEE_NODE_N) as tally:
        try:
            pair_n = asyncio.run(go())
        except KneeReached:
            return (tally.n, None)
    return (tally.n, pair_n)


def stream(line_list):
    """RETURN: str, the lines as a stream, closing token included."""
    return "\n".join(list(line_list) + ["<hwut-end>"]) + "\n"


def report(tag, subject_text, nominal_text, budget_n):
    """
    RETURN: bool, True where the search stayed inside 'budget_n' nodes.

    The budget is generous on purpose: it is there to catch an
    EXPLOSION, not to pin an implementation. A change that halves the
    node count is welcome and does not move this file.
    """
    node_n, pair_n = associate_n(subject_text, nominal_text)
    verdict = "ok" if node_n <= budget_n else "BUDGET EXCEEDED"
    print("    %-26s nodes %-9s pairs %-4s budget %-9s %s"
          % (tag, node_n, pair_n, budget_n, verdict))
    return node_n <= budget_n


def test_lines():
    print("N AGAINST N DIFFERING LINES -- the line-sequence search")
    ok = True
    for n in (2, 4, 8, 16):
        subject = stream("subject line %i" % i for i in range(n))
        nominal = stream("nominal line %i" % i for i in range(n))
        ok &= report("%2i lines" % n, subject, nominal, 200 * n * n)
    print("SUCCESS: the line search stayed inside its budget" if ok
          else "FAILURE: the line search exploded")


def test_long_lines():
    """
    RETURN: None. What a LONG line costs, holding the line count fixed.

    THIS IS THE DIMENSION THE FIELD HANG WAS IN. Measured on a real
    pair: two long, comma-rich lines cost 2568 nodes; the SAME two
    lines truncated to 40 characters cost 285. Nine times less, with
    the line count unchanged -- so the cost is in the NESTED
    line-level search, not in the line sequence.

    Note how this differs from 'tokens' below, where every token is
    WHOLLY different and the search prunes at once (4 nodes). What is
    expensive is not many tokens; it is many tokens that are NEARLY
    the same, so that no path is clearly worse than another and
    nothing is cut.
    """
    print("TWO LINES, GROWING IN LENGTH -- the line count never changes")
    part_s = "engine/compare/contract, engine/protocol, engine/procsitter, " \
             "auxiliary, test_writing_support"
    part_n = "engine/compare/api, engine/procsitter/api, " \
             "engine/coverage/api, engine/bookkeeper/api"
    ok = True
    for width in (20, 40, 80, 120):
        subject = stream(["    SEALED: %s -- nothing leaves" % part_s[:width],
                          "    DOORS: %s -- nothing enters" % part_n[:width]])
        nominal = stream(["    SEALED: %s -- nothing leaves" % part_n[:width],
                          "    DOORS: %s -- nothing enters" % part_s[:width]])
        ok &= report("%3i chars of tokens" % width, subject, nominal, 20000)
    print("SUCCESS: the nested search stayed inside its budget" if ok
          else "FAILURE: the nested search exploded")


def test_tokens():
    print("ONE LINE, N DIFFERING TOKENS -- the NESTED line-level search")
    print("  This is the dimension the observed hang was in: every step")
    print("  of the line-sequence search runs a search of its own.")
    ok = True
    for n in (2, 4, 8, 16):
        subject = stream(["-".join("s%i" % i for i in range(n))])
        nominal = stream(["-".join("n%i" % i for i in range(n))])
        ok &= report("%2i tokens" % n, subject, nominal, 400 * n * n)
    print("SUCCESS: the token search stayed inside its budget" if ok
          else "FAILURE: the token search exploded")


def test_unrelated():
    print("TWO STREAMS WITH NOTHING IN COMMON -- no prefix prunes")
    ok = True
    for n in (4, 8, 12):
        subject = stream("aaa%i bbb%i ccc%i" % (i, i, i) for i in range(n))
        nominal = stream("xxx%i yyy%i zzz%i" % (i, i, i) for i in range(n))
        ok &= report("%2i unrelated lines" % n, subject, nominal, 400 * n * n)
    print("SUCCESS: the worst case stayed inside its budget" if ok
          else "FAILURE: the worst case exploded")


def test_profile():
    print("GROWTH, SIDE BY SIDE -- read the ratio, not the number")
    print()
    previous = None
    for n in (2, 4, 8, 16):
        subject = stream("subject line %i" % i for i in range(n))
        nominal = stream("nominal line %i" % i for i in range(n))
        node_n, _ = associate_n(subject, nominal)
        ratio = "-" if previous is None else "x%.1f" % (node_n / previous)
        print("    lines %-4i nodes %-9i %s" % (n, node_n, ratio))
        previous = node_n
    print()
    print("    A ratio near x4 as the size DOUBLES is quadratic and")
    print("    expected. A ratio that itself grows is exponential, and")
    print("    that is what a face that never returns looks like.")
    print("SUCCESS: the profile is printed")


#  WHERE TO PUT A 'breakpoint()' -----------------------------------------
#
#  core/edit_operations/core.py
#      'WorkList.run',             the loop itself -- how many pops
#      'WorkList.produce_derived', every expansion, with the item
#      'WorkList.end_of_sequence', why a path was NOT cut
#
#  core/edit_operations/line_sequence.py
#      'subsequent_steps' line 222, where the NESTED line search is
#                                   entered through the cache
#      'Cache.get'         line 313, the memo -- a miss here is a full
#                                   line-level search, so watch the
#                                   hit rate before anything else
#
#  A first session worth having:
#      python3 -c "import vut.engine.compare.core.edit_operations.core as c; \
#                  c.WorkList.run = ..."      # or simply
#      VUT_DEBUG_EXCEPTION=1 <the face>       # then Ctrl-C for the stack
#
#  THE FIRST QUESTION IS THE CACHE. 'line_sequence.Cache.get' exists to
#  make the nested search pay once per (si, ni). If its hit rate is low,
#  the outer search is exploring paths whose line pairs it has never
#  seen -- and the cost is the product of the two searches.

def test_fixture():
    """
    RETURN: None. The node count for a REAL pair, where one was left in
            'FIXTURE/'.

    WHY THIS CHOICE EXISTS. Every synthetic shape tried here stayed
    linear or quadratic -- n differing lines, n differing tokens, two
    unrelated streams, and lines sharing a long prefix. The blow-up seen
    in the field is therefore a property of an input none of them
    models, and guessing further is not measuring. Put the pair that
    hangs in 'FIXTURE/subject.txt' and 'FIXTURE/nominal.txt' and this
    choice says what the search does with it.

    WITH NO FIXTURE it says so and passes: the suite must be green in a
    tree where nobody has captured one.
    """
    import os
    here    = os.path.dirname(os.path.abspath(__file__))
    subject = os.path.join(here, "FIXTURE", "subject.txt")
    nominal = os.path.join(here, "FIXTURE", "nominal.txt")

    print("A REAL PAIR, where one was captured")
    if not (os.path.exists(subject) and os.path.exists(nominal)):
        print("    no FIXTURE/subject.txt and FIXTURE/nominal.txt --")
        print("    nothing to measure, and that is not a fault")
        print("SUCCESS: no fixture stands")
        return

    with open(subject, encoding="utf-8") as fh: subject_text = fh.read()
    with open(nominal, encoding="utf-8") as fh: nominal_text = fh.read()
    print("    subject %i line(s), nominal %i line(s)"
          % (len(subject_text.splitlines()), len(nominal_text.splitlines())))

    #  THE SETUP THE FACE WOULD HAVE USED. One 'eq_pattern' per line of
    #  'FIXTURE/setup.txt' -- what the test's '@hwut' block declared.
    setup_path = os.path.join(here, "FIXTURE", "setup.txt")
    setup      = Configuration()
    if os.path.exists(setup_path):
        with open(setup_path, encoding="utf-8") as fh:
            pattern_tuple = tuple(line.strip() for line in fh
                                  if line.strip() and not line.startswith("#"))
        if pattern_tuple:
            setup.pattern_finder.equivalent_pattern_list = list(pattern_tuple)
            print("    eq_pattern(s): %s" % ", ".join(pattern_tuple))
    else:
        print("    no FIXTURE/setup.txt -- compare's DEFAULTS, which is")
        print("    not what the face uses where the test declares any")

    #  BISECTED, NOT RUN WHOLE. A pair that does not return is not
    #  measurable; its PREFIXES are. The curve says whether the cost is
    #  a large polynomial or an explosion, and where it turns.
    print()
    print("    the growth over the first n lines of each, STOPPING at")
    print("    the knee -- a test that reproduces a hang by hanging is")
    print("    no use to anybody:")
    previous, stopped_n = None, None
    line_n = min(len(subject_text.splitlines()),
                 len(nominal_text.splitlines()))
    for n in range(4, line_n + 1, 2):
        head_s = "\n".join(subject_text.splitlines()[:n] + ["<hwut-end>"]) + "\n"
        head_n = "\n".join(nominal_text.splitlines()[:n] + ["<hwut-end>"]) + "\n"
        node_n, pair_n = associate_n(head_s, head_n, setup)
        ratio = "-" if previous is None else "x%.1f" % (node_n / previous)
        if pair_n is None: ratio += "  ABANDONED at the knee"
        print("      first %2i lines   nodes %-10i %s" % (n, node_n, ratio))
        previous = node_n
        if node_n > KNEE_NODE_N:
            stopped_n = n
            break

    print()
    if stopped_n is None:
        print("    the whole pair was measured; no knee was met")
    else:
        print("    STOPPED at %i lines, over %i nodes. What enters between"
              % (stopped_n, KNEE_NODE_N))
        print("    line %i and line %i is where the heuristic stops"
              % (stopped_n - 2, stopped_n))
        print("    cutting -- that difference IS the bug, and the two runs")
        print("    either side of it are the pair worth stepping through.")
    print("SUCCESS: the fixture was bisected")


CHOICE_DB = {"fixture":    test_fixture,
             "long_lines": test_long_lines,
             "lines":     test_lines,
             "tokens":    test_tokens,
             "unrelated": test_unrelated,
             "profile":   test_profile}

CHOICE_DB[sys.argv[1] if len(sys.argv) > 1 else "lines"]()
print("<hwut-end>")
