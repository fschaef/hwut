"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer

PURPOSE: THE TEST REGISTER -- ids for applications and choices that
         survive a rename, return to the pool on removal, and live in
         one write-protected file.

CHOICES: allocation, healing, reuse, tables, faults, vanished, face.

allocation   an id is born on demand, lowest-unused, per scope; asking
             without allocating answers None.
healing      rename keeps the id and touches ONE entry; collisions and
             unknown ids are refused by name.
reuse        removal deletes the entry; the id returns to the pool and
             the NEXT registration receives it.
tables       the file round-trips; a rename in between survives it.
faults       every unreadable register, refused by name -- versions 1
             and 2 among them.
vanished     a registered application whose file is absent is named --
             the test that left without 'hwut.remove'.
face         'hwut.show --show-ids' prints the register.
"""
import os
import shutil
import sys
import tempfile

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.bookkeeper.test_id_db import (    # noqa E402
                                           TestIdDb, TestRunId,
                                           TestIdFault, FILE_NAME)
from   vut.engine.orchestrator.services  import show             # noqa E402


def _check(pair_list):
    """
    RETURN: True,  every claim held.
            False, at least one did not.
    """
    all_f = True
    for verdict, claim in pair_list:
        print("  %s: %s" % ("OK  " if verdict else "FAIL", verdict and claim
                            or claim))
        all_f = all_f and verdict
    return all_f


def _verdict(ok, message):
    """RETURN: None. The choice's last line: SUCCESS, or the failure."""
    print(("SUCCESS: %s" if ok else "FAILURE: %s") % message)


def _raised(work):
    """RETURN: str, the exception type's name; 'nothing' where none."""
    try:               work()
    except Exception as fault: return type(fault).__name__
    return "nothing"


def _place(*file_name_tuple):
    """RETURN: str, a directory holding empty files of those names."""
    directory = tempfile.mkdtemp(prefix="vut_ids_")
    for name in file_name_tuple:
        with open(os.path.join(directory, name), "w") as fh:
            fh.write("# stand-in\n")
    return directory


def _filled(directory):
    """RETURN: TestIdDb over 'directory', registering two apps and two
    choices of the first."""
    db = TestIdDb(directory)
    db.run_id_of("test-parse.py", "basic", allocate_f=True)
    db.run_id_of("test-parse.py", "deep",  allocate_f=True)
    db.run_id_of("test-other.py", None,    allocate_f=True)
    return db


def test_allocation():
    """Lowest-unused, per scope; asking is not allocating."""
    directory = _place("test-parse.py", "test-other.py")
    db = _filled(directory)

    print("--- what the fill allocated ---")
    for app_id, name, choice_tuple in db.app_iterable():
        print("INSPECT: [%i] %s" % (app_id, name))
        for choice_id, choice in choice_tuple:
            print("         [%i.%i] %s" % (app_id, choice_id, choice))

    print("--- asking without allocating ---")
    unknown = db.run_id_of("test-ghost.py")
    print("         test-ghost.py -> %s" % unknown)
    standing = db.run_id_of("test-parse.py", "deep")
    print("         test-parse.py deep -> %s" % standing)

    ok = _check([
        (str(db.run_id_of("test-parse.py", "basic")) == "1.1",
         "the first app's first choice is 1.1"),
        (str(db.run_id_of("test-parse.py", "deep")) == "1.2",
         "its second choice is 1.2 -- choice ids are scoped per app"),
        (str(db.run_id_of("test-other.py")) == "2",
         "the choice-less run spells the app id alone"),
        (unknown is None,
         "an unknown run answers None where allocation was not asked"),
        (db.run_id_of("test-parse.py", "basic", allocate_f=True)
         == TestRunId(1, 1),
         "allocating a standing run returns the standing id"),
        (os.path.isfile(os.path.join(directory, "GOOD", FILE_NAME)),
         "the register is on disk the moment the first id is born"),
    ])
    shutil.rmtree(directory)
    _verdict(ok, "an id is born at first sight, lowest unused, "
                 "in its own scope.")


