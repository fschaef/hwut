#! /usr/bin/env python3
# @hwut {
#     title    = "Needleman-Wunsch: the reported score is the alignment's score, and it is optimal"
#     choices {
#         correct    { features = ["matrix-shown", "score-recomputes", "optimal"]
#                      tolerance { constraints = ["rescore_errors == 0", "suboptimal == 0", "invalid == 0"] } }
#         off-by-one { features = ["matrix-shown", "breach-shown"]
#                      tolerance { constraints = ["rescore_errors > 0", "invalid == 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the score matrix, alignment and score ../nw.c reports for sequence
         pairs, against a brute force over all alignments
HISTORY  Needleman and Wunsch published the first dynamic-programming method
for the global alignment of two protein sequences (J. Mol. Biol. 48:443,
1970): a matrix of best prefix scores, filled row by row, and a traceback
from the corner. With a linear gap cost g, the first row and column hold
i * g -- a prefix aligned against nothing is i gaps. Writing (i - 1) * g
there ("the first gap is free / is the opening") is a classic slip that
compiles, runs, and returns plausible alignments.

REQUIREMENT  For every pair: the alignment printed spells both sequences;
its score, recomputed column by column, equals the score reported; and no
alignment of the pair scores higher.

The unit is C, '../nw.c' (compiled per run into a temp directory), match +1,
mismatch -1, gap -1. The test prints
    1. the CLASSIC case GATTACA / GCATGCU: the DP matrix (B across, A down)
       and the alignment -- row A, '|' for each match, row B -- in
       '##! verbatim', since the columns ARE the alignment;
    2. a SWEEP of 200 random pairs of length 1..6 over ACGT
       (deterministic_random, seed as a comment), under TWO scoring
       schemes: (+1, -1, -1) and (+1, -1, -2). In the first, a mismatch
       costs what a gap costs, so code that confuses the two parameters
       scores every alignment right; the second tells them apart. Each
       alignment is checked
       to spell its sequences ('((invalid: N))'), rescored from its
       columns ('((rescore_errors: N))'), and compared with a BRUTE FORCE
       over all alignments of the pair ('((suboptimal: N))' -- the DP score
       differs from the true optimum). The first two failing pairs of each scheme are
       drawn with both scores.

CHOICES
    correct     law: all three counts 0.
    off-by-one  compiled with -DOFF_BY_ONE: boundary (i - 1) * g. The
                classic case still scores 0 (its alignment uses no gap at
                the ends) -- the matrix shows the shifted border, the score
                does not. The sweep finds the pairs whose best alignment
                starts with a gap: the reported score is one higher than
                the alignment's own. Law 'rescore_errors > 0'.

HWUT CONCEPTS  verbatim for column-sensitive pictures (a blank row of bars
would be a blank line, and blank lines never count: the bars row ends
with its match count); constraints carry the
laws; the brute force is an independent oracle inside the test.

