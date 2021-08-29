from   vut.system.helper                                       import number_of_decimal_digits
from   vut.system.terminal                                     import ConsoleCanvas, LEFT, RIGHT, CENTER, FIXED, Fore, Back
from   vut.user_interface.difference_display.console.formatter import ConsoleCanvasFormatter
from   vut.engine.compare.engine.line_association_chunk        import LineAssociationChunk, \
                                                                      line_association_list_sort, \
                                                                      line_association_chunk_list_find_entries_relevant_to_analogy_errors
from   vut.engine.compare.engine.line_association              import LineAssociation
from   vut.engine.compare.engine.input_chunk                   import E_Chunk
from   vut.engine.compare.edit_operations.line                 import E_EditLine
import vut.engine.compare.edit_operations.line                 as     edit_operations_line
from   vut.external.quex.typed                                 import typed

from   copy import copy

@typed(lina_chunk_list=[LineAssociationChunk], sort_by_subject_line_n_f=bool)
def comparison(lina_chunk_list, text_offset, sort_by_subject_line_n=False):
    """Displays a comparison of subject and nominal lines clustered in 
    'LineAssociationChunk'-s.
    """
    line_n_width = number_of_decimal_digits(lina_chunk_list[-1].max_line_n())
    canvas       = ConsoleCanvasDiff(line_n_width, text_offset, 
                                     sort_potpourri_by_subject_line_n_f=sort_by_subject_line_n)
    for chunk in lina_chunk_list:
        canvas.display_LineAssociationChunk(chunk)

@typed(lina_chunk_list=[LineAssociationChunk], sort_by_subject_line_n_f=bool)
def analogy_error(lina_chunk_list, text_offset, sort_by_subject_line_n=False):
    """Displays lines related to analogy errors. That is, for each analogy error, the
    line where the analogy is defined and where it causes an error is displayed.
    """

    line_n_width = number_of_decimal_digits(lina_chunk_list[-1].max_line_n())
    canvas       = ConsoleCanvasDiff(line_n_width, text_offset) 

    lina_list = line_association_chunk_list_find_entries_relevant_to_analogy_errors(lina_chunk_list)

    for lina in line_association_list_sort(lina_list, sort_by_subject_line_n):
        canvas.display_LineAssociation(lina)

class ConsoleCanvasDiff(ConsoleCanvas):
    def __init__(self, line_n_width, text_offset, sort_potpourri_by_subject_line_n_f=True):
        ConsoleCanvas.__init__(self)

        self.format = ConsoleCanvasFormatter(self.width, line_n_width, text_offset)
        self.sort_potpourri_by_subject_line_n_f = sort_potpourri_by_subject_line_n_f
        self.set_format(*self.format.compare_line_sequence())
        
    def display_LineAssociation(self, lina):
        """RETURNS: True, in case of success.
                    False, else.

        Displays a formatted line of an association of a subject line with a 
        nominal line.
        """
        subject_txt, nominal_txt = self._format_line_association(lina)
        if lina.subject is None or lina.nominal is None:
            if lina.subject is None:
                subject_txt = self.format.empty_subject()
                self.push_format(*self.format.compare_line_sequence_no_subject())
                verdict = self.print_line("%s" % lina.nominal.line_n, nominal_txt)
            else:
                self.push_format(*self.format.compare_line_sequence_no_nominal())
                verdict = self.print_line(subject_txt, "%s" % lina.subject.line_n)
            self.pop_format()
        else:
            verdict = self.print_line(subject_txt, 
                                      "%s" % lina.subject.line_n, "%s" % lina.nominal.line_n, 
                                      nominal_txt)
        return verdict

    def display_LineAssociationChunk(self, chunk):
        """Displays a 'LineAssociationChunk' (LineSequences or Potpourri). It relies
        for each line association on 'display_LineAssociation()'.
        """
        if chunk.type() == E_Chunk.POTPOURRI:
            lina_list = chunk.line_association_list()
            content = lina_list[1:-1]
            line_association_list_sort(content, self.sort_potpourri_by_subject_line_n_f)

            self._print_potpourri_border(lina_list[0], True)
            for line_association in content:
                self.display_LineAssociation(line_association)
            self._print_potpourri_border(lina_list[-1], False)
        else:
            for line_association in chunk.line_association_list():
                self.display_LineAssociation(line_association)

    def _print_potpourri_border(self, lina, begin_f):
        """Displays the border of a Potpourri region. 

        'begin_f' = True: display the OPENING of a potpourri region.
        else:             display the CLOSING of a potpourri region.
        """
        subject_line_n = "" if lina.subject is None else "%s" % lina.subject.line_n
        nominal_line_n = "" if lina.nominal is None else "%s" % lina.nominal.line_n
        self.push_format(*self.format.compare_potpourri(begin_f))
        self.print_line(subject_line_n, nominal_line_n)
        self.pop_format()

    @typed(line=LineAssociation)
    def _format_line_association(self, lina):
        """RETURNS: [0] subject text: list of (color, text)
                    [1] nominal text: list of (color, text)

        Provides text and format information to display the 'LineAssociation'. 
        """
        subject_txt = []
        nominal_txt = []
        subject_n   = 0
        nominal_n   = 0
        for lela in lina.line_element_association_list():
            s_color, s_txt, n_color, n_txt = _edit_db[lela.edit_id](lela.subject, lela.nominal)
            subject_txt.append((s_color, s_txt.replace("\t", "\\t")))
            nominal_txt.append((n_color, n_txt.replace("\t", "\\t")))

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

