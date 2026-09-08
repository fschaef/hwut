#! /usr/bin/env python3
#
# @hwut {
#     title      = "Region framing: switchable, and its fault is caught"
#     choices    = ["caught", "content", "declared", "off", "on"]
#     interactive = true
#     tolerance { regions = false  eq_pattern = ["SUCCESS.*"] }
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

REGION FRAMING IS A LEXICAL FEATURE LIKE THE REST (compare C-4), and
like the rest it has a switch: 'regions_f', the hwut word
'tolerance.regions'.

    on         the default: '##! <handler>' opens a region, '####'
               closes it, and a malformed shebang is LOUD.
    off        the same two lines are NO LONGER REGIONS: nothing is
               framed, nothing is refused, and a text that talks
               ABOUT framing can be read. They fall to the ORDINARY
               rules, where '##! ...' meets the ignored-line marker
               '##' and reads as a COMMENT -- switching regions off
               does not invent a class, it removes one.
    content    the case that forced this (C-4): a side-by-side table
               whose CELLS hold '##! potpourri' -- unreadable with
               regions on, equivalent to itself with them off.
    declared   the switch is announced where every parameter is: it
               has a default in the declaration, and the hwut word
               'tolerance.regions' relates to it.
    caught     the one fault a caller must catch IS caught on the
               READING road (C-5): 'reading_view' answers False and
               names the line, rather than raising into the face.

