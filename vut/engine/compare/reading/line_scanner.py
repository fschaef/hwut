"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: THE single classification of raw input lines.

Both chunk pipes (equivalence and association) see the input through this
scanner. The pipes differ only in PACKAGING -- what they do with a class --
never in CLASSIFICATION. A line is one of:

    REGION_BEGIN       shebang region opening: '##! <handler> <params...>'
                       (interpretation of the tail: 'region/registry.py').
    REGION_END         region closing: the line '####', exactly (longer
                       '#'-runs remain IGNORED commentary bars).
    BLANK              only whitespace.
    IGNORED            carries the ignored-line markers ('##...' / '...##').
    CONTENT            everything else -- subject to comparison.

INSIGNIFICANCE INVARIANT (single-sourced with 'contract/semantics.py'):

    classify(line, pf) in INSIGNIFICANT_LINE_CLASS_SET
        <=>  semantics.is_insignificant_line(line, ...)

BLANK and IGNORED refine the insignificance judgment for reporting; they
never disagree with it. The equivalence pipe DROPS insignificant lines (the
Judge never sees them); the association pipe KEEPS them for display (they
are neutral filler in the Lawyer's reduction, see 'LinePair.is_equivalent').

PRECEDENCE (fixed, load-bearing):

    REGION_BEGIN  >  REGION_END  >  BLANK  >  IGNORED  >  CONTENT

A region marker must be recognized BEFORE the generic ignored-line rule:
the shebang framing ('##!', '####') BEGINS with the ignored-line marker
'##'. A line of five or more '#' is NOT a region end -- it stays an
IGNORED commentary bar; only the exact '####' closes a region.

NOT scanner business: the whole-line VISIBLE_NOTHING skip. That judgment
requires LEXING ('Line.is_visible_nothing'); the scanner classifies raw
text only. The equivalence pipe applies it after construction of 'Line'.
________________________________________________________________________________
"""
from enum import Enum, auto

from vut.engine.compare.contract.semantics import is_insignificant_line


class E_LineClass(Enum):
    REGION_BEGIN     = auto()
    REGION_END       = auto()
    BLANK            = auto()
    IGNORED          = auto()
    CONTENT          = auto()


INSIGNIFICANT_LINE_CLASS_SET = frozenset((E_LineClass.BLANK,
                                          E_LineClass.IGNORED))

REGION_BEGIN_MARKER = "##!"
REGION_END_LINE     = "####"


def classify(line, pattern_finder):
    """RETURNS: E_LineClass, the classification of the raw text 'line' under
                             the markers configured in 'pattern_finder'.

    Precedence as documented in the module header; the insignificance
    judgment itself (BLANK or IGNORED) delegates to
    'semantics.is_insignificant_line' -- THE single definition.
    """
    stripped = line.strip()
    if stripped.startswith(REGION_BEGIN_MARKER):
        return E_LineClass.REGION_BEGIN
    elif stripped == REGION_END_LINE:
        return E_LineClass.REGION_END
    elif not stripped:
        return E_LineClass.BLANK
    elif is_insignificant_line(line,
                               pattern_finder.ignored_line_begin_marker,
                               pattern_finder.ignored_line_end_marker):
        return E_LineClass.IGNORED
    else:
        return E_LineClass.CONTENT
