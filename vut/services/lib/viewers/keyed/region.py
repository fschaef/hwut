"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE UNACCEPTED REGIONS OF A WORKING NOMINAL, and the take that
         splits them.

DESCRIPTION
       A region is a READING of the text, never a structure kept beside
       it. 'region_list_of' scans the lines and says what regions stand;
       every act that changes the text calls it again. There is
       therefore no parallel bookkeeping to drift out of step with the
       nominal a person could also have edited in '$EDITOR'.

       THE TAKE (spec L-1..L-4) replaces a run of nominal lines with a
       run of subject lines. Where the replaced lines lie inside a
       region, the region SPLITS around them: the part above and the
       part below survive as regions of their own, and the taken lines
       stand plain between them. A part with nothing left in it is
       REMOVED, framing and all -- an empty region asserts nothing (C-9
       makes it equivalent) while it still reads as 'undecided'.
______________________________________________________________________________
"""
from vut.engine.compare.reading.line_scanner import (REGION_BEGIN_MARKER,
                                                     REGION_END_LINE)

from dataclasses import dataclass

UNACCEPTED_BEGIN_LINE = "%s unaccepted" % REGION_BEGIN_MARKER
#  THE FILLER: significant CONTENT, so that a filler standing against a
#  subject line is a REAL difference -- which is what 'nobody has judged
#  this' must look like to compare. NOT in the '##'...'##' family: that
#  reads as VISIBLE_NOTHING, which would make the region EQUIVALENT and
#  a first acceptance PASS. Not bare '--' either -- a comment in SQL,
#  Lua, Ada and Haskell, and patch syntax besides.
#
#  FIXED, not configured. It is overwritten the moment anybody takes the
#  line it stands on, and inside a region EVERY line is a filler by
#  construction, so nothing mechanical can confuse it with real output
#  that happens to read the same.
FILLER_LINE           = "--?--"


@dataclass(frozen=True)
class Region:
    """One '##! <kind>' ... '####' stretch of a working nominal.

    'begin_i' indexes the '##!' line, 'end_i' the '####' line; the
    CONTENT is what lies between them, which may be nothing. 'kind' is
    the handler's name -- 'unaccepted', 'potpourri', 'table', ...
    """
    begin_i: int
    end_i:   int
    kind:    str = "unaccepted"

    def unaccepted_f(self):
        """RETURN: bool, True where this region is 'nobody has judged
                   this' -- the one kind a take may SPLIT.
        """
        return self.kind == "unaccepted"

    def covers_content_f(self, first_i, last_i):
        """RETURN: bool, True where the lines 'first_i'..'last_i' include
                   EVERY content line of this region -- so that a take
                   replacing them leaves no remainder of it behind.
        """
        content_first_i, content_last_i = self.content_range()
        return first_i <= content_first_i and last_i >= content_last_i

    def touches_f(self, first_i, last_i):
        """RETURN: bool, True where any line of 'first_i'..'last_i' lies
                   inside this region, markers included.
        """
        return not (last_i < self.begin_i or first_i > self.end_i)

    def content_range(self):
        """RETURN: (int, int), the first and last index of this region's
                   CONTENT lines, both inclusive.

                   (begin_i + 1, begin_i), an empty range whose first
                   exceeds its last, where the region holds no content.
        """
        return (self.begin_i + 1, self.end_i - 1)

    def holds(self, i):
        """RETURN: bool, True where line 'i' is CONTENT of this region --
                   never True for its own two marker lines.
        """
        return self.begin_i < i < self.end_i

    def line_n(self):
        """RETURN: int, how many CONTENT lines this region holds."""
        return self.end_i - self.begin_i - 1


def region_list_of(line_list):
    """RETURN: tuple[Region], every '##! <kind>' region standing in
               'line_list', of whatever kind, ordered by line, never
               overlapping.

               An empty tuple, where none stands -- which is the
               ordinary shape of a nominal nobody has left undecided.

    An unterminated region at the end of the stream is NOT reported: a
    region without its '####' is a syntax fault, and saying so is
    compare's business, not a viewer's.
    """
    result  = []
    begin_i = None
    kind    = None
    for i, line in enumerate(line_list):
        stripped = line.strip()
        if stripped.startswith(REGION_BEGIN_MARKER):
            begin_i = i
            kind    = stripped[len(REGION_BEGIN_MARKER):].strip().split()[0] \
                      if stripped[len(REGION_BEGIN_MARKER):].strip() else ""
        elif stripped == REGION_END_LINE and begin_i is not None:
            result.append(Region(begin_i, i, kind))
            begin_i = None
    return tuple(result)


def region_of(region_list, i):
    """RETURN: Region, the region whose CONTENT holds line 'i'.

               None, where line 'i' stands outside every region, or is
               itself a region's marker line.
    """
    for region in region_list:
        if region.holds(i): return region
    return None


def take(line_list, first_i, last_i, taken_line_list):
    """RETURN: tuple[str], the nominal after the lines 'first_i'..'last_i'
               were replaced by 'taken_line_list' -- with the region
               containing them SPLIT around the replacement, and any part
               left empty removed entirely, framing and all.

               The lines spliced plainly, where 'first_i'..'last_i' lie
               in no region: there is then nothing to split.

               None, where the take would CUT a region of any kind but
               'unaccepted' -- cover part of a potpourri, a table, an
               ignore block -- leaving a remainder of it behind. Such a
               take is refused whole; a region of another kind is taken
               entire, markers included, or not at all.

    The counts need not agree: N taken lines may replace M nominal
    lines, and the nominal grows or shrinks accordingly (spec L-1).
    """
    placed = take_placed(line_list, first_i, last_i, taken_line_list)
    return None if placed is None else placed[0]


def take_placed(line_list, first_i, last_i, taken_line_list):
    """RETURN: [0] tuple[str], the nominal after the take, exactly as
                   'take' returns it.
               [1] int, the index at which the FIRST taken line now
                   stands -- the taken lines follow it, contiguous.

               None, where 'take' refuses.

    THE PLACE IS COMPUTED, NOT SEARCHED FOR. Locating a taken line by
    its text was MEASURED to find an EARLIER identical line in the
    nominal, pair the subject line with it, and cross the pairing -- the
    subject pane then drew the same subject lines twice, beside the
    nominal's copies, which reads as nominal text copied back into the
    subject.
    """
    region_list = region_list_of(line_list)

    #  A TAKE TOUCHES AT MOST ONE REGION. A range straddling two -- an
    #  unaccepted region and the table after it, say -- would have to
    #  split one and swallow the other in one act, and no key was ruled
    #  to mean that. Refused whole.
    touched_list = [r for r in region_list if r.touches_f(first_i, last_i)]
    if len(touched_list) > 1: return None

    #  NO REGION OF ANY OTHER KIND IS EVER CUT. Where the take touches a
    #  '##! potpourri', a '##! table' -- anything but 'unaccepted' -- it
    #  must cover that region's whole content, and then it replaces the
    #  region ENTIRE, markers included: a remainder of a potpourri left
    #  trailing after a merge is a nominal nobody wrote and compare
    #  cannot read. Anything less is REFUSED, and nothing changes.
    for region in region_list:
        if region.unaccepted_f():                continue
        if not region.touches_f(first_i, last_i): continue
        if not region.covers_content_f(first_i, last_i): return None
        first_i = min(first_i, region.begin_i)
        last_i  = max(last_i,  region.end_i)

    #  AN 'unaccepted' REGION'S MARKERS ARE NOT CONTENT. A range that
    #  reaches its '##! unaccepted' or its '####' without covering the
    #  whole content is drawn INTO the content; one covering it all
    #  takes the region whole, markers included (L-3). An insertion AT
    #  the closing rule belongs after it. Splicing over a marker was
    #  MEASURED to replace the label and leave a '####' closing nothing.
    for region in region_list:
        if not region.unaccepted_f():             continue
        if not region.touches_f(first_i, last_i): continue
        if region.holds(first_i) and region.holds(last_i): continue
        content_first_i, content_last_i = region.content_range()
        if last_i < first_i:                          # an insertion
            if first_i == region.end_i: first_i, last_i = first_i + 1, first_i
            continue
        if first_i <= content_first_i and last_i >= content_last_i:
            first_i = min(first_i, region.begin_i)
            last_i  = max(last_i,  region.end_i)
        else:
            first_i = max(first_i, content_first_i)
            last_i  = min(last_i,  content_last_i)

    region = region_of(region_list, first_i)
    if region is None or not region.unaccepted_f():
        return (tuple(line_list[:first_i])
                + tuple(taken_line_list)
                + tuple(line_list[last_i+1:]), first_i)

    content_first_i, content_last_i = region.content_range()
    head = tuple(line_list[:region.begin_i]) \
           + _framed(line_list[content_first_i:first_i])
    below = line_list[last_i+1:content_last_i+1]

    return (head
            + tuple(taken_line_list)
            + _framed(below)
            + tuple(line_list[region.end_i+1:]), len(head))


def frame(line_list):
    """RETURN: tuple[str], 'line_list' wrapped as one '##! unaccepted'
               region -- the marker, the lines, the closing rule.

               An empty tuple, where 'line_list' is empty: a region with
               nothing in it says nothing, so none is written.
    """
    return _framed(line_list)


def filler_region(line_n):
    """RETURN: tuple[str], an unaccepted region standing for 'line_n'
               subject lines -- the marker, 'line_n' filler lines, the
               closing rule.

               An empty tuple for 'line_n' of zero: a region with
               nothing in it says nothing, so none is written.

    THE FILLER IS CONTENT, not a comment and not a blank. compare pairs
    it 1:1 against the subject lines it stands for, and every such pair
    DIFFERS -- which is precisely 'nobody has judged this yet'. Copying
    the subject in instead would put the answer in the file before
    anyone had looked at it, and would nest that chunk's own framing
    inside this one.
    """
    return _framed((FILLER_LINE,) * line_n)


def _framed(line_list):
    """RETURN: tuple[str], the lines framed as a region, or an empty
               tuple where there are none to frame.
    """
    if not line_list: return ()
    return (UNACCEPTED_BEGIN_LINE,) + tuple(line_list) + (REGION_END_LINE,)
