"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE CHECKLIST -- the one menu every face uses to let an author
         pick which case to work next, and the one place that remembers
         which he has already worked.

DESCRIPTION
       ONE MENU, ONE BEHAVIOUR. 'hwut.accept.interactive' and
       'hwut.diff' both offer a list and both work the cases one after
       another. They held a copy of that loop each, and the copies had
       already drifted: one re-entered the menu and the other showed it
       once, so the SAME marks meant different things at the two
       doors. The menu and its marks live here now; a third face gets
       the behaviour by using this class, not by writing it again.

       '[X]' SAYS HANDLED, NOT SELECTED (E-65). Nothing is marked when
       the menu first appears, because nothing has been worked yet. A
       handled case is not offered again. What 'handled' means is the
       face's own business -- accepted, or merely viewed -- and the
       menu does not ask: it marks what it HANDED OVER, because that
       is the only thing it can know.

       ONE CASE PER ASK. 'pick' returns ONE case, or None. A number
       names it; '<enter>' takes the FIRST unhandled one, which is
       printed beside its own number so that the key and its effect
       are never two facts a person has to join up. Walking a list is
       therefore Enter, Enter, Enter, and nothing else.

       THE LIST PAGES when it is longer than the terminal. The last
       line of a partial page is an OPTION like any other -- 'n' and
       the count still to come -- and 'n' wraps at the end, so every
       case is reachable with one key and no second key is invented
       for going back. NUMBERS ARE ABSOLUTE: a number picks its case
       from any page, so a person who remembers 'case 17' need not
       page to it.

       NO TTY, NO PAGING. Every suite drives these faces through a
       pipe, and a pipe has no height; a paged menu there would record
       page prompts instead of a list. Where the output is not a
       terminal the whole list stands, as it always did.
