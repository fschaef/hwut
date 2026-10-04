#! /usr/bin/env python3
#
# @hwut {
#     title      = "hwut.cov.run end to end"
#     choices    = ["door", "output", "real", "run", "trace"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.cov.run' END TO END -- the coverage run through the real
         door, the real orchestrator and its own dispatcher (coverage
         RATIONALE D-19, D-21, D-38).

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
            GOOD/              nominals, and the book's register seeding
                               ids for test-py and test-hang

    The tool is the WITNESS reader, registered here and NAMED IN THE
    FIXTURE'S OWN 'hwut-root.conf' -- 'language-setup { python {
    coverage = ["witness"] } }' (coverage D-26, the one source) -- with
    a 'witness' executable placed on PATH so that election finds it. The
    run is deterministic on any machine: the chain is the unit, not a
    real coverage tool.

CHOICES: run, real, door, trace, output;

run     'hwut.cov.run' over the directory: one line per case says
        '[REC]' or why none stands; the one the register lacks is
        NOT MEASURED; 'GOOD/book.csv' does not move by a byte; the
        output names the test run that left a record.
real    THE REAL TOOL, coverage.py, through the face: no stand-in. The
        tool runs the script itself (D-39); each choice's record holds
        the lines THAT choice reached. Needs 'coverage' on PATH.
trace   the coverage run leaves a LOCAL TRACE under 'TMP/'
        ('hwut-traces-coverage.csv', D-41): one row per case it ran;
        a later run replaces the rows of the cases it selects and
        keeps the others; 'hwut.help' explains from it; no tracked
        file moves.
output  the output directory (D-42): the test run ids, the groups of
        test runs, one coverage file per source file with every
        covered range annotated by who executed it; no per-case record
        left behind; the directory emptied at every start; a directory
        of somebody else's files refused; no '-o' and nobody to ask
        refused.
door    'hwut.run' does not take '--coverage' (D-38); a wish narrows
        the coverage run; a wish that asks for nothing is EMPTY.
______________________________________________________________________________
"""
import io
import json
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import config                                                    # noqa F401
from vut.test_writing_support.python.script_runner import tree_boundary  # noqa: E402
from   config import HwutRunner                                  # noqa F401,E402

from   vut.services.lib.cov.run import main as cov_main   # noqa E402
from   vut.services.lib.cov.conv.to_humans import main as humans_main  # noqa E402
from   vut.services.run import main as run_main   # noqa E402
from   vut.engine.bookkeeper.api     import Bookkeeper          # noqa E402
from   vut.engine.bookkeeper.api     import Bookkeeper          # noqa E402
from   vut.engine.coverage.api           import (CCoverageFramework,
                                                  CCoverageFormat, register, # noqa E402
                                                  record_of,
                                                  artifact_directory_of)
from   vut.engine.coverage.api           import Output, OutputRefused  # noqa E402
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

    call_scheme = "python3 {test} --witness {choice}"

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

    #  The register: ids are born at accept; these WERE ACCEPTED, so
    #  say so the way the face does -- 'note_accept' issues the id in
    #  the acceptance's own act (E-41). Issuing an id alone would leave
    #  an ASPIRANT row beside a standing nominal (B-14), which is the
    #  stale state sanitize reports, not the state this fixture means.
    db = Bookkeeper(test)
    for app, choice in (("test-py.py", "a"), ("test-py.py", "b"),
                        ("test-hang.py", "x")):
        db.note_accept(app, choice)
    return root


def call(face, argument_list, root, no_output_f=False):
    """
    RETURN: int, the exit status. Prints the command line as an author
            writes it. The coverage run's own stream is SHOWN -- it is
            this face's; 'hwut.run's is silenced, being tested there.
    """
    if face == "hwut.cov.run" and "-o" not in argument_list \
       and "--dont-ask" not in argument_list and not no_output_f:
        #  THE OUTPUT DIRECTORY: where every choice below reads what
        #  the run gathered.
        argument_list = argument_list + ["-o", "<out>"]
    shown = " ".join(argument_list).replace(root, "<root>")
    print("$ %s %s" % (face, shown) if shown else "$ %s" % face)
    argument_list = [os.path.join(root, "out") if word == "<out>" else word
                     for word in argument_list]
    sink = []
    if face == "hwut.cov.run":
        #  '--jobs=1': one line per case, in plan order, on any machine.
        status = cov_main(argument_list + ["--directory=%s" % root,
                                           "--jobs=1"],
                          sink.append, demand=DEMAND)
        #  THE DURATIONS ARE THE MACHINE'S, not the subject's (O-30).
        for line in "\n".join(sink).splitlines():
            line = re.sub(r"\d\d:\d\d:\d\d", "<h:m:s>", line)
            line = re.sub(r"[0-9.]+ \[sec\]", "<s> [sec]", line)
            line = line.replace(root, "<root>")
            print("    | %s" % line.rstrip())
    else:
        status = run_main(argument_list + ["--directory=%s" % root,
                                           "--silent"],
                          sink.append)
    print("    [status %d]" % status)
    return status


def book_bytes(root):
    """RETURN: bytes, 'GOOD/book.csv' of the fixture's directory as it
    stands."""
    with open(os.path.join(root, "suite", "TEST", "GOOD", "book.csv"),
              "rb") as fh:
        return fh.read()


def show_book(root):
    """RETURN: dict, key -> coverage token of the book; prints the
    book's rows."""
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
    return token_db


