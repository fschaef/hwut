#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.affected' FACE -- a change in, the runs that executed
         it out. The face is driven through 'main(argv, write)', so what
         is shown is the face itself and no process stands between. The
         record root is stated with '--records'; its path is
         machine-chosen and never printed.

CHOICES: diff, answer, bare, empty, refused, help;

DESCRIPTION:

diff      the unified diff, read: an added line is itself; a REMOVED
          line is recorded at the new-side position where it stood --
          the line is gone, and saying nothing there would hide a
          deletion entirely. '-p' strips path components. A file
          removed wholesale contributes nothing.

answer    the framed answer over a fixture of three records: what was
          asked, what was indexed, and the runs -- with the LIMIT
          printed under it, always.

bare      '--bare' drops the frame for piping into a wish. It does NOT
          drop the note: that goes to stderr instead, so a pipeline
          carries names and a reader still sees the caveat.

empty     a change nobody executed: understood, answered, and given
          its own status -- an empty selection is not a failure, and
          not a success either.

refused   what the command line cannot mean: no '--records', a root
          that is no directory, a '-p' that is no number, a word the
          face does not know, and a diff that touches nothing.

help      the documentation, on demand.
______________________________________________________________________________
"""
import io
import os
import sys
import shutil
import tempfile
import config                                                   # noqa: F401

from vut.language_support.python.hwut_runner import HwutRunner
from vut.engine.coverage.record   import ranges_of, FileCoverage, \
                                         CoverageRecord, format_record
from vut.engine.coverage.affected import (change_db_of_diff, main,
                                          E_ExitCode)


DIFF = """diff --git a/parser/core.py b/parser/core.py
--- a/parser/core.py
+++ b/parser/core.py
@@ -5,7 +5,8 @@ def parse(text):
     head = text[0]
     tail = text[1:]
-    return head
+    result = head.strip()
+    return result
     # unreachable

@@ -40,3 +41,4 @@ def other():
     pass
+    return None
diff --git a/parser/gone.py b/parser/gone.py
--- a/parser/gone.py
+++ /dev/null
@@ -1,2 +0,0 @@
-print("x")
-print("y")
"""


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def check(pair_list):
    """
    RETURN: True,  every claim held; prints OK/FAIL per line.
            False, else.
    """
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def verdict(ok, sentence):
    """RETURN: None. The one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


def build_fixture():
    """
    RETURN: str, a fresh directory holding three coverage records in two
            sub directories -- the corpus in miniature.

        parser/TEST/  test-parse.py--basic   ../core.py            1..10
                      test-parse.py--deep    ../core.py            6..20
        other/TEST/   test-other.py          ../../parser/core.py  50..52

    All three name the SAME source file, each relative to its own test
    directory -- so the fixture exercises the rebasing, not merely the
    query.
    """
    root = tempfile.mkdtemp(prefix="vut_affected_")

    def place(sub, test, choice, line_iterable, source):
        """RETURN: None. Writes one record where a run would leave it."""
        directory = os.path.join(root, sub)
        os.makedirs(directory, exist_ok=True)
        record = CoverageRecord(
            language="python", tool="coverage",
            source="coverage.py-json", counts_f=False,
            test=test, choice=choice,
            file_db={source: FileCoverage(source,
                                          ranges_of(line_iterable),
                                          ranges_of(line_iterable))})
        name = test if choice is None else "%s--%s" % (test, choice)
        with io.open(os.path.join(directory, name + ".cover"), "w",
                     encoding="utf-8") as handle:
            handle.write(format_record(record))

    #  EVERY record names its source RELATIVE TO ITS OWN TEST DIRECTORY
    #  (D-4). Two different directories therefore spell ONE file two
    #  ways, and the face rebases both onto 'parser/core.py'.
    place("parser/TEST", "test-parse.py", "basic", range(1, 11),
          "../core.py")
    place("parser/TEST", "test-parse.py", "deep",  range(6, 21),
          "../core.py")
    place("other/TEST",  "test-other.py", None,    range(50, 53),
          "../../parser/core.py")
    return root


