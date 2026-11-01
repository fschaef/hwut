#! /usr/bin/env python3
# @hwut {
#     title    = "Conway's Game of Life: glider, blinker and block behave as B3/S23 demands"
#     choices {
#         classic       { features = ["glider-moves", "oscillator-still-life", "rule-pinned"]
#                         tolerance { constraints = ["breaches == 0"] } }
#         torus         { features = ["torus-returns", "rule-pinned"]
#                         tolerance { constraints = ["breaches == 0"] } }
#         rule-mistyped { features = ["breach-shown"]
#                         tolerance { constraints = ["breaches > 0"] } }
#         wrap-bug      { features = ["breach-shown"]
#                         tolerance { constraints = ["breaches > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the generations of glider, blinker and block under ../life.awk with
         one grid script, and the B3/S23 laws they keep or break
HISTORY  John Conway's "Life" reached the public through Martin Gardner's
Mathematical Games column, "The fantastic combinations of John Conway's
new solitaire game 'life'", Scientific American 223 (October 1970): a dead
cell with exactly 3 live neighbours is born, a live cell with 2 or 3 stays,
all others die -- B3/S23 (older programs wrote it '23/3', survival first).
Its best-known shapes: the GLIDER, which repeats its shape every 4
generations one cell further diagonally; the BLINKER, period 2; the BLOCK,
which never changes.

REQUIREMENT  Under B3/S23 the glider is, after 4 generations, its own
shape moved by (+1, +1); the blinker returns after 2 generations and is
different after 1; the block stays; on an 8 x 8 torus the glider is back
home after 32 generations, with 5 cells in every generation.

The unit is awk: '../life.awk' (the rule from '-v rule=', 'Bxx/Sxx' or the
older 'xx/yy' survival/birth notation) with a TOPOLOGY file that defines
the neighbour lookup: '../grid_bounded.awk' (outside the board is dead),
'../grid_torus.awk' (wraps), and the broken '../grid_torus_v1.awk'
('(x - 1) % W' -- awk's % keeps the sign, so the left and top edges do not
wrap). The test prints the generations SIDE BY SIDE in '##! verbatim'
(the columns are the board), then the RULE AS THE UNIT APPLIES IT: all
512 3x3 neighbourhoods, laid out as patches 4 cells apart on one board and
run one generation, folded into a born/stays row per neighbour count and
compared cell by cell with B3/S23 written in the test. Glider, blinker and
block never show a cell 6 or 8 neighbours, so they cannot tell B3/S23 from
HighLife (B36/S23) or S238; the sweep can. Last a LAW TABLE, each law
'kept' or 'BROKEN', and the number of broken ones, '((breaches: N))', with
its law and verdict.

CHOICES
    classic        8 x 8 bounded board, rule B3/S23: glider gens 0..4,
                   blinker 0..2, block 0..1. Law 'breaches == 0'.
    torus          8 x 8 torus, rule '23/3' (old notation): the glider at
                   gens 0, 8, 16, 24, 32 -- it crosses both edges and is
                   home again. Law 'breaches == 0'.
    rule-mistyped  BROKEN: the classic run with the rule copied as 'B23/S3'
                   (the old '23/3' read in the wrong order). The glider
                   falls apart, the rule rows show born at 2, stays only
                   at 3; law 'breaches > 0'.
    wrap-bug       BROKEN: the torus run with grid_torus_v1.awk: in the
                   bottom-right corner the glider's cells see the top-left
                   ones, but those do not see them back; it freezes into a
                   block of 4 cells. The rule sweep stays clean -- the
                   fault is the topology, not the rule. Law 'breaches > 0'.

HWUT CONCEPTS  verbatim (whitespace folding would merge board columns);
the law table judges, the picture shows; dead cells are '.', never blanks.

READING THE GOOD  The last glider board must equal the first, shifted one
down and one right (classic) or not shifted at all (torus); the two rule
rows must equal the 'B3/S23 requires' row.
______________________________________________________________________________
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.join(HERE, "..")
CHOICE_DB = {"classic": ("B3/S23", "grid_bounded.awk"), "torus": ("23/3", "grid_torus.awk"),
             "rule-mistyped": ("B23/S3", "grid_bounded.awk"), "wrap-bug": ("23/3", "grid_torus_v1.awk")}


def life(rule, grid, start, gens):
    start = start if os.path.isabs(start) else os.path.join(UNIT, start)
    out = subprocess.run(["awk", "-v", "rule=" + rule, "-v", "gens=%d" % gens, "-f", os.path.join(UNIT, grid),
                          "-f", os.path.join(UNIT, "life.awk"), start],
                         capture_output=True, text=True, check=True).stdout.split("gen ")[1:]
    return [b.splitlines()[1:] for b in out]


