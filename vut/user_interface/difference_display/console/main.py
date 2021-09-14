from   vut.system.helper                                       import number_of_decimal_digits
from   vut.system.terminal                                     import ConsoleCanvas, GLUE, LEFT, RIGHT, CENTER, FIXED, Fore, Back
import vut.system.keyboard                                     as     keyboard
from   vut.user_interface.difference_display.console.formatter import ConsoleCanvasFormatter
from   vut.engine.compare.engine.line_association_chunk        import LineAssociationChunk, \
                                                                      LineAssociationList
from   vut.engine.compare.engine.line_association              import LineAssociation
from   vut.engine.compare.engine.input_chunk                   import E_Chunk
from   vut.engine.compare.engine.core                          import E_PotpourriBorder
from   vut.engine.compare.edit_operations.line                 import E_EditLine, Edit
import vut.engine.compare.edit_operations.line                 as     edit_operations_line
from   vut.external.quex.typed                                 import typed

from   copy import copy
from   math import ceil

from   enum import Enum, auto
from   itertools import chain

@typed(lina_cnunk_list=[LineAssociationChunk], sort_potpourri_by_subject_line_n_f=bool)
def do(lina_chunk_list, text_offset=0, sort_potpourri_by_subject_line_n_f=False):
    """Displays a comparison of subject and nominal lines clustered in 
    'LineAssociationChunk'-s.
    """

    canvas = ConsoleCanvasDiff(lina_chunk_list) 

    canvas.interact()

class E_DiffMode(Enum):
    PLAIN     = auto()
    ERRORS    = auto()
    ANALOGIES = auto()


class LineAssociationDecorated(LineAssociation):
    def __init__(self, chunk_index, lina_index, lina):
        self.chunk_index   = chunk_index
        self.lina_index    = lina_index
        LineAssociation.__init__(self, lina.subject, lina.nominal, lina.edit_list, lina.border)
        self.subject_end_f = False
        self.nominal_end_f = False
        self.filler_f      = False

    @staticmethod
    def filler():
        result = LineAssociationDecorated(0, 0, LineAssociation(None, None))
        result.filler_f = True
        return result

def lina_list_from_lina_chunk_list(lina_chunk_list, sort_potpourri_by_subject_line_n_f):
    result = LineAssociationList([])
    
    for chunk_index, chunk in enumerate(lina_chunk_list):
        lina_list = LineAssociationList(chunk.line_association_list())
        result.extend(
            LineAssociationDecorated(chunk_index, lina_index, lina) 
            for lina_index, lina in enumerate(lina_list)
        )

    return result

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
    def set_mode(self, mode):
        self.__mode = mode
        self.prepare_data()

    def prepare_data(self):
        lina_list_source = lina_list_from_lina_chunk_list(self.__lina_chunk_list, 
                                                          self.__sort_potpourri_by_subject_line_n_f)
        if self.__mode == E_DiffMode.PLAIN:
            self.__lina_list = copy(lina_list_source)
        elif self.__mode == E_DiffMode.ANALOGIES:
            self.__lina_list = _prepare_display_analogy_errors(lina_list_source, self.__analogy_db)
        elif self.__mode == E_DiffMode.ERRORS:
            self.__lina_list = _prepare_display_brief(self.__lina_chunk_list)

        if not self.__lina_list:
            return

        # find last of each
        lina_n             = len(self.__lina_list) 
        end_subject_lina_i = None
        end_nominal_lina_i = None
        for lina_i, lina in reversed(list(enumerate(self.__lina_list))):
            if lina.border == E_PotpourriBorder.END: 
                end_subject_lina_i = lina_i + 1
                end_nominal_lina_i = lina_i + 1
                break
            if lina.subject is not None and end_subject_lina_i is None:
                end_subject_lina_i = lina_i + 1
            if lina.nominal is not None and end_nominal_lina_i is None:
                end_nominal_lina_i = lina_i + 1
            if end_subject_lina_i is not None and end_nominal_lina_i is not None:
                break

        if end_subject_lina_i == lina_n or end_nominal_lina_i == lina_n:
            extra = LineAssociationDecorated(-1, -1, LineAssociation.empty())
            self.__lina_list.append(extra)
        self.__lina_list[end_subject_lina_i].subject_end_f = True 
        self.__lina_list[end_nominal_lina_i].nominal_end_f = True 

    def _display_LineAssociations(self):
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

    def _display_fill_empty(self, diplayed_line_n):
        if diplayed_line_n >= self.height:
            return
        empty_formatted = self._prepare_LineAssociation(LineAssociationDecorated(0, 0, LineAssociation.empty(None)))
        for line_i in range(diplayed_line_n, self.height - 1):
            self.display(empty_formatted)

    def _display_status_line(self):
        L = len(self.__lina_list)
        if L == 0:     ratio = 1
        else:          ratio = min(L, self.__display_begin_line_i + self.height) / L
        if ratio == 1: percentage = "100" + "%"
        else:          percentage = "% 3i" % int(ceil(ratio*100)) + "%"
        self.display(self.prepare(self.format.status_line, [percentage]))

    def interact(self):
        delta_horizontal = 5 # int(canvas.width / 8)
        delta_vertical   = 5 # int(canvas.height / 8)
        self.prepare_data()
        while 1 + 1 == 2:
            displayed_line_n = self._display_LineAssociations()
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

