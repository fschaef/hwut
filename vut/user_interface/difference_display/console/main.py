from   vut.system.helper                                       import number_of_decimal_digits
from   vut.system.terminal                                     import ConsoleCanvas, LEFT, RIGHT, CENTER, FIXED, Fore, Back
from   vut.user_interface.difference_display.console.formatter import ConsoleCanvasFormatter
from   vut.engine.compare.engine.line_association_chunk        import LineAssociationChunk
from   vut.engine.compare.engine.line_association              import LineAssociation
from   vut.engine.compare.engine.input_chunk                   import E_Chunk
from   vut.engine.compare.edit_operations.line                 import E_EditLine
import vut.engine.compare.edit_operations.line                 as     edit_operations_line
from   vut.external.quex.typed                                 import typed

from   copy import copy

@typed(line_associations=[LineAssociationChunk])
def display(linachunks, text_offset):
    linachunks = list(linachunks)

    if not linachunks:
        return

    line_n_width = number_of_decimal_digits(linachunks[-1].max_line_n())
    canvas = ConsoleCanvasDiff(line_n_width, text_offset, 
                               sort_potpourri_by_subject_line_n_f=False)
    if False:
        for chunk in linachunks:
            canvas.do(chunk)
    else:
        def _get_lina(linachunks, subject_line_n, nominal_line_n):
            result = None
            for chunk in linachunks:
                result = chunk.get_line_association(subject_line_n, nominal_line_n)
                if result is not None: break
            return result

        analogy_db = linachunks[-1].analogy_db()
        lina_db = {}
        for subject, p in analogy_db.line_number_db.items():
            lina_db[(p.subject_line_n, p.nominal_line_n)] = \
                _get_lina(linachunks, p.subject_line_n, p.nominal_line_n)

        lina_db.update(
            ((lina.subject.line_n, lina.nominal.line_n), lina)
            for chunk in linachunks
            for lina in chunk.line_association_list()
            if lina.has_analogy_error()
        )

        for lina in lina_db.values():
            canvas.display_line_association(lina)

    return

class ConsoleCanvasAnalogyDiff(ConsoleCanvas):
    def __init__(self, linachunks, text_offset, sort_potpourri_by_subject_line_n_f):
        ConsoleCanvas.__init__(self)

        line_n_width = number_of_decimal_digits(linachunks[-1].max_line_n())
        self.format = ConsoleCanvasFormatter(self.width, line_n_width, 
                                             text_offset, 
                                             sort_potpourri_by_subject_line_n_f)
        self.set_format(*self.format.compare_line_sequence())

    def do(chunk):
        if chunk.type() == E_Chunk.POTPOURRI:
            lina_list = chunk.line_association_list()
            content = lina_list[1:-1]
            self.format.sort_potpourri_content(content)
            self._format_potpourri_border(lina_list[0], True)
            for line_association in content:
                self.display_line_association(line_association)
            self._format_potpourri_border(lina_list[-1], False)
        else:
            for line_association in chunk.line_association_list():
                self.display_line_association(line_association)

class ConsoleCanvasDiff(ConsoleCanvas):
    def __init__(self, line_n_width, text_offset, sort_potpourri_by_subject_line_n_f):
        ConsoleCanvas.__init__(self)

        self.format = ConsoleCanvasFormatter(self.width, line_n_width, 
                                             text_offset, 
                                             sort_potpourri_by_subject_line_n_f)
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

    def do(self, chunk):
        if chunk.type() == E_Chunk.POTPOURRI:
            lina_list = chunk.line_association_list()
            content = lina_list[1:-1]
            self.format.sort_potpourri_content(content)

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

