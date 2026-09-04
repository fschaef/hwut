#! /usr/bin/env python3
#
# @hwut {
#     title      = "The presenters: every registered axis answered, and no name outside the vocabulary"
#     choices    = ["html", "text", "tex", "vocabulary", "walk"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE VISITOR OVER THE COVERAGE RECORD, checked from two sides.

    ONE CHOICE PER PRESENTER ('text', 'html', 'tex'). A record is built
    carrying EVERY REGISTERED MEASURE -- the registry is asked, never a
    list written here, so an axis added tomorrow enters this test the
    day it registers. The presenter is then walked over it and must
    ACCOUNT FOR EVERY AXIS: either render it, or declare it unrendered
    and say so in its output (RATIONALE D-29). An axis that is neither
    is a document that looks complete and is not, which is the failure
    this test exists to catch.

    'vocabulary' CHECKS THE OTHER DIRECTION: every public method a
    presenter defines must be one the base declares. A presenter
    writing 'file_opened' for 'file_open' is NEVER CALLED and nothing
    complains -- the walk asks for the name it knows. So a name the
    base does not declare is a defect, not an extension, and this
    refuses it.

    'walk' CHECKS THE TRAVERSAL ITSELF: the order of visits, that a
    measure with no point is not visited at all, and that files come
    in sorted order so two runs of one test present identically.

THE REGISTRY IS THE SOURCE OF TRUTH throughout. Nothing here spells
'branch' or 'mcdc' as a literal expectation.
______________________________________________________________________________
"""
import inspect
import sys

from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.coverage.measure import (name_tuple,           # noqa E402
                                           measure_of)
from   vut.engine.coverage.record  import (CoverageRecord,       # noqa E402
                                           FileCoverage,
                                           I_Presenter,
                                           TextPresenter,
                                           walk)
from   vut.engine.coverage.present import (HtmlPresenter,        # noqa E402
                                           TexPresenter)


PRESENTER_DB = {"text": TextPresenter,
                "html": HtmlPresenter,
                "tex":  TexPresenter}


def _check(pair_list):
    """RETURN: True, every claim held; False, at least one did not."""
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def _verdict(ok, sentence):
    """RETURN: None. Prints the one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


def _point_tuple_of(measure):
    """
    RETURN: tuple, one point of the shape THAT measure encodes -- found
            by asking the measure to decode a specimen it wrote itself,
            so no shape is spelled here.

    A measure is asked for its own round trip rather than told what its
    points look like: this test knows the VOCABULARY, never the grain.
    """
    for candidate in (((3, 1, 2),),               # PointMeasure
                      ((3, "name", 1, 2),)):      # NamedPointMeasure
        try:
            if measure.decode(measure.encode(candidate)) == candidate:
                return candidate
        except Exception:                          # noqa BLE001
            continue
    return None


def _record_of_every_measure():
    """
    RETURN: [0] CoverageRecord, one file carrying a point of EVERY
                registered measure.
            [1] tuple[str], the measure names it carries, sorted.

    THE REGISTRY DECIDES what is in it. An axis registered tomorrow is
    in this record tomorrow, with no edit here.
    """
    measure_db = {}
    for name in name_tuple():
        point_tuple = _point_tuple_of(measure_of(name))
        if point_tuple is not None: measure_db[name] = point_tuple
    entry  = FileCoverage("src/a_b.c", ((1, 10),), ((1, 5),), None,
                          measure_db)
    record = CoverageRecord(language="c", tool="gcov", source="demo",
                            counts_f=False, file_db={"src/a_b.c": entry})
    return record, tuple(sorted(measure_db))


def _accounted_for(presenter_class, record, name_list, text):
    """
    RETURN: list[(bool, str)], one claim per registered axis: it was
            RENDERED, or DECLARED unrendered and NAMED in the output.
            Never neither.

    AN AXIS IS 'RENDERED' WHERE THE OUTPUT CARRIES THE MARK THAT
    PRESENTER USES FOR IT -- its NAME where the presenter writes names
    (html, tex), its TAG where the presenter writes tags (the storage
    form: 'BR:', 'MC:'). Asking for the name alone would fail the one
    presenter that cannot be deficient, which would say more about the
    question than the answer.
    """
    presenter = presenter_class()
    walk(record, presenter)
    pair_list = []
    for name in name_list:
        declared = name in presenter.unrendered_set
        mark     = measure_of(name).tag
        spoken   = name in text or ("%s:" % mark) in text
        pair_list.append(
            (spoken,
             "'%s' is %s" % (name, "declared unrendered, and said"
                                   if declared else "rendered")))
    return pair_list