def side_by_side(boards, labels):
    print("##! verbatim")
    width = max(len(boards[0][0]), max(len(l) for l in labels))
    print("  " + "   ".join(l.ljust(width) for l in labels).rstrip())
    for row in range(len(boards[0])):
        print("  " + "   ".join(b[row].ljust(width) for b in boards).rstrip())
    print("####")


def shifted(board, dy, dx):
    h, w = len(board), len(board[0])
    return ["".join(board[y - dy][x - dx] if 0 <= y - dy < h and 0 <= x - dx < w else "." for x in range(w))
            for y in range(h)]


def neighbourhood_sweep(rule, grid):
    """All 512 3x3 neighbourhoods, one generation, against B3/S23 written
    here (born with 3, stays with 2 or 3). The patches stand 4 cells apart
    on one 128 x 64 board, separated by dead rows and columns, so each
    centre sees exactly its own patch -- whatever the board's edges do.
    RETURN: (table, errors); table[(alive, n)] = set of next states seen."""
    rows = [["."] * 128 for _ in range(64)]
    for k in range(512):
        y0, x0 = 4 * (k // 32) + 1, 4 * (k % 32) + 1
        for j in range(9):
            if k >> j & 1:
                rows[y0 + j // 3][x0 + j % 3] = "O"
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "patches.txt")
        open(path, "w").write("".join("".join(r) + "\n" for r in rows))
        after = life(rule, grid, path, 1)[1]
    finally:
        shutil.rmtree(tmp)
    table, errors = {}, 0
    for k in range(512):
        alive = k >> 4 & 1
        n = bin(k).count("1") - alive
        nxt = after[4 * (k // 32) + 2][4 * (k % 32) + 2] == "O"
        table.setdefault((alive, n), set()).add(nxt)
        errors += nxt != (n == 3 or (alive and n == 2))
    return table, errors


def main(choice):
    rule, grid = CHOICE_DB[choice]
    print("unit: life.awk -v rule=%s + %s" % (rule, grid))
    print()
    law_list = []                  # (law, kept)
    if choice in ("classic", "rule-mistyped"):
        g = life(rule, grid, "glider.txt", 4)
        print("GLIDER")
        side_by_side(g, ["gen %d" % k for k in range(5)])
        law_list.append(("glider: gen 4 == gen 0 moved by (+1, +1)", g[4] == shifted(g[0], 1, 1)))
        b = life(rule, grid, "blinker.txt", 2)
        print("BLINKER")
        side_by_side(b, ["gen %d" % k for k in range(3)])
        law_list.append(("blinker: gen 2 == gen 0, gen 1 != gen 0", b[2] == b[0] and b[1] != b[0]))
        k = life(rule, grid, "block.txt", 1)
        print("BLOCK")
        side_by_side(k, ["gen %d" % i for i in range(2)])
        law_list.append(("block: gen 1 == gen 0", k[1] == k[0]))
    else:
        g = life(rule, grid, "glider.txt", 32)
        print("GLIDER on the torus, every 8th generation")
        side_by_side(g[::8], ["gen %d" % k for k in range(0, 33, 8)])
        population = [sum(r.count("O") for r in b) for b in g]
        print("cells per generation: %s" % " ".join(map(str, population)))
        law_list.append(("glider: gen 32 == gen 0 (4 x 8 generations around the torus)", g[32] == g[0]))
        law_list.append(("glider: 5 cells in every generation", all(p == 5 for p in population)))
    table, rule_errors = neighbourhood_sweep(rule, grid)
    print()
    print("RULE AS THE UNIT APPLIES IT  all 512 3x3 neighbourhoods, one generation ('?' = depends on more than the count)")
    print("##! verbatim")
    print("  live neighbours      " + " ".join(str(n) for n in range(9)))
    for alive, label in ((0, "dead cell -> born   "), (1, "live cell -> stays  ")):
        cells = []
        for n in range(9):
            seen = table[(alive, n)]
            cells.append("?" if len(seen) > 1 else ("O" if True in seen else "."))
        print("  " + label + " " + " ".join(cells))
    print("  B3/S23 requires      born: . . . O . . . . .   stays: . . O O . . . . .")
    print("####")
    law_list.append(("rule: all 512 neighbourhoods follow B3/S23 (%d differ)" % rule_errors, rule_errors == 0))
    print()
    print("LAWS")
    for law, kept in law_list:
        print("  %-62s %s" % (law, "kept" if kept else "BROKEN"))
    broken_n = sum(not k for _, k in law_list)
    print("laws broken ((breaches: %d)) of %d   law == 0   %s"
          % (broken_n, len(law_list), "kept" if broken_n == 0 else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
