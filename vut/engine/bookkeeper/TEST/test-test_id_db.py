"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer

PURPOSE: THE TEST REGISTER -- ids for applications and choices that
         survive a rename, are retired on removal and never re-issued,
         and live in one write-protected file.

CHOICES: allocation, healing, retire, tables, faults, vanished, face.

allocation   an id is born on demand, counting from 0, one above the
             highest its scope ever issued; asking without allocating
             answers None.
healing      rename keeps the id and touches ONE entry; collisions and
             unknown ids are refused by name.
retire       removal deletes the entry; the id is never issued again,
             across a reload too; the ceiling refuses by name.
give_back    an ABORTED accept hands its id back: the mark steps back
             where that id was the last issued, and stands where it
             was not.
tables       the file round-trips, marks included; a rename in between
             survives it.
faults       every unreadable register, refused by name -- versions 1,
             2 and 3 among them, and every mark a register could lack.
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
                                           TestIdFault, FILE_NAME,
                                           ID_LIMIT)
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
    """Counting from 0, per scope; asking is not allocating."""
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
        (str(db.run_id_of("test-parse.py", "basic")) == "0.0",
         "the first app's first choice is 0.0 -- both scopes count "
         "from 0"),
        (str(db.run_id_of("test-parse.py", "deep")) == "0.1",
         "its second choice is 0.1 -- choice ids are scoped per app"),
        (str(db.run_id_of("test-other.py")) == "1",
         "the choice-less run spells the app id alone"),
        (unknown is None,
         "an unknown run answers None where allocation was not asked"),
        (db.run_id_of("test-parse.py", "basic", allocate_f=True)
         == TestRunId(0, 0),
         "allocating a standing run returns the standing id"),
        (os.path.isfile(os.path.join(directory, "GOOD", FILE_NAME)),
         "the register is on disk the moment the first id is born"),
    ])
    shutil.rmtree(directory)
    _verdict(ok, "an id is born at first sight, one above its scope's "
                 "mark, from 0.")


def test_healing():
    """Rename keeps the id; collisions and unknowns are refused."""
    directory = _place("test-parse.py", "test-other.py")
    db = _filled(directory)

    print("--- rename the application ---")
    old = db.rename_app(0, "test-parser.py")
    now = db.name_of(TestRunId(0, None))[0]
    print("INSPECT: [0] '%s' -> '%s'" % (old, now))
    print("         one entry moved; the choices still answer:")
    print("         [0.1] -> %s" % str(db.name_of(TestRunId(0, 1))))

    print("--- rename the choice ---")
    db.rename_choice(0, 0, "quick")
    print("INSPECT: [0.0] -> %s" % str(db.name_of(TestRunId(0, 0))))

    print("--- refusals, by name ---")
    for label, work in (
            ("app rename onto a live name",
             lambda: db.rename_app(0, "test-other.py")),
            ("choice rename onto a live sibling",
             lambda: db.rename_choice(0, 0, "deep")),
            ("renaming an app never registered",
             lambda: db.rename_app(9, "x")),
            ("renaming a choice never registered",
             lambda: db.rename_choice(0, 9, "x"))):
        print("         %-38s -> %s" % (label, _raised(work)))

    ok = _check([
        (db.run_id_of("test-parser.py", "quick") == TestRunId(0, 0),
         "the id survives both renames -- THE POINT of the register"),
        (db.run_id_of("test-parse.py") is None,
         "the old application name resolves no more"),
        (_raised(lambda: db.rename_app(0, "test-other.py"))
         == "TestIdFault",
         "two live apps under one name is refused"),
        (len(db) == 2, "no rename ever allocated"),
    ])
    shutil.rmtree(directory)
    _verdict(ok, "a rename touches one entry; every id stands.")


