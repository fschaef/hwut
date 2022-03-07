"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE:
"""
from   vut.system.terminal.core                import GLUE, LEFT, RIGHT, CENTER, FIXED, Fore, Back
from   vut.engine.compare.engine.line          import Line
from   vut.engine.compare.engine.line_pair     import LinePair
from   vut.engine.compare.edit_operations.edit import E_EditId
from   vut.external.quex.typed                 import typed

class ConsoleCanvasFormatter:
    def __init__(self, line_n_width, text_offset, canvas):
        self.line_n_width  = line_n_width
        
        remaining          = canvas.width - 2 * self.line_n_width - 3
        self.subject_width = int(remaining/2)
        self.nominal_width = remaining - self.subject_width
        self.text_offset   = text_offset
        self.canvas        = canvas
        self.setup_formats()

    def add_text_offset(self, value):
        self.text_offset += value
        if self.text_offset < 0:
            self.text_offset = 0
        self.setup_formats()

    def setup_formats(self):
        """Adapts the format expression to local settings of text width's and
        offsets.
        """
        self.normal = [
            LEFT(self.subject_width, text_offset=self.text_offset), 
            FIXED(" ", "Uw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED("|", "Bw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED(" ", "Uw"), 
            LEFT(self.nominal_width, text_offset=self.text_offset)
        ]
        self.subject_empty = [
            FIXED(" " * self.subject_width, "Rw"),
            FIXED("<", "Rw"), 
            FIXED("<" * self.line_n_width, "Rw"), 
            FIXED("|", "Bw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED(" ", "Uw"), 
            LEFT(self.nominal_width, text_offset=self.text_offset)
        ]

        self.subject_end = [
            FIXED("-" * self.subject_width, "Bw"),
            FIXED("<", "Rw"), 
            FIXED("<" * self.line_n_width, "Rw"), 
            FIXED("|", "Bw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED(" ", "Uw"), 
            LEFT(self.nominal_width, text_offset=self.text_offset)
        ]
        self.subject_end_nominal_empty = [
            FIXED("-" * self.subject_width, "Bw"),
            FIXED("-", "Bw"), 
            FIXED("-" * self.line_n_width, "Bw"), 
            FIXED("|", "Bw"), 
            FIXED(" " * self.line_n_width, "Rw"), 
            FIXED(" ", "Rw"), 
            FIXED(" " * self.nominal_width, "Rw")
        ]
        self.nominal_empty = [
            LEFT(self.subject_width, text_offset=self.text_offset), 
            FIXED(" ", "Uw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED("|", "Bw"), 
            FIXED(">" * self.line_n_width, "Rw"), 
            FIXED(">", "Rw"), 
            FIXED(" " * self.nominal_width, "Rw")
        ]
        self.nominal_end = [
            LEFT(self.subject_width, text_offset=self.text_offset), 
            FIXED(" ", "Uw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED("|", "Bw"), 
            FIXED(">" * self.line_n_width, "Rw"), 
            FIXED(">", "Rw"), 
            FIXED("-" * self.nominal_width, "Bw")
        ]
        self.nominal_end_subject_empty = [
            FIXED(" " * self.subject_width, "Rw"),
            FIXED(" ", "Rw"), 
            FIXED(" " * self.line_n_width, "Rw"), 
            FIXED("|", "Bw"), 
            FIXED("-" * self.line_n_width, "Bw"), 
            FIXED("-", "Bw"), 
            FIXED("-" * self.nominal_width, "Bw")
        ]
        self.both_end = [
            FIXED("-" * self.subject_width, "Bw"),
            FIXED("-", "Bw"), 
            FIXED("-" * self.line_n_width, "Bw"), 
            FIXED("|", "Bw"), 
            FIXED("-" * self.line_n_width, "Bw"), 
            FIXED("-", "Bw"), 
            FIXED("-" * self.nominal_width, "Bw")
        ]
        self.empty = [
            FIXED(" " * self.subject_width, "Rw", text_offset=self.text_offset),
            FIXED(" ", "Rw"), 
            FIXED(" " * self.line_n_width, "Bw"), 
            FIXED(":", "Bw"), 
            FIXED(" " * self.line_n_width, "Bw"), 
            FIXED(" ", "Rw"), 
            FIXED(" " * self.nominal_width, "Rw", text_offset=self.text_offset)
        ]
        self.filler = [
            FIXED(" " * self.subject_width, "Rw", text_offset=self.text_offset),
            FIXED(":", "Bw"), 
            FIXED(" " * self.line_n_width, "Bw"), 
            FIXED("|", "Bw"), 
            FIXED(" " * self.line_n_width, "Bw"), 
            FIXED(":", "Bw"), 
            FIXED(" " * self.nominal_width, "Rw", text_offset=self.text_offset)
        ]
        self.potpourri_begin = [
            FIXED("|" * self.subject_width + "|", "Gw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED("|", "Uw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED("|" + "|" * self.nominal_width, "Gw"),
        ]
        self.potpourri_end = [
            FIXED("|" * self.subject_width + "|", "Gw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED("|", "Uw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED("|" + "|" * self.nominal_width, "Gw"),
        ]
        self.status_line = self.canvas.fix_glue(
            LEFT(self.canvas.width-19, "Bg"), 
            GLUE(" ", "Wg"),
            RIGHT(15, "Bg"),
            FIXED(" ", "Bg"),
            RIGHT(4, "Bg")
        )

    def end_of_stream_subject(self, line_n):
        return Line.from_string(line_n, "/" * self.subject_width)

    def end_of_stream_nominal(self, line_n):
        return Line.from_string(line_n, "/" * self.nominal_width)

@typed(line=LinePair)
def do_line_elements(max_line_length, lip, lip_i, add_background_color=""):
    """RETURNS: [0] new max line length
                [0] subject text: list of (color, text)
                [1] nominal text: list of (color, text)

       ADAPTS:  'self.__max_line_length' if a longer line occurred.

    Provides text and format information to display the 'LinePair'. 
    """
    subject_txt, nominal_txt = [], []
    subject_n,   nominal_n   = 0, 0
    s_length,    n_length    = 0, 0
    for lep in lip.line_element_pair_list():
        s_color, s_txt, n_color, n_txt = _edit_db[lep.edit_id](lep.subject, lep.nominal)
        subject_txt.append((s_color + add_background_color, s_txt.replace("\t", "\\t")))
        nominal_txt.append((n_color + add_background_color, n_txt.replace("\t", "\\t")))
        s_length += len(s_txt)
        n_length += len(n_txt)

    if max(s_length, n_length) > max_line_length: 
        max_line_length = max(s_length, n_length)

    return max_line_length, subject_txt, nominal_txt

def _good(subject, nominal):
    return "", subject.string, "", nominal.string

def _tolerated(subject, nominal):
    return Back.GREEN, subject.string, \
           Fore.GREEN, nominal.string

def _good_deleted(subject, nominal):
    return Back.GREEN, subject.string, \
           Fore.GREEN, " " * len(subject.string)

def _good_inserted(subject, nominal):
    return Back.GREEN, " " * len(nominal.string), \
           Fore.GREEN, nominal.string

def _deleted(subject, nominal):
    return Back.RED,                       subject.string, \
           Back.BLUE + Fore.LIGHTWHITE_EX, " " * len(subject.string)

def _inserted(subject, nominal):
    return Back.RED, " " * len(nominal.string), \
           Back.BLUE + Fore.LIGHTWHITE_EX, nominal.string

def _transpose(subject, nominal):
    return Back.RED, subject.string, \
           Back.YELLOW, nominal.string

def _substitute(subject, nominal):
    return Back.RED, subject.string, \
           Fore.RED,              nominal.string

def _substitute_type(subject, nominal):
    return Back.RED,                      subject.string, \
           Back.BLACK + Fore.LIGHTRED_EX, nominal.string

def _none(subject, nominal):
    if subject:
        return "", subject.string, Back.MAGENTA, ""
    else:
        return Back.MAGENTA, "", "", nominal.string

_edit_db = {
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