def shown(path):
    """RETURN: str, the file as a person reads it: a coverage file of the
    output directory (binary, D-43) through 'hwut.cov.conv.to_humans',
    the tables as they stand."""
    if not path.endswith(".cover"):
        with open(path, encoding="utf-8") as handle: return handle.read()
    chunk_list = []
    humans_main([path], lambda line: chunk_list.append(
                    (line + "\n").encode("utf-8")),
                write_bytes=chunk_list.append)
    return b"".join(chunk_list).decode("utf-8")


def show_output(root):
    """RETURN: (list of str, Output | None), the files under the output
    directory, relative and sorted, and the output read; prints the
    files and every table and coverage file as it stands."""
    out = os.path.join(root, "out")
    found = sorted(os.path.relpath(os.path.join(d, name), out)
                   for d, _, name_list in os.walk(out)
                   for name in name_list)
    print("    <out> { %s }" % ", ".join(found))
    for name in found:
        if name == "hwut-coverage.marker": continue
        print("      -- %s" % name)
        for line in shown(os.path.join(out, name)).splitlines():
            print("      | %s" % line)
    try:                  return found, Output(out)
    except OutputRefused: return found, None


def per_case_list(root):
    """RETURN: list of str, the per-case records standing in the
    fixture's 'TMP/store', sorted."""
    store = os.path.join(root, "suite", "TEST", "TMP", "store")
    return sorted(name for name in os.listdir(store)
                  if name.endswith(".cover")) if os.path.isdir(store) \
           else []


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
    """The coverage run over the whole directory."""
    root     = fixture()
    before   = book_bytes(root)
    status   = call("hwut.cov.run", [], root)
    after    = book_bytes(root)
    token_db = show_book(root)
    found, output = show_output(root)
    run_db = {} if output is None else output.run_db

    ok = check([
        (run_db == {("suite/TEST", "test-py.py", "a"): "00"},
         "a registered choice that left an artefact is the ONE test run "
         "of the output"),
        ("suite/TEST/py.py.cover" in found,
         "and the source it reached has its coverage file, under its "
         "path from the root"),
        (per_case_list(root) == [],
         "no per-case record is left in 'TMP/store'"),
        (before == after,
         "'GOOD/book.csv' did not move by a byte"),
        (set(token_db.values()) <= {"<absent>", "<no entry>"},
         "and holds no coverage token"),
        (status == 1,
         "the exit status says a case is without a record"),
    ])
    shutil.rmtree(root)
    verdict(ok, "the tool runs the application; the output directory "
                "is the whole product.")


def test_door():
    """'hwut.run' has no coverage door; the wish; the empty wish."""
    root    = fixture()
    refused = call("hwut.run", ["--coverage", "--glob", "test-py*"], root)
    wished  = call("hwut.cov.run", ["--glob", "test-py*"], root)
    _, output = show_output(root)
    run_db  = {} if output is None else output.run_db
    empty   = call("hwut.cov.run", ["--glob", "nothing-matches*"], root)

    ok = check([
        (refused == 2,
         "'hwut.run --coverage' is REFUSED: the test run measures no "
         "coverage"),
        (wished == 1
         and list(run_db) == [("suite/TEST", "test-py.py", "a")],
         "'hwut.cov.run' with a wish runs what the wish names, and "
         "nothing else"),
        (empty == 3,
         "a wish that asks for nothing is EMPTY, as hwut.run says"),
    ])
    shutil.rmtree(root)
    verdict(ok, "one door for coverage, and it is not the test run's.")


