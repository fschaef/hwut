#! /usr/bin/env python3
#
# @hwut {
#     title      = "Diagnosis: every silent failure names itself"
#     choices    = ["channel_hint", "empty_answer", "never_judges",
#                   "nothing", "one_source", "record", "resolution"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

DIAGNOSIS -- EVERY SILENT FAILURE NAMES ITSELF (todo-21).

This test SHOWS the diagnosis. It does not assert about it. What the
module writes is what stands in the GOOD file, so a reader sees the
very text a person would see at three in the morning when a runner
answered nothing and gave no reason.

    THE SEAM

        run finishes ──► DiagnosisObserver.finished(result)
                              │
                              │  reads ONLY facts already held
                              │  (law 2: nothing re-measured, re-spawned,
                              │   or guessed)
                              ▼
                         explain(configuration, choice, record, raw_db)
                              │
                              ▼
                         text ──► the sink (default: stdout)

    WHAT THE THREE LAWS LOOK LIKE, SHOWN

        law (1)  an empty answer is never reported empty
        law (2)  the argv comes from 'application_argv', the one source
        law (3)  resolution follows PATH, and the symlink chain is shown

    An observer may never change a verdict; the choice 'never_judges'
    shows that nothing it touches carries one.
______________________________________________________________________________
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.operations.configuration import (TestConfiguration,     # noqa E402
                                                 TestChoiceConfiguration,
                                                 E_SourceKind)
from   vut.engine.operations.result        import E_TestRunResult   # noqa E402
from   vut.engine.operations.report        import Provision         # noqa E402
from   vut.engine.operations.diagnosis     import (DiagnosisObserver,     # noqa E402
                                                 explain,
                                                 explain_channels,
                                                 explain_record,
                                                 resolution_chain)
from   vut.engine.procsitter.api  import (ProcsitterConfig,      # noqa E402
                                                 ProcsitterResult,
                                                 E_Containment)


def _show(title, line_list):
    """
    RETURN: None. Frames a reaction so the eye finds where it begins
            and where it ends.
    """
    print("REACTION %s {" % title)
    for line in line_list:
        print("    %s" % line)
    print("}")


def _configuration():
    """
    RETURN: TestConfiguration, one INTERPRETED test application, fixed
            in every field a diagnosis reads.
    """
    return TestConfiguration(
        source_file    = "parse.py",
        source_kind    = E_SourceKind.INTERPRETED,
        test_directory = "/tests/parser",
        interpreter    = ["vut-no-such-interpreter"],
        caps           = ProcsitterConfig(),
        choice_db      = {"basic": TestChoiceConfiguration()})


def _record(containment=E_Containment.FAIL_COMPLETED, exit_code=2,
            stderr_tail="error: no module named 'parser'\n"
                        "   raised at parse.py, line 3\n",
            unenforced=()):
    """
    RETURN: ProcsitterResult, one attribution record with the fields a
            diagnosis reads and nothing invented beyond them.
    """
    return ProcsitterResult(containment           = containment,
                            exit_code             = exit_code,
                            wall_clock_sec        = 0.417,
                            cpu_time_sec          = 0.390,
                            peak_memory_mb        = 12.5,
                            unenforced            = unenforced,
                            stderr_last_100_lines = stderr_tail)


# ---------------------------------------------------------------------------
def test_empty_answer_still_speaks():
    """LAW (1). The stimulus is the evening that earned todo-21: the
    application answered NOTHING. The reaction is what the runner used
    to print -- and what it prints now, side by side."""
    raw_db = {"stdout": "", "stderr": "ImportError: no module named 'parser'\n"}

    print("STIMULUS the test application answered:")
    print("             stdout  %r" % raw_db["stdout"])
    print("             stderr  %r" % raw_db["stderr"])
    print("         exit code 2, ended by itself")
    print()
    print("REACTION the old way {")
    print("    (empty)")
    print("}")
    _show("the diagnosis",
          explain(_configuration(), "basic",
                  Provision(report  = E_TestRunResult.TEST_APP_NO_OUTPUT,
                            records = (_record(),)),
                  raw_db).splitlines())
    print()
    print("An empty answer is rendered WITH its exit code, its")
    print("containment, and the other channel's tail.")
    print("SUCCESS: nothing that failed goes away without saying why.")


def test_wrong_channel_hint():
    """A HINT IS NEVER A VERDICT. Stdout empty while stderr is full is
    the pattern that costs an evening; the module names the pattern and
    judges nothing."""
    full_db  = {"stdout": "", "stderr": "print() went here\n"}
    both_db  = {"stdout": "the answer\n", "stderr": "a warning\n"}
    empty_db = {"stdout": "", "stderr": ""}

    print("STIMULUS three channel situations, in turn:")
    print()
    print("    stdout   stderr   hint expected")
    print("    ------   ------   ----------------------------------")
    print("    empty    full     yes -- the pattern that costs a night")
    print("    full     full     no  -- there IS an answer")
    print("    empty    empty    no  -- nothing to point at")
    print()
    _show("stdout empty, stderr full", explain_channels(full_db))
    _show("both channels carry text",  explain_channels(both_db))
    _show("both channels empty",       explain_channels(empty_db))
    print()
    print("SUCCESS: the hint names a pattern for a human, never a verdict.")


