from   vut.system.helper                                       import number_of_decimal_digits
from   vut.system.terminal                                     import ConsoleCanvas, GLUE, LEFT, RIGHT, CENTER, FIXED, Fore, Back
import vut.system.keyboard                                     as     keyboard
from   vut.user_interface.difference_display.console.formatter import ConsoleCanvasFormatter
from   vut.engine.compare.engine.line_association_chunk        import LineAssociationChunk, \
                                                                      line_association_chunk_list_find_entries_relevant_to_analogy_errors
from   vut.engine.compare.engine.line_association              import LineAssociation
from   vut.engine.compare.engine.input_chunk                   import E_Chunk
from   vut.engine.compare.edit_operations.line                 import E_EditLine
from   vut.engine.compare.engine.core                          import E_PotpourriBorder
import vut.engine.compare.edit_operations.line                 as     edit_operations_line
from   vut.external.quex.typed                                 import typed

from   copy import copy
from   math import ceil

class LineAssociationDecorated(LineAssociation):
    def __init__(self, chunk_index, lina_index, lina):
        self.chunk_index = chunk_index
        self.lina_index  = lina_index
        LineAssociation.__init__(self, lina.subject, lina.nominal, lina.edit_list, lina.border)

@typed(lina_chunk_list=[LineAssociationChunk], sort_by_subject_line_n_f=bool)
def comparison(lina_chunk_list, text_offset, sort_by_subject_line_n_f=False):
    """Displays a comparison of subject and nominal lines clustered in 
    'LineAssociationChunk'-s.
    """
    content_db = [
        LineAssociationDecorated(chunk_index, lina_index, lina) 
        for chunk_index, chunk in enumerate(lina_chunk_list)
        for lina_index, lina in enumerate(chunk.line_association_list(sort_by_subject_line_n_f))
    ]

    line_n_width = number_of_decimal_digits(lina_chunk_list[-1].max_line_n())
    canvas       = ConsoleCanvasDiff(line_n_width, text_offset, 
                                     sort_potpourri_by_subject_line_n_f=sort_by_subject_line_n_f)

    canvas.extend(lina for lina in content_db)
    canvas.interact()

@typed(lina_chunk_list=[LineAssociationChunk], sort_by_subject_line_n_f=bool)
def analogy_error(lina_chunk_list, text_offset, sort_by_subject_line_n_f=False):
    """Displays lines related to analogy errors. That is, for each analogy error, the
    line where the analogy is defined and where it causes an error is displayed.
    """

    line_n_width = number_of_decimal_digits(lina_chunk_list[-1].max_line_n())
    canvas       = ConsoleCanvasDiff(line_n_width, text_offset) 

    lina_list = line_association_chunk_list_find_entries_relevant_to_analogy_errors(lina_chunk_list,
                                                                                    sort_by_subject_line_n_f)

    canvas.extend(lina_list)

    canvas.interact()

class ConsoleCanvasDiff(ConsoleCanvas):
    def __init__(self, line_n_width, text_offset, sort_potpourri_by_subject_line_n_f=True):
        ConsoleCanvas.__init__(self)

        self.format = ConsoleCanvasFormatter(self.width, line_n_width, text_offset, self)
        self.sort_potpourri_by_subject_line_n_f = sort_potpourri_by_subject_line_n_f
        self.__lina_list            = []
        self.__display_cache_db     = {} # line_index -> formatted line
        self.__display_begin_line_i = 0
        self.__max_line_length      = 0

    @typed(lina=LineAssociationDecorated)
    def append(self, lina):
        self.__lina_list.append(lina)

    def extend(self, lina_iterable):
        self.__lina_list.extend(lina_iterable)

    def show(self):
        if self.height < 1:
            return
        L     = len(self.__lina_list)
        begin = self.__display_begin_line_i
        end   = min(begin + self.height - 1, L)
        if end <= begin:
            return

        for line_i in range(begin, end):
            formatted = self.__display_cache_db.get(line_i)
            if formatted is None:
                formatted = self._prepare_LineAssociation(self.__lina_list[line_i])
                self.__display_cache_db[line_i] = formatted
            self.display(formatted)

        if L == 0:     ratio = 1
        else:          ratio = min(L, self.__display_begin_line_i + self.height) / L
        if ratio == 1: percentage = "100" + "%"
        else:          percentage = "% 3i" % int(ceil(ratio*100)) + "%"
            
        self.display(self.prepare(self.format.status_line, [percentage]))

    def interact(self):
        delta_horizontal = 5 # int(canvas.width / 8)
        delta_vertical   = 5 # int(canvas.height / 8)
        while 1 + 1 == 2:
            self.show()
            while 1 + 1 == 2:
                key = keyboard.get()
                if   key == 'q': return
                elif key == 'a': self.__add_horizontal_offset(- delta_horizontal); break
                elif key == 'd': self.__add_horizontal_offset(delta_horizontal); break
                elif key == 'w': self.__add_vertical_offset(- delta_vertical); break
                elif key == 's': self.__add_vertical_offset(delta_vertical); break

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
        if lina.border != E_PotpourriBorder.NONE:
            line = self._prepare_potpourri_border(lina)
        elif lina.subject is None or lina.nominal is None:
            if lina.subject is None:
                line = self.prepare(self.format.empty_subject, ["%s" % lina.nominal.line_n, nominal_txt])
            else:
                line = self.prepare(self.format.empty_nominal, [nominal_txt, "%s" % lina.subject.line_n])
        else:
            line = self.prepare(self.format.normal, 
                                [ subject_txt, "%s" % lina.subject.line_n, 
                                "%s" % lina.nominal.line_n, nominal_txt])
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

