from   vut.system.helper                                       import number_of_decimal_digits
from   vut.system.terminal                                     import ConsoleCanvas, GLUE, LEFT, RIGHT, CENTER, FIXED, Fore, Back
import vut.system.keyboard                                     as     keyboard
from   vut.user_interface.difference_display.console.formatter import ConsoleCanvasFormatter
import vut.user_interface.difference_display.console.prepare   as     prepare
from   vut.engine.compare.engine.line_association_chunk        import LineAssociationChunk, \
                                                                      LineAssociationList
from   vut.engine.compare.engine.line_association              import LineAssociation
from   vut.engine.compare.engine.core                          import E_PotpourriBorder
from   vut.engine.compare.edit_operations.line                 import E_EditLine, Edit
import vut.engine.compare.edit_operations.line                 as     edit_operations_line
from   vut.external.quex.typed                                 import typed

from   copy import copy
from   math import ceil

from   enum import Enum, auto
from   itertools import chain
from   collections import defaultdict

@typed(lina_cnunk_list=[LineAssociationChunk], sort_potpourri_by_subject_line_n_f=bool)
def do(lina_chunk_list, text_offset=0, sort_potpourri_by_subject_line_n_f=False):
    """Displays a comparison of subject and nominal lines clustered in 
    'LineAssociationChunk'-s.
    """

    canvas = ConsoleCanvasDiff(lina_chunk_list) 

    canvas.interact()

class E_DiffMode(Enum):
    PLAIN                = auto()
    ERRORS               = auto()
    ERRORS_AND_TOLERATED = auto()
    ANALOGIES            = auto()

