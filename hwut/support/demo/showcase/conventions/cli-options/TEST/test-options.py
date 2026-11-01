#! /usr/bin/env python3
#
# @hwut {
#     title    = "CLI: the options of --help, README and man page match what the parser accepts"
#     features = ["same-options", "same-defaults"]
#     choices {
#         good   { tolerance { constraints = ["findings == 0"] } }
#         broken { tolerance { constraints = ["findings > 0"] } }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  the option matrix of one copy of benchctl (good/broken): each option
         and default in code, --help, README and man page
REQUIREMENT: a command line tool is described in four places, and they must
agree on the set of options and on every default:

    code     the 'case' patterns of the option parser in 'benchctl' (every
             alternative: '-x|--long)', '--long)', '-x)') and the values
             the script assigns before it parses     (the truth)
    --help   what './benchctl --help' prints            (run, not read)
    README   the options table of README.md
    man      the '.BR' entries of benchctl.1 and their 'Default:' lines

HOW: the test reads the script, RUNS it with --help, reads the Markdown
table and the troff source. The OPTION MATRIX has one row per option (its
long name; a short-only option by its short name) and one column per place. A cell holds the default the place states, 'yes'
where it names the option without a default, '-' where it does not name it
at all. A default that differs from the code's carries '!'.

CHOICES
    good     seven options (--retries has no short form), four places, all
             in agreement.
    broken   --help forgot --timeout; the README still documents the
             removed --verbose where --log-level should stand, and claims
             baud 9600; the man page lost --dry-run.

HWUT CONCEPTS
    constraints  'findings == 0' for good -- the requirement; 'findings > 0'
                 for broken -- the violation is reported, the FINDING lines
                 say which. The option count is exact text ('options: 7'):
                 an option the parser reader stops seeing changes it.
    exact lines  the matrix. Defaults are compared as text (/dev/ttyUSB0,
                 115200): a tolerance on numbers would make '115200' and
                 '115201' equal, which no operator would.

READING THE GOOD: every row reads the same across; '-' and '!' are findings.
______________________________________________________________________________
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def from_code(text):
    """RETURN: option -> default ('yes' for a flag). An option is a case
    pattern made of '-x' / '--long' alternatives; its name is the long one."""
    head, _, parser = text.partition("\nwhile ")
    init_db = dict(re.findall(r"(?:^|;)\s*([A-Z_]+)=([^;\s]+)", head, re.M))
    option_db = {}
    for pattern, body in re.findall(r"^\s*(-[\w-]+(?:\|-[\w-]+)*)\)\s*(.*)$", parser, re.M):
        name = max(pattern.split("|"), key=len)
        m = re.match(r"([A-Z_]+)=\$2", body)
        option_db[name] = init_db.get(m.group(1), "?") if m else "yes"
    return option_db


def from_help(text):
    option_db = {}
    for line in text.splitlines():
        m = re.match(r"^\s*(?:-\w,\s*)?(--[\w-]+|-\w\b)", line)
        if m:
            d = re.search(r"\(default: ([^)]+)\)", line)
            option_db[m.group(1)] = d.group(1) if d else "yes"
    return option_db


def from_readme(text):
    option_db = {}
    for m in re.finditer(r"^\|\s*(?:`-\w`,\s*)?`(--[\w-]+|-\w)`\s*\|\s*`?([^|`]*?)`?\s*\|", text, re.M):
        option_db[m.group(1)] = m.group(2) or "yes"
    return option_db


def from_man(text):
    option_db, line_list = {}, text.splitlines()
    for i, line in enumerate(line_list):
        m = re.match(r'^\.BR (?:\\-\w ", " )?((?:\\-|\w)+)', line)
        if m:
            option = m.group(1).replace("\\-", "-")
            d = re.search(r"Default: (\S+?)\.?$", line_list[i + 1]) if i + 1 < len(line_list) else None
            option_db[option] = d.group(1) if d else "yes"
    return option_db


def main(choice):
    root = os.path.join(HERE, "..", choice)
    help_text = subprocess.run([os.path.join(root, "benchctl"), "--help"],
                               capture_output=True, text=True).stdout
    place_list = [("code",   from_code(open(os.path.join(root, "benchctl")).read())),
                  ("--help", from_help(help_text)),
                  ("README", from_readme(open(os.path.join(root, "README.md")).read())),
                  ("man",    from_man(open(os.path.join(root, "benchctl.1")).read()))]
    code_db = place_list[0][1]
    option_list = sorted(set().union(*[db for _, db in place_list]))

    print("benchctl of '%s' -- four places that describe its options" % choice)
    print()
    print("OPTION MATRIX   cell: the default stated   yes: named, no default   -: not named")
    print("                !: a finding -- differs from the code, missing where the code has it,")
    print("                   or named though the parser does not accept it")
    print("  %-13s" % "option" + "".join("%-15s" % p for p, _ in place_list).rstrip())
    finding_list = []
    for option in option_list:
        cell_list = []
        for place, db in place_list:
            if option not in db:
                cell = "-"
                if option in code_db:
                    cell = "- !"
                    finding_list.append("%-6s does not name %s" % (place, option))
            elif option in code_db and db[option] != code_db[option]:
                cell = db[option] + " !"
                finding_list.append("%-6s says %s %s, the code %s" % (place, option, db[option], code_db[option]))
            else:
                cell = db[option]
                if option not in code_db:
                    cell = db[option] + " !"
                    finding_list.append("%-6s names %s, which the parser does not accept" % (place, option))
            cell_list.append(cell)
        print("  %-13s" % option + "".join("%-15s" % c for c in cell_list).rstrip())
    print()
    for f in sorted(set(finding_list)):
        print("FINDING " + f)
    n = len(set(finding_list))
    print("options: %d   ((findings: %d))   law == 0   %s" % (len(code_db), n, "kept" if n == 0 else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in ("good", "broken"):
        print("choices: good, broken")
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