def _presenter_choice(key, sentence):
    """RETURN: None. One presenter, walked over every registered axis."""
    record, name_list = _record_of_every_measure()
    presenter_class   = PRESENTER_DB[key]
    text              = walk(record, presenter_class())
    print("  registered axes: %s" % ", ".join(name_list))
    probe = presenter_class()
    walk(record, probe)
    print("  declared unrendered: %s"
          % (", ".join(sorted(probe.unrendered_set)) or "(none)"))
    pair_list = _accounted_for(presenter_class, record, name_list, text)
    pair_list.append((bool(text.strip()), "the presenter produced output"))
    if probe.unrendered_set:
        pair_list.append(
            ("not rendered by this presenter" in text,
             "the output NAMES the gap, so a reader sees it"))
    _verdict(_check(pair_list), sentence)


def test_text():
    """The storage presenter -- the one that cannot be deficient."""
    _presenter_choice("text",
                      "the storage form writes every registered axis.")


def test_html():
    """The HTML presenter."""
    _presenter_choice("html",
                      "the page accounts for every registered axis.")


def test_tex():
    """The TeX presenter."""
    _presenter_choice("tex",
                      "the table accounts for every registered axis.")


def test_vocabulary():
    """No presenter defines a name the base does not declare."""
    allowed = set(name for name, _ in
                  inspect.getmembers(I_Presenter, inspect.isfunction))
    allowed |= {"unrendered"}
    print("  the base declares: %s"
          % ", ".join(sorted(n for n in allowed if not n.startswith("_"))))
    pair_list = []
    for key in sorted(PRESENTER_DB):
        cls   = PRESENTER_DB[key]
        own   = set(vars(cls)) - {"__doc__", "__module__", "__dict__",
                                  "__weakref__", "__abstractmethods__"}
        method_set = set(n for n in own
                         if callable(vars(cls)[n])
                         or isinstance(vars(cls)[n], staticmethod))
        outside = sorted(n for n in method_set
                         if not n.startswith("_") and n not in allowed
                         and n not in ("escaped",))
        pair_list.append((not outside,
                          "%s defines nothing outside the vocabulary%s"
                          % (key, "" if not outside
                                  else " -- found %s" % ", ".join(outside))))
    #  AND THE VOCABULARY IS REAL: every step the base declares is a
    #  step the walk actually takes. A declared method nobody calls
    #  would be a promise the traversal does not keep.
    called = set()

    class Spy(I_Presenter):
        """RETURN: None per method. Records that the walk called it."""
        def header(self, record):        called.add("header")
        def file_open(self, path, e):    called.add("file_open")
        def lines(self, ex, cv, counts): called.add("lines")
        def measure(self, m, points):    called.add("measure")
        def file_close(self, path, e):   called.add("file_close")
        def done(self):                  called.add("done")

    record, _ = _record_of_every_measure()
    walk(record, Spy())
    declared = set(n for n in allowed
                   if not n.startswith("_") and n != "unrendered")
    print("  the walk called:   %s" % ", ".join(sorted(called)))
    pair_list.append((called == declared,
                      "every declared step is a step the walk takes"))
    _verdict(_check(pair_list),
             "the base declares the vocabulary, and nothing else stands.")


def test_walk():
    """The traversal: order, sorted files, and no visit without a point."""
    order = []

    class Trace(I_Presenter):
        """RETURN: None per method. Records the sequence of visits."""
        def header(self, record):        order.append("header")
        def file_open(self, path, e):    order.append("open:%s" % path)
        def lines(self, ex, cv, counts): order.append("lines")
        def measure(self, m, points):    order.append("measure:%s" % m.name)
        def file_close(self, path, e):   order.append("close:%s" % path)
        def done(self):                  order.append("done"); return None

    #  TWO FILES, DELIBERATELY OUT OF ORDER, and one carrying NO measure.
    bare  = FileCoverage("z/last.c",  ((1, 3),), ((1, 2),), None, {})
    first = name_tuple()[0]
    rich  = FileCoverage("a/first.c", ((1, 9),), ((1, 4),), None,
                         {first: _point_tuple_of(measure_of(first))})
    record = CoverageRecord(language="c", tool="t", source="s",
                            counts_f=False,
                            file_db={"z/last.c": bare, "a/first.c": rich})
    walk(record, Trace())
    for step in order: print("    %s" % step)
    ok = _check([
        (order[0] == "header",  "the header comes first"),
        (order[-1] == "done",   "'done' comes last"),
        (order.index("open:a/first.c") < order.index("open:z/last.c"),
         "files are visited in SORTED order, not insertion order"),
        (order.count("measure:%s" % first) == 1,
         "the file carrying a point is visited for it"),
        (order.count("measure") == 0,
         "a file carrying NO point is not visited for any measure"),
        (order.index("lines") < order.index("measure:%s" % first),
         "the line axis precedes the other measures"),
    ])
    _verdict(ok, "the traversal is ordered, sorted, and visits no absence.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The presenters: every registered axis answered",
        choice_map = {
            "html":       test_html,
            "text":       test_text,
            "tex":        test_tex,
            "vocabulary": test_vocabulary,
            "walk":       test_walk,
        }).run()
