#! /usr/bin/env python3
#
# @hwut {
#     title      = "The converters are visitors: every measure accounted for, no name outside the vocabulary"
#     choices    = ["accounted", "vocabulary", "walk"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE VISITOR OVER THE OUTPUT DIRECTORY (coverage D-44, under D-29's law),
checked from the two sides 'database/TEST/test-presenter-visitor.py'
checks the record's visitor from.

CHOICES: accounted, vocabulary, walk;

accounted   a summary carrying EVERY REGISTERED MEASURE -- the registry
            is asked, nothing is spelled here -- is walked by every
            converter's visitor. Each must ACCOUNT FOR EVERY MEASURE:
            render it, or declare it unrendered and NAME it in its
            output, so a reader sees the gap. A measure that is neither
            is a document that looks complete and is not.
vocabulary  every public method a visitor defines is one the base
            declares -- a misspelt step is never called and nothing
            complains -- and every step the base declares is one the
            walk takes.
walk        the traversal: the order of visits, measures in registered
            order, a measure with no point not visited, sources in the
            order given.
______________________________________________________________________________
"""
import inspect
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.coverage.api             import measure_of, name_tuple  # noqa E402
from   vut.services.lib.cov.summary        import SourceSummary    # noqa E402
from   vut.services.lib.cov.visitor        import I_OutputVisitor, walk  # noqa E402
from   vut.services.lib.cov.conv.to_lcov      import LcovVisitor      # noqa E402
from   vut.services.lib.cov.conv.to_html      import HtmlVisitor      # noqa E402
from   vut.services.lib.cov.conv.to_cobertura import CoberturaVisitor # noqa E402
from   vut.services.lib.cov.conv.to_jacoco    import JacocoVisitor    # noqa E402
from   vut.services.lib.cov.conv.to_json      import JsonVisitor      # noqa E402
from   vut.services.lib.cov.conv.to_tex       import TexVisitor       # noqa E402

VISITOR_DB = {"lcov":      LcovVisitor,
              "html":      HtmlVisitor,
              "cobertura": CoberturaVisitor,
              "jacoco":    JacocoVisitor,
              "json":      JsonVisitor,
              "tex":       TexVisitor}


def check(pair_list):
    """RETURN: True, every claim held; False, at least one did not."""
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def verdict(ok, sentence):
    """RETURN: None. The one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


def _entry_of(measure):
    """RETURN: tuple, one point of the shape THAT measure encodes --
    found by asking the measure for its own round trip, so no shape is
    spelled here. None where neither candidate is its shape."""
    for candidate in (((3, 1, 2),), ((3, "name_x", 1, 1),)):
        try:
            if measure.decode(measure.encode(candidate)) == candidate:
                return candidate
        except Exception:                          # noqa BLE001
            continue
    return None


def _summary_of_every_measure():
    """RETURN: (SourceSummary, tuple of measure names), one source
    carrying a point of EVERY registered measure."""
    measure_db = {}
    for name in name_tuple():
        entry = _entry_of(measure_of(name))
        if entry is not None: measure_db[name] = entry
    summary = SourceSummary("src/a_b.c", ((1, 10),), ((1, 5),), ((5, 10),),
                            measure_db, ((("t0",), ((1, 5),)),))
    return summary, tuple(sorted(measure_db))


def _text_of(result):
    """RETURN: str, a visitor's result as text: a string as it is, a
    dict of pages joined."""
    if isinstance(result, dict): return "\n".join(result.values())
    return str(result)


