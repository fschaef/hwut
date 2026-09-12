"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: state -> rows. WHAT the two panes show, with no notion of how
         it is painted.

DESCRIPTION
       A ROW pairs one subject line with one nominal line, either of
       which may be absent. Rows are built by walking the NOMINAL in
       order and laying each paired subject line beside its partner;
       a subject line with no partner is laid out before the next
       partnered one, and a nominal line with none stands alone.

       THE MARKERS STAND LEVEL WITH THE CONTENT THEY FRAME (spec P-35).
       A region's '##! unaccepted' is a nominal line with no partner,
       and so is its '####': they take a row of their own, the subject
       side blank. Between them the fillers pair 1:1 with the subject
       lines they stand for, so the two panes stay level throughout.

       EVERY ROW CARRIES ITS OWN KIND, so that a painter need decide
       nothing: cursor, marked, target-virgin, target-latched, marker,
       filler, token, plain. The painter maps kinds to styles and that
       is the whole of its judgement.

       THIS MODULE IMPORTS NOTHING OF 'prompt_toolkit'.
______________________________________________________________________________
"""
from vut.services.lib.viewers.keyed.act    import E_Pane
from vut.services.lib.viewers.keyed.region import (UNACCEPTED_BEGIN_LINE,
                                                   FILLER_LINE)
from vut.services.lib.viewers.keyed.state  import CLOSING_TOKEN
from vut.engine.compare.reading.line_scanner import REGION_END_LINE

from dataclasses import dataclass
from enum        import Enum, auto


class E_Kind(Enum):
    """What a cell IS, for a painter to style."""
    PLAIN     = auto()
    MARKER    = auto()   # '##! unaccepted' or '####'
    FILLER    = auto()   # '--?--'
    TOKEN     = auto()   # '<hwut-end>'
    ABSENT    = auto()   # no line on this side of the row


@dataclass(frozen=True)
class Cell:
    """One side of a row."""
    text:      str
    kind:      E_Kind
    cursor_f:  bool = False   # the cursor of THIS pane stands here
    marked_f:  bool = False   # inside the range the author anchored
    target_f:  bool = False   # inside the range a take would replace
    virgin_f:  bool = True    # ... and that target is still derived
    index:     int  = -1      # the line's index in its own list, or -1


@dataclass(frozen=True)
class Row:
    subject: Cell
    nominal: Cell


ABSENT = Cell("", E_Kind.ABSENT)


def project(state):
    """RETURN: tuple[Row], the screen's rows in order -- each subject
               line beside the nominal line it is paired with, markers
               and unpartnered lines on rows of their own.
    """
    rev = {i_n: i_s for i_s, i_n in state.pairing.items() if i_n is not None}
    subject_n = len(state.subject_line_list)
    nominal_n = len(state.nominal_line_list)

    rows, s_next = [], 0
    for i_n in range(nominal_n):
        i_s = rev.get(i_n)
        if i_s is None:
            rows.append(Row(ABSENT, _nominal_cell(state, i_n)))
            continue
        while s_next < i_s:
            rows.append(Row(_subject_cell(state, s_next), ABSENT))
            s_next += 1
        rows.append(Row(_subject_cell(state, i_s), _nominal_cell(state, i_n)))
        s_next = i_s + 1
    while s_next < subject_n:
        rows.append(Row(_subject_cell(state, s_next), ABSENT))
        s_next += 1
    return tuple(rows)


def banner(state, subject_name):
    """RETURN: str, the one line above the panes -- the subject's name,
               which pane the keys drive, and how stale the marks are.
    """
    pane  = "SUBJECT" if state.pane is E_Pane.SUBJECT else "NOMINAL"
    stale = ("takes since realign: %i" % state.take_n_since_realign
             if state.take_n_since_realign else "aligned")
    latch = "virgin" if state.virgin_f else "AIMED"
    return "%s   [%s]   target %s   %s   ?=help" % (subject_name, pane,
                                                    latch, stale)


def row_of_cursor(rows, pane):
    """RETURN: int, the index of the row carrying the active pane's
               cursor.

               0, where no row carries it -- an empty stream.
    """
    for i, row in enumerate(rows):
        cell = row.subject if pane is E_Pane.SUBJECT else row.nominal
        if cell.cursor_f: return i
    return 0


#  ----------------------------------------------------------------- cells

def _subject_cell(state, i_s):
    """RETURN: Cell, subject line 'i_s' with its flags."""
    text = state.subject_line_list[i_s]
    first_s, last_s = state.subject_range()
    return Cell(text     = text,
                kind     = _kind_of(text),
                cursor_f = (i_s == state.cursor_s),
                marked_f = (state.anchor_s is not None and first_s <= i_s <= last_s),
                index    = i_s)


def _nominal_cell(state, i_n):
    """RETURN: Cell, nominal line 'i_n' with its flags -- including
               whether a take would replace it, and whether that target
               is still the alignment's or the author's own.
    """
    text   = state.nominal_line_list[i_n]
    target = state.target_range()
    marked = state.marked_nominal_range()
    return Cell(text     = text,
                kind     = _kind_of(text),
                cursor_f = (i_n == state.cursor_n),
                marked_f = (marked is not None and marked[0] <= i_n <= marked[1]),
                target_f = (target is not None and target[0] <= i_n <= target[1]),
                virgin_f = state.virgin_f,
                index    = i_n)


def _kind_of(text):
    """RETURN: E_Kind, what this line is -- decided by the text alone,
               the same way 'region_list_of' reads it.
    """
    stripped = text.strip()
    if stripped == UNACCEPTED_BEGIN_LINE: return E_Kind.MARKER
    if stripped == REGION_END_LINE:       return E_Kind.MARKER
    if stripped == FILLER_LINE:           return E_Kind.FILLER
    if stripped == CLOSING_TOKEN:         return E_Kind.TOKEN
    return E_Kind.PLAIN
