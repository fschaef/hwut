#! /usr/bin/env python3
#
# @hwut {
#     title    = "Whitespace and encoding hygiene, per file -- and over this showcase's own tests"
#     choices {
#         good   { features = ["hygiene-report"]
#                  tolerance { constraints = ["findings == 0"] } }
#         broken { features = ["hygiene-report"]
#                  tolerance { constraints = ["findings > 0"] } }
#         self   { features = ["hygiene-self"]
#                  tolerance { constraints = ["findings == 0", "files >= 14"] } }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  the hygiene grid (file x rule W1..W6) of one file set: a fixture
         (good/broken), or this showcase's own test applications (self)
REQUIREMENT: the bytes of every text file are clean.

    W1  no tab in the indentation           (a Makefile's recipes need it)
    W2  no blank at the end of a line
    W3  lines end in LF, never CR LF
    W4  no UTF-8 byte order mark
    W5  non-ASCII only inside strings, comments and documentation -- a
        'gr\u00f6\u00dfe' as an identifier compiles with gcc 13 and breaks the next
        tool in the chain
    W6  the file ends with a newline

HOW: the files are read as BYTES; nothing is decoded on the way. The HYGIENE
GRID has one row per file and one column per rule: '.' clean, else the
number of lines that break the rule. Under it, for each broken (file, rule),
the first offending line made VISIBLE: [TAB], [CR], [BOM], a trailing blank
as [SP], a missing final newline as [no LF at EOF], a non-ASCII character
as [U+00F6]. An invisible fault becomes a
readable one.

CHOICES
    good     six files: C, Makefile (tabs, rightly), shell, JavaScript,
             Markdown with umlauts -- all clean.
    broken   filter.c saved by a Windows editor (CR LF) with two trailing
             blanks; units.c names a variable 'gr\u00f6\u00dfe'; app.js got a BOM and
             a tab; run.sh lost its final newline.
    self     the same rules over the test applications of this showcase
             area (conventions/*/TEST/test-*). That set GROWS with every
             example: the output prints counts only, and the laws say what
             must hold whatever the count -- no re-accept when an example
             is added. A finding would print its own line and fail.

HWUT CONCEPTS
    constraints  on 'self' they ARE the test: 'files >= 14' (the glob found
                 the area; a lower bound, because the set may grow) and
                 'findings == 0'. On good/broken the file set is fixed, so
                 its count is exact text ('files: 6'); 'findings == 0' states
                 the requirement for good, 'findings > 0' the reported
                 violation for broken.
    exact lines  grid and visible lines: the picture is the specification.

READING THE GOOD: in the grid, any cell other than '.'; under it, what the
bytes really were.
______________________________________________________________________________
"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RULE_LIST = ("W1", "W2", "W3", "W4", "W5", "W6")


def visible(raw):
    text = raw.decode("utf-8", "replace")
    stripped = text.rstrip(" \r\n")
    trail = text[len(stripped):].replace("\r", "").replace("\n", "")
    out = stripped.replace("\t", "[TAB]") + "[SP]" * len(trail) + ("[CR]" if b"\r" in raw else "")
    out = out.replace("\ufeff", "[BOM]")
    return "".join(c if ord(c) < 128 else "[U+%04X]" % ord(c) for c in out)


def code_part(line):
    """The line without string literals and comments (good enough for W5)."""
    line = re.sub(rb'"([^"\\]|\\.)*"|\'([^\'\\]|\\.)*\'|`[^`]*`', b'""', line)
    return re.split(rb"/\*|//|#(?!!)", line)[0]


def check(path, name):
    data = open(path, "rb").read()
    line_list = data.split(b"\n")
    hit_db = dict((r, []) for r in RULE_LIST)
    is_make, is_doc = os.path.basename(name) == "Makefile", name.endswith(".md")
    for i, raw in enumerate(line_list, 1):
        body = raw[3:] if i == 1 and raw.startswith(b"\xef\xbb\xbf") else raw
        if re.match(rb"^ *\t", body) and not is_make:
            hit_db["W1"].append((i, raw))
        if re.search(rb"[ \t]+\r?$", body):
            hit_db["W2"].append((i, raw))
        if body.endswith(b"\r"):
            hit_db["W3"].append((i, raw))
        if not is_doc and re.search(rb"[\x80-\xff]", code_part(body)):
            hit_db["W5"].append((i, raw))
    if data.startswith(b"\xef\xbb\xbf"):
        hit_db["W4"].append((1, line_list[0]))
    if data and not data.endswith(b"\n"):
        hit_db["W6"].append((len(line_list), line_list[-1]))
    return hit_db


def main(choice):
    if choice == "self":
        path_list = sorted(glob.glob(os.path.join(HERE, "..", "..", "*", "TEST", "test-*")))
    else:
        root = os.path.join(HERE, "..", choice)
        path_list = sorted(glob.glob(os.path.join(root, "**", "*"), recursive=True))
    path_list = [p for p in path_list if os.path.isfile(p)]
    base = os.path.join(HERE, "..", "..") if choice == "self" else os.path.join(HERE, "..", choice)
    findings, detail_list = 0, []
    if choice == "self":
        print("HYGIENE of this area's own test applications, conventions/*/TEST/test-*, rules W1..W6")
    else:
        print("HYGIENE GRID of '%s'   '.' clean, else the number of lines breaking the rule" % choice)
        print("  W1 tab indent  W2 trailing blank  W3 CR LF  W4 BOM  W5 non-ASCII in code  W6 final newline")
        print("  %-17s %s" % ("file", "  ".join(RULE_LIST)))
    for path in path_list:
        name = os.path.relpath(path, base)
        hit_db = check(path, name)
        cell_list = [str(len(hit_db[r])) if hit_db[r] else "." for r in RULE_LIST]
        findings += sum(1 for r in RULE_LIST if hit_db[r])
        if choice != "self":
            print("  %-17s %s" % (name, "   ".join(cell_list)))
        for r in RULE_LIST:
            if hit_db[r]:
                line, raw = hit_db[r][0]
                detail_list.append("%s %s:%d  %s%s" % (r, name, line, visible(raw),
                                                        "[no LF at EOF]" if r == "W6" else ""))
    print()
    if detail_list:
        print("THE FIRST OFFENDING LINE OF EACH, MADE VISIBLE")
        for d in detail_list:
            print("  " + d)
        print()
    if choice == "self":
        print("test applications ((files: %d))   law >= 14 (one per example)" % len(path_list))
        files = ""
    else:
        files = "files %d   " % len(path_list)
    print("%sfiles x rules broken ((findings: %d))   law == 0   %s"
          % (files, findings, "kept" if findings == 0 else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in ("good", "broken", "self"):
        print("choices: good, broken, self")
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