def test_accounted():
    """Every visitor accounts for every registered measure."""
    summary, name_list = _summary_of_every_measure()
    print("  registered measures: %s" % ", ".join(name_list))
    pair_list = []
    for key in sorted(VISITOR_DB):
        visitor = VISITOR_DB[key]()
        text    = _text_of(walk(None, [summary], visitor))
        print("  %-9s declared unrendered: %s"
              % (key, ", ".join(sorted(visitor.unrendered_set)) or "(none)"))
        for name in name_list:
            measure  = measure_of(name)
            declared = name in visitor.unrendered_set
            #  RENDERED where the output carries the mark the visitor
            #  uses: the tag, the name, or the named point's own name.
            rendered = measure.tag in text or name in text or "name_x" in text
            spoken   = name in text
            pair_list.append((
                (declared and spoken) or (not declared and rendered),
                "%s: '%s' is %s" % (key, name,
                                    "declared unrendered and named"
                                    if declared else "rendered")))
        pair_list.append((bool(text.strip()), "%s produced output" % key))
    verdict(check(pair_list),
            "every converter renders a measure or says that it does not.")


def test_vocabulary():
    """No visitor defines a public name the base does not declare."""
    allowed = set(name for name, _ in
                  inspect.getmembers(I_OutputVisitor, inspect.isfunction))
    print("  the base declares: %s"
          % ", ".join(sorted(n for n in allowed if not n.startswith("_"))))
    pair_list = []
    for key in sorted(VISITOR_DB):
        cls = VISITOR_DB[key]
        own = {n for n, v in vars(cls).items()
               if not n.startswith("_") and (callable(v)
                                             or isinstance(v, staticmethod))}
        outside = sorted(own - allowed)
        pair_list.append((not outside,
                          "%s defines nothing outside the vocabulary%s"
                          % (key, "" if not outside
                                  else " -- found %s" % ", ".join(outside))))
    called = set()

    class Spy(I_OutputVisitor):
        """RETURN: None per method. Records that the walk called it."""
        def header(self, root, summary_list):   called.add("header")
        def source_open(self, summary):         called.add("source_open")
        def lines(self, ex, cv, un):            called.add("lines")
        def measure(self, m, entry):            called.add("measure")
        def who_ran(self, by_reference):        called.add("who_ran")
        def source_close(self, summary):        called.add("source_close")
        def done(self):                         called.add("done")

    summary, _ = _summary_of_every_measure()
    walk(None, [summary], Spy())
    declared = {n for n in allowed if not n.startswith("_") and n != "unrendered"}
    print("  the walk called:   %s" % ", ".join(sorted(called)))
    pair_list.append((called == declared,
                      "every declared step is a step the walk takes"))
    verdict(check(pair_list),
            "the base declares the vocabulary, and nothing else stands.")


def test_walk():
    """The traversal: order, registered order, no visit without a point."""
    order = []

    class Trace(I_OutputVisitor):
        """RETURN: None per method. Records the sequence of visits."""
        def header(self, root, summary_list):   order.append("header(%s)" % root)
        def source_open(self, summary):         order.append("open(%s)" % summary.source)
        def lines(self, ex, cv, un):            order.append("lines")
        def measure(self, m, entry):            order.append("measure(%s)" % m.name)
        def who_ran(self, by_reference):        order.append("who_ran(%i)" % len(by_reference))
        def source_close(self, summary):        order.append("close(%s)" % summary.source)
        def done(self):                         order.append("done"); return "built"

    full, name_list = _summary_of_every_measure()
    bare = SourceSummary("b.c", ((1, 3),), (), ((1, 3),), {"branch": ()}, ())
    result = walk("/r", [full, bare], Trace())
    for step in order: print("  %s" % step)
    measure_steps = [s for s in order if s.startswith("measure(")]
    ok = check([
        (order[0] == "header(/r)", "the header comes first, with the root"),
        (measure_steps == ["measure(%s)" % n for n in name_list],
         "measures come in registered-name order, every one once"),
        (order.index("close(src/a_b.c)") < order.index("open(b.c)"),
         "a source closes before the next opens"),
        (order[-1] == "done" and result == "built",
         "'done' is last and its value comes back"),
        ("who_ran(0)" in order, "a source nobody ran still passes 'who_ran'"),
    ])
    verdict(ok, "one traversal, in one order, with nothing visited that "
                "has no point.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The converters are visitors",
        choice_map = {
            "accounted":  test_accounted,
            "vocabulary": test_vocabulary,
            "walk":       test_walk,
        },
        happy      = "SUCCESS.*",
    ).run()