class ConsoleCanvasDiff(ConsoleCanvas):
    def __init__(self, lina_chunk_list):
        ConsoleCanvas.__init__(self)
        self.__lina_chunk_list = lina_chunk_list
        self.__analogy_db      = lina_chunk_list[-1].analogy_db()

        line_n_width = number_of_decimal_digits(lina_chunk_list[-1].max_line_n())
        self.format  = ConsoleCanvasFormatter(self.width, line_n_width, 0, self)
        self.__sort_potpourri_by_subject_line_n_f = True
        
        self.__lina_list            = [] # filtered list of LineAssociationDecorated objects 
        #                                # according to mode.
        self.__display_cache_db     = {} # line_index -> formatted line
        self.__display_begin_line_i = 0
        self.__max_line_length      = 0
        self.__mode                 = E_DiffMode.PLAIN

    @typed(mode=E_DiffMode)
    def set_mode(self, mode, verbosity_level=2):
        self.__mode = mode
        self._prepare_data(verbosity_level)

    def show(self):
        if self.height < 1:
            return 0

        L     = len(self.__lina_list)
        begin = self.__display_begin_line_i
        end   = min(begin + self.height - 1, L)
        if end <= begin:
            return 0

        for lina_i in range(begin, end):
            formatted = self.__display_cache_db.get(lina_i)
            if formatted is None:
                formatted = self._prepare_LineAssociation(self.__lina_list[lina_i])
                self.__display_cache_db[lina_i] = formatted
            self.display(formatted)

        return end

    def interact(self):
        delta_horizontal = 5 # int(canvas.width / 8)
        delta_vertical   = 5 # int(canvas.height / 8)
        self.set_mode(E_DiffMode.ERRORS, verbosity_level=2)
        while 1 + 1 == 2:
            displayed_line_n = self.show()
            self._display_fill_empty(displayed_line_n)
            self._display_status_line()
            while 1 + 1 == 2:
                key = keyboard.get()
                if   key == 'q': return
                elif key == 'a': self.__add_horizontal_offset(- delta_horizontal); break
                elif key == 'd': self.__add_horizontal_offset(delta_horizontal); break
                elif key == 'w': self.__add_vertical_offset(- delta_vertical); break
                elif key == 's': self.__add_vertical_offset(delta_vertical); break
                elif key == 'A': self.set_mode(E_DiffMode.ANALOGIES); break
                elif key == 'P': self.set_mode(E_DiffMode.PLAIN); break
                elif key == 'E': self.set_mode(E_DiffMode.ERRORS); break

    def _prepare_data(self, verbosity_level):
        """verbosity_level: level of verbosity in diff display
                  0  - only error line associations are displayed
                  1  - add '...' line associtions to show borders
                  2  - add one good line and '...' around error lines
        The 'verbosity_level' argument is only used for analogy errors and 
        'error' display
        """
        if self.__mode == E_DiffMode.PLAIN:
            lina_list_source = prepare.plain(self.__lina_chunk_list, 
                                             self.__sort_potpourri_by_subject_line_n_f)
            self.__lina_list = copy(lina_list_source)
        elif self.__mode == E_DiffMode.ANALOGIES:
            self.__lina_list = prepare.analogy_errors(self.__lina_chunk_list, 
                                                      self.__analogy_db, 
                                                      verbosity_level=verbosity_level)
        elif self.__mode == E_DiffMode.ERRORS:
            self.__lina_list = prepare.errors(self.__lina_chunk_list, 
                                              verbosity_level=verbosity_level)

        elif self.__mode == E_DiffMode.ERRORS_AND_TOLERATED:
            self.__lina_list = prepare.errors_and_tolerated(self.__lina_chunk_list, 
                                                            verbosity_level=verbosity_level)

        prepare.plug_end(self.__lina_list)

    def _display_fill_empty(self, diplayed_line_n):
        if diplayed_line_n >= self.height:
            return
        empty_formatted = self._prepare_LineAssociation(
            prepare.LineAssociationDecorated(0, 0, LineAssociation.empty(None)))
        for line_i in range(diplayed_line_n, self.height - 1):
            self.display(empty_formatted)

    def _display_status_line(self):
        L = len(self.__lina_list)
        if L == 0:     ratio = 1
        else:          ratio = min(L, self.__display_begin_line_i + self.height) / L
        if ratio == 1: percentage = "100" + "%"
        else:          percentage = "% 3i" % int(ceil(ratio*100)) + "%"

        self.display(self.prepare(self.format.status_line, [self.__mode.name, percentage]))

    def __add_horizontal_offset(self, value):
        if self.__max_line_length - (self.format.text_offset + value) <= 0:
            return
        self.format.add_text_offset(value)
        self.__display_cache_db.clear()
        self.__max_line_length = 0

    def __add_vertical_offset(self, value):
        self.__display_begin_line_i += value
        last_i = len(self.__lina_list) - (self.height - 1) # 1 -> status line
        if self.__display_begin_line_i >= last_i:
            self.__display_begin_line_i = last_i 
        if self.__display_begin_line_i < 0:
            self.__display_begin_line_i = 0
        
    def _prepare_LineAssociation(self, lina):
        """Displays a formatted line of an association of a subject line with a 
        nominal line.
        """
        subject_txt, nominal_txt = self._format_line_association(lina)
        if lina.filler_f:
            line = self.prepare(self.format.filler)
        elif lina.border != E_PotpourriBorder.NONE:
            line = self._prepare_potpourri_border(lina)
        elif lina.subject is None and lina.nominal is None:
            if lina.subject_end_f and lina.nominal_end_f: f = self.format.both_end
            elif lina.subject_end_f:                      f = self.format.subject_end_nominal_empty
            elif lina.nominal_end_f:                      f = self.format.nominal_end_subject_empty
            else:                                         f = self.format.empty
            line = self.prepare(f)
        elif lina.subject is None:
            if lina.subject_end_f: f = self.format.subject_end
            else:                  f = self.format.subject_empty
            line = self.prepare(f, ["%s" % lina.nominal.line_n, nominal_txt])
        elif lina.nominal is None:
            if lina.nominal_end_f: f = self.format.nominal_end
            else:                  f = self.format.nominal_empty
            line = self.prepare(f, [subject_txt, "%s" % lina.subject.line_n])
        else:
            def _line_n(line_n):
                return " " if line_n is None else "%s" % line_n         
            line = self.prepare(self.format.normal, 
                                [ subject_txt, 
                                  _line_n(lina.subject.line_n), 
                                  _line_n(lina.nominal.line_n), 
                                  nominal_txt])
        return line

    def _prepare_potpourri_border(self, lina):
        """Displays the border of a Potpourri region. 

        'begin_f' = True: display the OPENING of a potpourri region.
        else:             display the CLOSING of a potpourri region.
        """
        subject_line_n = "" if lina.subject is None else "%s" % lina.subject.line_n
        nominal_line_n = "" if lina.nominal is None else "%s" % lina.nominal.line_n
        if lina.border == E_PotpourriBorder.BEGIN: f = self.format.potpourri_begin
        else:                                      f = self.format.potpourri_end
        return self.prepare(f, [subject_line_n, nominal_line_n])

    @typed(line=LineAssociation)
    def _format_line_association(self, lina):
        """RETURNS: [0] subject text: list of (color, text)
                    [1] nominal text: list of (color, text)

           ADAPTS:  'self.__max_line_length' if a longer line occurred.

        Provides text and format information to display the 'LineAssociation'. 
        """
        subject_txt, nominal_txt = [], []
        subject_n,   nominal_n   = 0, 0
        s_length,    n_length    = 0, 0
        for lela in lina.line_element_association_list():
            s_color, s_txt, n_color, n_txt = _edit_db[lela.edit_id](lela.subject, lela.nominal)
            subject_txt.append((s_color, s_txt.replace("\t", "\\t")))
            nominal_txt.append((n_color, n_txt.replace("\t", "\\t")))
            s_length += len(s_txt)
            n_length += len(n_txt)

        if max(s_length, n_length) > self.__max_line_length:
            self.__max_line_length = max(s_length, n_length)

        return subject_txt, nominal_txt

def _good(subject, nominal):
    return "", subject.string, "", nominal.string

def _tolerated(subject, nominal):
    return Back.GREEN, subject.string, \
           Fore.GREEN, nominal.string

def _deleted(subject, nominal):
    return Back.RED, subject.string, \
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
    E_EditLine.GOOD:            _good,
    E_EditLine.GOOD_TOLERATED:  _tolerated,
    E_EditLine.DELETE:          _deleted,
    E_EditLine.INSERT:          _inserted,
    E_EditLine.TRANSPOSE:       _transpose,
    E_EditLine.SUBSTITUTE:      _substitute,
    E_EditLine.SUBSTITUTE_TYPE: _substitute_type,
    E_EditLine.NONE:            _none
}

