#! /usr/bin/env python3
#
# @hwut {
#     title      = "hwut.play: shows and forgets, or saves the candidate"
#     choices    = ["accept_runs", "entrance", "forgets", "save"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

'hwut.play' THROUGH THE ONE CHANNEL (operations disc-2, services E-40).

    forgets    a bare play renders and writes NOTHING: no candidate, no
               book entry, no register entry.
    save       '--save' hands the subjects to the channel's 'record()':
               the candidates stand in the store; still no verdict, no
               book entry.
    entrance   A NEW TEST'S WAY IN: 'hwut.play --save', then
               'hwut.accept --yes' -- and a nominal stands in GOOD/.
               Nothing in between asked 'hwut.run'.
    accept_runs  the text changed after the save: 'hwut.accept' does
               not refuse, it RUNS the case through the channel, says
               so ('RUN: ...'), and blesses what the NEW text printed
               (E-39's NOT DONE, closed by E-40).
______________________________________________________________________________
"""
import io
import os
import shutil
import sys
import tempfile
import contextlib

import config                                                    # noqa F401
from vut.test_writing_support.python.script_runner import tree_boundary  # noqa: E402
from   config import HwutRunner                                  # noqa F401,E402

from   vut.services.play   import main as play_main              # noqa E402
from   vut.services.accept import main as accept_main            # noqa E402
from   vut.engine.bookkeeper.api import Bookkeeper, Store, TestIdDb  # noqa E402

ROOT_CONF = """\
hwut {
    language-setup {
        python { extensions  = [".py"]
                 interpreter = "python3" }
    }
}
"""

SCRIPT = '''\
#! /usr/bin/env python3
# @hwut { title = "New" }
print("hello from new")
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


def fixture():
    """RETURN: (str, str), the tree root and its TEST directory holding
    ONE new test application with no GOOD, no book, no register."""
    root = tempfile.mkdtemp(prefix="vut_play_")
    tree_boundary(root, ROOT_CONF)
    test = os.path.join(root, "suite", "TEST")
    os.makedirs(test)
    with open(os.path.join(test, "hwut.conf"), "w") as fh:
        fh.write("hwut { }\n")
    path = os.path.join(test, "test-new.py")
    with open(path, "w") as fh:
        fh.write(SCRIPT)
    os.chmod(path, 0o755)
    return root, test


def _play(test, *extra):
    """RETURN: (E_ExitCode, str), the status and what the face wrote
    (its own lines AND the rendering it sends to stdout)."""
    line_list = []
    sink      = io.StringIO()
    with contextlib.redirect_stdout(sink):
        status = play_main(["test-new.py", "--plain",
                            "--directory=%s" % test] + list(extra),
                           write=line_list.append)
    return status, "\n".join(line_list) + sink.getvalue()


def _state(test):
    """RETURN: dict, what stands on disk after a face ran."""
    store = Store(Bookkeeper(test))
    return {
        "candidate": store.candidate_path("test-new.py", None,
                                          "stdout").exists(),
        "nominal":   store.nominal_path("test-new.py", None,
                                        "stdout").exists(),
        "booked":    "test-new.py" in Bookkeeper(test).tests(),
        "registered": TestIdDb(test).run_id_of("test-new.py") is not None,
    }


def test_forgets():
    """A bare play renders and writes nothing."""
    root, test = fixture()
    status, text = _play(test)
    state = _state(test)
    print("  rendered 'hello from new': %s" % ("hello from new" in text))
    ok = _check([
        (status.value == 0, "status OK"),
        ("hello from new" in text, "the subject is rendered"),
        (not state["candidate"], "no candidate written"),
        (not state["booked"], "no book entry"),
        (not state["registered"], "no register entry"),
    ])
    shutil.rmtree(root, ignore_errors=True)
    _verdict(ok, "play shows and forgets.")


def test_save():
    """'--save' stores the candidates and nothing else."""
    root, test = fixture()
    status, text = _play(test, "--save")
    state = _state(test)
    saved_line = [l for l in text.splitlines() if l.startswith("SAVED:")]
    print("  %s" % (saved_line[0] if saved_line else "(no SAVED line)"))
    ok = _check([
        (status.value == 0, "status OK"),
        (bool(saved_line), "the face says what it saved"),
        (state["candidate"], "the candidate stands in the store"),
        (not state["nominal"], "no nominal: play blesses nothing"),
        (not state["booked"], "no book entry: play judges nothing"),
    ])
    shutil.rmtree(root, ignore_errors=True)
    _verdict(ok, "--save records the candidate, and only that.")


def test_entrance():
    """play --save, then accept --yes: a nominal, a book entry, a
    register entry -- without one 'hwut.run'."""
    root, test = fixture()
    _play(test, "--save")
    line_list = []
    status = accept_main(["test-new.py", "--yes",
                          "--directory=%s" % test],
                         write=line_list.append)
    for line in line_list:
        if line.startswith(("RUN:", "REFUSED", "NOTE")): print("  " + line)
    state = _state(test)
    nominal = Store(Bookkeeper(test)).nominal_path("test-new.py", None,
                                                   "stdout")
    ok = _check([
        (status.value == 0, "accept status OK"),
        (not any(l.startswith("RUN:") for l in line_list),
         "accept did not need to run: the saved candidate was current"),
        (state["nominal"], "a nominal stands in GOOD/"),
        (nominal.read_text().startswith("hello from new"),
         "and it is what the application printed"),
        (state["registered"], "the register has the test"),
    ])
    shutil.rmtree(root, ignore_errors=True)
    _verdict(ok, "a new test enters by play --save, then accept.")


def test_accept_runs():
    """The source changed after the save: accept runs, says so, and
    blesses the new text's output."""
    root, test = fixture()
    _play(test, "--save")
    import time; time.sleep(0.05)
    path = os.path.join(test, "test-new.py")
    with open(path, "w") as fh:
        fh.write(SCRIPT.replace("hello from new", "hello, changed"))
    os.utime(path, None)
    line_list = []
    status = accept_main(["test-new.py", "--yes",
                          "--directory=%s" % test],
                         write=line_list.append)
    run_line = [l for l in line_list if l.startswith("RUN:")]
    print("  %s" % (run_line[0].split("   ")[0] if run_line
                    else "(no RUN line)"))
    nominal = Store(Bookkeeper(test)).nominal_path("test-new.py", None,
                                                   "stdout")
    ok = _check([
        (status.value == 0, "accept status OK"),
        (len(run_line) == 1, "accept said it ran, once"),
        (run_line and "(A.1)" in run_line[0],
         "and named the step that decided"),
        (nominal.exists() and
         nominal.read_text().startswith("hello, changed"),
         "the nominal is the NEW text's output"),
    ])
    shutil.rmtree(root, ignore_errors=True)
    _verdict(ok, "a stale candidate is re-run by accept, not refused.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "hwut.play: shows and forgets, or saves the candidate",
        choice_map = {
            "accept_runs": test_accept_runs,
            "entrance": test_entrance,
            "forgets":  test_forgets,
            "save":     test_save,
        }).run()