THIS FILE STATES 'tolerance { regions = false }' ITSELF: its own
output quotes framing markers, which is the very predicament the
switch exists for.
______________________________________________________________________________
"""
import asyncio
import io
import sys

from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.compare.api import (Configuration,             # noqa E402
                                      RegionSyntaxError,
                                      is_equivalent)
from   vut.engine.compare.reading.line_scanner import classify   # noqa E402
from   vut.engine.compare.reading.pattern_finder import PatternFinder  # noqa E402
from   vut.services.diff    import reading_view                  # noqa E402

#  The table that forced C-4: each CELL holds a framing marker.
TABLE = ("SUBJECT                        | NOMINAL\n"
         "Define ((A))                   | Define ((1))\n"
         "##! potpourri                  | ##! potpourri\n"
         "Use ((A))                      | Use ((1))\n"
         "####                           | ####\n")

FRAMED = "before\n##! potpourri\ninside\n####\nafter\n"


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


def _configuration(regions_f):
    """RETURN: Configuration, with the framing switch as given."""
    configuration = Configuration()
    configuration.pattern_finder.regions_f = regions_f
    return configuration


def _class_of(line, regions_f):
    """RETURN: str, the E_LineClass name 'line' is read as."""
    finder = PatternFinder(_configuration(regions_f).pattern_finder)
    return classify(line, finder).name


def _equivalent(text, regions_f):
    """
    RETURN: True/False, the text against itself.
            str, the RegionSyntaxError's message where reading refused.
    """
    try:
        return asyncio.run(is_equivalent(_configuration(regions_f),
                                         io.StringIO(text),
                                         io.StringIO(text)))
    except RegionSyntaxError as error:
        return str(error)


def test_on():
    """The default: the markers frame, and a bad shebang is loud."""
    begin = _class_of("##! potpourri\n", True)
    end   = _class_of("####\n",          True)
    bad   = _equivalent("##! quacksalber\n####\n", True)
    print("  '##! potpourri' reads as %s" % begin)
    print("  '####'          reads as %s" % end)
    ok = _check([
        (begin == "REGION_BEGIN", "the shebang opens a region"),
        (end   == "REGION_END",   "the rule closes it"),
        (_equivalent(FRAMED, True) is True,
         "a well-framed text is equivalent to itself"),
        (isinstance(bad, str) and "unknown region handler" in bad,
         "an unknown handler is refused, by name"),
    ])
    _verdict(ok, "with regions on, the markers frame and faults are loud.")


def _class_no_comments(line):
    """RETURN: str, the class of 'line' with regions AND the ignored-line
    marker both off -- nothing left to claim it."""
    configuration = _configuration(False)
    configuration.pattern_finder.ignored_line_f            = False
    configuration.pattern_finder.ignored_line_begin_marker = "\x00"
    configuration.pattern_finder.ignored_line_end_marker   = "\x00"
    return classify(line, PatternFinder(configuration.pattern_finder)).name


def test_off():
    """Switched off, the two lines are no longer regions -- they fall
    to the ordinary rules."""
    begin = _class_of("##! potpourri\n", False)
    end   = _class_of("####\n",          False)
    bad   = _equivalent("##! quacksalber\n####\n", False)
    print("  '##! potpourri' reads as %s" % begin)
    print("  '####'          reads as %s" % end)
    print("  with comments off too:  %s / %s"
          % (_class_no_comments("##! potpourri\n"),
             _class_no_comments("####\n")))
    ok = _check([
        (begin != "REGION_BEGIN", "the shebang no longer opens a region"),
        (end   != "REGION_END",   "the rule no longer closes one"),
        (begin == "IGNORED" and end == "IGNORED",
         "they fall to the ordinary rules, where '##' means comment"),
        (_class_no_comments("##! potpourri\n") == "CONTENT"
         and _class_no_comments("####\n") == "CONTENT",
         "with comments off too, nothing claims them: CONTENT"),
        (_equivalent(FRAMED, False) is True,
         "the framed text is still equivalent to itself"),
        (bad is True,
         "an unknown handler is no fault: it was never a handler"),
        (_class_of("\n", False) == "BLANK",
         "and the other classes are untouched: a blank is BLANK"),
    ])
    _verdict(ok, "switching regions off removes a class, it invents none.")


def test_content():
    """The case that forced the switch: framing inside a table."""
    on  = _equivalent(TABLE, True)
    off = _equivalent(TABLE, False)
    print("  regions on:  %s" % (on if isinstance(on, str)
                                 else "equivalent"))
    print("  regions off: %s" % ("equivalent" if off is True else off))
    ok = _check([
        (isinstance(on, str) and "knows no parameter" in on,
         "with regions on the table cannot be read, and says why"),
        (off is True,
         "with regions off it is equivalent to itself"),
    ])
    _verdict(ok, "a text that talks about framing can be read.")


def test_declared():
    """The switch is announced where every parameter is."""
    from dataclasses import fields
    from vut.engine.compare.configuration import ConfigurationPatternFinder
    from vut.engine.orchestrator.exploration.relation import (RELATION,
                                                              default_of)
    declared = {f.name: f.default
                for f in fields(ConfigurationPatternFinder)}
    related  = RELATION.get("tolerance.regions")
    print("  declaration: regions_f = %s"
          % declared.get("regions_f"))
    print("  hwut word:   tolerance.regions -> %s"
          % (related[1] if related else "(unrelated)"))
    ok = _check([
        (declared.get("regions_f") is True,
         "compare declares it, and its default is ON"),
        (related is not None and related[1] == "regions_f",
         "the hwut word 'tolerance.regions' names it"),
        (default_of("tolerance.regions") is True,
         "so the default is derivable, as every other's is"),
    ])
    _verdict(ok, "the declaration is the announcement.")


class _Silent:
    """A display adapter that accepts the sequence and shows nothing:
    this test judges the REFUSAL, not the rendering."""

    async def open(self, subject_name=None):  pass
    async def present(self, item):            pass
    async def close(self):                    pass


def test_caught():
    """The reading road catches the one fault a caller must catch."""
    line_list = []
    shown_f   = asyncio.run(reading_view(TABLE, _Silent(),
                                         subject_name="table",
                                         write=line_list.append))
    for line in line_list[:2]: print("  " + line)
    ok = _check([
        (shown_f is False, "the reading answers False, and does not raise"),
        (any(l.startswith("REFUSED:") for l in line_list),
         "it says REFUSED"),
        (any("line 3:" in l for l in line_list),
         "and names the line that could not be read"),
    ])
    _verdict(ok, "the fault is caught on the road that meets it.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Region framing: switchable, and its fault is caught",
        choice_map = {
            "caught":   test_caught,
            "content":  test_content,
            "declared": test_declared,
            "off":      test_off,
            "on":       test_on,
        }).run()
