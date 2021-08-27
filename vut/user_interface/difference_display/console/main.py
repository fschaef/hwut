from   vut.system.helper                                import number_of_decimal_digits
from   vut.system.terminal                              import ConsoleCanvas, LEFT, RIGHT, CENTER, FIXED, Fore, Back
from   vut.engine.compare.engine.line_association_chunk import LineAssociationChunk
from   vut.engine.compare.engine.line_association       import LineAssociation
from   vut.engine.compare.engine.input_chunk            import E_Chunk
from   vut.engine.compare.edit_operations.line          import E_EditLine
import vut.engine.compare.edit_operations.line          as     edit_operations_line
from   vut.external.quex.typed                          import typed

from   copy import copy

@typed(line_associations=[LineAssociationChunk])
def display(linachunks, text_offset):
    linachunks = list(linachunks)

    if not linachunks:
        return

    canvas = ConsoleCanvasDiff(linachunks, text_offset, 
                               sort_potpourri_by_subject_line_n_f=False,
                               show_only_analogy_development_f=False)
    for chunk in linachunks:
        canvas.display_line_association_chunk(chunk)

    return

class ConsoleCanvasDiff(ConsoleCanvas):
    def __init__(self, linachunks, text_offset, sort_potpourri_by_subject_line_n_f, show_only_analogy_development_f):
        ConsoleCanvas.__init__(self)

        line_n_width = number_of_decimal_digits(linachunks[-1].max_line_n())
        self.format = ConsoleCanvasFormatter(self.width, line_n_width, 
                                             text_offset, 
                                             sort_potpourri_by_subject_line_n_f, 
                                             show_only_analogy_development_f)
        self.set_format(*self.format.compare_line_sequence())
        
    def display_line_association(self, lina):
        subject_txt, nominal_txt = self._format_line_association(lina)
        if lina.subject is None:
            subject_txt = self.format.empty_subject()
            self.push_format(*self.format.compare_line_sequence_no_subject())
        elif lina.nominal is None:
            nominal_txt = self.format.empty_nominal()
            self.push_format(*self.format.compare_line_sequence_no_nominal())

        subject_line_n = "<" if lina.subject is None else "%s" % lina.subject.line_n
        nominal_line_n = ">" if lina.nominal is None else "%s" % lina.nominal.line_n

        verdict = self.print_line(subject_txt, "%s" % subject_line_n, 
                                  "%s" % nominal_line_n, nominal_txt)
        if lina.subject is None or lina.nominal is None: 
            self.pop_format()
        return verdict

    def display_line_association_chunk(self, chunk):
        if chunk.type() == E_Chunk.POTPOURRI:
            lina_list = chunk.line_association_list()
            content = lina_list[1:-1]
            if self.format.sort_potpourri_by_subject_f:
                content.sort(key=lambda x: (1, x.nominal.line_n) if x.subject is None else (0, x.subject.line_n))
            else:
                content.sort(key=lambda x: (1, x.subject.line_n) if x.nominal is None else (0, x.nominal.line_n))

            self._format_potpourri_border(lina_list[0], True)
            for line_association in content:
                self.display_line_association(line_association)
            self._format_potpourri_border(lina_list[-1], False)
        else:
            for line_association in chunk.line_association_list():
                self.display_line_association(line_association)

    def _format_potpourri_border(self, lina, begin):
        subject_line_n = "" if lina.subject is None else "%s" % lina.subject.line_n
        nominal_line_n = "" if lina.nominal is None else "%s" % lina.nominal.line_n
        self.push_format(*self.format.compare_potpourri())
        self.print_line("", "%s" % subject_line_n, "%s" % nominal_line_n, "")
        self.pop_format()

    @typed(line=LineAssociation)
    def _format_line_association(self, lina):
        subject_txt = []
        nominal_txt = []
        subject_n   = 0
        nominal_n   = 0
        for lela in lina.line_element_association_list():
            s_color, s_txt, n_color, n_txt = _edit_db[lela.edit_id](lela.subject, lela.nominal)
            subject_txt.append((s_color, s_txt.replace("\t", "\\t")))
            nominal_txt.append((n_color, n_txt.replace("\t", "\\t")))
        return subject_txt, nominal_txt

class ConsoleCanvasFormatter:
    def __init__(self, terminal_width, line_n_width, text_offset, sort_potpourri_by_subject_line_n_f, show_only_analogy_development_f):
        self.line_n_width  = line_n_width
        
        remaining          = terminal_width - 2 * self.line_n_width - 3
        self.subject_width = int(remaining/2)
        self.nominal_width = remaining - self.subject_width
        self.text_offset = text_offset
        self.sort_potpourri_by_subject_f = sort_potpourri_by_subject_line_n_f


    def compare_line_sequence(self):
        return [
            LEFT(self.subject_width, text_offset=self.text_offset), 
            FIXED(" ", "Uw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED("|", "Bw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED(" ", "Uw"), 
            LEFT(self.nominal_width, text_offset=self.text_offset)
        ]

    def compare_line_sequence_no_subject(self):
        return [
            LEFT(self.subject_width, text_offset=self.text_offset), 
            FIXED(" ", "Uw"), 
            LEFT(self.line_n_width, "Rw"), 
            FIXED("|", "Bw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED(" ", "Uw"), 
            LEFT(self.nominal_width, text_offset=self.text_offset)
        ]

    def compare_line_sequence_no_nominal(self):
        return [
            LEFT(self.subject_width, text_offset=self.text_offset), 
            FIXED(" ", "Uw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED("|", "Bw"), 
            LEFT(self.line_n_width, "Rw"), 
            FIXED(" ", "Uw"), 
            LEFT(self.nominal_width, text_offset=self.text_offset)
        ]


    def compare_potpourri(self):
        return [
            FIXED("|" * self.subject_width, "Gw"), 
            FIXED(" ", "Uw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED("|", "Uw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED(" ", "Uw"), 
            FIXED("|" * self.nominal_width, "Gw"),
        ]

    @staticmethod
    def _empty(width):
        return " " * width

    def empty_subject(self):
        return [(Back.WHITE+Fore.RED, self._empty(self.text_offset) + ">" + self._empty(self.subject_width-1))]

    def empty_nominal(self):
        return [(Back.WHITE+Fore.RED, self._empty(self.nominal_width-1+self.text_offset) + "<")]

def _good(subject, nominal):
    return "", subject.string, "", nominal.string

def _tolerated(subject, nominal):
    return Back.GREEN + Fore.WHITE, subject.string, \
           Back.GREEN + Fore.WHITE, nominal.string

def _deleted(subject, nominal):
    return Back.BLUE + Fore.WHITE, subject.string, \
           Back.CYAN, " " * len(subject.string)

def _inserted(subject, nominal):
    return Back.CYAN, " " * len(nominal.string), \
           Back.BLUE + Fore.WHITE, nominal.string

def _transpose(subject, nominal):
    return Back.YELLOW, subject.string, \
           Back.YELLOW, nominal.string

def _substitute(subject, nominal):
    return Back.RED + Fore.WHITE, subject.string, \
           Back.RED + Fore.WHITE, nominal.string

def _substitute_type(subject, nominal):
    return Back.RED + Fore.BLACK, subject.string, \
           Back.RED + Fore.BLACK, nominal.string

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

