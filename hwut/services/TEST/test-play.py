#! /usr/bin/env python3
#
# @hwut {
#     title      = "hwut.play: shows and records"
#     features   = ["play-save"]
#     choices {
#         accept_hints { features = ["accept-names-recording"] }
#         entrance    { features = ["play-save", "accept-whole"] }
#         records     { features = ["play-reading", "play-save"] }
#     }
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

'hwut.play' THROUGH THE ONE CHANNEL (operations disc-2, services E-40).

    records    play renders AND records (services E-165): the subjects go
               to the channel's 'record()', the candidate stands, the
               freshness sidecar says 'by: hwut.play'; still no nominal,
               no verdict, no book entry. MEASURED 2026-10-22 before:
               a bare play wrote nothing; '--save' recorded.
    entrance   A NEW TEST'S WAY IN: 'hwut.play', then
               'hwut.accept --force' -- and a nominal stands in GOOD/.
               Nothing in between asked 'hwut.run'.
    accept_hints the text changed after the play: 'hwut.accept' RUNS
               NOTHING (E-165) -- it blesses the recording as it stands,
               names it ('RECORDING: ... by hwut.play, <when>') and says
               that the source changed since. MEASURED 2026-10-22
               before (E-40): accept ran the case, 'RUN: ...', and
               blessed the new text's output.
______________________________________________________________________________
"""
import io
import os
import shutil
import sys
import tempfile
import contextlib

import config                                                    # noqa F401
from hwut.test_writing_support.python.script_runner import tree_boundary  # noqa: E402
from   config import HwutRunner                                  # noqa F401,E402

from hwut.services.lib.run.play import main as play_main              # noqa E402
from hwut.services.accept import main as accept_main            # noqa E402
from hwut.engine.bookkeeper.api import Bookkeeper, Store         # noqa E402

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
    root = tempfile.mkdtemp(prefix="hwut_play_")
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
        "registered": Bookkeeper(test).run_id_of("test-new.py") is not None,
    }


def test_records():
    """Play shows what it ran and records it, by name; nothing else."""
    root, test = fixture()
    status, text = _play(test)
    state = _state(test)
    recorded = [l for l in text.splitlines() if l.startswith("RECORDED:")]
    print("  %s" % (recorded[0] if recorded else "(no RECORDED line)"))
    when = Store(Bookkeeper(test)).freshness("test-new.py", None, "stdout")
    print("  recorded by: %s" % (when or {}).get("by"))
    ok = _check([
        (status.value == 0, "status OK"),
        ("hello from new" in text, "the subject is rendered"),
        (bool(recorded), "the face says what it recorded"),
        (state["candidate"], "the recording stands in the store"),
        ((when or {}).get("by") == "hwut.play", "and says who made it"),
        (not state["nominal"], "no nominal: play blesses nothing"),
        (not state["booked"], "no book entry: play judges nothing"),
    ])
    shutil.rmtree(root, ignore_errors=True)
    _verdict(ok, "play shows and records, and only that.")


def test_entrance():
    """play, then accept --force: a nominal, a book entry, a register
    entry -- without one 'hwut.run'."""
    root, test = fixture()
    _play(test)
    line_list = []
    status = accept_main(["test-new.py", "--force",
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
    _verdict(ok, "a new test enters by play, then accept.")


def test_accept_hints():
    """The source changed after the play: accept runs nothing, blesses the
    recording, names it, and hints that the source changed."""
    root, test = fixture()
    _play(test)
    path = os.path.join(test, "test-new.py")
    with open(path, "w") as fh:
        fh.write(SCRIPT.replace("hello from new", "hello, changed"))
    line_list = []
    status = accept_main(["test-new.py", "--force",
                          "--directory=%s" % test],
                         write=line_list.append)
    recording = [l for l in line_list if l.startswith("RECORDING:")]
    hint      = [l for l in line_list if l.startswith("HINT:")]
    print("  %s" % (recording[0].rsplit(",", 1)[0] if recording
                    else "(no RECORDING line)"))
    print("  %s" % (hint[0] if hint else "(no HINT line)"))
    nominal = Store(Bookkeeper(test)).nominal_path("test-new.py", None,
                                                   "stdout")
    ok = _check([
        (status.value == 0, "accept status OK"),
        (not any(l.startswith("RUN:") for l in line_list),
         "accept ran nothing"),
        (bool(recording) and "by hwut.play" in recording[0],
         "it named the recording and who made it"),
        (bool(hint), "it said the source changed since"),
        (nominal.exists() and
         nominal.read_text().startswith("hello from new"),
         "the nominal is what was RECORDED, not what the edit prints"),
    ])
    shutil.rmtree(root, ignore_errors=True)
    _verdict(ok, "accept blesses the recording, and says it is older "
                 "than the source.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "hwut.play: shows and records",
        choice_map = {
            "accept_hints": test_accept_hints,
            "entrance": test_entrance,
            "records":  test_records,
        }).run()