def test_one_source_for_the_request():
    """LAW (2). The argv shown is the argv that RAN -- taken from
    'application_argv', not rebuilt here. Two source kinds, so the
    reader sees the one source answering differently."""
    interpreted = _configuration()

    print("STIMULUS an INTERPRETED application, interpreter ['vut-no-such-interpreter'],")
    print("         source 'parse.py', choice 'basic'")
    line_list = explain(interpreted, "basic",
                        Provision(report = E_TestRunResult.OK)).splitlines()
    _show("the REQUEST line",
          [line for line in line_list if "REQUEST" in line])
    print()
    print("STIMULUS the same application, but NO choice (the 'None' key)")
    line_list = explain(interpreted, None,
                        Provision(report = E_TestRunResult.OK)).splitlines()
    _show("the REQUEST line",
          [line for line in line_list if "REQUEST" in line])
    print()
    print("The choice name is the last argument, and it is absent when")
    print("there is no choice -- because that is what the runner did.")
    print("SUCCESS: the diagnosis quotes the run; it does not re-invent it.")


def test_resolution_chain():
    """LAW (3). PATH is the shell's own semantics, and a command PATH
    cannot answer SAYS so rather than being guessed at.

    The chain below is BUILT BY THIS TEST in a temporary directory, so
    the hops shown are its own property and not the machine's -- the
    directory is rendered as '<dir>' for the same reason.
    """
    import tempfile

    print("STIMULUS a command three hops from its file:")
    print()
    print("             cmd  ->  hop-a  ->  hop-b  ->  real-file")
    print()
    with tempfile.TemporaryDirectory() as directory:
        real = os.path.join(directory, "real-file")
        open(real, "w").close()
        os.chmod(real, 0o755)
        os.symlink(real,                            os.path.join(directory, "hop-b"))
        os.symlink(os.path.join(directory, "hop-b"), os.path.join(directory, "hop-a"))
        os.symlink(os.path.join(directory, "hop-a"), os.path.join(directory, "cmd"))
        path_before  = os.environ["PATH"]
        os.environ["PATH"] = directory
        try:    line_list = resolution_chain("cmd")
        finally: os.environ["PATH"] = path_before
        _show("its resolution",
              [line.replace(directory, "<dir>") for line in line_list])
    print()
    print("STIMULUS a command that is NOT on PATH:")
    _show("its resolution", resolution_chain("vut-no-such-command"))
    print()
    print("One line per hop, so a command three hops from its binary is")
    print("visible rather than mysterious; and what PATH cannot answer")
    print("is SAID, never guessed.")
    print("SUCCESS: what PATH answers is shown; what it cannot is said.")


def test_one_record_rendered():
    """The attribution of a single supervised call: containment, exit,
    wall clock -- and the caps the platform could not enforce, which are
    shown only when there are any."""
    print("STIMULUS a call that ended by itself with exit code 2")
    _show("its attribution", explain_record(_record(), "call[0]"))
    print()
    print("STIMULUS a call the watchdog stopped, caps unenforced")
    _show("its attribution",
          explain_record(_record(containment = E_Containment.FAIL_WALL_CLOCK_EXCEEDED,
                                 exit_code   = None,
                                 unenforced  = ("peak_memory_mb",)),
                         "call[0]"))
    print()
    print("STIMULUS a call that succeeded, stderr silent")
    _show("its attribution",
          explain_record(_record(containment = E_Containment.OK_COMPLETED,
                                 exit_code   = 0,
                                 stderr_tail = ""),
                         "call[0]"))
    print()
    print("SUCCESS: containment, exit and duration always; the rest when it exists.")


def test_observer_never_judges():
    """AN OBSERVER MAY NEVER CHANGE A VERDICT. The observer is given a
    sink, so the test sees exactly what it wrote -- and the result it
    was handed is shown before and after, unchanged."""
    written = []

    class _Result:
        """A run that finished. Nothing here is a verdict the observer
        may touch."""
        def __init__(self, provision):
            self.provision = provision
            self.verdict   = False

    result   = _Result(Provision(report  = E_TestRunResult.TEST_APP_NO_OUTPUT,
                                 records = (_record(),)))
    observer = DiagnosisObserver(_configuration(), "basic", write=written.append)

    print("STIMULUS a finished run, verdict = %s, report = %s"
          % (result.verdict, result.provision.report))
    observer.finished(result)
    _show("what the observer wrote",
          "".join(written).splitlines())
    print()
    print("         after the observer ran: verdict = %s, report = %s"
          % (result.verdict, result.provision.report))
    print()
    print("SUCCESS: it renders and returns; the verdict is none of its business.")


def test_nothing_to_diagnose():
    """A result WITHOUT a provision record is not an error and not an
    empty diagnosis -- the observer writes nothing at all, because
    there is nothing that ran to explain."""
    written = []

    class _Bare:
        """A result that carries no provision."""
        provision = None

    observer = DiagnosisObserver(_configuration(), "basic", write=written.append)

    print("STIMULUS a result that carries no provision record")
    observer.finished(_Bare())
    print("REACTION the observer wrote %i character(s)" % len("".join(written)))
    print()
    print("Silence is the honest answer: nothing ran, so nothing is")
    print("explained. An empty EXPLAIN block would suggest a run.")
    print("SUCCESS: no run, no diagnosis -- and no noise.")


if __name__ == "__main__":
    HwutRunner(
        argv        = sys.argv,
        title       = "Diagnosis: every silent failure names itself",
        choice_map  = {
            "empty_answer":  test_empty_answer_still_speaks,
            "channel_hint":  test_wrong_channel_hint,
            "one_source":    test_one_source_for_the_request,
            "resolution":    test_resolution_chain,
            "record":        test_one_record_rendered,
            "never_judges":  test_observer_never_judges,
            "nothing":       test_nothing_to_diagnose,
        },
        happy       = "SUCCESS.*",
    ).run()
