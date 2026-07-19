"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: The shared decision core of the 'table' region -- BOTH faces
derive their judgment from the classification computed here (THE LAW by
construction).
________________________________________________________________________________
"""
from vut.engine.compare.region.registry import RegionSyntaxError
import vut.engine.compare.region.potpourri.solver.maximum_bipartite_matching \
    as solver_max_bpm


class Judgment:
    """Complete classification of one subject/nominal table pair.

    .verdict           bool -- THE equivalence verdict.
    .subject_class     aligned with subject.row_list:
                       ('ok', nominal_index) or ('bad', reason)
    .nominal_uncovered set of nominal row indices without counterpart
    """
    def __init__(self, subject, nominal):
        # NOMINAL IS AUTHORITATIVE: all criteria from the nominal chunk.
        self.key_column  = nominal.key_column
        self.ignore_set  = nominal.ignore_set
        self.numeric_db  = nominal.numeric_db
        self.unordered_f = nominal.unordered_f
        self._validate_nominal(nominal)

        self.verdict           = True
        self.subject_class     = []
        self.nominal_uncovered = set()

        width  = nominal.width()
        s_rows = [cells if (width is None or len(cells) == width) else None
                  for _, cells in subject.row_list]
        n_rows = [cells for _, cells in nominal.row_list]

        if width is None:
            # empty nominal table: every subject row is surplus.
            for _ in s_rows:
                self.subject_class.append(("bad", "surplus"))
                self.verdict = False
            return

        for cells in s_rows:
            self.subject_class.append(None if cells is not None
                                      else ("bad", "width"))
        if any(c is not None for c in self.subject_class):
            self.verdict = False

        if self.key_column is not None:
            self._match_by_key(s_rows, n_rows)
        elif self.unordered_f:
            self._match_unordered(s_rows, n_rows)
        else:
            self._match_ordered(s_rows, n_rows)

    # -- nominal-side specification checks (loud) --------------------------
    def _validate_nominal(self, nominal):
        # Constraint bindings need line sequentiality; 'unordered' and keyed
        # tables are order-free by construction ('engine/constraints.py').
        # (Tables never tolerance-lex their cells, so in an ORDERED table a
        # binding is plain text -- allowed, but inert.)
        if self.unordered_f or self.key_column is not None:
            for line, _ in nominal.row_list:
                if line.lexer.has_constraint_binding(line._string):
                    raise RegionSyntaxError(line.line_n,
                        "constraint binding in an order-free scope (table "
                        "%s) -- constraints require line sequentiality"
                        % ("unordered" if self.unordered_f else "key"))
        width = nominal.width()
        for line, cells in nominal.row_list:
            if len(cells) != width:
                raise RegionSyntaxError(line.line_n,
                    "table NOMINAL row has %d columns where the first row "
                    "has %d" % (len(cells), width))
        if width is not None:
            referenced = set(self.ignore_set) | set(self.numeric_db)
            if self.key_column is not None:
                referenced.add(self.key_column)
            for col in sorted(referenced):
                if not (0 <= col < width):
                    raise RegionSyntaxError(nominal.start_line_n,
                        "table parameter references column %d; the table "
                        "has columns 0..%d" % (col, width - 1))
        for line, cells in nominal.row_list:
            for col, tol in self.numeric_db.items():
                try:
                    float(cells[col])
                except ValueError:
                    raise RegionSyntaxError(line.line_n,
                        "table NOMINAL cell in numeric column %d is not a "
                        "number: %r" % (col, cells[col]))
        if self.key_column is not None:
            seen = {}
            for line, cells in nominal.row_list:
                key = cells[self.key_column]
                if key in seen:
                    raise RegionSyntaxError(line.line_n,
                        "table NOMINAL key %r appears twice (also line %d)"
                        % (key, seen[key]))
                seen[key] = line.line_n

    # -- cell / row comparison ---------------------------------------------
    def _cell_equal(self, col, s_cell, n_cell):
        if col in self.ignore_set:
            return True
        if col in self.numeric_db:
            try:
                s_value = float(s_cell)
            except ValueError:
                return False
            n_value = float(n_cell)               # nominal validated above
            return abs(s_value - n_value) <= self.numeric_db[col] * abs(n_value)
        return s_cell == n_cell

    def _row_equal(self, s_cells, n_cells):
        return all(self._cell_equal(col, s, n)
                   for col, (s, n) in enumerate(zip(s_cells, n_cells)))

    # -- matching modes ------------------------------------------------------
    def _match_ordered(self, s_rows, n_rows):
        for i, cells in enumerate(s_rows):
            if self.subject_class[i] is not None:
                continue
            if i >= len(n_rows):
                self.subject_class[i] = ("bad", "surplus")
                self.verdict = False
            elif self._row_equal(cells, n_rows[i]):
                self.subject_class[i] = ("ok", i)
            else:
                self.subject_class[i] = ("bad", "differs")
                self.verdict = False
        for ni in range(len(s_rows), len(n_rows)):
            self.nominal_uncovered.add(ni)
            self.verdict = False

    def _match_unordered(self, s_rows, n_rows):
        adjacency = {
            si: {ni for ni, n_cells in enumerate(n_rows)
                 if self._row_equal(s_cells, n_cells)}
            for si, s_cells in enumerate(s_rows) if s_cells is not None
            if self.subject_class[si] is None
        }
        pairing = dict(solver_max_bpm.do(adjacency))
        for si, entry in enumerate(self.subject_class):
            if entry is not None:
                continue
            if si in pairing:
                self.subject_class[si] = ("ok", pairing[si])
            else:
                self.subject_class[si] = ("bad", "unmatched")
                self.verdict = False
        matched = set(pairing.values())
        for ni in range(len(n_rows)):
            if ni not in matched:
                self.nominal_uncovered.add(ni)
                self.verdict = False

    def _match_by_key(self, s_rows, n_rows):
        n_by_key = {cells[self.key_column]: ni
                    for ni, cells in enumerate(n_rows)}
        seen_keys = {}
        for si, cells in enumerate(s_rows):
            if self.subject_class[si] is not None:
                continue
            key = cells[self.key_column]
            if key in seen_keys:
                self.subject_class[si] = ("bad", "duplicate-key")
                self.verdict = False
                continue
            seen_keys[key] = si
            ni = n_by_key.get(key)
            if ni is None:
                self.subject_class[si] = ("bad", "unknown-key")
                self.verdict = False
            elif self._row_equal(cells, n_rows[ni]):
                self.subject_class[si] = ("ok", ni)
            else:
                self.subject_class[si] = ("bad", "differs")
                self.verdict = False
        covered = {n_by_key[k] for k in seen_keys if k in n_by_key}
        for ni in range(len(n_rows)):
            if ni not in covered:
                self.nominal_uncovered.add(ni)
                self.verdict = False
