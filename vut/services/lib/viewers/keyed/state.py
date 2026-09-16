"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE MERGE STATE -- two cursors, a marked range, a target, and
         what the author has done so far.

DESCRIPTION
       THIS MODULE IMPORTS NOTHING OF 'prompt_toolkit'. The derived
       target, the virgin latch, the whole-range take and the region
       split are RULINGS, and a ruling belongs in a module that can
       state it -- not inferred from two Buffer cursor positions. It is
       therefore constructible, and every law testable, with the import
       absent.

       IT HOLDS NO VIEWPORT OFFSET. Scrolling belongs to the layout, and
       the layout is 'prompt_toolkit's; a second copy of the offset here
       is the classic bug of this shape, seen by the author as a cursor
       that jumps.

       ABSENCE IS None. No line number stands in for 'no anchor'.
______________________________________________________________________________
"""
from vut.services.lib.viewers.keyed.act    import E_Pane
from vut.services.lib.viewers.keyed.region import region_list_of, region_of

from dataclasses import dataclass, replace, field

CLOSING_TOKEN = "<hwut-end>"


@dataclass(frozen=True)
class MergeState:
    """Everything the keyed session knows.

    'pairing' maps a subject line index to the nominal line index it
    stands against, or to None where the nominal has no partner for it.
    It comes from compare on entry and from the local re-index after
    every take.

    'copied_s' holds every subject line already COPIED into the nominal.
    A copied line is SPENT: no cursor reaches it and no range may
    intersect one. It is NOT derivable from 'pairing' -- a REALIGN
    re-pairs from scratch and an identical line pairs the same whether
    it was copied or always matched -- so it is recorded, and it
    survives a REALIGN because the subject text never changes within a
    session.
    """
    subject_line_list: tuple = ()
    nominal_line_list: tuple = ()
    pairing:           dict  = field(default_factory=dict)

    pane:      object = E_Pane.SUBJECT
    cursor_s:  int    = 0
    cursor_n:  int    = 0
    anchor_s:  object = None      # None -- no range marked in the subject
    anchor_n:  object = None      # None -- no range marked in the nominal
    virgin_f:  bool   = True      # the target still tracks the subject

    copied_s:  frozenset = frozenset()   # subject lines already COPIED
    aspirant_f: bool  = False     # no nominal stood when the session opened

    take_n_since_realign: int   = 0
    undo_stack:           tuple = ()

    #  ---------------------------------------------------------------- ranges

    def subject_range(self):
        """RETURN: (int, int), the first and last subject line the author
                   has marked, both inclusive.

                   The cursor line twice, where no anchor stands: an
                   unmarked take is a take of one line.
        """
        if self.anchor_s is None: return (self.cursor_s, self.cursor_s)
        return (min(self.anchor_s, self.cursor_s),
                max(self.anchor_s, self.cursor_s))

    def derived_target(self):
        """RETURN: (int, int), the nominal range the ALIGNMENT puts
                   opposite the marked subject range -- what a take
                   replaces while the target is still virgin.

                   None, where the pairing gives the marked subject lines
                   no nominal partner at all: an insertion has no lines
                   to replace, and the take becomes one at the seam,
                   which 'insertion_seam' names.
        """
        first_s, last_s = self.subject_range()
        partner_list = [self.pairing.get(i) for i in range(first_s, last_s+1)]
        partner_list = [i for i in partner_list if i is not None]
        if not partner_list: return None
        return (min(partner_list), max(partner_list))

    def insertion_seam(self):
        """RETURN: int, the nominal index BEFORE which lines with no
                   partner are to be inserted -- the line after the
                   nearest paired subject line above the marked range.

                   0, where nothing above the range is paired: the
                   insertion belongs at the top.
        """
        first_s, _ = self.subject_range()
        for i in range(first_s-1, -1, -1):
            partner = self.pairing.get(i)
            if partner is not None: return partner + 1
        return 0

    def marked_nominal_range(self):
        """RETURN: (int, int), the nominal range the author has marked
                   with his own anchor, both ends inclusive.

                   None, where he has marked none -- which is the state
                   a virgin target is in until he widens or moves it.

        This is asked SEPARATELY from 'target_range' on purpose: the
        latch must compare what the author marked against what the
        alignment derives, and a 'target_range' that answers 'derived'
        while virgin could never differ from it.
        """
        if self.anchor_n is None: return None
        return (min(self.anchor_n, self.cursor_n),
                max(self.anchor_n, self.cursor_n))

    def target_range(self):
        """RETURN: (int, int), the nominal lines a take would replace --
                   the author's own marked range where he has aimed one,
                   otherwise the range the alignment derives.

                   None, where neither stands: the take is an insertion
                   at 'insertion_seam' and replaces nothing.
        """
        if not self.virgin_f:
            marked = self.marked_nominal_range()
            if marked is not None: return marked
        return self.derived_target()

    #  --------------------------------------------------------------- regions

    def region_list(self):
        """RETURN: tuple[Region], the unaccepted regions standing in the
                   working nominal, read from the text itself.
        """
        return region_list_of(self.nominal_line_list)

    def region_at_cursor(self):
        """RETURN: Region, the region whose CONTENT holds the nominal
                   cursor.

                   None, where the cursor stands outside every region or
                   on a region's own marker line.
        """
        return region_of(self.region_list(), self.cursor_n)

    #  ------------------------------------------------------------ the anchor

    def token_i_s(self):
        """RETURN: int, the index of the subject's closing-token line.

                   None, where the subject carries none -- a stream that
                   never COMPLETED, which no session may open on (R-70).
        """
        return _token_i(self.subject_line_list)

    def token_i_n(self):
        """RETURN: int, the index of the nominal's closing-token line.

                   None, where the nominal carries none.
        """
        return _token_i(self.nominal_line_list)

    def last_reachable_s(self):
        """RETURN: int, the highest subject line a cursor may stand on --
                   the last one, the closing token included: taking it
                   ENDS the nominal (L-11, services E-77).
        """
        return max(len(self.subject_line_list)-1, 0)

    def copied_f(self, i_s):
        """
        RETURN: bool, True where subject line 'i_s' has already been
                copied into the nominal and is therefore spent -- no
                cursor may stand on it and no range may cover it.

                False for a line still to be decided.
        """
        return i_s in self.copied_s

    def reachable_s(self, i_s, direction_n=+1):
        """
        RETURN: int, the first subject line from 'i_s' onward in
                'direction_n' that a cursor may stand on -- not copied.

                None, where the search walks off the end without
                finding one: every line that way is spent.
        """
        last_i = self.last_reachable_s()
        i      = i_s
        while 0 <= i <= last_i:
            if not self.copied_f(i): return i
            i += direction_n
        return None

    def last_reachable_n(self):
        """RETURN: int, the highest nominal line a cursor may stand on."""
        token_i = self.token_i_n()
        if token_i is None: return max(len(self.nominal_line_list)-1, 0)
        return max(token_i - 1, 0)

    #  ----------------------------------------------------------------- steps

    def with_(self, **kwargs):
        """RETURN: MergeState, a NEW state differing in the named fields.

        The state is never mutated: 'reduce' returns a new object, so an
        undo stack of past states costs nothing to keep honest.
        """
        return replace(self, **kwargs)

    def pushed(self):
        """RETURN: MergeState, this state with ITSELF pushed onto the undo
                   stack -- called once per act that changes anything, so
                   that a bulk take is ONE entry and not N (spec L-9).
        """
        return replace(self, undo_stack=self.undo_stack + (self,))


def _token_i(line_list):
    """RETURN: int, the index of the trailing closing-token line.

               None, where the last line is not the closing token.
    """
    if not line_list: return None
    if line_list[-1].strip() != CLOSING_TOKEN: return None
    return len(line_list) - 1
