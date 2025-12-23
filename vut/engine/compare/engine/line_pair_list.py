"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: A list of 'LinePair' objects.
________________________________________________________________________________
"""
from   vut.engine.compare.engine.line_pair         import LinePair
from   vut.engine.compare.engine.analogy_db        import AnalogyDb
from   vut.engine.compare.edit_operations.edit     import E_EditId, Edit
from   vut.engine.compare.tolerance.pattern_finder import E_ToleranceId
from   vut.external.quex.typed                     import typed

class LinePairList(list):
    def __init__(self, iterable=None):
        if iterable is not None: 
            list.__init__(self, iterable)
            assert all(isinstance(x, LinePair) for x in self)

    @staticmethod
    def from_subject_only(line_list):
        return LinePairList(LinePair(x, None, []) for x in line_list)

    @staticmethod
    def from_nominal_only(line_list):
        return LinePairList(LinePair(None, x, []) for x in line_list)

    def append(self, lp):
        assert isinstance(lp, LinePair)
        list.append(self, lp)

    def extend(self, lp_iterable):
        end_i = len(self)
        list.extend(self, lp_iterable)
        assert all(isinstance(x, LinePair) for x in self[end_i:])

    def __setitem__(self, lp):
        assert isinstance(lp, LinePair)
        list.__setitem__(self, lp)

    def enumerate(self, begin, end):
        if begin >= 0 or end < len(self) and begin < end: 
            yield from enumerate(self[begin:end], start=begin)
                
    def sort(self, sort_by_subject_line_n_f):
        if sort_by_subject_line_n_f:
            key = lambda x: (1, x.nominal.line_n) if x.subject is None else (0, x.subject.line_n)
        else:
            key = lambda x: (1, x.subject.line_n) if x.nominal is None else (0, x.nominal.line_n)
        list.sort(self, key=key)
        return self

    def find_line_association(self, subject_line_n, nominal_line_n):
        for i, lina in enumerate(self):
            if lina.subject is None or lina.subject.line_n != subject_line_n: 
                continue
            elif lina.nominal is None or lina.nominal.line_n != nominal_line_n:
                # 'subject.line_n' is only associated with one 'nominal.line_n'
                return None # => (subject_line_n, nominal_line_n) cannot be found
            else:
                return i
        return None

    def analogy_errors(lina_list, errors_f=True):
        """RETURNS: [0] list of indices of LinePair objects
                        in the same order as in 'lina_list'
                    [1] set of (subject, nominal)

        If 'error_f' == False, than no entries are made in 'lina_db'.
                     
        Find LinePair-s with analogy errors.  Using a dictionary prevents 
        duplicate entries.
        """
        result              = []
        subject_nominal_set = set()
        for i, lina in enumerate(lina_list):
            linas_subject_nominal_set = lina.analogy_errors()
            if not linas_subject_nominal_set: 
                continue
            if errors_f:
                result.append(i)
            subject_nominal_set.update(linas_subject_nominal_set)

        return result, subject_nominal_set

    def max_line_n(self):
        def _get(line, max_line_n):
            if line and line.line_n is not None and line.line_n > max_line_n: 
                return line.line_n
            else:
                return max_line_n
        result = 0
        for lina in self:
            result = _get(lina.subject, result)
            result = _get(lina.nominal, result)
        return result

    def indices_plain(self):
        return range(len(self))

    def indices_error(self):
        """RETURNS: list of LinePair that contain some type of errors.
        """
        return [lina_i
                for lina_i, lina in enumerate(self)
                if not lina.is_good_or_tolerated()]

    def indices_error_and_tolerated(self):
        """RETURNS: list of LinePair that contain some type of errors.
        """
        return [lina_i
                for lina_i, lina in enumerate(self)
                if not lina.is_good()]

    @typed(analogy_db=AnalogyDb, subject_nominal_set=set)
    def indices_analogy_definitions(self, analogy_db, subject_nominal_set):
        """RETURNS: [0] list of indices of LinePair objects containing analogy
                        definitions relevant to 'subject_nominal_set'.

        Searches for LinePair-s where either the 'subject' or 'nominal' from
        the 'subject_nominal_set' occurrs.
        """
        def _enter(result, subject_line_n, nominal_line_n):
            lina_index = self.find_line_association(subject_line_n, nominal_line_n)
            if lina_index is None: 
                return
            result.append(lina_index)

        result = []
        # For those analogies where errors occur, search for the definition of the
        # original analogy.
        for subject, nominal in subject_nominal_set:
            s_line_n, n_line_n, associated = analogy_db.first_association_subject(subject)
            if associated is not None:
                _enter(result, s_line_n, n_line_n)
            s_line_n, n_line_n, associated = analogy_db.first_association_nominal(nominal)
            if associated is not None:
                _enter(result, s_line_n, n_line_n)

        return result

    def __pretty__(self):
        return "LinePairList", list(self)