def test_retire():
    """Removal retires the id; nothing is ever issued twice."""
    directory = _place("test-parse.py", "test-other.py")
    db = _filled(directory)

    print("--- remove the first application ---")
    gone = db.remove_app(0)
    print("INSPECT: removed '%s'; register now:" % gone)
    for app_id, name, _ in db.app_iterable():
        print("         [%i] %s" % (app_id, name))
    freed_answer = db.name_of(TestRunId(0, None))
    print("         asking for the retired id: %s" % (freed_answer,))

    print("--- the next registration, before and after a reload ---")
    fresh = db.run_id_of("test-fresh.py", allocate_f=True)
    print("INSPECT: test-fresh.py -> [%s]" % fresh)
    reloaded = TestIdDb(directory)
    later    = reloaded.run_id_of("test-later.py", allocate_f=True)
    print("INSPECT: after reload, test-later.py -> [%s]" % later)

    print("--- remove one choice; its sibling keeps its id ---")
    both = TestIdDb(_place())      # scratch register in one line
    both.run_id_of("a.py", "x", allocate_f=True)
    both.run_id_of("a.py", "y", allocate_f=True)
    both.remove_choice(0, 0)
    next_id = both.run_id_of("a.py", "z", allocate_f=True)
    print("INSPECT: removed 0.0; 'y' still [%s]; 'z' got [%s]"
          % (both.run_id_of("a.py", "y"), next_id))

    print("--- an aborted accept hands its id back ---")
    aborting = TestIdDb(_place())
    first    = aborting.run_id_of("a.py", "x", allocate_f=True)
    last     = aborting.run_id_of("a.py", "y", allocate_f=True)
    stepped  = aborting.give_back(last)
    after    = aborting.run_id_of("a.py", "z", allocate_f=True)
    print("INSPECT: gave back %s (the last issued) -> mark stepped back: %s"
          % (last, stepped))
    print("         the next accept receives [%s]" % after)
    held       = aborting.give_back(first)
    held_after = aborting.run_id_of("a.py", "w", allocate_f=True)
    print("INSPECT: gave back %s (NOT the last) -> mark stepped back: %s"
          % (first, held))
    print("         the next accept receives [%s]" % held_after)

    print("--- the ceiling ---")
    full = TestIdDb(_place())
    full._next_app = ID_LIMIT
    ceiling = _raised(lambda: full.run_id_of("q.py", allocate_f=True))
    print("INSPECT: a scope at ID_LIMIT asked to issue -> %s" % ceiling)

    ok = _check([
        (freed_answer is None,
         "a removed entry is GONE -- no flag, no tombstone; only the "
         "mark remembers"),
        (str(fresh) == "2",
         "the retired id is not handed out again"),
        (str(later) == "3",
         "the mark is persisted: a reload does not lower it"),
        (str(both.run_id_of("a.py", "y")) == "0.1",
         "a sibling's id never moves when a choice is removed"),
        (str(next_id) == "0.2",
         "the retired choice id is not re-issued in its scope"),
        (ceiling == "TestIdFault",
         "the 2**32nd id of a scope is refused by name"),
        (stepped is True and str(after) == "0.1",
         "an aborted accept giving back the LAST id steps the mark "
         "back: nothing persisted ever carried that number"),
        (held is False and str(held_after) == "0.2",
         "giving back an id that is NOT the last leaves the mark: "
         "lowering it would hand the later id out twice"),
        (_raised(lambda: db.remove_app(9)) == "TestIdFault",
         "removing what was never registered is refused"),
    ])
    shutil.rmtree(directory)
    _verdict(ok, "removal deletes the name; the number is retired.")


def test_tables():
    """The file round-trips, healing included."""
    directory = _place("test-parse.py", "test-other.py")
    db = _filled(directory)
    db.rename_app(0, "test-parser.py")

    print("--- the file, as stored ---")
    text = db.format()
    for line in text.splitlines():
        print("         | %s" % line)

    back     = TestIdDb(directory)
    stable_f = back.format() == text
    print("--- read back ---")
    print("INSPECT: byte-identical after a round trip: %s" % stable_f)
    print("         [0.1] decodes to %s" % str(back.name_of(TestRunId(0, 1))))

    ok = _check([
        (stable_f, "format(parse(format())) is the identity"),
        (back.run_id_of("test-parser.py", "deep") == TestRunId(0, 1),
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

    H = "##VUT-TEST-IDS 5\n"

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
        ("no version line",       good.replace("##VUT-TEST-IDS 5\n", "")),
        ("version 1, pair-interned",
         "##VUT-TEST-IDS 1\nT:1 . -|a|-\n"),
        ("version 2, pair-interned",
         "##VUT-TEST-IDS 2\nT:1 . a|-\n"),
        ("version 3, re-using, no mark",
         "##VUT-TEST-IDS 3\nA:1 a.py\n"),
        ("version 4, no generation",
         "##VUT-TEST-IDS 4\nN:1\nA:0 a.py\nN:0.0\n"),
        ("an app id that spells no number",
         H + "N:1\nA:x demo.py\nN:x.0\n"),
        ("an app id standing twice",
         H + "N:2\nA:1 a.py\nN:1.0\nA:1 b.py\n"),
        ("an app name standing twice",
         H + "N:3\nA:1 a.py\nN:1.0\nA:2 a.py\nN:2.0\n"),
        ("a choice under no registered app",
         H + "N:0\nC:1.1 basic\n"),
        ("a run id standing twice",
         H + "N:2\nA:1 a.py\nN:1.2\nC:1.1 x\nC:1.1 y\n"),
        ("a choice name standing twice",
         H + "N:2\nA:1 a.py\nN:1.3\nC:1.1 x\nC:1.2 x\n"),
        ("a line that names nothing",
         H + "N:2\nA:1\n"),
        ("a line that is no entry",
         H + "N:0\nZ:1 a.py\n"),
        ("no app mark at all",
         H + "A:0 a.py\nN:0.0\n"),
        ("an app mark standing twice",
         H + "N:1\nN:1\nA:0 a.py\nN:0.0\n"),
        ("an app without its choice mark",
         H + "N:1\nA:0 a.py\n"),
        ("a choice mark under no registered app",
         H + "N:1\nA:0 a.py\nN:0.0\nN:5.0\n"),
        ("an app id at its mark (would re-issue)",
         H + "N:0\nA:0 a.py\nN:0.0\n"),
        ("a run id at its mark (would re-issue)",
         H + "N:1\nA:0 a.py\nN:0.1\nC:0.1 x\n"),
        ("a mark that spells no number",
         H + "N:many\nA:0 a.py\nN:0.0\n"),
        ("a mark beyond the ceiling",
         H + "N:%i\n" % (ID_LIMIT + 1)),
        ("a generation that spells no number",
         H + "G:many\nN:1\nA:0 a.py\nN:0.0\n"),
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
        (gone == ((1, "test-other.py"),),
         "the register names the id and the name that left"),
        (db.run_id_of("test-other.py") == TestRunId(1, None),
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
        (any("[0.1] deep" in line for line in line_list),
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
            "retire":     test_retire,
            "tables":     test_tables,
            "faults":     test_faults,
            "vanished":   test_vanished,
            "face":       test_face,
        },
        happy      = "SUCCESS.*",
    ).run()
