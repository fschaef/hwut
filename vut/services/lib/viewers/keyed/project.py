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

       THE LABEL STANDS BESIDE THE FIRST SURVIVOR (ruling: the label
       displaces the region's first filler). A region's fillers pair
       1:1 with the subject lines they stand for, so the first filler
       and the '##! unaccepted' above it both want the first not-copied
       subject line's row. The LABEL takes it and that filler is NOT
       drawn: four fillers become the label and three rows, and a
       person reading down the region sees, on the very line the label
       is on, which subject line is still undecided.

       IT IS PROJECTION ONLY. The region's text is untouched, so
       'region_take' is unchanged and compare never sees the
       displacement.

       '####' KEEPS ITS OWN ROW, subject side blank. Giving it the LAST
       survivor by the same rule was weighed and dropped: a region with
       ONE content line would then need both markers on one row, and
       the shape has no answer for its own edge case.

       EVERY ROW CARRIES ITS OWN KIND, so that a painter need decide
       nothing: cursor, marked, target-virgin, target-latched, marker,
       filler, token, plain. The painter maps kinds to styles and that
       is the whole of its judgement.

       THIS MODULE IMPORTS NOTHING OF 'prompt_toolkit'.
______________________________________________________________________________
"""
from vut.services.lib.viewers.keyed.act    import E_Pane
from vut.services.lib.viewers.keyed        import keymap
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
    COPIED    = auto()   # a subject line already taken -- spent (L-13)
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
    label_db, displaced_set, label_flag_db = _label_partner_db(state, rev)

    rows, s_next = [], 0
    for i_n in range(nominal_n):
        if i_n in displaced_set: continue     # its row belongs to the label
        i_s = label_db.get(i_n, rev.get(i_n))
        if i_s is not None and i_s < s_next:
            #  A CROSSING PAIR: its subject line is already on the screen.
            #  An aimed take can put a subject line above the partner of
            #  an earlier one; two columns cannot draw that side by side,
            #  and drawing the subject line AGAIN was measured to read as
            #  nominal text copied into the subject. The nominal line
            #  stands alone until 'g' asks compare again; a label that
            #  loses its partner gives its filler back its own row.
            if i_n in label_db: displaced_set.discard(label_flag_db.pop(i_n))
            i_s = None
        if i_s is None:
            rows.append(Row(ABSENT, _nominal_cell(state, i_n,
                                                  flag_i=label_flag_db.get(i_n))))
            continue
        while s_next < i_s:
            rows.append(Row(_subject_cell(state, s_next), ABSENT))
            s_next += 1
        rows.append(Row(_subject_cell(state, i_s),
                        _nominal_cell(state, i_n,
                                      flag_i=label_flag_db.get(i_n))))
        s_next = i_s + 1
    while s_next < subject_n:
        rows.append(Row(_subject_cell(state, s_next), ABSENT))
        s_next += 1
    return tuple(rows)


def _label_partner_db(state, rev):
    """
    RETURN: [0] dict, the nominal index of each unaccepted region's
                '##! unaccepted' line -> the subject index to lay beside
                it: the FIRST not-copied subject line the region stands
                for.
            [1] set, the nominal indices NOT to draw -- each region's
                first content filler, whose row the label has taken.
            [2] dict, the label's nominal index -> the displaced
                filler's index, so the shared row carries the FILLER's
                flags: a take aimed at that survivor must still show
                what it would replace, and the nominal cursor standing
                on the filler must still be seen.

    A region with no content, or whose first content line the pairing
    gives no subject partner, appears in neither: its label keeps its
    own row with the subject side blank, as before.
    """
    label_db, displaced_set, label_flag_db = {}, set(), {}
    for region in state.region_list():
        if not region.unaccepted_f(): continue
        first_i, last_i = region.content_range()
        if first_i > last_i: continue
        i_s = rev.get(first_i)
        if i_s is None: continue
        label_db[region.begin_i]      = i_s
        label_flag_db[region.begin_i] = first_i
        displaced_set.add(first_i)
    return label_db, displaced_set, label_flag_db


def foot(hint_list, width, head="<F1>=help"):
    """RETURN: str, the bottom bar (E-93): 'head' at the LEFT, the key
               hints RIGHT-ALIGNED -- as many whole hints as the width
               allows, dropped one at a time from the right; a hint is
               never cut. Without 'width', everything."""
    hint_list = list(hint_list)
    if width is None:
        return "%s   %s" % (head, "  ".join(hint_list))
    room = width - 1
    while hint_list and len(head) + 3 + len("  ".join(hint_list)) > room:
        hint_list.pop()
    right = "  ".join(hint_list)
    pad   = max(1, room - len(head) - len(right))
    return head + " " * pad + right


def banner(state, subject_name, basic=None, width=None):
    """RETURN: str, kept for the tests: the foot without a name."""
    if basic is None: basic = keymap.basic_text()
    hint_list = basic.split("  ")
    hint_list = [h for h in hint_list if not h.startswith("<F1>")]
    return foot(hint_list, width)


def fitted(piece_tuple, drop_order, width, tail="F1=help"):
    """RETURN: str, the pieces joined by three spaces and 'tail' set at
               the right edge of 'width' -- pieces dropped in
               'drop_order' (their indices) until the line fits; the
               line cut only where even the first piece alone does not.
               Without 'width', every piece and 'tail', unpadded."""
    piece_list = list(piece_tuple)
    def line_of():
        return "   ".join(p for p in piece_list if p)
    if width is None: return "%s   %s" % (line_of(), tail)
    #  ONE COLUMN SPARE: a line as wide as the screen was measured to
    #  wrap its last character onto the next row.
    width -= 1
    for i in drop_order:
        if len(line_of()) + 3 + len(tail) <= width: break
        piece_list[i] = ""
    left = line_of()
    room = width - len(tail) - 1
    if len(left) > room: left = left[:max(room, 0)]
    return left + " " * (width - len(left) - len(tail)) + tail


#  THE SECOND HEADER (E-86): what each pane IS. The subject is what the
#  program printed; the nominal is what it is judged against.
PANE_TITLE_DB = {E_Pane.SUBJECT: "OUTPUT", E_Pane.NOMINAL: "GOOD"}


def pane_title(state, pane, subject_name="", differ_n=0):
    """RETURN: str, the pane's heading (E-90) -- 'OUTPUT of <test>
               <choice>' or 'GOOD' -- marked '>' where the keys drive
               that pane."""
    mark = ">" if state.pane is pane else " "
    name = PANE_TITLE_DB[pane]
    if pane is E_Pane.SUBJECT and subject_name:
        name = "%s of: %s" % (name, subject_name)
    if pane is E_Pane.NOMINAL and differ_n:
        name = "%s   %i differ" % (name, differ_n)
    return "%s %s" % (mark, name)


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
    """RETURN: Cell, subject line 'i_s' with its flags -- COPIED where
               the line is spent (L-13), whatever its text says.
    """
    text = state.subject_line_list[i_s]
    first_s, last_s = state.subject_range()
    return Cell(text     = text,
                kind     = E_Kind.COPIED if state.copied_f(i_s)
                           else _kind_of(text),
                cursor_f = (i_s == state.cursor_s),
                marked_f = (state.anchor_s is not None and first_s <= i_s <= last_s),
                index    = i_s)


def _nominal_cell(state, i_n, flag_i=None):
    """RETURN: Cell, nominal line 'i_n' with its flags -- including
               whether a take would replace it, and whether that target
               is still the alignment's or the author's own.

    'flag_i' names a DIFFERENT nominal line whose flags this cell is to
    wear: the filler a label displaced. The text stays the label's; the
    cursor, the mark and the target are the filler's, because that is
    the line this row now stands for.
    """
    text   = state.nominal_line_list[i_n]
    target = state.target_range()
    marked = state.marked_nominal_range()
    if flag_i is not None: i_n = flag_i
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
