#! /usr/bin/env python3
#
# @hwut {
#     title    = "Comments: only the permitted forms -- owned TODOs, no block comments in C++, no dead code"
#     features = ["todo-owner", "cpp-line-comments", "no-dead-code"]
#     choices {
#         good   { tolerance { constraints = ["violations == 0"] } }
#         broken { tolerance { constraints = ["violations > 0"] } }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  the comments of one C/C++ source tree (good/broken), each with its
         form and its verdict under the comment rules
REQUIREMENT (the comment rules of a C/C++ firmware code base)

    C1  a work note is 'TODO(owner): text' -- with an owner. FIXME, XXX,
        HACK and an anonymous 'TODO:' are not allowed: nobody owns them,
        nobody closes them.
    C2  C++ files (.cpp, .hpp) use '//' only; '/* */' is the form of C.
    C3  no commented-out code: a comment whose text ends in ';', '{' or '}'
        -- after a trailing note of its own ('// x;  // why') is cut off --
        is code somebody did not dare to delete. Version control keeps it.

HOW: a small lexer walks each file (code, string, char literal, '//'
comment, '/* */' comment), so that "http://x" or a "/* */" inside a string
is not taken for a comment. The output is
    1. the COMMENT INVENTORY: every comment of every file, with its line,
       its form and the rule it breaks ('ok' where it breaks none);
    2. the RULE MATRIX: files x rules, the number of breaches per cell;
    3. two counts.

CHOICES
    good     four files, 17 comments, all permitted (the inventory is the
             proof that the lexer saw them all, strings included).
    broken   an anonymous TODO and a block of dead code in pid.c, a FIXME,
             a block comment and a dead call with a note behind it
             ('// pwm_.set(0.5f);  // bench value') in motor.cpp, a
             commented-out 'case' in can.cpp.

HWUT CONCEPTS
    constraints  'violations == 0' for good -- the requirement;
                 'violations > 0' for broken -- the breaches are reported,
                 the matrix says where. The comment count is exact text
                 ('comments: 17'): a comment the lexer stops seeing
                 changes it.
    exact lines  inventory and matrix. Comment text is cut at 40 characters
                 for the page; the cut is part of the picture.

READING THE GOOD: the verdict column of the inventory, then the matrix --
every cell '.' in the good choice.
______________________________________________________________________________
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RULE_LIST = ("C1", "C2", "C3")


def comments(text):
    """YIELDS: (line, form, body) for every comment, strings skipped."""
    i, line, n = 0, 1, len(text)
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1; i += 1
        elif c in "\"'":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            line += text.count("\n", i, j); i = j + 1
        elif text.startswith("//", i):
            j = text.find("\n", i); j = n if j < 0 else j
            yield line, "//", text[i + 2:j].strip(); i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2); j = n if j < 0 else j
            yield line, "/*", " ".join(text[i + 2:j].split()); line += text.count("\n", i, j); i = j + 2
        else:
            i += 1


def verdict(path, form, body):
    rule_list = []
    if re.search(r"\b(FIXME|XXX|HACK)\b", body) or re.search(r"\bTODO\b(?!\(\w+\):)", body):
        rule_list.append("C1")
    if form == "/*" and path.endswith((".cpp", ".hpp")):
        rule_list.append("C2")
    if re.search(r"[;{}]$", re.sub(r"\s*(//.*|/\*.*\*/)$", "", body)):
        rule_list.append("C3")
    return rule_list


def main(choice):
    src = os.path.join(HERE, "..", choice, "src")
    matrix_db, comment_n = {}, 0
    print("rules: C1 TODO(owner) only   C2 no /* */ in C++   C3 no commented-out code")
    print()
    print("COMMENT INVENTORY of '%s/src'" % choice)
    print("line  form  text (first 40 characters; under C3 the last 40)   verdict")
    for name in sorted(os.listdir(src)):
        print("%s" % name)
        matrix_db[name] = dict((r, 0) for r in RULE_LIST)
        for line, form, body in comments(open(os.path.join(src, name)).read()):
            comment_n += 1
            rule_list = verdict(name, form, body)
            for r in rule_list:
                matrix_db[name][r] += 1
            if len(body) <= 40:
                text = body
            elif "C3" in rule_list:          # C3 reads the END of the text: show it
                text = "..." + body[-37:]
            else:
                text = body[:37] + "..."
            print("  %3d  %-4s  %-42s  %s" % (line, form, text, " ".join(rule_list) or "ok"))
    print()
    print("RULE MATRIX  breaches per file and rule ('.' = none)")
    print(("  %-12s %s" % ("file", "  ".join("%-3s" % r for r in RULE_LIST))).rstrip())
    total = 0
    for name in sorted(matrix_db):
        cell_list = [str(matrix_db[name][r]) if matrix_db[name][r] else "." for r in RULE_LIST]
        total += sum(matrix_db[name].values())
        print(("  %-12s %s" % (name, "  ".join("%-3s" % c for c in cell_list))).rstrip())
    print()
    print("comments: %d   ((violations: %d))   law == 0   %s" % (comment_n, total, "kept" if total == 0 else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in ("good", "broken"):
        print("choices: good, broken")
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