______________________________________________________________________________
"""
from vut.services.report import height_of

import sys


#  The menu's own lines, subtracted from the terminal's height to leave
#  the room the entries get: the header, the '(N more)' option, the
#  prompt, and one line of air above whatever the face printed before.
CHROME_LINE_N = 4


class Checklist:
    """The menu over a list of cases, and the marks of what was worked."""

    def __init__(self, item_list, write, read_line, label_of=str,
                 all_f=False, height=None, paging_f=None):
        """
        RETURN: None.

        'label_of' says how one item prints; the menu holds items of
        any kind and knows nothing of what they are.

        'all_f' hands every item over in turn with no menu at all --
        what '--all' and '--dont-ask' mean. The face's loop does not
        change shape between the two modes, which is the point.

        'height' states the terminal's, for a test that wants a short
        page without a short terminal; None asks 'report.height_of'.
        'paging_f' forces paging on or off; None measures the output.
        """
        self.item_list   = list(item_list)
        self.write       = write
        self.read_line   = read_line
        self.label_of    = label_of
        self.all_f       = all_f
        self.height      = height
        self.handled_set = set()
        self.first_i     = 0        # the page's first index
        self.quit_f      = False

        if paging_f is not None: self.paging_f = paging_f
        else:
            try:    self.paging_f = sys.stdout.isatty()
            except Exception: self.paging_f = False

    #  ------------------------------------------------------------ asking

    def pick(self):
        """
        RETURN: the next item to work -- the one the author named by
                number, or the first unhandled one where he pressed
                '<enter>', or simply the next unhandled one where the
                menu is not shown at all.

                None, where the author quit, where the input ended, or
                where nothing is left unhandled. A face's loop ends on
                None and on nothing else.

        THE ITEM IS MARKED HANDLED BY THIS CALL. It was handed over;
        whether the face made anything of it is the face's own
        account, and offering it twice would lose the author's place.
        """
        if self.quit_f: return None
        open_list = self._open_list()
        if not open_list: return None
        if self.all_f or len(self.item_list) <= 1:
            return self._taken(open_list[0])

        while True:
            self._show(open_list[0])
            answer = self._read()
            if answer is None or answer == "q":
                self.quit_f = True
                return None
            if answer == "":  return self._taken(open_list[0])
            if answer == "n" and self._more_n():
                self._turn_page()
                continue
            picked = self._picked(answer)
            if picked is not None: return self._taken(picked)

    def handled_f(self, item):
        """RETURN: bool, True where this item has already been handed
                   over by 'pick' -- what the '[X]' beside it says.
        """
        return id(item) in self.handled_set

    #  ----------------------------------------------------------- drawing

    def _show(self, enter_i):
        """RETURN: None. One page of the menu, the '<enter>' mark beside
                   the case that key would take, and -- where the page
                   is partial -- the 'n' option and how many remain.
        """
        self.write("differing cases -- a number to work it, <enter> for "
                   "the marked one, q to quit")
        last_i = min(self.first_i + self._page_n(), len(self.item_list))
        for i in range(self.first_i, last_i):
            self.write("  [%s] %2d %s %s"
                       % ("X" if self.handled_f(self.item_list[i]) else " ",
                          i + 1,
                          "<enter>" if i == enter_i else "       ",
                          self.label_of(self.item_list[i])))
        more_n = self._more_n()
        if more_n: self.write("   n           (%d more)" % more_n)
        if not (self.first_i <= enter_i < last_i):
            #  THE '<enter>' TARGET IS ABSOLUTE (the first unhandled
            #  case, wherever it stands), so where this page does not
            #  show it the header would name a mark nobody can see.
            self.write("  <enter>  %2d %s" % (enter_i + 1,
                                              self.label_of(self.item_list[enter_i])))
        self.write("> ")

    def _page_n(self):
        """RETURN: int, how many entries one page holds -- the whole
                   list where nothing pages, otherwise the terminal's
                   height less the menu's own lines, and never below 1.
        """
        if not self.paging_f: return len(self.item_list)
        return max(1, height_of(self.height) - CHROME_LINE_N)

    def _more_n(self):
        """RETURN: int, how many entries stand OUTSIDE this page -- 0
                   where the page shows the list whole.
        """
        page_n = self._page_n()
        if page_n >= len(self.item_list): return 0
        shown_n = min(self.first_i + page_n, len(self.item_list)) - self.first_i
        return len(self.item_list) - shown_n

    def _turn_page(self):
        """RETURN: None. The next page, wrapping to the top at the end
                   so 'n' alone reaches every case.
        """
        self.first_i += self._page_n()
        if self.first_i >= len(self.item_list): self.first_i = 0

    #  ---------------------------------------------------------- the keys

    def _read(self):
        """RETURN: str, the author's line, trimmed and lowered.
                   None, where the input ended -- an ending, not an error.
        """
        try:    text = self.read_line()
        except EOFError: return None
        if text == "": return None
        return (text or "").strip().lower()

    def _picked(self, answer):
        """
        RETURN: the item the author named by number.
                None, where the word was not a number in range or named
                a case already handled -- said out loud, so a person
                learns why nothing happened.
        """
        if not (answer.isdigit() and 1 <= int(answer) <= len(self.item_list)):
            self.write("  (not a number in 1..%d: '%s')"
                       % (len(self.item_list), answer))
            return None
        item = self.item_list[int(answer) - 1]
        if self.handled_f(item):
            self.write("  (%s is handled already)" % answer)
            return None
        return item

    def _open_list(self):
        """RETURN: list[int], the indices not yet handled, in order."""
        return [i for i, item in enumerate(self.item_list)
                if not self.handled_f(item)]

    def _taken(self, i_or_item):
        """RETURN: the item, marked handled -- the one thing every exit
                   from 'pick' that hands something over goes through.
        """
        item = self.item_list[i_or_item] if isinstance(i_or_item, int) \
               else i_or_item
        self.handled_set.add(id(item))
        return item