REAL_APP = '''\
#! /usr/bin/env python3
# @hwut { title = "Real" choices = ["one", "two"] }
import sys
def one():
    print("one")
def two():
    print("two")
{"one": one, "two": two}[sys.argv[1]]()
print("<hwut-end>")
if sys.argv[1] == "one":
    pass
else:
    pass
'''


def test_real():
    """coverage.py itself, run by the face over a two-choice script."""
    root = tempfile.mkdtemp(prefix="vut_cov_real_")
    tree_boundary(root, ROOT_CONF.replace('"witness"', '"coverage"'))
    test = os.path.join(root, "suite", "TEST")
    good = os.path.join(test, "GOOD")
    os.makedirs(good)
    for name, content in (("hwut.conf", "hwut { }\n"),
                          ("test-real.py", REAL_APP)):
        with open(os.path.join(test, name), "w") as fh: fh.write(content)
    os.chmod(os.path.join(test, "test-real.py"), 0o755)
    keeper = Bookkeeper(test)
    for choice in ("one", "two"):
        with open(os.path.join(good, "test-real.py--%s.txt" % choice),
                  "w") as fh:
            fh.write("%s\n<hwut-end>\n" % choice)
        keeper.note_accept("test-real.py", choice)

    status = call("hwut.cov.run", [], root)
    _, output = show_output(root)
    covered_db = {}
    for choice in ("one", "two"):
        found = None if output is None \
                else output.of_run("suite/TEST", "test-real.py", choice)
        if not found:
            print("    %s: <nothing>" % choice); continue
        covered_db[choice] = {line for source, reached, _ in found
                                   if source == "suite/TEST/test-real.py"
                                   for begin, end in reached
                                   for line in range(begin, end)}
        print("    %s: covered lines %s"
              % (choice, sorted(covered_db[choice])))
    branch_db = {}
    for choice in ("one", "two"):
        found = None if output is None \
                else output.measures_of_run("suite/TEST", "test-real.py",
                                            choice)
        branch_db[choice] = dict(found or ()).get(
            "suite/TEST/test-real.py", {}).get("branch")
        print("    %s: branch points %s" % (choice, branch_db[choice]))
    shutil.rmtree(root)

    one, two = covered_db.get("one", set()), covered_db.get("two", set())
    ok = check([
        (status == 0, "every case left a record"),
        (5 in one and 7 not in one,
         "choice 'one' reached the body of 'one()' and not of 'two()'"),
        (7 in two and 5 not in two,
         "choice 'two' reached the body of 'two()' and not of 'one()'"),
        (output is not None and len(output.group_db) == 1,
         "the lines both reached stand under ONE group of the two"),
        (branch_db.get("one") == ((10, 1, 2),)
         and branch_db.get("two") == ((10, 2, 2),),
         "the decision both reached has two arms, and each choice took "
         "its own: the output carries which"),
    ])
    verdict(ok, "the real tool runs the script; the output says which "
                "test run reached which lines.")


def show_trace(root):
    """RETURN: str, the trace file's text; prints it."""
    path = os.path.join(root, "suite", "TEST", "TMP",
                        "hwut-traces-coverage.csv")
    text = open(path).read() if os.path.isfile(path) else "<none>\n"
    print("    TMP/hwut-traces-coverage.csv {")
    for line in text.splitlines(): print("      %s" % line)
    print("    }")
    return text


