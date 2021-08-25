from   vut.system.helper                                import number_of_decimal_digits
from   vut.system.terminal                              import ConsoleCanvas, LEFT, RIGHT, CENTER, FIXED, Fore, Back
from   vut.engine.compare.engine.line_association_chunk import LineAssociationChunk
from   vut.engine.compare.engine.line_association       import LineAssociation
from   vut.engine.compare.engine.input_chunk            import E_Chunk
from   vut.engine.compare.edit_operations.line          import E_EditLine
import vut.engine.compare.edit_operations.line          as     edit_operations_line
from   vut.external.quex.typed                          import typed

@typed(line_associations=[LineAssociationChunk])
def display(linachunks, text_offset):
    linachunks = list(linachunks)

    if not linachunks:
        return

    canvas = ConsoleCanvasDiff(linachunks, text_offset)
    for chunk in linachunks:
        canvas.display_line_association_chunk(chunk)

    return


class ConsoleCanvasDiff(ConsoleCanvas):
    def __init__(self, linachunks, text_offset):
        ConsoleCanvas.__init__(self)

        self.line_n_width  = number_of_decimal_digits(linachunks[-1].max_line_n())
        
        remaining          = self.width - 2 * self.line_n_width - 2
        self.subject_width = remaining >> 1
        self.nominal_width = remaining - self.subject_width

        self.set_format(LEFT(self.subject_width, text_offset=text_offset), 
                        FIXED(" ", "Uw"), 
                        LEFT(self.line_n_width, "Uw"), 
                        FIXED("|", "Bw"), 
                        LEFT(self.line_n_width, "Uw"), 
                        FIXED(" ", "Uw"), 
                        LEFT(self.nominal_width, text_offset=text_offset))

    def display_line_association_chunk(self, chunk):
        if chunk.type() == E_Chunk.POTPOURRI:
            lina_list = chunk.line_association_list()
            self._format_potpourri_border(lina_list[0], True)
            for line_association in lina_list[1:-1]:
                self.display_line_association(line_association)
            self._format_potpourri_border(lina_list[-1], False)
        else:
            for line_association in chunk.line_association_list():
                self.display_line_association(line_association)

    def display_line_association(self, lina):
        subject_txt, nominal_txt = self._format_line_association(lina)
        subject_line_n = "" if lina.subject is None else "%s" % lina.subject.line_n
        nominal_line_n = "" if lina.nominal is None else "%s" % lina.nominal.line_n

        return self.print_line(subject_txt, "%s" % subject_line_n, 
                               "%s" % nominal_line_n, nominal_txt)

    def _format_potpourri_border(self, lina, begin):

        subject_line_n = "" if lina.subject is None else "%s" % lina.subject.line_n
        nominal_line_n = "" if lina.nominal is None else "%s" % lina.nominal.line_n
        self.push_format(FIXED("||||", "Ub"), LEFT(self.subject_width-4, "Gb"), 
                         FIXED(" ", "Uw"), 
                         LEFT(self.line_n_width, "Uw"), 
                         FIXED("|", "Uw"), 
                         LEFT(self.line_n_width, "Uw"), 
                         FIXED(" ", "Uw"), 
                         RIGHT(self.nominal_width-4, "Gb"), FIXED("||||", "Ub"))
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
    return Back.GREEN, subject.string, \
           Back.GREEN, nominal.string

def _deleted(subject, nominal):
    return Back.BLUE, subject.string, \
           Back.CYAN, " " * len(subject.string)

def _inserted(subject, nominal):
    return Back.CYAN, " " * len(nominal.string), \
           Back.BLUE, nominal.string

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

