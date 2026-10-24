#! /usr/bin/env python3
#
# @hwut {
#     title    = "Makefile: touching one file rebuilds exactly what depends on it"
#     features = ["exact-rebuild", "declared-deps"]
#     choices {
#         good   { tolerance { constraints = ["missed == 0", "extra == 0", "builds == 1"] } }
#         broken { tolerance { constraints = ["missed > 0", "builds == 1"] } }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  the rebuild matrix of one gcc/make project (good/broken) after
         touching each source file once
REQUIREMENT: an incremental build is exact. After touching any one source
file, 'make' rebuilds exactly the targets that depend on it -- none MISSED
(a stale object linked into the product: the bug that shows up a week
later as "works after make clean") and none EXTRA (wasted build time).

HOW: the fixture project is copied into a scratch directory and built once
for real (gcc). Then every file gets a fixed time stamp: sources old,
products new -- the tree is up to date. For each source file in turn, only
that file is made newer, and 'make -n --trace' says what it WOULD rebuild
and why. The ORACLE is the compiler, not the Makefile: 'gcc -MM' lists the
headers each object really includes (transitively).

The output shows
    1. the dependencies, declared (Makefile) against real (gcc -MM);
    2. the REBUILD MATRIX: one row per touched file, one column per
       target.  R  rebuilt, as it must    .  left alone, as it must
                  MISSED  must be rebuilt, make would not
                  EXTRA   make rebuilds it, nothing it uses changed
    3. the counts.

CHOICES
    good     complete, minimal dependencies: R and . only.
    broken   two classic slips: 'main.o' does not declare 'util.h', which
             it includes only through 'log.h' (MISSED); 'util.o' declares
             'log.h', which it never includes (EXTRA).

HWUT CONCEPTS
    constraints   'missed', 'extra' and 'builds' are bound values. The laws
                  in the header ARE the requirement (good: 0 missed, 0
                  extra); the broken choice states only that something is
                  missed, the matrix above it says exactly what.
                  'builds == 1': the initial real build succeeded once.
    exact lines   the matrix itself: every cell is the verdict for one
                  (file, target) pair. Time stamps are fixed integers, so
                  nothing in the output depends on the clock.

READING THE GOOD: scan the matrix for any word other than R and '.'.
______________________________________________________________________________
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
T_SOURCE, T_PRODUCT, T_TOUCH = 1000000000, 1000000100, 1000000200
ENV = dict(os.environ, LC_ALL="C", MAKEFLAGS="")


def real_deps(work, source_list):
    """RETURN: object -> sorted list of the files 'gcc -MM' says it reads."""
    dep_db = {}
    for c in [s for s in source_list if s.endswith(".c")]:
        text = subprocess.run(["gcc", "-MM", c], cwd=work, env=ENV,
                              capture_output=True, text=True).stdout
        target, rest = text.replace("\\\n", " ").split(":", 1)
        dep_db[target.strip()] = sorted(rest.split())
    return dep_db


def declared_deps(work, object_list):
    text = open(os.path.join(work, "Makefile")).read()
    return {o: sorted(re.search(r"^%s:(.*)$" % re.escape(o), text, re.M).group(1).split())
            for o in object_list}


def would_rebuild(work, touched, product_list, source_list):
    for name in source_list:
        os.utime(os.path.join(work, name), (T_SOURCE, T_SOURCE))
    for name in product_list:
        os.utime(os.path.join(work, name), (T_PRODUCT, T_PRODUCT))
    os.utime(os.path.join(work, touched), (T_TOUCH, T_TOUCH))
    text = subprocess.run(["make", "-n", "--trace"], cwd=work, env=ENV,
                          capture_output=True, text=True).stdout
    return set(re.findall(r"update target '([^']+)' due to", text))


def main(choice):
    work = tempfile.mkdtemp(prefix="hwut-incremental-")
    try:
        fixture = os.path.join(HERE, "..", choice)
        source_list = sorted(os.listdir(fixture))
        for name in source_list:
            shutil.copy(os.path.join(fixture, name), work)
        build = subprocess.run(["make"], cwd=work, env=ENV, capture_output=True, text=True)
        source_list = [s for s in source_list if s.endswith((".c", ".h"))]
        dep_db = real_deps(work, source_list)
        object_list = sorted(dep_db)
        product_list = object_list + ["app"]
        declared_db = declared_deps(work, object_list)

        print("project '%s': %s" % (choice, " ".join(source_list)))
        print("first build: %s  ((builds: %d))" % ("ok" if build.returncode == 0 else "FAILED",
                                                   1 if build.returncode == 0 else 0))
        print()
        print("DEPENDENCIES  declared in the Makefile | read by the compiler (gcc -MM)")
        for o in object_list:
            lack = [d for d in dep_db[o] if d not in declared_db[o]]
            surplus = [d for d in declared_db[o] if d not in dep_db[o]]
            note = "".join(["  undeclared: " + " ".join(lack) if lack else "",
                            "  never read: " + " ".join(surplus) if surplus else ""])
            print("  %-7s %-22s| %-22s%s" % (o, " ".join(declared_db[o]), " ".join(dep_db[o]), note))
        print("  %-7s %-22s| %s" % ("app", " ".join(object_list), " ".join(object_list)))
        print()
        print("REBUILD MATRIX  touch one file, then 'make -n --trace'")
        print("  R rebuilt, as it must   . left alone, as it must   MISSED   EXTRA")
        print()
        print("  touched   " + "".join("%-8s" % p for p in product_list))
        missed = extra = 0
        cause_list = []
        for touched in source_list:
            rebuilt = would_rebuild(work, touched, product_list, source_list)
            must = {o for o in object_list if touched in dep_db[o]}
            if must:
                must.add("app")
            cell_list = []
            for p in product_list:
                if p in must and p in rebuilt:
                    cell = "R"
                elif p in must:
                    cell, missed = "MISSED", missed + 1
                    if p in declared_db and touched not in declared_db[p]:
                        cause_list.append("MISSED %-7s <- %s undeclared in its rule" % (p, touched))
                elif p in rebuilt:
                    cell, extra = "EXTRA", extra + 1
                    if p in declared_db and touched not in dep_db.get(p, []):
                        cause_list.append("EXTRA  %-7s <- %s declared, never read" % (p, touched))
                else:
                    cell = "."
                cell_list.append(cell)
            print("  %-10s" % touched + "".join("%-8s" % c for c in cell_list).rstrip())
        print()
        for cause in cause_list:
            print("  " + cause)
        law = lambda n: "law == 0   %s" % ("kept" if n == 0 else "BROKEN")
        print("missed ((missed: %d))   %s" % (missed, law(missed)))
        print("extra ((extra: %d))   %s" % (extra, law(extra)))
    finally:
        shutil.rmtree(work)


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in ("good", "broken"):
        print("choices: good, broken")
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