def call(argv, diff_text=None):
    """
    RETURN: [0] int, the exit code.
            [1] str, what the face wrote to its output stream.
            [2] str, what it wrote to its error stream.

    Stdin carries the diff where the face reads '-'.
    """
    out, err = io.StringIO(), io.StringIO()
    saved    = sys.stdin
    if diff_text is not None: sys.stdin = io.StringIO(diff_text)
    try:     status = main(argv, out.write, err.write)
    finally: sys.stdin = saved
    return status, out.getvalue(), err.getvalue()


def show(status, out, err, root=None):
    """RETURN: None. Prints a call's reaction, streams framed.

    The fixture root is MACHINE-CHOSEN, so it is masked to '<work>'
    wherever a refusal names it: a GOOD that carried a temporary path
    would differ on every run and on every machine.

    A framed line is right-stripped: an empty line must not become a
    prefix with a blank after it -- a byte nobody meant is a byte an
    oracle inherits.
    """
    def masked(text):
        """RETURN: str, with the machine-chosen root spoken as '<work>'."""
        return text if root is None else text.replace(root, "<work>")

    print("REACTION  status %s   stderr %i byte(s)" % (status, len(err)))
    for line in masked(out).splitlines():
        print(("          | %s" % line).rstrip())
    for line in masked(err).splitlines():
        print(("          ! %s" % line).rstrip())


# ---------------------------------------------------------------------------

def test_diff():
    """The unified diff, read into changed line ranges."""
    banner("the fixture diff, -p1")
    change_db = change_db_of_diff(DIFF, strip=1)
    for path in sorted(change_db):
        print("         %-14s %s" % (path, change_db[path]))

    banner("-p0 keeps the leading component")
    print("         %s" % sorted(change_db_of_diff(DIFF, strip=0)))

    banner("a diff that touches nothing")
    print("         %s" % change_db_of_diff("no diff here\n"))

    ok = check([
        (sorted(change_db) == ["parser/core.py"],
         "a file removed wholesale contributes nothing: there is no "
         "new-side line to ask about"),
        (change_db["parser/core.py"] == ((7, 9), (42, 43)),
         "added lines are themselves; the removal is recorded where it "
         "stood"),
        (sorted(change_db_of_diff(DIFF, strip=0)) == ["b/parser/core.py"],
         "'-p0' keeps what '-p1' strips"),
        (change_db_of_diff("no diff here\n") == {},
         "a text that is no diff yields no change, and does not raise"),
    ])
    verdict(ok, "a diff becomes the lines a query can be put to.")


def test_answer():
    """The framed answer, and the limit printed under it."""
    root = build_fixture()
    try:
        banner("a change in the region both parse runs executed")
        show(*call(["hwut.affected", "--records", root], DIFF), root=root)

        elsewhere = ("--- a/parser/core.py\n+++ b/parser/core.py\n"
                     "@@ -51,0 +51,1 @@\n+    pass\n")
        banner("a change at line 51 -- a different region, a different run")
        show(*call(["hwut.affected", "--records", root], elsewhere), root=root)

        status, out, _ = call(["hwut.affected", "--records", root], DIFF)
        _, elsewhere_out, _ = call(["hwut.affected", "--records", root],
                                   elsewhere)
        ok = check([
            (status == E_ExitCode.OK,
             "a selection was made"),
            ("parser/TEST:1.1" in out
             and "parser/TEST:1.2" in out,
             "both runs that executed lines 7..8 are named"),
            ("other/TEST:" not in out,
             "the run that reached only 50..52 is NOT named -- the "
             "change touched 7..8 and 42"),
            ("other/TEST:1" in elsewhere_out
             and "test-parse.py" not in elsewhere_out,
             "and a change at line 51 names IT alone: the selection "
             "follows the lines, not the file"),
            ("3 run(s)" in out,
             "the index says how many runs it was built from"),
            ("SUGGESTION, never a clearance" in out,
             "and the LIMIT is printed, always"),
        ])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    verdict(ok, "the answer names who executed the change, and what it "
                "does not mean.")


