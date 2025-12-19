"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE:
"""
from   vut.system.terminal.core                import LEFT, RIGHT, FIXED, Fore, Back
from   vut.engine.compare.engine.line          import Line
from   vut.engine.compare.engine.line_pair     import LinePair
from   vut.engine.compare.edit_operations.edit import E_EditId
from   vut.external.quex.typed                 import typed
from   vut.engine.constants                    import E_Side


class MarkDisplaySide(object):
    __slots__ = ("lip_i_1st", "lip_i_2nd", "lip_i_last", "tags", "referene_defined_f")

    def __init__(self):
        self.lip_i_1st  = None   # lip_i_1st, lip_i_2nd -- borders of focus region
        self.lip_i_2nd  = None
        self.lip_i_last = None

    def init(self, lip_i, lip_i_end):
        """Prepare for display.
        """
        if self.virgin():
            self.lip_i_1st  = lip_i
            self.lip_i_2nd  = lip_i
            self.lip_i_last = lip_i_end - 1

    def virgin(self):
        return self.lip_i_1st is None

    def add_1st(self, delta):
        self.lip_i_1st = max(0, min(self.lip_i_1st + delta, self.lip_i_last))

    def add_2nd(self, delta):
        self.lip_i_2nd = max(0, min(self.lip_i_2nd + delta, self.lip_i_last))

    @typed(lip_i=int)
    def locate(self, lip_i):
        """RETURNS:  0,  if lip_i = first border
                     1,  if lip_i = second border
                     2,  if lip_i inside borders
                    -1, if lip_i is not inside borders
        """
        if   self.lip_i_1st is not None and  lip_i == self.lip_i_1st: 
            return 0
        elif self.lip_i_2nd is not None and lip_i == self.lip_i_2nd:   
            return 1
        elif self.lip_i_1st is None or self.lip_i_2nd is None:
            return -1
        elif self.lip_i_1st > self.lip_i_2nd: 
            if self.lip_i_2nd <= lip_i <= self.lip_i_1st: return 2
        else:
            if self.lip_i_1st <= lip_i <= self.lip_i_2nd: return 2
        return -1

class MarkDisplays(object):
    __slots__ = ("focus_side", "_focus_mirror", "_focus_next", "_focus_side", 
                 "subject", "nominal", "borders_done_f", "focus_index")

    def __init__(self):
        self.focus_side        = E_Side.SUBJECT
        self.subject           = MarkDisplaySide() # E_Side.SUBJECT
        self.nominal           = MarkDisplaySide() # E_Side.NOMINAL
        self.focus_index       = 0 # 0: subject first; 1: subject second; 
        #                          # 2: nominal first; 3: nominal second;
        self._focus_mirror = { 0: 3, 1: 2, 2: 1, 3: 0 }
        self._focus_next   = { 0: 1, 1: 2, 2: 3, 3: 0 }
        self._focus_side   = { 
            0: E_Side.SUBJECT, 1: E_Side.SUBJECT, 
            2: E_Side.NOMINAL, 3: E_Side.NOMINAL 
        }
        self.borders_done_f = False

    def init(self, lip_i, lip_i_subject_end, lip_i_nominal_end):
        """Setup the cursor for being displayed.
        """
        self.focus_side = E_Side.SUBJECT
        self.subject.init(lip_i, lip_i_subject_end)
        self.nominal.init(lip_i, lip_i_nominal_end)

    def virgin(self):
        return self.subject.virgin() and self.nominal.virgin()

    def switch_side(self):
        target = self._focus_mirror[self.focus_index]
        while self.focus_index != target:
            self.iterate_focus()

    def iterate_focus(self):
        self.focus_index = self._focus_next[self.focus_index]
        if self.focus_index in (2, 3):
            self.borders_done_f = True

    def set_initial_focus(self):
        while self.focus_index != 0:
            self.iterate_focus()

    def marks(self, lip_i):
        def mark(x, focus):
            if   x == 0: return "*" if focus == 0 else "<"
            elif x == 1: return "*" if focus == 1 else "<"
            elif x == 2: return "<"
            else:        return " "
        s = mark(self.subject.locate(lip_i), self.focus_index)
        n = mark(self.nominal.locate(lip_i), self.focus_index - 2)
                    
        return s, n 

    def add_lip_i(self, delta):
        """ADDS 'delta' to the current cursor position depending on the 
           focus side being 'SUBJECT' or 'NOMINAL'.
        """
        if  self.focus_index == 0:
            self.subject.add_1st(delta)
            if not self.borders_done_f: 
                self.subject.add_2nd(delta)
                self.nominal.add_1st(delta)
                self.nominal.add_2nd(delta)
            return self.subject.lip_i_1st
        elif self.focus_index == 1:
            self.subject.add_2nd(delta)
            if not self.borders_done_f: 
                self.nominal.add_1st(delta)
                # nominal.2nd = remains
            return self.subject.lip_i_2nd
        elif self.focus_index == 2:
            self.nominal.add_1st(delta)
            return self.nominal.lip_i_1st
        elif self.focus_index == 3:
            self.nominal.add_2nd(delta)
            return self.nominal.lip_i_2nd
        else:
            assert False

class ConsoleCanvasFormatter:
    def __init__(self, line_n_width, text_offset, canvas):
        self.line_n_width  = line_n_width
        
        remaining          = canvas.width - 2 * self.line_n_width - 3
        self.subject_width = int(remaining/2)
        self.nominal_width = remaining - self.subject_width
        self.text_offset   = text_offset
        self.canvas        = canvas
        self.cursor        = MarkDisplays()

    def add_text_offset(self, value):
        self.text_offset += value
        if self.text_offset < 0:
            self.text_offset = 0

    def header(self, app_name, choice_name):
        f = [
            LEFT(self.nominal_width, "Bg"), 
            FIXED("_" * (self.line_n_width+1), "Uw"), 
            FIXED("|", "Bw"), 
            FIXED("_" * (self.line_n_width+1), "Uw"), 
            LEFT(self.subject_width, "Bg")
        ]
        return self.canvas.prepare(f, ["GOOD:", "OUT: %s %s" % (app_name, choice_name)])

    def _center_column(self, lip_i, sc="Uw", nc="Uw"):
        s, n = self.cursor.marks(lip_i)
        color_s = sc if s == " " else "Wu"
        color_n = nc if n == " " else "Wu"
        if sc == "Uw": cell_n = LEFT(self.line_n_width, color_n)
        else:          cell_n = FIXED("-" * self.line_n_width, color_n)
        if nc == "Uw": cell_s = LEFT(self.line_n_width, color_s)
        else:          cell_s = FIXED("-" * self.line_n_width, color_s)
        result = [ FIXED(n, color_n), cell_n, FIXED("|", "Bw"), cell_s, FIXED(s, color_s) ]
        sc     = None if s == " " else "By"
        nc     = None if n == " " else "By"
        return result, sc, nc
 
    def normal(self, lip_i, lip):
        center, sc, nc = self._center_column(lip_i)
        f =   [ LEFT(self.nominal_width, text_offset=self.text_offset, color=nc) ] \
            + center \
            + [ LEFT(self.subject_width, text_offset=self.text_offset, color=sc) ]
        sline_str, nline_str = lip.line_number_strings()
        return self.canvas.prepare(f, [ lip.nominal_text(), nline_str, sline_str, lip.subject_text()])

    def subject_empty(self, lip_i, lip):
        center, sc, nc = self._center_column(lip_i, nc="Rw")
        f =   [ LEFT(self.nominal_width, color=nc) ] \
            + center                             \
            + [ LEFT(" " * self.subject_width, text_offset=self.text_offset, colord=sc) ]
        return self.canvas.prepare(f, [lip.nominal_text(), "%s" % lip.nominal.line_n])

    def subject_end(self, lip_i, lip):
        center, sc, nc = self._center_column(lip_i, nc="Rw")
        f =   [ FIXED("-" * self.nominal_width, color=nc) ] \
            + center                                    \
            + [ LEFT(self.subject_width, text_offset=self.text_offset, color=sc) ]
        return self.canvas.prepare(f, [lip.nominal_text(), "%s" % lip.nominal.line_n])

    def subject_end_nominal_empty(self, lip_i, lip):
        f = [
            FIXED(" " * (self.line_n_width + self.subject_width + 1), color=nc),
            FIXED("|", "Bw"), 
            FIXED("_" * (self.nominal_width + self.line_n_width + 1), color=sc),
        ]
        return self.canvas.prepare(f)

    def nominal_empty(self, lip_i, lip):
        center, sc, nc = self._center_column(lip_i, sc="Rw")
        f =   [ FIXED(" " * self.nominal_width, text_offset=self.text_offset, color=nc) ] \
            + center                                                            \
            + [ LEFT(self.subject_width, color=sc) ]
        return self.canvas.prepare(f, ["%s" % lip.subject.line_n, lip.subject_text()])

    def nominal_end(self, lip_i, lip):
        center, sc, nc = self._center_column(lip_i, sc="Rw")
        f =   [ FIXED("_" * self.nominal_width, text_offset=self.text_offset, color=nc) ] \
            + center                                                            \
            + [ LEFT(self.subject_width, color=sc) ]
        return self.canvas.prepare(f, ["%s" % lip.subject.line_n, lip.subject_text()])

    def nominal_end_subject_empty(self, lip_i, lip):
        f = [
            FIXED("_" * (self.line_n_width + self.subject_width + 1), color=nc),
            FIXED("|", "Bw"), 
            FIXED(" " * (self.nominal_width + self.line_n_width + 1), color=sc),
        ]
        return self.canvas.prepare(f)

    def both_end(self, lip_i, lip):
        f = [
            FIXED("_" * (self.nominal_width + self.line_n_width + 1), "Bw"),
            FIXED("|", "Bw"), 
            FIXED("_" * (self.line_n_width + self.subject_width + 1), "Bw")
        ]
        return self.canvas.prepare(f)

    def empty(self, lip_i, lip):
        f = [
            FIXED(" " * self.nominal_width, "Bw", text_offset=self.text_offset),
            FIXED(" ", "Rw"), 
            FIXED(" " * self.line_n_width, "Bw"), 
            FIXED(".", "Bw"), 
            FIXED(" " * self.line_n_width, "Bw"), 
            FIXED(" ", "Rw"), 
            FIXED(" " * self.subject_width, "Bw", text_offset=self.text_offset)
        ]
        return self.canvas.prepare(f)

    def filler(self, lip_i, lip):
        f = [
            FIXED(" " * self.nominal_width, "Rw", text_offset=self.text_offset),
            FIXED(":", "Bw"), 
            FIXED(" " * self.line_n_width, "Bw"), 
            FIXED("|", "Bw"), 
            FIXED(" " * self.line_n_width, "Bw"), 
            FIXED(":", "Bw"), 
            FIXED(" " * self.subject_width, "Rw", text_offset=self.text_offset)
        ]
        return self.canvas.prepare(f)

    def potpourri_begin(self, lip_i, lip):
        f = [
            FIXED("|" * self.nominal_width + "|", "Gw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED("|", "Uw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED("|" + "|" * self.subject_width, "Gw"),
        ]
        sline_str, nline_str = lip.line_number_strings()
        return self.canvas.prepare(f, [nline_str, sline_str])

    def potpourri_end(self, lip_i, lip):
        f = [
            FIXED("|" * self.nominal_width + "|", "Gw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED("|", "Uw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED("|" + "|" * self.subject_width, "Gw"),
        ]
        sline_str, nline_str = lip.line_number_strings()
        return self.canvas.prepare(f, [nline_str, sline_str])

    def end_of_stream_subject(self, line_n):
        return Line.from_string(line_n, "/" * self.nominal_width)

    def end_of_stream_nominal(self, line_n):
        return Line.from_string(line_n, "/" * self.nominal_width)

def _good(subject, nominal):
    return "", subject.string, "", nominal.string

def _tolerated(subject, nominal):
    return Fore.GREEN, subject.string, \
           Back.GREEN, nominal.string

def _good_deleted(subject, nominal):
    return Fore.GREEN, subject.string, \
           Back.GREEN, " " * len(subject.string)

def _good_inserted(subject, nominal):
    return Fore.GREEN, " " * len(nominal.string), \
           Back.GREEN, nominal.string

def _deleted(subject, nominal):
    return Fore.BLUE,                     subject.string, \
           Back.RED + Fore.LIGHTWHITE_EX, "*" * len(subject.string)

def _inserted(subject, nominal):
    return Fore.BLUE, "*" * len(nominal.string), \
           Back.RED + Fore.LIGHTWHITE_EX, nominal.string

def _transpose(subject, nominal):
    return Fore.YELLOW, subject.string, \
           Back.RED,    nominal.string

def _substitute(subject, nominal):
    return Fore.RED, subject.string, \
           Back.RED, nominal.string

def _substitute_type(subject, nominal):
    return Fore.RED,               subject.string, \
           Back.RED + Fore.YELLOW, nominal.string

def _none(subject, nominal):
    if subject:
        return "", subject.string, Back.MAGENTA, ""
    else:
        return Back.MAGENTA, "", "", nominal.string

edit_db = {
    E_EditId.GOOD:            _good,
    E_EditId.GOOD_TOLERATED:  _tolerated,
    E_EditId.GOOD_DELETE:     _good_deleted,
    E_EditId.GOOD_INSERT:     _good_inserted,
    E_EditId.DELETE:          _deleted,
    E_EditId.INSERT:          _inserted,
    E_EditId.TRANSPOSE:       _transpose,
    E_EditId.SUBSTITUTE:      _substitute,
    E_EditId.SUBSTITUTE_TYPE: _substitute_type,
    E_EditId.NONE:            _none
}

