#! /usr/bin/env python3
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
"""
rescue_goods -- the REFUSED block in, a 'git mv' list out.

    bin/hwut 2>&1 | python3 vut/adm/rescue_goods.py > moves.sh
    python3 vut/adm/rescue_goods.py < refused.txt > moves.sh

For every refused case (directory, test, choice) -- 'no nominal stands
in GOOD/' -- looks for a nominal of that name in EVERY OTHER 'GOOD/' of
the tree. Where one stands, prints

    git mv <where it is> <where it belongs>

and nothing else. You read the list, delete what you do not want, run
it. Cases with no nominal anywhere are listed as comments at the end.
Nothing is moved by this script.

Finds the tree the way 'TEST/config.py' does: walking up from its own
location to the directory named 'vut'.
"""

import os
import sys

_cur = os.path.abspath(os.path.dirname(__file__))
while os.path.basename(_cur) != "vut":
    _parent = os.path.dirname(_cur)
    if _parent == _cur:
        sys.exit("rescue_goods.py: no directory 'vut' above '%s'" % __file__)
    _cur = _parent
ROOT = _cur

BOOK_TUPLE = ("result_db.csv", "result_db.json", "test_ids.dat")


def refused_cases(text):
    """
    RETURN: list of (directory, test, choice), every case named in the
            REFUSED block of a 'hwut.run' report; choice None where
            the line carries none.
    """
    cases = []
    directory = None
    in_block = False
    for line in text.splitlines():
        if line.startswith("REFUSED"):
            in_block = True; continue
        if not in_block or line.startswith("==="):
            if in_block and line.startswith("==="): in_block = False
            continue
        if not line.strip() or line.startswith("---"): continue
        if not line.startswith(" "):
            directory = line.strip(); continue
        tokens = line.split()
        if not tokens or directory is None: continue
        test   = tokens[0]
        choice = tokens[1] if len(tokens) > 1 and tokens[1] != "no" else None
        cases.append((directory, test, choice))
    return cases


def good_file_db():
    """
    RETURN: dict, BASE NAME of a GOOD file -> list of its full paths,
            over the WHOLE tree. One walk. A base name standing in
            several GOOD/ directories lists them all.
    """
    db = {}
    for base, dirs, files in os.walk(ROOT):
        if ".git" in dirs: dirs.remove(".git")
        if os.path.basename(base) != "GOOD": continue
        for name in files:
            if name in BOOK_TUPLE: continue
            db.setdefault(name, []).append(os.path.join(base, name))
    return db


def missing_stems(test, choice):
    """
    RETURN: tuple of str, the base-name STEMS a nominal of (test,
            choice) would carry: 'test--choice.' and 'test.' -- the
            choice-less form every choice shares -- any suffix after.
    """
    return (test + ".",) if choice is None \
           else ("%s--%s." % (test, choice), test + ".")


def main():
    """RETURN: int, 0."""
    text  = sys.stdin.read()
    cases = refused_cases(text)
    found_db = good_file_db()                 # base name -> [path, ...]
    print("#! /bin/sh")
    print("# rescue_goods: one 'git mv' per nominal found elsewhere. Edit, then run")
    print("# from the directory holding 'vut/'. %d refused case(s) read." % len(cases))
    print("set -e")
    lost = []
    for directory, test, choice in cases:
        home  = os.path.abspath(os.path.join(ROOT, directory, "GOOD"))
        stems = missing_stems(test, choice)
        #  THE LOOKUP: every base name in the tree that a nominal of
        #  this case would carry, wherever it stands but here.
        hits = [(name, path)
                for name, path_list in found_db.items()
                if name.startswith(stems)
                for path in path_list
                if os.path.dirname(os.path.abspath(path)) != home]
        if not hits:
            lost.append((directory, test, choice)); continue
        label = test if choice is None else "%s %s" % (test, choice)
        print()
        print("# %s  <-  %s" % (directory, label))
        home_rel = os.path.relpath(home, os.path.dirname(ROOT))
        print("mkdir -p '%s'" % home_rel)      # 'git mv' wants it there
        for name, path in sorted(hits):
            src = os.path.relpath(path, os.path.dirname(ROOT))
            dst = os.path.join(home_rel, name)
            print("git mv '%s' \\\n       '%s'" % (src, dst))
    if lost:
        print()
        print("# NO NOMINAL ANYWHERE for these -- new tests, or truly gone:")
        for directory, test, choice in lost:
            print("#   %s  %s%s" % (directory, test,
                                    "" if choice is None else " " + choice))
    return 0


if __name__ == "__main__":
    sys.exit(main())
