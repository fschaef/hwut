#! /usr/bin/env python3
#
# @hwut {
#     title      = "hwut.cov end to end"
#     choices    = ["door", "run"]
#     eq-pattern = ["SUCCESS.*"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.cov' END TO END -- the demand through the real door, the
         real orchestrator, the real dispatcher, the real bookkeeper
         (coverage RATIONALE D-19, D-21).

    THE FIXTURE, one directory:

        suite/TEST/
            test-py.py         choices a, b -- a Python test whose
                               choice 'a' writes a witness artefact
                               and 'b' does not
            test-hang.py       choice x -- writes the artefact, then
                               sleeps and ends WITHOUT the terminal
                               token: it never testified. (The time
                               cap is lifted under coverage, D-19, so
                               it is not killed -- it merely does not
                               finish its statement.)
            test-new.py        no choices -- never accepted: NO
                               register entry, so no id
            GOOD/              nominals, and 'test_ids.dat' seeding
                               ids for test-py and test-hang

    The tool is the WITNESS reader, registered here and NAMED IN THE
    FIXTURE'S OWN 'hwut-root.conf' -- 'language-setup { python {
    coverage = ["witness"] } }' (coverage D-26, the one source) -- with
    a 'witness' executable placed on PATH so that election finds it. The
    run is deterministic on any machine: the chain is the unit, not a
    real coverage tool.

CHOICES: run, door;

run     'hwut.cov' over the directory: every registered choice is
        harvested or noted, the unregistered one runs plain; the book
        says which; the records carry the register's ids.
door    the same wish through 'hwut.run --coverage' says the same
        thing; a wish that asks for nothing is EMPTY; the verbs still
        answer.
______________________________________________________________________________
"""
import io
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import config                                                    # noqa F401
from vut.test_writing_support.python.script_runner import tree_boundary  # noqa: E402
from   config import HwutRunner                                  # noqa F401,E402

from   vut.services.cov import main as cov_main   # noqa E402
from   vut.services.run import main as run_main   # noqa E402
from   vut.engine.bookkeeper.api     import Bookkeeper          # noqa E402
from   vut.engine.bookkeeper.api     import TestIdDb            # noqa E402
from   vut.engine.coverage.api           import (CCoverageFramework,
                                                  CCoverageFormat, register, # noqa E402
                                                  record_of,
                                                  artifact_directory_of)
from   vut.engine.coverage.api           import unpack_record       # noqa E402
from   vut.engine.coverage.api           import format_record       # noqa E402
from   vut.engine.coverage.api    import CoverageConfig       # noqa E402

DEMAND = CoverageConfig()                   # what THIS RUN gathers; the tool
                                            # is the root conf's word (D-26)
ROOT_CONF = """\
hwut {
    language-setup {
        python { extensions  = [".py"]
                 interpreter = "python3"
                 coverage    = ["witness"] }
    }
}
"""

WITNESS_FILE = "witness.json"


class WitnessFormat(CCoverageFormat):
    """The witness file: which lines ran."""
    name = "witness-json"

    def read(self, work_dir, source_root, config=None):
        """RETURN: CoverageRecord of the witness file; None where none."""
        path = os.path.join(artifact_directory_of(work_dir), WITNESS_FILE)
        if not os.path.isfile(path): return None
        with io.open(path, encoding="utf-8") as fh:
            entry_db = json.load(fh)
        os.remove(path)          # one artefact per run, never inherited
        return record_of(self, "python",
                         ((p, e["executable"], e["covered"], None)
                          for p, e in entry_db.items()))


class WitnessFramework(CCoverageFramework):
    """A tool that measures by being asked to ('--witness')."""
    name   = "witness"
    format = WitnessFormat()

    def wrap(self, argv, config, work_dir):
        """RETURN: list of str, the call with '--witness' appended."""
        return list(argv) + ["--witness"]

    def report_argv(self, config, work_dir):
        """RETURN: None: no second call."""
        return None


register(WitnessFramework())

HEAD = '''\
#! /usr/bin/env python3
import json, os, sys
# @hwut { title = "%s" %s }
choice = [a for a in sys.argv[1:] if not a.startswith("--")]
choice = choice[0] if choice else None
if "--hwut-info" in sys.argv:
    print("%s;")%s; sys.exit(0)
def witness(lines):
    if "--witness" not in sys.argv: return
    os.makedirs(os.path.join("OUT", "COVERAGE"), exist_ok=True)
    with open(os.path.join("OUT", "COVERAGE", "witness.json"), "w") as fh:
        json.dump({"%s": {"executable": [1,2,3,4,5,6,7,8],
                          "covered": lines}}, fh)
'''


def script(title, choice_list, body, source):
    """RETURN: str, a fixture test application."""
    quoted = ", ".join('"%s"' % c for c in choice_list)
    stated = " choices = [%s]" % quoted if choice_list else ""
    info   = '; print("CHOICES: %s;")' % ", ".join(choice_list) \
             if choice_list else ""
    return HEAD % (title, stated, title, info, source) + body


def fixture():
    """RETURN: str, the fixture root, for the caller to remove."""
    root = tempfile.mkdtemp(prefix="vut_cov_e2e_")
    #  THE TREE'S BOUNDARY: every face ascends collecting
    #  'hwut.conf' until it meets this file; a tree without one
    #  is refused, so a fixture states its own.
    tree_boundary(root, ROOT_CONF)
    #  ELECTION ASKS THE SYSTEM whether a candidate can be launched:
    #  a 'witness' that can be found is what makes the table's word
    #  come true here.
    tool_dir = os.path.join(root, "bin")
    os.makedirs(tool_dir)
    with open(os.path.join(tool_dir, "witness"), "w") as fh:
        fh.write("#! /bin/sh\nexit 0\n")
    os.chmod(os.path.join(tool_dir, "witness"), 0o755)
    os.environ["PATH"] = tool_dir + os.pathsep + os.environ.get("PATH", "")
    test = os.path.join(root, "suite", "TEST")
    good = os.path.join(test, "GOOD")
    os.makedirs(good)

    def put(directory, name, content):
        path = os.path.join(directory, name)
        with open(path, "w") as fh:
            fh.write(content)
        if name.endswith(".py"): os.chmod(path, 0o755)

    put(test, "hwut.conf", 'hwut { }\n')
    put(test, "test-py.py", script("Py", ["a", "b"],
        'if choice == "a": witness([1,2,3])\n'
        'print("py " + choice)\nprint("<hwut-end>")\n', "py.py"))
    put(good, "test-py.py--a.txt", "py a\n<hwut-end>\n")
    put(good, "test-py.py--b.txt", "py b\n<hwut-end>\n")
    put(test, "test-hang.py", script("Hang", ["x"],
        'import time\nwitness([5,6])\nprint("hang x")\n'
        'sys.stdout.flush()\ntime.sleep(3)\n', "hang.py"))
    put(good, "test-hang.py--x.txt", "hang x\n<hwut-end>\n")
    put(test, "test-new.py", script("New", [],
        'witness([7,8])\nprint("new")\nprint("<hwut-end>")\n', "new.py"))
    put(good, "test-new.py.txt", "new\n<hwut-end>\n")

    #  The register: ids are born at accept; these were accepted.
    db = TestIdDb(test)
    for app, choice in (("test-py.py", "a"), ("test-py.py", "b"),
                        ("test-hang.py", "x")):
        db.run_id_of(app, choice, allocate_f=True)
    return root


def call(face, argument_list, root):
    """
    RETURN: int, the exit status. Prints the command line as an author
            writes it; the face's own stream is SILENCED here -- it is
            'hwut.run's and tested there -- and the book is shown instead.
    """
    shown = " ".join(argument_list)
    print("$ %s %s" % (face, shown) if shown else "$ %s" % face)
    sink   = []
    status = (cov_main if face == "hwut.cov" else run_main)(
        argument_list + ["--directory=%s" % root, "--silent"],
        sink.append, demand=DEMAND)
    print("    [status %d]" % status)
    return status


def show_book(root):
    """RETURN: dict, key -> coverage token; prints the book and the
    records, converted."""
    test = os.path.join(root, "suite", "TEST")
    keeper = Bookkeeper(test)
    token_db = {}
    print("    the book {")
    for key in ("test-py.py--a", "test-py.py--b", "test-hang.py--x",
                "test-new.py"):
        app, _, choice = key.partition("--")
        entry = keeper.result(app, choice or None)
        token = entry.get("coverage", "<absent>") if entry else "<no entry>"
        token_db[key] = token
        print("      %-14s report %-24s coverage %s"
              % (key, entry.get("report", "-") if entry else "-", token))
    print("    }")
    print("    the records {")
    for key in ("test-py.py--a", "test-py.py--b", "test-hang.py--x",
                "test-new.py"):
        app, _, choice = key.partition("--")
        path = keeper.coverage_path(app, choice or None)
        if not path.is_file():
            print("      %-14s <none>" % key); continue
        text = format_record(unpack_record(path.read_bytes()))
        print("      %-14s %s | %s" % (key, text.splitlines()[1].strip(),
                                       text.splitlines()[-1]))
    print("    }")
    return token_db


def check(pair_list):
    """RETURN: True, every claim held; False, at least one did not."""
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def verdict(ok, sentence):
    """RETURN: None. The one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


