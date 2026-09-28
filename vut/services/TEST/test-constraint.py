#! /usr/bin/env python3
#
# @hwut {
#     title   = "Constraints as a verdict: the run, the book, the GOOD (E-123)"
#     choices = ["accept", "cleared", "diff", "good", "interactive",
#                "output", "sanitize", "tightened"]
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHAT A RUN DOES WITH WHAT THE CONSTRAINTS FOUND (compare C-20),
         through the face 'hwut.run', in a scratch tree with one
         application 't.py': choice 'a' plain, 'b' under 'load <= 100',
         'c' under 'twice == 2 * once' (which never prints 'twice').

    accept    'hwut.accept --force' of candidates that break their
              constraints: 'b' binds 150, 'c' never binds 'twice' -- both
              REFUSED by name, '--force' or not; 'a' is blessed.
    diff      'hwut.run.diff' of a candidate that broke its constraint in a
              run: the finding stands in the candidate, directly after the
              line that caused it, and the view shows it there -- nothing
              is said beside the view.
    interactive
              what the merge refuses to commit: a text that breaks its
              constraints, held against itself; the text that keeps them
              passes.
    good      GOODs standing that contradict their constraints (written
              here as fixtures -- accept would refuse them): 'b' binds
              150, 'c' never binds 'twice'. The run fails both BY NAME
              ('constraint'), says each finding in full, and 'a' still runs
              -- the directory is not ended (o-6). The book's stain says
              'constraint'; each GOOD carries the finding in an
              '##! constraint-violation' region directly after the line that caused
              it -- 'c''s never-bound variable at the head. A second run
              adds no line to either GOOD.
    output    a GOOD that keeps its law, an OUTPUT that breaks it: the run
              fails 'b' by name with the OUTPUT's finding and writes it
              into the candidate, after the line that caused it; the GOOD
              is not touched and the book carries no stain.
    sanitize  'hwut.sanitize --constraints' finds the GOODs that
              contradict their constraints without running anything;
              '--apply' writes each finding into the GOOD where it was
              found and stains the book, as a run would; asked again,
              nothing is found: what is written stands.
    tightened a GOOD accepted under 'load <= 200' (b printing 150), then the
              page's constraint tightened to 'load <= 100': the run writes
              '##! constraint-violation' into the GOOD, after the line --
              never '##! unaccepted' -- and fails the case although the
              OUTPUT is exactly the GOOD. A second run fails it again, by
              name.
    cleared   a 'constraint' stain standing on a case whose run passes: the
              stain goes.
______________________________________________________________________________
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
ENV  = dict(os.environ, PYTHONPATH=os.path.dirname(ROOT))
sys.path.insert(0, os.path.dirname(ROOT))

APP = ('#! /usr/bin/env python3\n'
       '# @hwut {\n'
       '#     title = "T"\n'
       '#     choices {\n'
       '#         a { }\n'
       '#         b { tolerance { constraints = ["load <= 100"] } }\n'
       '#         c { tolerance { constraints = ["twice == 2 * once"] } }\n'
       '#     }\n'
       '# }\n'
       'import os, sys\n'
       'choice = sys.argv[1]\n'
       'if choice == "b": print("x ((load: %s))" % os.environ["LOAD"])\n'
       'elif choice == "c": print("x ((once: 3))")\n'
       'else: print("plain")\n'
       'print("<hwut-end>")\n')


def tree_of(load, said=None):
    """RETURN: (str, str), the scratch root and its TEST directory, with
               't.py' accepted once through the face -- 'b' printing
               'load'. What the face said is appended to 'said'."""
    root = tempfile.mkdtemp(prefix="vut_constraint_")
    test = os.path.join(root, "TEST")
    os.makedirs(test)
    with open(os.path.join(root, "hwut-root.conf"), "w") as fh:
        fh.write("hwut {\n}\n")
    path = os.path.join(test, "t.py")
    with open(path, "w") as fh: fh.write(APP)
    os.chmod(path, 0o755)
    text = face(test, "accept", "--force", "--dont-ask", load=load)
    if said is not None: said.append(text)
    return root, test


