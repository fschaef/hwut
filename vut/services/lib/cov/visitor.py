"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE VISITOR OVER AN OUTPUT DIRECTORY -- the one traversal every
         converter ('conv/to_<format>.py') is written over (coverage
         RATIONALE D-44, under the law of D-29).

DESCRIPTION
       'walk(root, summary_list, visitor)' is the traversal;
       'I_OutputVisitor' is the operation half. The converters are
       visitors, and NOTHING ELSE reads a 'SourceSummary'.

       THE VOCABULARY, every step abstract on the base so a visitor
       answers each one way or the other -- rendering, or stating that
       it emits nothing there:

           header(root, summary_list)   the whole run, before any
                                        source: for an index, totals,
                                        the root
           source_open(summary)         one source begins
           lines(executable, covered, uncovered)
                                        the line axis
           measure(measure, entry)      one measure the source carries,
                                        in REGISTERED-NAME order; a
                                        measure with no point is not
                                        visited
           who_ran(by_reference)        per reference with lines, the
                                        run names and the ranges -- the
                                        one fact only hwut's own
                                        formats carry
           source_close(summary)        the source ends
           done()                       whatever the visitor built

       A MEASURE A VISITOR DOES NOT RENDER IS DECLARED, NOT DROPPED
       ('unrendered'): a fraction standing in for MC/DC looks like a
       presentation and is not one (D-29). 'done' says the names where
       the medium allows -- an XML comment, a TeX remark, an HTML
       paragraph, an lcov comment line -- so a reader sees the gap.
       The two formats that carry the measure's OWN SHAPE (json, and
       the text spelling of the record) render every measure by
       construction and declare none.

       'TEST/test-cov_visitor.py' holds every visitor to D-29's two
       checks: every registered measure accounted for, and no public
       name outside this vocabulary.
______________________________________________________________________________
"""
from   abc import ABC, abstractmethod

from   vut.engine.coverage.api import measure_of, name_tuple


class I_OutputVisitor(ABC):
    """One operation over an output directory (module header)."""

    def __init__(self):
        self.unrendered_set = set()

    @abstractmethod
    def header(self, root, summary_list):
        """RETURN: None. The run: its root (None where the marker names
        none) and every source's summary, in path order."""

    @abstractmethod
    def source_open(self, summary):
        """RETURN: None. One source file begins."""

    @abstractmethod
    def lines(self, executable, covered, uncovered):
        """RETURN: None. The line axis, as ranges: what could run, what
        did (the union over every run), what did not."""

    @abstractmethod
    def measure(self, measure, entry):
        """
        RETURN: None. One measure of this source, the entry in the
                measure's own shape over EVERY run (measure.py).

        A visitor renders the measures it knows and calls 'unrendered'
        for the rest; it may not simply ignore one.
        """

    def unrendered(self, measure):
        """RETURN: None. THIS VISITOR CANNOT RENDER THAT MEASURE, and
        says so: the name is collected, and 'done' states it where the
        medium allows. Not an override point."""
        self.unrendered_set.add(measure.name)

    @abstractmethod
    def who_ran(self, by_reference):
        """RETURN: None. Per reference with lines: (tuple of run names,
        tuple of (begin, end)), in reference order."""

    @abstractmethod
    def source_close(self, summary):
        """RETURN: None. The source ends."""

    @abstractmethod
    def done(self):
        """RETURN: object, whatever the visitor built -- what 'walk'
        hands back."""


def walk(root, summary_list, visitor):
    """
    RETURN: object, 'visitor.done()'.

    THE ONE TRAVERSAL of an output directory: sources in the order the
    summaries come (path order), measures in registered-name order, a
    measure with no point not visited.
    """
    visitor.header(root, summary_list)
    for summary in summary_list:
        visitor.source_open(summary)
        visitor.lines(summary.executable, summary.covered, summary.uncovered)
        for name in name_tuple():
            entry = summary.measure_db.get(name)
            if not entry: continue
            visitor.measure(measure_of(name), entry)
        visitor.who_ran(summary.by_reference)
        visitor.source_close(summary)
    return visitor.done()