def test_bare():
    """'--bare' for a pipeline; the note moves, it does not vanish."""
    root = build_fixture()
    try:
        banner("--bare")
        show(*call(["hwut.affected", "--records", root, "--bare"], DIFF), root=root)

        status, out, err = call(
            ["hwut.affected", "--records", root, "-b"], DIFF)
        ok = check([
            (status == E_ExitCode.OK, "the status is the same"),
            (out.splitlines() == ["parser/TEST:1.1",
                                  "parser/TEST:1.2"],
             "stdout carries names alone, one per line, sorted"),
            ("==[" not in out, "no frame"),
            ("SUGGESTION, never a clearance" in err,
             "the note went to stderr -- it did not vanish"),
        ])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    verdict(ok, "a pipeline gets names; a reader still gets the caveat.")


def test_empty():
    """A change nobody executed."""
    root  = build_fixture()
    lonely = ("--- a/x/core.py\n+++ b/x/core.py\n"
              "@@ -30,0 +30,1 @@\n+    pass\n")
    try:
        banner("a change in a region nobody reached")
        show(*call(["hwut.affected", "--records", root], lonely), root=root)

        status, out, _ = call(["hwut.affected", "--records", root], lonely)
        ok = check([
            (status == E_ExitCode.EMPTY,
             "an empty selection has its OWN status: understood, "
             "answered, and answered with nothing"),
            (status != E_ExitCode.OK and status != E_ExitCode.REFUSED,
             "it is neither a success nor a refusal"),
            ("NONE executed the changed lines" in out,
             "and the answer SAYS the selection is empty, rather than "
             "printing an empty list"),
        ])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    verdict(ok, "an empty selection is spoken, not left blank.")


def test_refused():
    """What the command line cannot mean."""
    root = build_fixture()
    try:
        for label, argv, diff_text in (
                ("no '--records'",       ["hwut.affected"], DIFF),
                ("a root that is no directory",
                 ["hwut.affected", "--records", os.path.join(root, "nope")],
                 DIFF),
                ("'-p' that is no number",
                 ["hwut.affected", "--records", root, "-p", "x"], DIFF),
                ("a word the face does not know",
                 ["hwut.affected", "--records", root, "--deep"], DIFF),
                ("a diff that touches nothing",
                 ["hwut.affected", "--records", root], "not a diff\n")):
            banner(label)
            show(*call(argv, diff_text), root=root)

        status_list = [call(argv, text)[0] for argv, text in (
            (["hwut.affected"], DIFF),
            (["hwut.affected", "--records", os.path.join(root, "nope")], DIFF),
            (["hwut.affected", "--records", root, "-p", "x"], DIFF),
            (["hwut.affected", "--records", root, "--deep"], DIFF),
            (["hwut.affected", "--records", root], "not a diff\n"))]
        ok = check([
            (all(s == E_ExitCode.REFUSED for s in status_list),
             "every one is REFUSED, by name, with nothing printed to "
             "stdout"),
        ])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    verdict(ok, "what cannot mean anything is refused at the door.")


def test_help():
    """The documentation, on demand."""
    banner("--help")
    show(*call(["hwut.affected", "--help"]))
    status, out, _ = call(["hwut.affected", "--help"])
    ok = check([
        (status == E_ExitCode.OK, "asking for help is not a fault"),
        ("--records" in out,      "and the usage names what is required"),
    ])
    verdict(ok, "the face explains itself.")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "hwut.affected: the runs that executed a change",
        choice_map = {
            "diff":    test_diff,
            "answer":  test_answer,
            "bare":    test_bare,
            "empty":   test_empty,
            "refused": test_refused,
            "help":    test_help,
        },
        happy      = "SUCCESS.*",
    ).run()
