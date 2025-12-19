import vut.system.file_system  as     file_system
import vut.engine.compare.main as     compare
from   vut.system.helper       import Interval

class Action:
    @typed(subject=Interval, nominal=Interval)
    def __init__(self, subject_line_n_begin, subject_line_n_end, nominal_line_n_begin, nominal_line_n_end):
        self.subject_line_n_begin = subject_line_n_begin
        self.subject_line_n_end   = subject_line_n_end
        self.nominal_line_n_begin = nominal_line_n_begin
        self.nominal_line_n_end   = nominal_line_n_end

    def nominal_size(self):
        return self.nominal_line_n_end - self.nominal_line_n_begin

    def subject_size(self):
        return self.subject_line_n_end - self.subject_line_n_begin

class ComparisonData:
    def __init__(self, subject_file_name, nominal_file_name):
        self.subject_file_name = subject_file_name
        self.subject_fh        = file_system.open(subject_file_name)
        self.nominal_file_name = nominal_file_name
        self.nominal_fh        = file_system.open(nominal_file_name)
        self.nominal_work_fh   = self.nominal_fh
        self.action_stack      = []
        self.chunk_pair_list   = None
        self.update()

    def update(self):
        self.chunk_pair_list = ChunkPairList(compare.associate(config, 
                                                               subject_fh, 
                                                               nominal_work_fh))

    @typed(action=Action)
    def move(self, subject_line_n_begin, subject_line_n_end, nominal_line_n_begin, nominal_line_n_end):
        """Moves lines from subject range to nominal range.
        """
        action = Action(subject_line_n_begin, subject_line_n_end, 
                        nominal_line_n_begin, nominal_line_n_end)
        self._do(action)
        self._stack_register(action)

    def delete(self, nominal_line_n_begin, nominal_line_n_end):
        """Deletes range from nominal file.
        """
        self.move(0, 0, nominal_line_n_begin, nominal_line_n_end)

    def undo(self):
        if self.stack_i > 0: self.stack_i -= 1
        self._stack_do(self.stack_i)

    def redo(self):
        if self.stack_i > 0 and self.stack_i < len(self.stack) - 1: self.stack_i += 1
        self._stack_do(self.stack_i)

    def _stack_register(self, action):
        if self.stack_i != len(self.stack): # If on 'undo' 
            del self.stack[stack_i:]        # remove previously done(s)
        self.stack.append(action)

    def _stack_do(self, i):
        assert self.stack_i > 0

        self.reset_nominal()
        for action in self.stack[:self.stack_i]:
            self._do(action)

    def _do(self, action)
        out_fh = file_system.clear(self.nominal_work_fh)

        chunk  = file_system.get_range(self.nominal_fh, 0, action.nominal_line_n_begin)
        out_fh.write(chunk)

        chunk = file_system.get_range(self.subject_fh, 
                                      action.subject_line_n_begin, 
                                      action.subject_line_n_end)
        out_fh.write(chunk)

        chunk = file_system.get_range(self.nominal_fh, nominal_line_n_end, -1)
        out_fh.write(chunk)

        file_system.copy(temporary, self.nominal_file_name)

