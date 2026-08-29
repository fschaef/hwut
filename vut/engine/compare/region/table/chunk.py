"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: 'table' region -- every line is a row of columns.

    ##! table key=0 ignore=2 numeric={3:0.05} [unordered] [sep={;}]
    alpha   42   2026-07-18T09:31:02   0.981
    ####

Columns are 0-based. Cells split on whitespace by default; 'sep={<string>}'
splits on a literal separator instead (cells stripped). Comparison
criteria, ALL nominal-authoritative:

    key=<col>          rows are matched by equality of this column's cell
                       (implies unordered matching). Duplicate keys in the
                       NOMINAL are a broken specification (loud).
    ignore=<cols>      comma-separated column indices excluded from
                       comparison (timestamps, PIDs, ...).
    numeric={c:t,...}  per-column RELATIVE numeric tolerance:
                       |s - n| <= t * |n|  (t=0: exact; n=0 forces s=0).
    unordered          rows form a bag: a bijective matching of
                       rule-equal rows must exist (bipartite matching).
    (neither)          rows compare positionally; counts must agree.

MALFORMED DATA is asymmetric, as everywhere ('nominal is authoritative'):
nominal defects -- inconsistent column count, referenced column out of
range, unparsable numeric cell, duplicate key -- are broken specifications
-> loud RegionSyntaxError. The same defects on the subject side are test
failures -> not equivalent, shown red.

The NOMINAL's first row defines the table's column count.
________________________________________________________________________________
"""
from   vut.engine.compare.contract.enums               import E_Chunk
from   vut.engine.compare.reading.input_chunk   import (
                                                 AssociationRelatedInputChunk,
                                                 EquivalenceRelatedInputChunk)
import vut.engine.compare.region.table.equivalence   as equivalence_table
import vut.engine.compare.region.table.associate     as association_table


def convert_ignore(raw):
    """RETURNS: frozenset of int, the column indices of 'ignore=0,2,5'."""
    return frozenset(int(field) for field in str(raw).split(","))


def convert_numeric(raw):
    """RETURNS: dict int -> float, the per-column tolerances of
                'numeric={3:0.05, 1:0.01}'.
    """
    result = {}
    for entry in str(raw).split(","):
        col, _, tol = entry.partition(":")
        if not _:
            raise ValueError(entry)
        result[int(col.strip())] = float(tol.strip())
    return result


class InputChunkTable(AssociationRelatedInputChunk,
                      EquivalenceRelatedInputChunk):
    def __init__(self, start_line_n, end_line_n, line_list, config,
                 params=None):
        super().__init__(E_Chunk.TABLE, start_line_n, end_line_n,
                         line_list, config)
        params = params or {}
        self.key_column   = params.get("key")
        self.ignore_set   = params.get("ignore") or frozenset()
        self.numeric_db   = params.get("numeric") or {}
        self.unordered_f  = bool(params.get("unordered")) \
                            or self.key_column is not None
        self.separator    = params.get("sep")

        # Parse rows: [(Line, tuple-of-cells)] -- structural validity
        # (column count) is judged against the NOMINAL's width in the face.
        self.row_list = []
        for line in line_list:
            raw = line._string.rstrip("\n")
            if self.separator is not None:
                cells = tuple(c.strip() for c in raw.split(self.separator))
            else:
                cells = tuple(raw.split())
            self.row_list.append((line, cells))

    def width(self):
        """RETURNS: int, the column count of the first row. None, if the
        region is empty.
        """
        if not self.row_list:
            return None
        return len(self.row_list[0][1])

    def _is_equivalent_to_nominal(self, nominal, analogy_db):
        return equivalence_table.do(self, nominal, analogy_db)

    def _associate_with_nominal(self, nominal, analogy_db):
        return association_table.do(self, nominal, analogy_db)
