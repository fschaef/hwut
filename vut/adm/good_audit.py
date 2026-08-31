"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE SHAPE OF EVERY DIFFERENCE IN A TREE, in one reading.

For each 'GOOD/<member>.txt' that has a candidate from the last run in
'TMP/store/<member>.stdout', the two texts are read and one shape is
reported:

    SAME       the texts are equal
    GREW       every recorded line stands, in order; lines stand
               between or around them
    SHRANK     every line that stands was recorded, in order; lines
               the GOOD holds are gone
    DIVERGED   neither: a recorded line changed or moved
    UNREADABLE a file could not be read

The shapes are 'hwut.run''s own ('operations/result.py'); this reads a
whole tree at once, from what a run already left, and runs nothing.

EVERY SHAPE BUT 'SAME' IS A FAILURE. The shape says WHERE TO LOOK, not
who is wrong. A GOOD blessed under a framework that swallowed output
GREW; so did a filter that stopped filtering. One is stale ground, the
other is the defect a golden master exists to catch, and they wear the
same shape. Nothing here decides which, and nothing here blesses:
'hwut.accept' is the one door a nominal changes through.

    adm/good_audit.py [<directory>] [--verbose]

EXIT: 0 where every member stands as recorded, 1 where any does not,
      2 where the directory does not exist.
______________________________________________________________________________
"""
import os
import sys


def subsequence_f(small, large):
    """
    RETURN: bool, True where every line of 'small' appears in 'large'
            in the same order -- 'large' may hold lines between and
            around them, and holds no line of 'small' out of turn.
    """
    it = iter(large)
    return all(line in it for line in small)


def shape_of(good_path, candidate_path):
    """
    RETURN: str, one of 'SAME', 'GREW', 'SHRANK', 'DIVERGED',
            'UNREADABLE' -- the shape of the difference between the
            GOOD and the candidate, in the framework's own words.
    """
    try:
        with open(good_path, encoding="utf-8", errors="replace") as fh:
            old = fh.read().splitlines()
        with open(candidate_path, encoding="utf-8", errors="replace") as fh:
            new = fh.read().splitlines()
    except OSError:
        return "UNREADABLE"

    if old == new:                       return "SAME"
    if len(new) > len(old) and subsequence_f(old, new): return "GREW"
    if len(old) > len(new) and subsequence_f(new, old): return "SHRANK"
    return "DIVERGED"


def pair_list_of(directory):
    """
    YIELD: [0] str  the GOOD's path
           [1] str  the candidate's path in 'TMP/store'
           [2] str  '<test>--<choice>', the member's name

    Only members a run has left a candidate for: a GOOD with no
    candidate was not run and cannot be judged.
    """
    for here, dir_name_list, file_name_list in os.walk(directory):
        if os.path.basename(here) != "GOOD": continue
        store = os.path.join(os.path.dirname(here), "TMP", "store")
        if not os.path.isdir(store): continue
        for name in sorted(file_name_list):
            if not name.endswith(".txt"): continue
            stem = name[:-len(".txt")]
            candidate = os.path.join(store, stem + ".stdout")
            if os.path.isfile(candidate):
                yield os.path.join(here, name), candidate, stem


def main(argv):
    """
    RETURN: int, 0 where every member stands as recorded, 1 where any
            does not -- EVERY shape but 'SAME' is a failure; 2 where
            the directory does not exist.
    """
    directory  = "."
    verbose_f  = False
    for argument in argv:
        if   argument in ("-v", "--verbose"): verbose_f = True
        elif argument in ("-h", "--help"):    print(__doc__); return 0
        else:                                 directory = argument

    if not os.path.isdir(directory):
        print("no such directory: %s" % directory, file=sys.stderr)
        return 2

    bin_db = {"SAME": [], "GREW": [], "SHRANK": [], "DIVERGED": [],
              "UNREADABLE": []}
    for good, candidate, stem in pair_list_of(directory):
        bin_db[shape_of(good, candidate)].append(
            (os.path.relpath(good, directory), stem))

    for kind, note in (("GREW", "extra lines; every recorded line "
                                "stands, in order"),
                       ("SHRANK", "lines missing; what stands was "
                                  "recorded, in order"),
                       ("DIVERGED", "a recorded line changed or moved"),
                       ("UNREADABLE", "could not be read")):
        entry_list = bin_db[kind]
        if not entry_list: continue
        print("%s -- %d:" % (kind, len(entry_list)))
        print("    %s" % note)
        for path, _stem in entry_list: print("        %s" % path)
        print()

    if verbose_f and bin_db["SAME"]:
        print("SAME -- %d member(s) stand as recorded" % len(bin_db["SAME"]))
    else:
        print("%d member(s) stand as recorded" % len(bin_db["SAME"]))

    return 0 if len(bin_db["SAME"]) == sum(len(v) for v in bin_db.values()) \
             else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
