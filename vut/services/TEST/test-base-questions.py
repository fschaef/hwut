#! /usr/bin/env python3
#
# @hwut {
#     title      = "The base questions: --fail, --pass, --since, --until"
#     choices    = ["asked", "fail", "never_run", "pass", "until"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE BASE QUESTIONS -- the wishes that can only be answered out of the
Bookkeeper's base or this machine's observations (E-1's 'asks_base_f'):
'--fail', '--pass', '--since', '--until', '--faster-than'.

    asked      every one of them SELECTS: the face answers, and no
               question raises. This is the regression: 'task_list_
               query' handed 'Bookkeeper.result()' an OPERATION as a
               third argument, which it has never taken, so every
               base question died in a TypeError before a single case
               was judged.
    fail       '--fail' runs what the book last recorded as failing,
               and nothing else.
    pass       '--pass' is its complement.
    until      the clock is STATED (E-80); '--until' alone among them wants the test the book has
               never seen: never run is older than every point.
    never_run  '--fail' and '--pass' do NOT want it: a case with no
               verdict has no verdict to match.

THE OPERATION NAMES AN OBSERVATION, NEVER A DECISION (E-36). The book
answers what the software IS -- a verdict for a (test, choice) -- and
knows no operation; the local database records what THIS MACHINE SAW,
per operation, and is reached through 'observation_of_case' alone.
______________________________________________________________________________
"""
import io
import os
import shutil
import sys
import contextlib

import config                                                    # noqa F401
from vut.test_writing_support.python.script_runner import tree_boundary  # noqa: E402
from   config import HwutRunner                                  # noqa F401,E402

from   vut.services.run import main as run_main                  # noqa E402

ROOT_CONF = """\
hwut {
    language-setup {
        python { extensions  = [".py"]
                 interpreter = "python3" }
    }
}
"""

#  'test-good.py' passes, 'test-bad.py' fails, 'test-fresh.py' has a
#  nominal but the book has never seen it.
SCRIPT = '''\
#! /usr/bin/env python3
# @hwut { title = "%s" }
print("%s")
print("<hwut-end>")
'''


def _check(pair_list):
    """RETURN: True, every claim held; False, at least one did not."""
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def _verdict(ok, sentence):
    """RETURN: None. Prints the one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


def fixture(first_run_f=True):
    """
    RETURN: (str, str), the tree root and its TEST directory.

    Three accepted tests; 'test-bad.py' is edited AFTER acceptance so
    its nominal no longer matches. With 'first_run_f' a run has
    happened, so the book holds a verdict for two of them and none for
    'test-fresh.py', which is added afterwards.
    """
    root = tempfile_mkdtemp()
    tree_boundary(root, ROOT_CONF)
    test = os.path.join(root, "suite", "TEST")
    good = os.path.join(test, "GOOD")
    os.makedirs(good)

    def put(directory, name, content, executable_f=False):
        path = os.path.join(directory, name)
        with open(path, "w") as fh: fh.write(content)
        if executable_f: os.chmod(path, 0o755)

    put(test, "hwut.conf", "hwut { }\n")
    put(test, "test-good.py", SCRIPT % ("Good", "good"), True)
    put(good, "test-good.py.txt", "good\n<hwut-end>\n")
    put(test, "test-bad.py", SCRIPT % ("Bad", "bad"), True)
    put(good, "test-bad.py.txt", "SOMETHING ELSE\n<hwut-end>\n")
    if first_run_f: _run(root)
    #  ADDED AFTER THE RUN: accepted (a nominal stands), and the book
    #  has never seen it.
    put(test, "test-fresh.py", SCRIPT % ("Fresh", "fresh"), True)
    put(good, "test-fresh.py.txt", "fresh\n<hwut-end>\n")
    return root, test


def tempfile_mkdtemp():
    """RETURN: str, a fresh directory for one fixture."""
    import tempfile
    return tempfile.mkdtemp(prefix="vut_base_")


def _run(root, *extra):
    """
    RETURN: (E_ExitCode, list[str]), the status and the rendering.

    The face's own stderr is swallowed: FAULT and NOTE are the log's
    (the flow), and this test judges the SELECTION.
    """
    line_list = []
    sink      = io.StringIO()
    with contextlib.redirect_stderr(sink):
        status = run_main(["--directory=%s" % root, "--plain"]
                          + list(extra),
                          write=line_list.append,
                          write_error=lambda _line: None)
    return status, line_list


def _selected(line_list):
    """RETURN: set[str], the test files that appear as flow lines --
    what the wish selected, whatever its verdict."""
    result = set()
    for line in line_list:
        for name in ("test-good.py", "test-bad.py", "test-fresh.py"):
            if name in line and ("[OK]" in line or "[FAIL]" in line):
                result.add(name)
    return result


def test_asked():
    """Every base question answers; none of them raises."""
    root, _ = fixture()
    outcome = []
    for wish in ("--fail", "--pass", "--since=1h", "--until=1h",
                 "--faster-than=100000"):
        try:
            status, _ = _run(root, wish)
            outcome.append((wish, "status %d" % status.value))
        except Exception as error:                       # noqa BLE001
            outcome.append((wish, "%s: %s" % (type(error).__name__, error)))
    for wish, said in outcome: print("  %-22s %s" % (wish, said))
    ok = _check([
        (all("status" in said for _, said in outcome),
         "every base question answers, none raises"),
    ])
    shutil.rmtree(root, ignore_errors=True)
    _verdict(ok, "the base questions are asked, and answered.")


def test_fail():
    """'--fail' selects what the book recorded as failing."""
    root, _ = fixture()
    _, line_list = _run(root, "--fail")
    selected = _selected(line_list)
    print("  selected: %s" % ", ".join(sorted(selected)) or "(none)")
    ok = _check([
        ("test-bad.py" in selected, "the failing case is selected"),
        ("test-good.py" not in selected, "the passing one is not"),
    ])
    shutil.rmtree(root, ignore_errors=True)
    _verdict(ok, "--fail selects what last failed.")


def test_pass():
    """'--pass' is the complement."""
    root, _ = fixture()
    _, line_list = _run(root, "--pass")
    selected = _selected(line_list)
    print("  selected: %s" % ", ".join(sorted(selected)) or "(none)")
    ok = _check([
        ("test-good.py" in selected, "the passing case is selected"),
        ("test-bad.py" not in selected, "the failing one is not"),
    ])
    shutil.rmtree(root, ignore_errors=True)
    _verdict(ok, "--pass selects what last passed.")


def test_never_run():
    """A case the book has never seen matches neither verdict."""
    root, _ = fixture()
    _, fail_lines = _run(root, "--fail")
    _, pass_lines = _run(root, "--pass")
    ok = _check([
        ("test-fresh.py" not in _selected(fail_lines),
         "--fail does not want a case with no verdict"),
        ("test-fresh.py" not in _selected(pass_lines),
         "--pass does not want it either"),
    ])
    shutil.rmtree(root, ignore_errors=True)
    _verdict(ok, "no verdict is no match for a verdict question.")


def test_until():
    """'--until' alone wants the case the book has never seen -- and
    the recorded cases exactly where the clock puts them.

    THE CLOCK IS STATED (auxiliary/clock, E-80): the fixture's run is
    recorded at T, and each question is asked at an instant this test
    chooses. Nothing here waits, and nothing here flips at a second's
    or an hour's boundary -- the recorded page was measured to do so
    when the run and the question read the wall clock separately.
    """
    from datetime import datetime, timedelta, timezone
    from vut.auxiliary import clock
    T = datetime(2026, 9, 16, 11, 59, 59, tzinfo=timezone.utc)
    print("  the run is recorded at            %s" % T.isoformat())
    #  EVERY QUESTION IS ALSO A RUN ('hwut.run' records what it selects),
    #  so each is asked of a FRESH fixture recorded at T -- which is the
    #  mechanism of the flip: a page that asked twice depended on where
    #  the first answer's second fell.
    outcome = []
    try:
        for label, later, spec in (
            ("asked in the same second", 0,    "--until=1s"),
            ("asked one second later",   1,    "--until=1s"),
            ("asked two seconds later",  2,    "--until=1s"),
            ("across the hour",          1,    "--until=1h"),
            ("an hour and a second on",  3601, "--until=1h"),
        ):
            clock.state(T)
            root, _ = fixture()
            clock.state(T + timedelta(seconds=later))
            _, line_list = _run(root, spec)
            selected = _selected(line_list)
            shutil.rmtree(root, ignore_errors=True)
            print("  %-26s %-11s selected: %s"
                  % (label, spec, ", ".join(sorted(selected)) or "(none)"))
            outcome.append((label, selected))
        ok = _check([
            ("test-fresh.py" in outcome[0][1],
             "never run is older than every point: --until wants it"),
            (not {"test-good.py", "test-bad.py"} & outcome[0][1],
             "a run in this very second does not lie BEFORE now-1s"),
            (not {"test-good.py", "test-bad.py"} & outcome[1][1],
             "at now-1s the run lies ON the point, not before it"),
            ({"test-good.py", "test-bad.py"} <= outcome[2][1],
             "two seconds on, the run lies before now-1s"),
            (not {"test-good.py", "test-bad.py"} & outcome[3][1],
             "an hour's point is not crossed by a second"),
            ({"test-good.py", "test-bad.py"} <= outcome[4][1],
             "an hour and a second on, it is"),
            (all("test-fresh.py" in each for _, each in outcome),
             "the never-run case is wanted whatever the clock says"),
        ])
    finally:
        clock.release()
    _verdict(ok, "--until is answered by the clock, and the clock is stated.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The base questions: --fail, --pass, --since, --until",
        choice_map = {
            "asked":     test_asked,
            "fail":      test_fail,
            "never_run": test_never_run,
            "pass":      test_pass,
            "until":     test_until,
        }).run()