def _prepare_display_brief(lina_chunk_list, level=3):
    """RETURNS: list of LineAssociationDecorated

    to display errors. That is, lines which are equivalent are omitted from
    display, except for those neighbouring error lines.
    """
    def _some_border(prev_lina_i, lina_i, lina_list):
        delta = lina_i - prev_lina_i
        if delta > 4:
            yield LineAssociationDecorated(0, 0, lina_list[prev_lina_i+1])
            yield LineAssociationDecorated.filler()
            yield LineAssociationDecorated(0, 0, lina_list[lina_i - 1])
        elif delta == 4:
            yield LineAssociationDecorated(0, 0, lina_list[prev_lina_i+1])
            yield LineAssociationDecorated(0, 0, lina_list[lina_i - 2])
            yield LineAssociationDecorated(0, 0, lina_list[lina_i - 1])
        elif delta == 3:
            yield LineAssociationDecorated(0, 0, lina_list[lina_i - 2])
            yield LineAssociationDecorated(0, 0, lina_list[lina_i - 1])
        elif delta == 2:
            yield LineAssociationDecorated(0, 0, lina_list[lina_i - 1])
        yield LineAssociationDecorated(0, 0, lina_list[lina_i])

    def _no_border(prev_lina_i, lina_i, lina_list):
        delta = lina_i - prev_lina_i
        if delta > 2:
            yield LineAssociationDecorated.filler()
        elif delta == 2:
            yield LineAssociationDecorated(0, 0, lina_list[lina_i - 1])
        yield LineAssociationDecorated(0, 0, lina_list[lina_i])

    def _no_filler(prev_lina_i, lina_i, lina_list):
        yield LineAssociationDecorated(0, 0, lina_list[lina_i])

    if   level == 0: _handle = _no_filler
    elif level == 1: _handle = _no_border
    elif level == 2: _handle = _some_border

    prev_lina_i = -1
    if not lina_index_list:
        return
    elif lina_index_list[0] != 0 and level > 0:
        yield LineAssociationDecorated.filler()

    prev_lina_i = lina_index_list[0] - 1
    for lina_i in lina_index_list:
        yield from _handle(prev_lina_i, lina_i, lina_list)
        prev_lina_i = lina_i

    if lina_i != len(lina_list) - 1 and level > 0:
        yield LineAssociationDecorated.filler()

def _prepare_display_errors(lina_chunk_list, level=3):
    result = LineAssociationList()
    for chunk in lina_chunk_list:
        lina_list = chunk.line_association_list()
        if chunk.type() == E_Chunk.LINE_SEQUENCE:
            lina_index_list = chunk.find_indices_of_error_linas()
            result.extend(_prepare_display_brief(lina_index_list, level)
        else:
            result.extend(_prepare_display_brief(lina_index_list, level=0)

    return result

            
@typed(errors_f=bool, definitions_f=bool)
def _prepare_display_analogy_errors(lina_list, 
                                    analogy_db,
                                    errors_f=True, 
                                    definitions_f=True):
    """RETURNS: list of LineAssociation objects.

    Each 'LineAssociation' contains the association of a subject and a nominal line
    which is concerned with an analogy error. 
    
    errors_f:       report 'LineAssociation' containing analogy errors.
    definitions_f:  report 'LineAssociation' containing lines where analogies are
                    defined that later cause errors.
    """
    assert errors_f or definitions_f

    error_lina_list, \
    subject_nominal_set = lina_list.analogy_errors(errors_f) 

    if definitions_f:
        definition_lina_list = lina_list.find_definitions(analogy_db, subject_nominal_set)
    else:
        definition_lina_list = []

    done   = set()
    result = LineAssociationList()
    for lina in chain(definition_lina_list, error_lina_list):
        key = (lina.subject.line_n, lina.nominal.line_n)
        if key in done: continue 
        result.append(lina)
        done.add(key)

    return result.sort(True)