def test_tightened():
    root = tempfile.mkdtemp(prefix="vut_constraint_")
    try:
        test = os.path.join(root, "TEST")
        os.makedirs(test)
        with open(os.path.join(root, "hwut-root.conf"), "w") as fh:
            fh.write("hwut {\n}\n")
        path = os.path.join(test, "t.py")
        with open(path, "w") as fh:
            fh.write(APP.replace("load <= 100", "load <= 200"))
        os.chmod(path, 0o755)
        print("-- accepted under 'load <= 200'")
        for line in face(test, "accept", "--force", "--dont-ask",
                         load="150").splitlines():
            if "t.py b" in line or line.startswith("REFUSED"):
                print("   %s" % line.rstrip())
        with open(path, "w") as fh: fh.write(APP)
        print("-- the constraint tightened to 'load <= 100'; OUTPUT unchanged")
        for label in ("first run", "second run"):
            print("-- %s" % label)
            for line in hint_list(face(test, "run", "t.py", "b",
                                       load="150")):
                print("   %s" % line)
        print("-- GOOD of 'b'")
        show_good(test, "b")
        print("-- the book's stain: %s" % stain_db(test))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def put_good(test, choice, text):
    """RETURN: None. A GOOD standing for 'choice', booked as accepted -- a
               fixture, written where the face would refuse it."""
    from vut.engine.bookkeeper.api import Bookkeeper
    with open(os.path.join(test, "GOOD", "t.py--%s.txt" % choice), "w") as fh:
        fh.write(text)
    Bookkeeper(test).note_accept("t.py", choice)


def face(test, name, *word_list, load="50"):
    """RETURN: str, what the face 'vut.services.<name>' said, both
               streams."""
    done = subprocess.run([sys.executable, "-m", "vut.services.%s" % name]
                          + list(word_list), cwd=test, text=True,
                          capture_output=True, env=dict(ENV, LOAD=load))
    return done.stdout + done.stderr


def hint_list(text):
    """RETURN: list[str], the run's HINTS lines and its RESULTS line --
               what does not depend on the order the cases ran in."""
    import re
    return [re.sub(r", [0-9.]+ \[sec\].*$", "", line.rstrip())
            for line in text.splitlines()
            if line.startswith("    t.py") or line.startswith("    :")
            or line.startswith("RESULTS:")]


def stain_db(test):
    """RETURN: dict, choice -> the book's stain cell."""
    from vut.engine.bookkeeper.api import Bookkeeper, stain_text
    book = Bookkeeper(test)
    return {c: stain_text(book.stain("t.py", c)) for c in ("a", "b", "c")}


def show_good(test, choice, where="GOOD"):
    """RETURN: None. The GOOD of 'choice' (or its candidate, 'OUT'), line
               by line."""
    with open(os.path.join(test, where, "t.py--%s.txt" % choice)) as fh:
        for line in fh.read().splitlines(): print("      | %s" % line)


