#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: One-shot migration of the LEGACY '||||' potpourri framing to the
         shebang region syntax:

             ||||                    ##! potpourri
             ...          ==>        ...
             ||||                    ####

USAGE:

    migrate_region_syntax.py <file> [<file> ...]      rewrite files in place
    migrate_region_syntax.py --check <file> ...       report only, no writes

The legacy '||||' was a TOGGLE: within one file the 1st, 3rd, 5th, ...
occurrence opens a region, the 2nd, 4th, 6th, ... closes it. The rewrite
alternates accordingly. A file ending with an OPEN region (odd count) is
reported -- the legacy engine silently flushed such regions; the shebang
syntax requires an explicit '####' (append one, or re-record the file).

Indentation of the delimiter line is preserved.

This is a CLEAN BREAK: after migration, '||||' has no meaning to the
engine and is treated as ordinary content.
________________________________________________________________________________
"""
import sys


def is_legacy_delimiter(line, marker="||||"):
    """RETURNS: True, if 'line' is a legacy potpourri delimiter: stripped, a
                      run of '|' of at least the marker's length.
                False, else.
    """
    stripped = line.strip()
    return stripped.startswith(marker) and len(set(stripped)) == 1


def migrate_text(text):
    """RETURNS: [0] str, the text with legacy delimiters rewritten.
                [1] int, the number of rewritten delimiter lines.
                [2] bool, True if the text ends with an OPEN region.
    """
    out     = []
    n       = 0
    open_f  = False
    for line in text.splitlines(keepends=True):
        if is_legacy_delimiter(line):
            indent  = line[:len(line) - len(line.lstrip())]
            newline = "\n" if line.endswith("\n") else ""
            out.append(indent + ("##! potpourri" if not open_f else "####")
                       + newline)
            open_f  = not open_f
            n      += 1
        else:
            out.append(line)
    return "".join(out), n, open_f


def main(argv):
    check_only = "--check" in argv
    file_list  = [a for a in argv[1:] if not a.startswith("--")]
    if not file_list:
        print(__doc__)
        return 1

    for path in file_list:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        migrated, n, open_f = migrate_text(text)
        state = "OPEN-REGION-AT-EOF" if open_f else "ok"
        if n == 0:
            print("%-60s nothing to do" % path)
            continue
        print("%-60s %3d delimiter(s) rewritten [%s]" % (path, n, state))
        if not check_only:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(migrated)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
