#! /usr/bin/env python3
# @hwut {
#     title    = "Frame header check: the field matrix, described in space.conf, judged against the spec"
#     features = ["first-rule", "space-from-file"]
#     choices {
#         release-1.0 { features = ["first-rule", "space-from-file", "every-rule"]
#                       tolerance { constraints = ["unreached == 0", "mismatches == 0"] } }
#         release-0.9 { features = ["first-rule", "space-from-file", "every-rule", "wrong-named"]
#                       tolerance { constraints = ["unreached == 0", "mismatches > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the verdict of hdr_check (../hdr_check*.c) on every point of the
         header field space of space.conf, against the spec
REQUIREMENT  hdr_check reports the FIRST broken rule of a received header,
             in this order: fewer than 4 bytes received (T), version != 1
             (V), header length < 1 word (H), total length < header length
             (L), fewer bytes received than the total length (T), type not
             in 1..3 (Y); else ok (.).

The unit is C: '../hdr_check.c' (release 1.0) and '../hdr_check_v0.c'
(release 0.9, which checks the total length only against the minimal 4-byte
header). '../drive.c' builds each frame in a heap buffer of exactly the
received size and prints the code letter.

THE TESTED SPACE IS A FILE: '../space.conf', read with hwut's own HOCON
reader (hwut_hocon.parse), so a reviewer -- or the protocol owner -- edits
the space without reading Python. It names five dimensions, how the two
lengths derive from a point, and a 'where' condition. Every field carries
its borders from both sides (version 0|1|2, type 0|1 .. 3|4). The lengths
are RELATIVE coordinates (total = 4*max(1,words) + d1, received = total +
d2): in absolute bytes the borders would move with 'words', and the product
would miss them; relative to the field they are checked against, d1 in
{-1, 0, 1} and d2 in {-1, 0} sit on the length borders for every header
length. The anchor is at least 4 bytes, so 'words = 0' comes with a frame
long enough to reach the rule H. space_iterator.do() makes the product; it
has no pruning, so the test filters by 'where' and SAYS how many points it
pruned.

A SPACE IS ONLY A SPEC IF EVERY RULE IS IN IT. The test counts, per rule,
the points at which the SPEC (not the unit) says that rule fires, prints
the counts and binds the rules that no point reaches as '((unreached: 0))'.
Law of both choices: 'unreached == 0' -- shrink space.conf so that a rule
falls out of reach, and the verdict fails before any unit is judged.

release-1.0  every point gets the letter the spec gives it:
             law 'mismatches == 0'.
release-0.9  a header with options (words = 2, 15) and a total length one
             byte short of it passes as ok or as truncated -- the frame's
             options would be read past its end. The cells carry 'unit/spec',
             the list names the rows; law 'mismatches > 0'.

HOW TO READ THE GOOD   One row per (version, words, d1), one column per
(d2, type); the cell is the unit's letter, '-' a pruned point, 'X/Y' the
unit's letter X where the spec says Y; one '!!' line per matrix row that
holds such cells.
Read the 'L' diagonal: it must appear in every d1 = -1 row with version 1
and words >= 1; 'H' stands in the version-1, words-0 rows. The matrix is
'##! verbatim' (columns carry meaning); the rest is exact, except the two
bindings, judged by the laws above.
______________________________________________________________________________
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
import hwut.test_writing_support.python.space_iterator as space_iterator
import hwut.test_writing_support.python.hwut_hocon as hwut_hocon

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.join(HERE, "..")
CHOICE_DB = {"release-1.0": "hdr_check.c", "release-0.9": "hdr_check_v0.c"}


def plain(node):
    """hwut_hocon hands back an annotated tree; the test wants values."""
    if isinstance(node, hwut_hocon.ObjectNode):
        return dict((e.key, plain(e.node)) for e in node.entry_list)
    if isinstance(node, hwut_hocon.ListNode):
        return [plain(n) for n in node.item_list]
    return node.value


def read_space(path):
    with open(path) as fh:
        lines = [hwut_hocon.SourceLine(text.rstrip("\n"), i + 1, 0) for i, text in enumerate(fh)]
    document, faults = hwut_hocon.parse(lines, "space.conf")
    for fault in faults:
        print("!! %s" % fault)
    space = document.get("space")
    dims = [(e.key, plain(e.node), e.key_position) for e in space.node.entry_list]
    return dims, plain(document.get("derive").node), plain(document.get("where").node)


# The spec's rules in their order: (name, letter). Two rules share 'T'.
RULES = [("T received < 4", "T"), ("V version", "V"), ("H header length", "H"),
         ("L total length", "L"), ("T received < total", "T"), ("Y type", "Y"), (". ok", ".")]