def test_accept():
    said_list = []
    root, test = tree_of(load="150", said=said_list)
    try:
        for line in said_list[0].splitlines():
            if line.startswith(("REFUSED", "    ", "ACCEPTED")):
                print("   %s" % line.rstrip())
        print("-- GOOD/ holds: %s" % sorted(n for n in os.listdir(
                                        os.path.join(test, "GOOD"))
                                        if n.endswith(".txt")))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_diff():
    root, test = tree_of(load="50")
    try:
        face(test, "run", "t.py", "b", load="150")
        said = face(test, "lib.run.diff", "t.py", "b")
        print("-- no 'CONSTRAINT:' line: %s" % ("CONSTRAINT:" not in said))
        for line in said.splitlines():
            if line.startswith(("S ", "N ", " ", "--[")): print("   %s" % line)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_interactive():
    from vut.engine.compare.api import Configuration
    from vut.services.lib.accept.engine import refusal
    from vut.engine.bookkeeper.api import Store, Bookkeeper
    root, test = tree_of(load="50")
    try:
        setup = Configuration()
        setup.constraint_expression_list = ["load <= 100"]
        setup.derive_constraint_db()
        class Key:
            test = "t.py"; choice = "b"; label = "t.py b"
        Key.setup = setup
        store = Store(Bookkeeper(test))
        for text in ("x ((load: 150))\n<hwut-end>\n",
                     "x ((load: 99))\n<hwut-end>\n",
                     "x 150\n<hwut-end>\n"):
            print("   %-22r -> %s" % (text.split("\n")[0],
                                     refusal(store, Key, text, False, print)
                                     or "may become the GOOD"))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_good():
    root, test = tree_of(load="50")
    try:
        put_good(test, "b", "x ((load: 150))\n<hwut-end>\n")
        put_good(test, "c", "x ((once: 3))\n<hwut-end>\n")
        print("-- the first run")
        for line in hint_list(face(test, "run")): print("   %s" % line)
        print("-- the book's stain: %s" % stain_db(test))
        for choice in ("b", "c"):
            print("-- GOOD of '%s'" % choice)
            show_good(test, choice)
        print("-- a second run: the GOODs gain nothing")
        for line in hint_list(face(test, "run")): print("   %s" % line)
        for choice in ("b", "c"):
            print("-- GOOD of '%s'" % choice)
            show_good(test, choice)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_output():
    root, test = tree_of(load="50")
    try:
        print("-- the run, 'b' printing 150")
        for line in hint_list(face(test, "run", "t.py", "b", load="150")):
            print("   %s" % line)
        print("-- the book's stain: %s" % stain_db(test))
        print("-- GOOD of 'b'")
        show_good(test, "b")
        print("-- the candidate of 'b', as the run recorded it")
        show_good(test, "b", "OUT")
        print("-- a second run: the candidate is recorded afresh, the "
              "remark written once")
        face(test, "run", "t.py", "b", load="150")
        show_good(test, "b", "OUT")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_cleared():
    root, test = tree_of(load="50")
    try:
        from vut.engine.bookkeeper.api import Bookkeeper
        Bookkeeper(test).note_stain_keyword("t.py", "b", "constraint", True)
        print("-- before: %s" % stain_db(test))
        for line in hint_list(face(test, "run", "t.py", "b")):
            print("   %s" % line)
        print("-- after:  %s" % stain_db(test))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_sanitize():
    import re
    root, test = tree_of(load="50")
    try:
        put_good(test, "b", "x ((load: 150))\n<hwut-end>\n")
        put_good(test, "c", "x ((once: 3))\n<hwut-end>\n")
        for label, word_list in (("reported", ()), ("--apply", ("--apply",)),
                                 ("again", ())):
            print("-- %s" % label)
            said = face(test, "sanitize", "--constraints", *word_list)
            for line in said.splitlines():
                line = re.sub(r"^TOUCHED.*", "TOUCHED ...", line.rstrip())
                if line.strip() and not line.startswith("    could not"):
                    print("   %s" % line.replace(test, "<TEST>"))
        print("-- the book's stain: %s" % stain_db(test))
        for choice in ("b", "c"):
            print("-- GOOD of '%s'" % choice)
            show_good(test, choice)
    finally:
        shutil.rmtree(root, ignore_errors=True)


CHOICE_DB = {"sanitize": test_sanitize, "good": test_good, "output": test_output,
             "cleared": test_cleared, "accept": test_accept,
             "diff": test_diff, "interactive": test_interactive,
             "tightened": test_tightened}
CHOICE_DB[sys.argv[1] if len(sys.argv) > 1 else "good"]()
print("<hwut-end>")