def test_healing():
    """Rename keeps the id; collisions and unknowns are refused."""
    directory = _place("test-parse.py", "test-other.py")
    db = _filled(directory)

    print("--- rename the application ---")
    old = db.rename_app(1, "test-parser.py")
    now = db.name_of(TestRunId(1, None))[0]
    print("INSPECT: [1] '%s' -> '%s'" % (old, now))
    print("         one entry moved; the choices still answer:")
    print("         [1.2] -> %s" % str(db.name_of(TestRunId(1, 2))))

    print("--- rename the choice ---")
    db.rename_choice(1, 1, "quick")
    print("INSPECT: [1.1] -> %s" % str(db.name_of(TestRunId(1, 1))))

    print("--- refusals, by name ---")
    for label, work in (
            ("app rename onto a live name",
             lambda: db.rename_app(1, "test-other.py")),
            ("choice rename onto a live sibling",
             lambda: db.rename_choice(1, 1, "deep")),
            ("renaming an app never registered",
             lambda: db.rename_app(9, "x")),
            ("renaming a choice never registered",
             lambda: db.rename_choice(1, 9, "x"))):
        print("         %-38s -> %s" % (label, _raised(work)))

    ok = _check([
        (db.run_id_of("test-parser.py", "quick") == TestRunId(1, 1),
         "the id survives both renames -- THE POINT of the register"),
        (db.run_id_of("test-parse.py") is None,
         "the old application name resolves no more"),
        (_raised(lambda: db.rename_app(1, "test-other.py"))
         == "TestIdFault",
         "two live apps under one name is refused"),
        (len(db) == 2, "no rename ever allocated"),
    ])
    shutil.rmtree(directory)
    _verdict(ok, "a rename touches one entry; every id stands.")


def test_reuse():
    """Removal frees the id; the next registration receives it."""
    directory = _place("test-parse.py", "test-other.py")
    db = _filled(directory)

    print("--- remove the first application ---")
    gone = db.remove_app(1)
    print("INSPECT: removed '%s'; register now:" % gone)
    for app_id, name, _ in db.app_iterable():
        print("         [%i] %s" % (app_id, name))
    freed_answer = db.name_of(TestRunId(1, None))
    print("         asking for the freed id: %s" % (freed_answer,))

    print("--- the pool hands the freed id out again ---")
    fresh = db.run_id_of("test-fresh.py", allocate_f=True)
    print("INSPECT: test-fresh.py -> [%s]" % fresh)

    print("--- remove one choice; its sibling keeps its id ---")
    both = TestIdDb(_place())      # scratch registers in one line
    both.run_id_of("a.py", "x", allocate_f=True)
    both.run_id_of("a.py", "y", allocate_f=True)
    both.remove_choice(1, 1)
    next_id = both.run_id_of("a.py", "z", allocate_f=True)
    print("INSPECT: removed 1.1; 'y' still [%s]; 'z' got [%s]"
          % (both.run_id_of("a.py", "y"), next_id))

    ok = _check([
        (freed_answer is None,
         "a removed entry is GONE -- no retirement, no flag"),
        (str(fresh) == "1",
         "the freed id returned to the pool and was handed out again"),
        (str(both.run_id_of("a.py", "y")) == "1.2",
         "a sibling's id never moves when a choice is removed"),
        (str(next_id) == "1.1",
         "the freed choice id is reused in its own scope"),
        (_raised(lambda: db.remove_app(9)) == "TestIdFault",
         "removing what was never registered is refused"),
    ])
    shutil.rmtree(directory)
    _verdict(ok, "removal deletes; the pool is the id space itself.")


def test_tables():
    """The file round-trips, healing included."""
    directory = _place("test-parse.py", "test-other.py")
    db = _filled(directory)
    db.rename_app(1, "test-parser.py")

    print("--- the file, as stored ---")
    text = db.format()
    for line in text.splitlines():
        print("         | %s" % line)

    back     = TestIdDb(directory)
    stable_f = back.format() == text
    print("--- read back ---")
    print("INSPECT: byte-identical after a round trip: %s" % stable_f)
    print("         [1.2] decodes to %s" % str(back.name_of(TestRunId(1, 2))))

    ok = _check([
        (stable_f, "format(parse(format())) is the identity"),
        (back.run_id_of("test-parser.py", "deep") == TestRunId(1, 2),
         "the rename survived the disk"),
        (back.name_of(TestRunId(9, None)) is None,
         "a number this directory never issued answers None"),
    ])
    shutil.rmtree(directory)
    _verdict(ok, "one file, atomically replaced, write-protected.")


