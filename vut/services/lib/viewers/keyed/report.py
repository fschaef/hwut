"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE TOLERANCE REPORT (services E-91) -- what compare ALLOWED and
         what it BOUND, told by line: the screen's 't' window.

DESCRIPTION
       Built from the pairs compare delivered, in delivery order, one
       record per pair holding its two cell lists and its line numbers.
       Three sections, each empty section named as such:

         ANALOGIES    line pair by line pair, what OUTPUT's analogy stands
                      for beside what GOOD's does, and where the binding
                      ORIGINATES (compare's own origin pair); a mismatch
                      is marked
         PATTERNS     every equivalence pattern that MATCHED, OUTPUT's
                      text beside GOOD's
         CONSTRAINTS  every constraint binding that FAILED

       Pure: no screen, tested on made-up cells.
______________________________________________________________________________
"""
from collections import namedtuple

Pair = namedtuple("Pair", "line_n_s line_n_n cells_s cells_n")


def _kind(cell):
    return cell.tolerance_id.name


def _ok(cell):
    relation = getattr(cell, "relation_id", None)
    return relation is None or relation.name.startswith("OK_")


def _partner(cell_n, cells_s):
    ref = getattr(cell_n, "subject_ref_i", None)
    if ref is None or ref >= len(cells_s): return None
    return cells_s[ref]


def _origin(cell):
    pair = getattr(cell, "analogy_origin_line_number_pair", None)
    if pair is None: return ""
    s = getattr(pair, "line_n_in_subject", None)
    n = getattr(pair, "line_n_in_nominal", None)
    if s is None and isinstance(pair, tuple) and len(pair) == 2: s, n = pair
    return "" if s is None else " (bound at %s/%s)" % (s, n)


def lines_of(pair_list):
    """RETURN: list[str], the report's lines for 'pair_list'
               ([Pair], delivery order). One scheme throughout:
               '<subject line>:<nominal line>   <information>'."""
    analogy, pattern, constraint = [], [], []
    for pair in pair_list:
        where = "%s:%s" % (pair.line_n_s, pair.line_n_n)
        for cell_n in pair.cells_n:
            kind = _kind(cell_n)
            if kind not in ("ANALOGY", "EQUIVALENCE_PATTERN",
                            "CONSTRAINT_BINDING"): continue
            cell_s = _partner(cell_n, pair.cells_s)
            text_s = getattr(cell_s, "subject", None) if cell_s else None
            text_n = getattr(cell_n, "nominal", "")
            ok_f   = _ok(cell_n) and (cell_s is None or _ok(cell_s))
            if kind == "ANALOGY":
                mark = "  " if ok_f else "! "
                analogy.append("%s%-9s %r ~ %r%s"
                               % (mark, where, text_s, text_n, _origin(cell_n)))
            elif kind == "EQUIVALENCE_PATTERN":
                #  ONLY WHEN IT MATCHED AND THE LEXEMES DIFFER (E-92): a
                #  pattern that matched identical text says nothing.
                if ok_f and text_s != text_n:
                    pattern.append("  %-9s %r matches %r" % (where, text_s, text_n))
            elif not ok_f:
                constraint.append("! %-9s %r failed against %r"
                                  % (where, text_s, text_n))
    def section(title, body):
        return [title] + (body or ["  (none)"])
    return (section("ANALOGIES", analogy)
            + [""] + section("EQUIVALENCE PATTERNS", pattern)
            + [""] + section("CONSTRAINTS", constraint))


def line_pair_at(line_list, row):
    """RETURN: (int, int), the subject and nominal line numbers the
               report line at 'row' names; None where it names none
               (a heading, a blank, '(none)')."""
    if row is None or not 0 <= row < len(line_list): return None
    word = line_list[row].strip().lstrip("! ").split()
    if not word or ":" not in word[0]: return None
    s, _, n = word[0].partition(":")
    try:    return int(s), int(n)
    except ValueError: return None
