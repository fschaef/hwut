#! /usr/bin/env python3
#
# @hwut {
#     title   = "Word wrap: fill and justify to 40 columns"
#     choices {
#         awk-justify { features = ["width", "whole-words", "justified"]
#                       tolerance { constraints = ["breaches == 0"] } }
#         fmt         { features = ["violation-shown"]
#                       tolerance { constraints = ["breaches > 0"] } }
#         fold        { features = ["violation-shown"]
#                       tolerance { constraints = ["breaches > 0"] } }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  the lines one wrapping tool (../justify.awk, fmt, fold) makes of
         ../text.txt at 40 columns
REQUIREMENT. Text wrapped to a width of 40 columns:
    R1  no line is longer than 40 columns;
    R2  no word is cut: the words out are the words in, in order;
    R3  every line but the last of a paragraph is flush on both edges.

CHOICES -- one text (../text.txt), three tools:
    awk-justify  ../justify.awk, the tool under test. All three hold
                 (law: breaches == 0).
    fmt          coreutils 'fmt -w 40': R1 and R2 hold, R3 does not; the
                 picture marks each RAGGED line.
    fold         coreutils 'fold -w 40': cuts words in the middle; the
                 picture marks each CUT line, the check counts lost words.
                 For both: law 'breaches > 0'.

HWUT CONCEPT. '##! verbatim' around the page: no whitespace folding, so
two blanks are not one blank -- which is the whole point of justification
(by default hwut treats a run of blanks as one). Lines are drawn between
'|' so a trailing blank and an empty separator line stay visible and count
(blank lines never count in hwut). Nothing varies between runs: no
tolerance is declared, and none is needed. The number of broken rules is
a constraint binding '((breaches: n))', judged by the choice's law.

READING THE GOOD. Hold the ruler against the right '|': every line not
marked 'last' must reach column 40. Other marks: RAGGED (not flush), CUT
(a word split), LOST (words run together or missing), LONG (past 40). The
table under the page repeats the three rules as counts with 'holds' /
'BROKEN'.
______________________________________________________________________________
"""
import os
import subprocess
import sys

HERE   = os.path.dirname(os.path.abspath(__file__))
TEXT   = os.path.join(HERE, "..", "text.txt")
WIDTH  = 40
TOOL_DB = {
    "awk-justify": ["awk", "-v", "W=%d" % WIDTH, "-f", os.path.join(HERE, "..", "justify.awk"), TEXT],
    "fmt":         ["fmt", "-w", str(WIDTH), TEXT],
    "fold":        ["fold", "-w", str(WIDTH), TEXT],
}


def judge(lines, in_word_list):
    """RETURN: (mark_list, cut_n): one mark per output line, and the number of
    input words that did not come out whole -- cut apart, run together with
    a neighbour, or lost. Walks the input words along the output tokens."""
    mark_list = [""] * len(lines)
    cut_n     = 0
    k, pending = 0, ""             # index of input word, prefix seen so far
    for i, line in enumerate(lines):
        for token in line.split():
            want = in_word_list[k] if k < len(in_word_list) else ""
            if pending + token == want:
                k, pending = k + 1, ""
            elif want.startswith(pending + token):
                if not pending:
                    cut_n += 1
                pending += token
                mark_list[i] = "CUT"
            else:                  # run together ('tocheck') or lost
                mark_list[i] = "LOST"
                rest, j = pending + token, k
                while j < len(in_word_list) and in_word_list[j] and rest.startswith(in_word_list[j]):
                    rest, j = rest[len(in_word_list[j]):], j + 1
                cut_n += max(j - k, 1)
                k, pending = (j if not rest and j > k else k + 1), ""
    last_set = {i for i, line in enumerate(lines)
                if line.strip() and (i + 1 == len(lines) or not lines[i + 1].strip())}
    for i, line in enumerate(lines):
        if not line.strip():
            mark_list[i] = "(gap)"
            continue
        if len(line) > WIDTH:
            mark_list[i] = "LONG"
        elif mark_list[i]:
            pass
        elif i in last_set:
            mark_list[i] = "last"
        elif len(line.rstrip()) != WIDTH or line[0] == " ":
            mark_list[i] = "RAGGED"
    return mark_list, cut_n


def main(choice):
    with open(TEXT) as fh:
        in_word_list = fh.read().split()
    out = subprocess.run(TOOL_DB[choice], capture_output=True, text=True, check=True).stdout
    lines = out.rstrip("\n").split("\n")
    mark_list, cut_n = judge(lines, in_word_list)
    out_word_n = sum(len(l.split()) for l in lines)

    print("tool:  %s" % " ".join(os.path.basename(a) for a in TOOL_DB[choice]))
    print("##! verbatim")
    print(" " + "".join("%10d" % n for n in range(1, WIDTH // 10 + 1)))
    print(" " + "1234567890" * (WIDTH // 10))
    for line, mark in zip(lines, mark_list):
        print("|%-*s| %s" % (WIDTH, line, mark or "ok"))
    print("####")

    longest  = max(len(l) for l in lines)
    full_n   = sum(1 for m in mark_list if m == "")
    should_n = sum(1 for m in mark_list if m in ("", "RAGGED"))
    ok = lambda flag: "holds" if flag else "BROKEN"
    print("rule                      measured            verdict")
    print("R1 longest line           %2d <= %d            %s" % (longest, WIDTH, ok(longest <= WIDTH)))
    print("R2 words not whole        %2d of %d            %s" % (cut_n, len(in_word_list), ok(cut_n == 0)))
    print("R3 flush lines            %2d of %-2d            %s" % (full_n, should_n, ok(full_n == should_n)))
    print("   (words in %d, tokens out %d)" % (len(in_word_list), out_word_n))
    breaches = (longest > WIDTH) + (cut_n != 0) + (full_n != should_n)
    print("rules broken ((breaches: %d))   law == 0   %s" % (breaches, ok(breaches == 0)))


if len(sys.argv) < 2 or sys.argv[1] not in TOOL_DB:
    print("choices: %s" % ", ".join(TOOL_DB))
    sys.exit(1)
main(sys.argv[1])
print("<hwut-end>")