def spec_rule(version, words, total, received, type_):
    """Index into RULES of the first rule the spec says fires."""
    if received < 4:          return 0
    if version != 1:          return 1
    if words < 1:             return 2
    if total < 4 * words:     return 3
    if received < total:      return 4
    if not 1 <= type_ <= 3:   return 5
    return 6


def spec(*frame):
    return RULES[spec_rule(*frame)][1]


def run_unit(source, frames):
    with tempfile.TemporaryDirectory() as build:
        exe = os.path.join(build, "drive")
        subprocess.check_call(["gcc", "-O1", "-g", "-fsanitize=address", "-Wall", "-Werror",
                               "-I", UNIT, "-o", exe, os.path.join(UNIT, "drive.c"),
                               os.path.join(UNIT, source)])
        text = "".join("%d %d %d %d %d\n" % f for f in frames)
        out = subprocess.run([exe], input=text, capture_output=True, text=True, check=True).stdout
    return out.split()


def main(choice):
    dims, derive, where = read_space(os.path.join(UNIT, "space.conf"))
    names = [name for name, _, _ in dims]
    print("space.conf, as read by hwut_hocon:")
    for name, values, position in dims:
        print("    %-21s %-16s (space.conf:%s)" % (name, values, position))
    for name, expression in derive.items():
        print("    %-21s = %s" % (name, expression))
    print("    where %s" % where)
    print()

    frames, kept = [], {}
    for point in space_iterator.do([values for _, values, _ in dims]):
        p = dict(zip(names, point))
        total = eval(derive["total"], {"max": max}, p)
        received = eval(derive["received"], {}, dict(p, total=total))
        if not eval(where, {}, {"total": total, "received": received}):
            continue
        frame = (p["version"], p["words"], total, received, p["type"])
        kept[point] = len(frames)
        frames.append(frame)
    all_n = 1
    for _, values, _ in dims:
        all_n *= len(values)
    letters = run_unit(CHOICE_DB[choice], frames)
    print("unit: ../%s   space: %d points, %d pruned by 'where', %d run"
          % (CHOICE_DB[choice], all_n, all_n - len(frames), len(frames)))
    print("letters: . ok  V version  H header length  L total length  T truncated  Y type")
    print("cells:   the unit's letter; 'T/L' the unit says T where the spec says L; '-' pruned")
    print()

    reached = [0] * len(RULES)
    for frame in frames:
        reached[spec_rule(*frame)] += 1
    print("points per rule, as the spec assigns them:")
    for (name, _), n in zip(RULES, reached):
        print("    %-20s %3d%s" % (name, n, "" if n else "   !! unreachable in this space"))
    print("rules no point reaches ((unreached: %d))   law == 0   %s"
          % (reached.count(0), "kept" if not reached.count(0) else "BROKEN"))
    print()

    (_, vs, _), (_, ws, _), (_, d1s, _), (_, d2s, _), (_, ts, _) = dims
    columns = [(d2, t) for d2 in d2s for t in ts]
    wrong = []
    print("##! verbatim")
    print("                      d2=received-total: " + "".join("%5s" % ("%+d" % d2) for d2, _ in columns))
    print("  ver words d1=total-4*words   type:     " + "".join("%5d" % t for _, t in columns))
    wrong_rows = []
    for v in vs:
        for w in ws:
            for d1 in d1s:
                row, row_wrong = [], []
                for d2, t in columns:
                    point = (v, w, d1, d2, t)
                    if point not in kept:
                        row.append("-")
                        continue
                    frame = frames[kept[point]]
                    got, want = letters[kept[point]], spec(*frame)
                    if got != want:
                        wrong.append((frame, got, want))
                        row_wrong.append((got, want))
                        row.append(got + "/" + want)
                    else:
                        row.append(got)
                if row_wrong:
                    wrong_rows.append((v, w, d1, row_wrong))
                print("  %3d %5d %8s                     " % (v, w, "%+d" % d1)
                      + "".join("%5s" % c for c in row))
    print("####")
    print()
    for v, w, d1, row_wrong in wrong_rows:
        print("!! version %d, %2d words, total %+d against the header: unit %s, spec %s (%d cells)"
              % (v, w, d1, " ".join(g for g, _ in row_wrong),
                 "/".join(sorted(set(s for _, s in row_wrong))), len(row_wrong)))
    print("points that differ from the spec ((mismatches: %d)) of %d   law == 0   %s"
          % (len(wrong), len(frames), "kept" if not wrong else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
