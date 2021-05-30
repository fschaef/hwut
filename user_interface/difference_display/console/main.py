from   ut.system.helpers  import number_of_decimal_digits
import ut.system.terminal as     terminal

@typed(line_associations=[LineAssociationChunk])
def do(linachunks):
    if not linachunks:
        return

    canvas = ConsoleCanvas(linachunks)
    for chunk in linachunks:
        for line_association in chunk:
            canvas.do(line_association)

    return


class ConsoleCanvasDiff(ConsoleCanvas):
    def __init__(self, linachunks):
        ConsoleCanvas.__init__()

        self.max_subject_line_n = linachunks[-1].max_subject_line_n
        self.max_nominal_line_n = linachunks[-1].max_nominal_line_n
        
        line_n_width = max(number_of_decimal_digits(max_subject_line_n),
                           number_of_decimal_digits(max_nominal_line_n))
        
        remaining = self.width - 2 * line_n_width - 2
        subject_width = (self.width - remaining) >> 1
        nominal_width = self.width - nominal_width

        self.set_format(subject_width, 1, line_n_width, 1, line_n_width, nominal_width)


    def do(self, line_association):
        subject_line_n_str = self._format_subject_line_n(line_association.subject.line_n)
        nominal_line_n_str = self._format_nominal_line_n(line_association.nominal.line_n)
        subject_txt = self.format_line(line_association.subject, line_association.edit_list)
        nominal_txt = self.format_line(line_association.nominal, line_association.edit_list)

        return self.prepare(subject_txt, " ", subject_line_n_str, "|", nominal_line_n_str, " ", nominal_txt)

    @typed(line=LineAssociation)
    def _format_line_association(self, lina):
        subject_txt = []
        nominal_txt = []
        si = ni = 0
        transposed_list = []
        for edit in edit_list:
            subject, nominal = subject_sequence[si], nominal_sequence[ni]

            subject_txt.append(self._format_subject_line_element(self, subject, nominal, edit))
            nominal_txt.append(self._format_nominal_line_element(self, nominal, nominal, edit))

            s_incr, n_incr = edit_operations_line_sequence.position_increment_db[edit_id]
            si += s_incr
            ni += n_incr

    def _format_subject_line_element(self, subject, nominal, edit):
        if   edit.id == GOOD:
            if subject.string != nominal.string:                id = TOLERATED
            elif subject.tolerance_id == E_ToleranceId.ANALOGY: id = TOLERATED
            else:                                               id = GOOD
        elif edit.id == TRANSPOSED:
            transposed_list.append(edit.transpose_i)
        elif subject_i in transposed_list:                      id = TRANSPOSED
        else:                                                   id = edit.id
        yield db[id](subject, nominal)

    def _format_subject_line_n(self, N):
        space = " " * (self.max_subject_line_n - number_of_decimal_digits(N))
        return self._format_line_n(space, N)

    def _format_nominal_line_n(self, N):
        space = " " * (self.max_nominal_line_n - number_of_decimal_digits(N))
        return self._format_line_n(space, N)

    def _format_line_n(self, space, N):
        if N is None: return space
        else:         return space + "%i" % N

    def _good(self, this, that):
        return this.string

    def _tolerated(self, this, that):
        return "t(%s)" % this.string

    def _deleted(self, this, that):
        return "d(%s)" % this.string

    def _inserted(self, this, that):
        return "i(%s)" % that.string

    def _transpose(self, this, that):
        return "T(%s)" % this.string

    def _substitute(self, this, that):
        return "s(%s)" % that.string

    def _substitute_type(self, this, that):
        return "S(%s)" % this.string
