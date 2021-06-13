from   vut.system.helper                                import number_of_decimal_digits
from   vut.system.terminal                              import ConsoleCanvas, LEFT, RIGHT, CENTER
from   vut.engine.compare.engine.line_association_chunk import LineAssociationChunk
from   vut.engine.compare.engine.line_association       import LineAssociation
from   vut.engine.compare.engine.input_chunk            import E_Chunk
from   vut.engine.compare.edit_operations.line          import E_EditLine
import vut.engine.compare.edit_operations.line          as     edit_operations_line
from   vut.engine.quex.typed                            import typed

@typed(line_associations=[LineAssociationChunk])
def display(linachunks):
    if not linachunks:
        return
    linachunks = list(linachunks)

    canvas = ConsoleCanvasDiff(linachunks)
    for chunk in linachunks:
        canvas.display_line_association_chunk(chunk)

    return


class ConsoleCanvasDiff(ConsoleCanvas):
    def __init__(self, linachunks):
        ConsoleCanvas.__init__(self)

        self.line_n_width  = number_of_decimal_digits(linachunks[-1].max_line_n())
        
        remaining     = self.width - 2 * self.line_n_width - 2
        self.subject_width = remaining >> 1
        self.nominal_width = remaining - self.subject_width

        self.set_format(LEFT(self.subject_width), " ", LEFT(self.line_n_width), 
                        "|", 
                        LEFT(self.line_n_width), " ", LEFT(self.nominal_width))

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
        if begin:
            border_raw = ".-=-._" * (int((self.width - 8) / 12) + 1)
        else:
            border_raw = "-._.-=" * (int((self.width - 8) / 12) + 1)
        subject_line_n = "" if lina.subject is None else "%s" % lina.subject.line_n
        nominal_line_n = "" if lina.nominal is None else "%s" % lina.nominal.line_n
        border     = border_raw[:self.width - 8] 
        self.push_format(LEFT(self.subject_width), " ", LEFT(self.line_n_width), 
                         "|", 
                        LEFT(self.line_n_width), " ", RIGHT(self.nominal_width))
        self.print_line("||||" + border_raw, "%s" % subject_line_n, 
                        "%s" % nominal_line_n, border_raw + "||||")
        self.pop_format()

    @typed(line=LineAssociation)
    def _format_line_association(self, lina):
        subject_txt = []
        nominal_txt = []
        for lela in lina.line_element_association_list():
            s_txt, n_txt = _edit_db[lela.edit.id](lela.subject, lela.nominal)
            subject_txt.append(s_txt)
            nominal_txt.append(n_txt)
        return "".join(subject_txt), "".join(nominal_txt)

def _good(subject, nominal):
    return subject.string, nominal.string

def _tolerated(subject, nominal):
    return "t(%s)" % subject.string, nominal.string

def _deleted(subject, nominal):
    return "d(%s)" % subject.string, ""

def _inserted(subject, nominal):
    return "i(%s)" % (" " * len(nominal.string)), nominal.string

def _transpose(subject, nominal):
    return "T(%s)" % subject.string, nominal.string

def _substitute(subject, nominal):
    return "s(%s)" % subject.string, nominal.string

def _substitute_type(subject, nominal):
    return "S(%s)" % subject.string, nominal.string

def _none(subject, nominal):
    return "" if not subject else subject.string, "" if not nominal else nominal.string 

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