READING THE GOOD  In the matrix the first row and column must read 0 -1 -2 ...;
the test re-prints the unit's matrix and marks with '!' every cell that does
not follow from its neighbours by the recurrence (the border: i * gap), and
counts them. Under the drawn alignment the reported score is set against
its rescoring. In the sweep, 'reported' and 'rescored' must agree; the three
counts end with their law and verdict.
______________________________________________________________________________
"""
import itertools
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
from hwut.test_writing_support.python.deterministic_random import DeterministicStream

HERE = os.path.dirname(os.path.abspath(__file__))
MATCH, MISMATCH, GAP = 1, -1, -1                 # the classic case
SCHEME_LIST = [(1, -1, -1), (1, -1, -2)]          # the sweep: mismatch == gap, and mismatch != gap
SEED = 19700343
CHOICE_DB = {"correct": [], "off-by-one": ["-DOFF_BY_ONE"]}


def plural(n, one, many):
    return "%d %s" % (n, one if n == 1 else many)


def column_score(x, y, scheme):
    match, mismatch, gap = scheme
    if x == "-" or y == "-":
        return gap
    return match if x == y else mismatch


def brute_best(a, b, scheme):
    """Best score over ALL alignments, by enumeration (no DP)."""
    gap = scheme[2]
    if not a:
        return len(b) * gap
    if not b:
        return len(a) * gap
    return max(brute_best(a[1:], b[1:], scheme) + column_score(a[0], b[0], scheme),
               brute_best(a[1:], b, scheme) + gap, brute_best(a, b[1:], scheme) + gap)


def run_nw(binary, pairs, scheme, show=False):
    r = subprocess.run([binary] + [str(v) for v in scheme] + (["-m"] if show else []),
                       input="".join("%s %s\n" % p for p in pairs), capture_output=True, text=True, check=True)
    return r.stdout.splitlines()


def main(choice):
    build = tempfile.mkdtemp()
    try:
        binary = os.path.join(build, "nw")
        subprocess.run(["gcc", "-Wall", "-Werror"] + CHOICE_DB[choice] + ["-o", binary, os.path.join(HERE, "..", "nw.c")],
                       check=True)
        print("unit: nw.c %s; match %+d, mismatch %+d, gap %+d" % (" ".join(CHOICE_DB[choice]) or "(as written)", MATCH, MISMATCH, GAP))
        print()
        print("##! verbatim")
        lines = run_nw(binary, [("GATTACA", "GCATGCU")], (MATCH, MISMATCH, GAP), show=True)
        matrix_lines = [l for l in lines[:-4] if l.strip()]
        cols = matrix_lines[0].split()
        grid = [(l.split()[0], [int(v) for v in l.split()[1:]]) for l in matrix_lines[1:]]
        h = [row for _, row in grid]
        def expected(i, j):
            """The recurrence, applied to the unit's own neighbouring cells."""
            if i == 0 or j == 0:
                return (i + j) * GAP
            s = MATCH if grid[i][0] == cols[j] else MISMATCH
            return max(h[i - 1][j - 1] + s, h[i - 1][j] + GAP, h[i][j - 1] + GAP)
        wrong_cells = 0
        print("    " + "".join("%5s" % c for c in cols))
        for i, (letter, row) in enumerate(grid):
            marks = ["!" if v != expected(i, j) else " " for j, v in enumerate(row)]
            wrong_cells += marks.count("!")
            print(("    %s" % letter + "".join("%4d%s" % (v, m) for v, m in zip(row, marks))).rstrip())
        print("    ('!' a cell that breaks the recurrence, given its neighbours: %d)" % wrong_cells)
        print()
        a_al, bars, b_al = lines[-3], lines[-2], lines[-1]
        reported = int(lines[-4].split()[1])
        rescored = sum(column_score(x, y, (MATCH, MISMATCH, GAP)) for x, y in zip(a_al, b_al))
        print("    %s   rescored %d %s reported" % (lines[-4], rescored, "=" if rescored == reported else "!="))
        print("    A  " + a_al)
        print("       %s   %s" % (bars, plural(bars.count("|"), "match", "matches")))
        print("    B  " + b_al)
        print("####")
        print()

        rng = DeterministicStream(SEED)
        pairs = [tuple("".join(rng.select("ACGT") for _ in range(rng.next_int(1, 6))) for _ in "ab")
                 for _ in range(200)]
        invalid = rescore_errors = suboptimal = 0
        print("## seed %d" % SEED)
        print("sweep: 200 random pairs, length 1..6 over ACGT, against a brute force over all alignments,")
        print("       under each scheme (match, mismatch, gap): %s" % "  ".join("(%+d, %+d, %+d)" % sc for sc in SCHEME_LIST))
        print("##! verbatim")
        for scheme in SCHEME_LIST:
            out = run_nw(binary, pairs, scheme)
            shown = s_invalid = s_rescore = s_subopt = 0
            for k, (a, b) in enumerate(pairs):
                score, ra, bars, rb = out[4 * k: 4 * k + 4]
                reported = int(score.split()[1])
                rescored = sum(column_score(x, y, scheme) for x, y in zip(ra, rb))
                best = brute_best(a, b, scheme)
                bad_spell = ra.replace("-", "") != a or rb.replace("-", "") != b or len(ra) != len(rb)
                s_invalid += bad_spell
                s_rescore += rescored != reported
                s_subopt += reported != best
                if (bad_spell or rescored != reported or reported != best) and shown < 2:
                    shown += 1
                    print("  %-6s / %-6s  reported %d  rescored %d  brute force %d" % (a, b, reported, rescored, best))
                    print("      A  " + ra)
                    print("         %s   %s" % (bars, plural(bars.count("|"), "match", "matches")))
                    print("      B  " + rb)
            print("  scheme (%+d, %+d, %+d): invalid %d, rescore errors %d, suboptimal %d%s"
                  % (scheme + (s_invalid, s_rescore, s_subopt,
                               "   (failing pairs above, at most two)" if shown else "")))
            invalid += s_invalid
            rescore_errors += s_rescore
            suboptimal += s_subopt
        print("####")
        law = lambda n: "law == 0   %s" % ("kept" if n == 0 else "BROKEN")
        print("alignments not spelling their sequences ((invalid: %d))   %s" % (invalid, law(invalid)))
        print("reported score != rescored ((rescore_errors: %d))   %s" % (rescore_errors, law(rescore_errors)))
        print("reported score != brute-force optimum ((suboptimal: %d))   %s" % (suboptimal, law(suboptimal)))
    finally:
        shutil.rmtree(build)


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
