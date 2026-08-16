#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE WISH -- the selection keywords read off a command line, and
         the cases they select out of a directory.

CHOICES: parsing, anchors, refused, globs, base;

DESCRIPTION:

parsing  every keyword read, alone and together, and how the wish
         writes itself back; arguments that are none of them are handed
         back untouched.

anchors  the instant every anchor names, reckoned in UTC off a stated
         clock: a Thursday in May.

refused  a point that cannot be read, a keyword standing without its
         value, '--fail' beside '--pass', an empty window: refused at
         the door, by name.

globs    globs over both members of the target form; several globs hold
         one question and are OR'ed; an empty match is legal.

base     the base questions answered out of a book: '--fail', '--pass',
         '--since=' shunning the never-run, '--until=' wanting them --
         the stale wish -- and the questions AND'ed. Asking the base
         without a Bookkeeper is refused.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from config import HwutRunner                                # noqa: F401

from vut.engine.orchestrator.exploration.explorer        import explore
from vut.engine.orchestrator.exploration.task_list_query import \
                                                         CTestTaskListQuery
from vut.engine.orchestrator.plan.wish import (Wish, WishError,
                                               cutoff_instant, parse_wish)


NOW = datetime(2026, 5, 14, 15, 30, 0, tzinfo=timezone.utc)   # a Thursday


class BookStub:
    """A book of stated entries: (file, choice) -> (verdict, age in
    seconds). It answers 'result' and nothing else -- what the query
    asks of a Bookkeeper."""

    def __init__(self, entry_db):
        """RETURN: BookStub over 'entry_db'."""
        self.entry_db = entry_db

    def result(self, test, choice, operation):
        """
        RETURN: dict, the entry for that call / None, where the book
                has none.
        """
        entry = self.entry_db.get((test, choice))
        if entry is None: return None
        verdict, age_sec = entry
        when = NOW - timedelta(seconds=age_sec)
        return {"verdict": verdict, "when": when.isoformat()}


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def build_directory():
    """
    RETURN: [0] CTestAppSet  four applications of mixed shape.
            [1] str          the directory, for the caller to remove.
    """
    directory = tempfile.mkdtemp(prefix="vut_wish_")
    file_db = {
        "test-a.py":   '# hwut { title = "A"  choices = ["one", "two"] }\n',
        "test-b.py":   '# hwut { title = "B" }\n',
        "test-net.py": '# hwut { title = "Net" }\n',
        "quick-3.py":  '# hwut { title = "Q"  choices = ["one"] }\n',
    }
    for name, content in file_db.items():
        with open(os.path.join(directory, name), "w") as fh:
            fh.write(content)
    return explore(directory).app_set, directory


def show(sequence):
    """RETURN: None. The selected calls, one per line."""
    print("    %d case(s)" % len(sequence))
    for case in sequence:
        print("        %s %s" % (case.source_file,
                                 "-" if case.choice is None
                                     else case.choice))


def select(app_set, wish, book=None):
    """RETURN: None. Shows the wish and what it selects."""
    print("    WISH: %s" % wish)
    show(CTestTaskListQuery(wish, book, now=NOW).get_test_cases(app_set))


def test_parsing():
    """RETURN: None. Every keyword read off a command line."""
    for argv in ([],
                 ["--fail"],
                 ["--pass"],
                 ["--since=2h"],
                 ["--until=yesterday"],
                 ["--since=monday", "--until=last-week"],
                 ["--glob", "test-*.py"],
                 ["--glob=test-a.py one"],
                 ["--fail", "--since=7d", "--glob", "test-a.py *",
                  "--glob", "quick-[0-9].py"],
                 ["--fail", "--directory=x", "some-file.py"]):
        wish, rest = parse_wish(argv)
        banner(" ".join(argv) or "(nothing)")
        print("    wish : %s" % wish)
        print("    rest : %s" % (", ".join(rest) or "-"))
        print("    asks nothing: %s" % wish.states_nothing_f())


def test_anchors():
    """RETURN: None. The instant every anchor names, off the stated
    clock: Thursday, 14 May 2026, 15:30 UTC."""
    banner("clock: %s (a Thursday)" % NOW.isoformat())
    for spec in ("2h", "today", "yesterday", "last-week", "last-month",
                 "monday", "thursday", "friday", "sunday",
                 "january", "may", "december"):
        print("    %-12s -> %s"
              % (spec, cutoff_instant(spec, NOW).isoformat()))


def test_refused():
    """RETURN: None. What the command line cannot mean."""
    for argv in (["--since=2"], ["--since=xh"], ["--since="],
                 ["--since"], ["--until"], ["--glob"], ["--since=-1h"],
                 ["--until=noon"], ["--fail", "--pass"],
                 ["--since=1h", "--until=2h"]):
        banner(" ".join(argv))
        try:
            parse_wish(argv)
            print("NOT REFUSED -- a law is broken")
        except WishError as error:
            print("REFUSED: %s" % error)


def test_globs():
    """RETURN: None. Globs over both members of the target form."""
    app_set, directory = build_directory()
    try:
        banner("everything the directory offers")
        select(app_set, Wish())

        banner("a file glob: every choice of every match")
        select(app_set, Wish(glob_tuple=("test-*.py",)))

        banner("a choice glob beside it")
        select(app_set, Wish(glob_tuple=("test-a.py *",)))

        banner("a set in the file member")
        select(app_set, Wish(glob_tuple=("quick-[0-3].py *",)))

        banner("two globs hold ONE question: OR")
        select(app_set, Wish(glob_tuple=("test-b.py", "test-a.py one")))

        banner("a glob matching nothing: legal, empty")
        select(app_set, Wish(glob_tuple=("test-*.pt",)))
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_base():
    """RETURN: None. The questions the book answers."""
    app_set, directory = build_directory()
    book = BookStub({
        ("test-a.py", "one"): (False,   600),    # failed, 10 minutes ago
        ("test-a.py", "two"): (True,    600),    # stood,  10 minutes ago
        ("test-b.py", None):  (False, 90000),    # failed, over a day ago
        ("test-net.py", None): (True, 90000),    # stood,  over a day ago
        #  'quick-3.py one' was never run.
    })
    try:
        banner("--fail")
        select(app_set, Wish(fail_f=True), book)

        banner("--pass")
        select(app_set, Wish(pass_f=True), book)

        banner("--since=2h : the never-run case is not wanted")
        select(app_set, Wish(since_spec="2h"), book)

        banner("--until=2h : the stale wish -- the never-run counted")
        select(app_set, Wish(until_spec="2h"), book)

        banner("--until=yesterday : older anchors reach further back")
        select(app_set, Wish(until_spec="yesterday"), book)

        banner("--fail --since=2h : the questions are AND'ed")
        select(app_set, Wish(fail_f=True, since_spec="2h"), book)

        banner("--fail --until=2h : the never-run answers NO to --fail")
        select(app_set, Wish(fail_f=True, until_spec="2h"), book)

        banner("--fail --glob 'test-b.py' : keyword and glob, AND'ed")
        select(app_set, Wish(fail_f=True, glob_tuple=("test-b.py",)),
               book)

        banner("asking the base without a Bookkeeper: refused")
        try:
            CTestTaskListQuery(Wish(fail_f=True))
            print("NOT REFUSED -- a law is broken")
        except AssertionError as error:
            print("REFUSED: %s" % error)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "Wish: keywords read, cases selected;", {
        "parsing": test_parsing,
        "anchors": test_anchors,
        "refused": test_refused,
        "globs":   test_globs,
        "base":    test_base,
    }).run()