def test_trace():
    """The local trace, its replacement by key, and 'hwut.help'."""
    from vut.services.help import main as help_main
    root   = fixture()
    before = book_bytes(root)
    call("hwut.cov.run", ["--silent"], root)
    first = show_trace(root)

    print("$ hwut.help")
    sink   = []
    status = help_main(["--directory=%s" % root], sink.append)
    for line in sink: print("    | %s" % line.rstrip())
    print("    [status %d]" % status)

    #  'b' now leaves its witness: the next run of THAT choice alone
    #  replaces its row and keeps the others.
    path = os.path.join(root, "suite", "TEST", "test-py.py")
    text = open(path).read().replace('if choice == "a": witness',
                                     'if choice in ("a", "b"): witness')
    with open(path, "w") as fh: fh.write(text)
    call("hwut.cov.run", ["test-py.py", "b", "--silent"], root)
    second = show_trace(root)
    after  = book_bytes(root)
    shutil.rmtree(root)

    ok = check([
        ("test-py.py;a;ok" in first and ";b;no-data-provided" in first
         and "test-hang.py;x;run-incomplete" in first
         and "test-new.py;;not-registered" in first,
         "one row per case the run was asked for: 'ok', or the token"),
        (status == 0 and any("CONCERNED:" in line for line in sink),
         "'hwut.help' explains the cases without a record, from the "
         "trace"),
        (";b;ok" in second and "test-hang.py;x;run-incomplete" in second,
         "a later run replaces the rows it selects and keeps the rest"),
        (before == after,
         "'GOOD/book.csv' did not move by a byte"),
    ])
    verdict(ok, "the trace says what the last coverage run came to; "
                "the record stays the product.")


def test_output():
    """The output directory, the gathering, and what is refused."""
    root = fixture()
    #  'b' leaves its witness too, other lines than 'a': a range both
    #  reach, and one each reaches alone.
    path = os.path.join(root, "suite", "TEST", "test-py.py")
    text = open(path).read().replace(
        'if choice == "a": witness([1,2,3])',
        'witness([1,2,3] if choice == "a" else [3,4,5])')
    with open(path, "w") as fh: fh.write(text)

    call("hwut.cov.run", ["-o", "<out>", "--silent"], root)
    first, output = show_output(root)
    left = per_case_list(root)
    print("    per-case records: %s" % (left or "none"))
    covered = [] if output is None else \
              [(reference, sorted(output.run_set_of(reference)), ranges)
               for _, _, by in output.source_iterable()
               for reference, ranges in by]

    call("hwut.cov.run", ["test-py.py", "a", "-o", "<out>", "--silent"],
         root)
    second, narrowed = show_output(root)

    foreign = os.path.join(root, "mine")
    os.makedirs(foreign)
    with open(os.path.join(foreign, "notes.txt"), "w") as fh: fh.write("x")
    refused = call("hwut.cov.run", ["-o", foreign, "--silent"], root)
    nobody  = call("hwut.cov.run", ["--silent"], root, no_output_f=True)
    untouched_f = os.path.isfile(os.path.join(foreign, "notes.txt"))
    shutil.rmtree(root)

    ok = check([
        (first == ["hwut-coverage.marker", "suite/TEST/py.py.cover",
                   "test_run_group_id_db.csv", "test_run_id_db.csv"],
         "the two tables, one coverage file per source file, and the "
         "marker"),
        (output is not None
         and output.run_db == {("suite/TEST", "test-py.py", "a"): "00",
                               ("suite/TEST", "test-py.py", "b"): "01"},
         "every test run that left a record has its id"),
        (covered == [("00", ["00"], ((1, 3),)),
                     ("01", ["01"], ((4, 6),)),
                     ("10", ["00", "01"], ((3, 4),))],
         "a range one run executed carries that run's id; the range "
         "both executed carries a GROUP id, and the group names both"),
        (left == [],
         "no per-case record is left behind"),
        (narrowed is not None and list(narrowed.run_db.values()) == ["00"]
         and "test_run_id_db.csv" in second,
         "the output directory holds exactly the last run: emptied at "
         "the start, the narrowed run alone in it"),
        (refused == 2 and untouched_f,
         "a directory holding files and no marker is REFUSED, and "
         "left as it stands"),
        (nobody == 2,
         "no '-o' and nobody to ask: REFUSED"),
    ])
    verdict(ok, "coverage is gathered into one place that holds one "
                "run, every covered range with who executed it.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "hwut.cov.run end to end",
        choice_map = {
            "run":  test_run,
            "real": test_real,
            "output": test_output,
            "trace": test_trace,
            "door": test_door,
        },
        happy      = "SUCCESS.*",
    ).run()
