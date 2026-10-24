#! /usr/bin/env python3
#
# @hwut {
#     title    = "C: every value of an enum is handled in every switch over it"
#     features = ["switch-complete", "gcc-agrees"]
#     choices {
#         good   { tolerance { constraints = ["holes == 0", "holes == gcc"] } }
#         broken { tolerance { constraints = ["holes > 0",  "holes == gcc"] } }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  which values of motor_state_t each switch over it handles, in one C
         code base (good/broken)
REQUIREMENT: every switch over 'motor_state_t' names every value of the enum
in a 'case'. A 'default:' does not count: it is exactly the place where a
newly added value disappears without a word ("?" on the display, -1 in the
telemetry) -- the review question after every new enum value.

HOW: two independent witnesses.
  1. The test reads the C sources itself: the enum from the header, every
     'switch' with its 'case' labels and its enclosing function. It prints
     the COVERAGE MATRIX: enum values down, switch sites across.
        x  handled by a case     -  NOT handled     default: yes/-
  2. gcc compiles each file with -Wswitch-enum (-fsyntax-only, LC_ALL=C).
     Its warnings are reduced to 'file:line misses VALUE' -- the column and
     the wording of a gcc version are left out.
  The two must agree: 'holes == gcc' is a law over two bound values.

CHOICES
    good     five values, three switches, every cell 'x'.
    broken   MOTOR_PAUSED was added to the enum and handled in motor.c only;
             display.c hides it behind a new 'default:'; telemetry.c also
             lost its MOTOR_FAULT case.

HWUT CONCEPTS
    constraints  'holes' (the matrix) and 'gcc' (the compiler) are bound
                 separately; "holes == gcc" holds them against each other
                 on every run -- if the parser and the compiler ever
                 disagree, the run is red, whatever the GOOD file says.
                 'holes == 0' is the requirement of good; 'holes > 0' the
                 reported violation of broken. The switch count is exact
                 text ('switches: 3'): a switch the parser loses changes it.
    exact lines  the matrix: one cell per (value, switch).

READING THE GOOD: any '-' in the matrix is a hole; the gcc lines below must
name the same holes.
______________________________________________________________________________
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def enum_values(text, name):
    body = re.search(r"typedef\s+enum\s*\{([^}]*)\}\s*%s\s*;" % name, text).group(1)
    return [v.split("=")[0].strip() for v in body.split(",") if v.strip()]


def switches(path):
    """YIELDS: (function, line, case_set, has_default) for every switch."""
    text = open(path).read()
    for m in re.finditer(r"\bswitch\s*\(", text):
        start = text.index("{", m.end())
        depth, i = 1, start + 1
        while depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        body = text[start:i]
        before = text[:m.start()]
        function = re.findall(r"^\w[\w\s\*]*?\b(\w+)\s*\([^;]*?\)\s*\{", before, re.M)[-1]
        yield (function, before.count("\n") + 1,
               set(re.findall(r"\bcase\s+(\w+)\s*:", body)),
               re.search(r"\bdefault\s*:", body) is not None)


def main(choice):
    src = os.path.join(HERE, "..", choice)
    value_list = enum_values(open(os.path.join(src, "motor.h")).read(), "motor_state_t")
    site_list = []
    for name in sorted(f for f in os.listdir(src) if f.endswith(".c")):
        for function, line, case_set, has_default in switches(os.path.join(src, name)):
            if case_set & set(value_list):
                site_list.append(("%s:%d" % (name, line), function, case_set, has_default))

    print("enum motor_state_t (motor.h of '%s'): %d values" % (choice, len(value_list)))
    print()
    print("COVERAGE MATRIX   x handled by a case   - NOT handled")
    width = 16
    print("%-16s" % "switch at" + "".join("%-*s" % (width, s[0]) for s in site_list).rstrip())
    print("%-16s" % "in function" + "".join("%-*s" % (width, s[1]) for s in site_list).rstrip())
    holes = 0
    for value in value_list:
        cell_list = []
        for site in site_list:
            if value in site[2]:
                cell_list.append("x")
            else:
                cell_list.append("-"); holes += 1
        print("%-16s" % value + "".join("%-*s" % (width, c) for c in cell_list).rstrip())
    print("%-16s" % "default:" + "".join("%-*s" % (width, "yes" if s[3] else "-")
                                         for s in site_list).rstrip())
    print()
    print("SECOND WITNESS  gcc -Wswitch-enum -fsyntax-only, per file")
    gcc_n = 0
    for name in sorted(f for f in os.listdir(src) if f.endswith(".c")):
        text = subprocess.run(["gcc", "-Wswitch-enum", "-fsyntax-only", name], cwd=src,
                              capture_output=True, text=True,
                              env=dict(os.environ, LC_ALL="C")).stderr
        for file, line, value in re.findall(r"^(\S+?):(\d+):\d+: warning: enumeration value "
                                            r"'(\w+)' not handled in switch", text, re.M):
            print("  %s:%s misses %s" % (file, line, value))
            gcc_n += 1
    if gcc_n == 0:
        print("  (no warning)")
    print()
    print("switches: %d   holes in the matrix ((holes: %d))   law == 0   %s"
          % (len(site_list), holes, "kept" if holes == 0 else "BROKEN"))
    print("gcc warnings ((gcc: %d))   law == holes   %s"
          % (gcc_n, "agree: two witnesses, one count" if gcc_n == holes else "DISAGREE"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in ("good", "broken"):
        print("choices: good, broken")
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