def test_run():
    """The demand over the whole directory."""
    root = fixture()
    status   = call("hwut.cov", [], root)
    token_db = show_book(root)
    test = os.path.join(root, "suite", "TEST")
    a_path = Bookkeeper(test).coverage_path("test-py.py", "a")
    a_rec  = unpack_record(a_path.read_bytes()) if a_path.is_file() else None

    ok = check([
        (token_db["test-py.py--a"] == "ok",
         "a registered choice that left an artefact: harvested"),
        (a_rec is not None and str(next(iter(a_rec.run))) == "0.0",
         "and its record carries the REGISTER's id, not a name"),
        (token_db["test-py.py--b"] == "no-data-provided",
         "a registered choice that left none: noted, no record"),
        (token_db["test-hang.py--x"] == "run-incomplete",
         "a run that ended without '<hwut-end>' did not testify: not "
         "harvested, though it left an artefact"),
        (token_db["test-new.py"] == "<absent>",
         "an unregistered test ran plain: no id, no key, no record"),
        (status == 1,
         "the exit status is the run's: the unfinished test failed"),
    ])
    shutil.rmtree(root)
    verdict(ok, "the demand shapes every run; the book says what each "
                "one bore.")


def test_door():
    """The same demand through hwut.run; the verbs; the empty wish."""
    root = fixture()
    call("hwut.run", ["--coverage", "--glob", "test-py*"], root)
    token_db = show_book(root)
    empty   = call("hwut.cov", ["--glob", "nothing-matches*"], root)
    shutil.rmtree(root)

    ok = check([
        (token_db["test-py.py--a"] == "ok"
         and token_db["test-hang.py--x"] == "<no entry>",
         "'hwut.run --coverage' with a wish is the same demand, "
         "the wish honoured"),
        (empty == 3,
         "a wish that asks for nothing is EMPTY, as hwut.run says"),
    ])
    verdict(ok, "one door, one demand, two spellings of the command.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "hwut.cov end to end",
        choice_map = {
            "run":  test_run,
            "door": test_door,
        },
        happy      = "SUCCESS.*",
    ).run()