def test_faults():
    """Every unreadable register, refused by name."""
    directory = _place("test-parse.py", "test-other.py")
    good = _filled(directory).format()
    shutil.rmtree(directory)

    def wrote(text):
        scratch = _place()
        os.makedirs(os.path.join(scratch, "GOOD"), exist_ok=True)
        with open(os.path.join(scratch, "GOOD", FILE_NAME), "w") as fh:
            fh.write(text)
        try:               TestIdDb(scratch)
        except Exception as fault: return type(fault).__name__
        finally:           shutil.rmtree(scratch)
        return "nothing"

    case_list = [
        ("no version line",       good.replace("##VUT-TEST-IDS 3\n", "")),
        ("version 1, pair-interned",
         "##VUT-TEST-IDS 1\nT:1 . -|a|-\n"),
        ("version 2, pair-interned",
         "##VUT-TEST-IDS 2\nT:1 . a|-\n"),
        ("an app id that spells no number",
         "##VUT-TEST-IDS 3\nA:x demo.py\n"),
        ("an app id standing twice",
         "##VUT-TEST-IDS 3\nA:1 a.py\nA:1 b.py\n"),
        ("an app name standing twice",
         "##VUT-TEST-IDS 3\nA:1 a.py\nA:2 a.py\n"),
        ("a choice under no registered app",
         "##VUT-TEST-IDS 3\nC:1.1 basic\n"),
        ("a run id standing twice",
         "##VUT-TEST-IDS 3\nA:1 a.py\nC:1.1 x\nC:1.1 y\n"),
        ("a choice name standing twice",
         "##VUT-TEST-IDS 3\nA:1 a.py\nC:1.1 x\nC:1.2 x\n"),
        ("a line that names nothing",
         "##VUT-TEST-IDS 3\nA:1\n"),
        ("a line that is no entry",
         "##VUT-TEST-IDS 3\nZ:1 a.py\n"),
    ]
    result_list = []
    for label, text in case_list:
        name = wrote(text)
        print("         %-38s -> %s" % (label, name))
        result_list.append((name == "TestIdFault", "refused: %s" % label))

    print("--- and the two honest absences ---")
    scratch = _place()
    empty   = TestIdDb(scratch)
    print("         no file at all -> %i apps (a fresh directory)"
          % len(empty))
    result_list.append((len(empty) == 0,
                        "a MISSING register reads empty; only a "
                        "DAMAGED one refuses"))
    shutil.rmtree(scratch)

    ok = _check(result_list)
    _verdict(ok, "damage refuses by name; absence is a fresh start.")


def test_vanished():
    """A registered application whose file left without a service."""
    directory = _place("test-parse.py", "test-other.py")
    db = _filled(directory)

    print("--- both files stand ---")
    print("INSPECT: vanished: %s" % (db.vanished(),))

    os.remove(os.path.join(directory, "test-other.py"))
    print("--- 'test-other.py' deleted around the framework ---")
    gone = db.vanished()
    for app_id, name in gone:
        print("INSPECT: [%i] %s VANISHED" % (app_id, name))

    ok = _check([
        (gone == ((2, "test-other.py"),),
         "the register names the id and the name that left"),
        (db.run_id_of("test-other.py") == TestRunId(2, None),
         "the entry STANDS -- healing is a service, never a guess"),
    ])
    shutil.rmtree(directory)
    _verdict(ok, "an unofficial disappearance is detected, not healed.")


def test_face():
    """'hwut.show --show-ids' prints the register."""
    directory = _place("test-parse.py", "test-other.py")
    _filled(directory)
    os.remove(os.path.join(directory, "test-other.py"))

    line_list = []
    code = show.main(["--show-ids", "--directory=%s" % directory],
                     write=line_list.append)
    for line in line_list:
        print(line)
    print("(exit: %s)" % code.name)

    scratch = _place()
    empty_list = []
    show.main(["--show-ids", "--directory=%s" % scratch],
              write=empty_list.append)
    print("--- a fresh directory ---")
    for line in empty_list:
        print(line)

    ok = _check([
        (any("[1.2] deep" in line for line in line_list),
         "choices print beneath their application"),
        (any("VANISHED" in line for line in line_list),
         "the unofficial disappearance is said where ids are shown"),
        (any("first accept" in line for line in empty_list),
         "an empty register says how an id is born"),
    ])
    shutil.rmtree(directory)
    shutil.rmtree(scratch)
    _verdict(ok, "the register has a face, and it names what left.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The test register: ids that survive renames",
        choice_map = {
            "allocation": test_allocation,
            "healing":    test_healing,
            "reuse":      test_reuse,
            "tables":     test_tables,
            "faults":     test_faults,
            "vanished":   test_vanished,
            "face":       test_face,
        },
        happy      = "SUCCESS.*",
    ).run()
