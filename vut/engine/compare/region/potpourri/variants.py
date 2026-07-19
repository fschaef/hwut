"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: The potpourri VARIANTS -- 'subset' and 'duplicates' flags.

    ##! potpourri subset       every SUBJECT line must have a distinct
                               equivalent partner in the nominal; surplus
                               nominal lines are legal (subject <= nominal).
    ##! potpourri duplicates   duplicate lines COLLAPSE before matching
                               (set semantics): repetitions of a line count
                               as one. Collapse is LITERAL (by the
                               whitespace-normalized 'uniform string'); two
                               different-but-tolerantly-equal lines do NOT
                               collapse. The collapsed duplicates appear
                               neutrally in the display.

Both flags combine. Both are NOMINAL-AUTHORITATIVE like every region
parameter (region/registry.py).
________________________________________________________________________________
"""


class VariantView:
    """A potpourri chunk reduced to its matching-relevant line lists --
    possibly deduplicated. Quacks like the chunk for 'pairing.do' and
    'best_match.do' (which access only the two partition lists).
    """
    __slots__ = ("analogy_line_list", "non_analogy_line_list", "dup_list")

    def __init__(self, chunk, duplicates_f):
        if not duplicates_f:
            self.analogy_line_list     = chunk.analogy_line_list
            self.non_analogy_line_list = chunk.non_analogy_line_list
            self.dup_list              = []
            return
        self.analogy_line_list,     dup_a = _dedup(chunk.analogy_line_list)
        self.non_analogy_line_list, dup_n = _dedup(chunk.non_analogy_line_list)
        self.dup_list = dup_a + dup_n


def _dedup(line_list):
    """RETURNS: [0] list of Line, first occurrence of every distinct line
                    (distinct by 'Line.uniform_string()').
                [1] list of Line, the collapsed later occurrences.
    """
    seen, kept, dup = {}, [], []
    for line in line_list:
        key = line.uniform_string()
        if key in seen:
            dup.append(line)
        else:
            seen[key] = line
            kept.append(line)
    return kept, dup
