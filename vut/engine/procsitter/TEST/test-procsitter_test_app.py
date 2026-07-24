#!/usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Verify the judged test application run: a CHAIN
         (supervised calls chained by pipes) whose tail is judged on
         the two axes of compare/main.py.

DESCRIPTION:

RUNNING and JUDGING are separate concerns. RUNNING is the general
chain (launch_chain, procsitter.py): supervised calls connected stdout ->
stdin, one attribution record per stage. PIPE-CONSTRUCTION IS THE
INTERFACE in both directions -- between the stages, and toward
compare, which reads the chain's tail. JUDGING is the two axes:

    judge_equivalence  'is_equivalent' -- THE JUDGE: investigating
                       correctness, quickly; fast-fail.
    judge_association  'associate' -- THE LAWYER: associating subject
                       lines with nominal lines for display.

Every judge_* returns one ProcsitterResult PER STAGE; every stage must
have completed (or been stopped by the fast-fail) for a verdict to
stand.

CHOICES:

  equivalence_ok:        subject equals nominal
                         -> ((COMPLETED,), True).            [Judge]
  equivalence_fail_fast: an early mismatching line -> compare aborts,
                         the chain's stop_event kills the test app
                         long before its natural end
                         -> ((STOPPED,), False).             [Judge]
  association:           the same divergence through BOTH axes: the
                         Lawyer yields ChunkPairs to a consumer (run to
                         natural end, no fast-fail); the reduction over
                         ChunkPair.is_equivalent() must equal the
                         Judge's verdict -- THE LAW.  [Judge + Lawyer]
  pype_deterministicalize: a two-stage chain: test app emitting
                         lines in RANDOM order | pype stage (its OWN
                         supervised call) deterministicalizing them ->
                         verdict True whatever the order was; BOTH
                         stage records COMPLETED.            [Judge]
  contained_run:         a memory bomb under judgement
                         -> ((MEMORY_EXCEEDED,), False); the chain
                         unwinds cleanly on the kill.        [Judge]
  output_file:           an output FILE judged post-exit.    [Judge]
  spec_channel_and_files: THE INTERFACE: input = configuration
                         (ProcsitterConfigTestRun), output = result
                         (ProcsitterResultTestRun), via 'run_test_app()' --
                         stdout judged LIVE, two output files judged
                         POST-EXIT, one judgement record per subject;
                         a mismatching file turns the overall verdict
                         False and is NAMED; the Lawyer over the SAME
                         configuration labels every ChunkPair with its
                         subject and reduces to the same verdicts (THE
                         LAW).                      [Judge + Lawyer]
  spec_file_pype:        a file with non-deterministic line order,
                         deterministicalized POST-EXIT by a pype
                         comparator (a one-stage chain reading the
                         file) -> True; pype's own record accounted.
                                                             [Judge]
  stderr_channel:        stderr is a CHANNEL like any other: nominal
                         behavior may be defined on it. Judged LIVE
                         and concurrently with stdout
                         (config.error_channel; the err pipe follows
                         the configuration); a stderr mismatch is
                         NAMED and fast-fails the run.      [Judge]
  resource_usage:        the result carries the run's RESOURCE USAGE:
                         cpu time (summed over stages -- work adds),
                         wall clock (elapsed), peak memory (high-water
                         mark). Presence/sign asserted, never
                         magnitudes: GOOD stable across machines.
  result_classification: E_TestRunResult, THE BRIEF REPORT: one
                         provoked reason per case -- ok,
                         not-equivalent-with-nominal,
                         test-app-no-output, test-app-contained,
                         nominal-file-not-found,
                         output-file-not-found,
                         pype-interpreter-not-found,
                         pype-file-not-found, pype-file-syntax-error.
                                                             [Judge]

AUTHOR: Frank-Rene Schaefer
"""

import io
import logging
import os
import sys
import tempfile

from   config import HwutRunner                                     # noqa F401

from   vut.engine.procsitter.procsitter      import (Procsitter,             # noqa E402
                                               ProcsitterConfig,
                                               launch_chain,
                                               E_Containment)
from   vut.engine.procsitter.procsitter_test_app import (judge_equivalence,   # noqa E402
                                               judge_association,
                                               judge_output_file,
                                               run_test_app,
                                               Comparator,
                                               ProcsitterConfigTestRun)
from   vut.engine.compare.configuration import Configuration        # noqa E402
from   vut.auxiliary.test_run_result    import E_TestRunResult      # noqa E402

# Child-reap races between the harness's kill discipline and asyncio's
# child watcher may emit spurious warnings ("Unknown child process ...")
# -- harmless, but nondeterministic; the GOOD file must not see them.
logging.getLogger("asyncio").setLevel(logging.ERROR)

ROOT_DIR  = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                         "..", "..", "..", ".."))
HWUT_PYPE = os.path.abspath("../../hwut_pype/hwut_pype.py")
def _require_hwut_pype() -> bool:
    """
    RETURN: True,  the pype interpreter is present.
            False, else -- with an ACTIONABLE report: this is an
                   environment defect, not a code defect.
    """
    if os.path.exists(HWUT_PYPE):
        return True
    print(f"FAIL: pype interpreter not found: '{HWUT_PYPE}'")
    print("      undump component-hwut_pype.txt so that hwut_pype.py")
    print("      lies at <project root>/tools/hwut_pype/, or set the")
    print("      environment variable VUT_HWUT_PYPE to its path.")
    return False


def _print_stage_diagnostics(label, record):
    """
    RETURN: None. On a failed stage: prints exit code and the captured
            stderr tail -- the WHY. (Failure paths only; the GOOD file
            never sees this.)
    """
    if record.containment is E_Containment.OK_COMPLETED \
       and record.exit_code == 0:
        return
    print(f"DIAGNOSTIC: {label}: containment={record.containment.name}, "
          f"exit_code={record.exit_code}")
    for line in record.stderr_last_100_lines.splitlines():
        print(f"DIAGNOSTIC: {label} stderr| {line}")


def _argv(app_code: str) -> list:
    """
    RETURN: list[str], argv running 'app_code' with this interpreter.
    """
    return [sys.executable, "-c", app_code]


def _check(results):
    """
    RETURN: True,  all (bool, label) pairs in results are True;
                   prints OK/FAIL per line.
            False, else.
    """
    ok = True
    for result, label in results:
        print(f"  {'OK  ' if result else 'FAIL'}: {label}")
        ok = ok and result
    return ok


def _verdict(ok, subject):
    """
    RETURN: None. Prints the final SUCCESS/FAIL line for the choice.
    """
    if ok: print(f"SUCCESS: {subject}")
    else:  print(f"FAIL: {subject} (see above)")


# ---------------------------------------------------------------------------

async def test_equivalence_ok():
    """The happy path of the Judge axis: matching output."""
    app     = ("print('alpha')\n"
               "print('value 42')\n"
               "print('omega')\n")
    nominal = "alpha\nvalue 42\nomega\n"

    with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
        chain = launch_chain(
            [(Procsitter(ProcsitterConfig(max_wall_clock_sec=10.0), work_dir),
              _argv(app))])
        result_list, verdict = await judge_equivalence(
            chain, io.StringIO(nominal), Configuration())
        result, = result_list

    print(f"INSPECT: containment = {result.containment.name}, "
          f"verdict = {verdict}")
    ok = _check([
        (result.containment is E_Containment.OK_COMPLETED, "test app completed"),
        (result.exit_code == 0,                         "exit code 0"),
        (verdict is True,                               "judged equivalent"),
    ])
    _verdict(ok, "matching subject judged equivalent.")


async def test_equivalence_fail_fast():
    """The Judge investigates correctness QUICKLY: the second line
    already contradicts the nominal; the app would otherwise sleep 30 s
    and print more. Fast-fail must kill it within moments."""
    app     = ("import sys, time\n"
               "print('alpha', flush=True)\n"
               "print('WRONG', flush=True)\n"
               "time.sleep(30)\n"
               "print('never reached')\n")
    nominal = "alpha\nbeta\ngamma\n"

    with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
        chain = launch_chain(
            [(Procsitter(ProcsitterConfig(max_wall_clock_sec=20.0), work_dir),
              _argv(app))])
        result_list, verdict = await judge_equivalence(
            chain, io.StringIO(nominal), Configuration())
        result, = result_list

    print(f"INSPECT: containment = {result.containment.name}, "
          f"verdict = {verdict}")
    ok = _check([
        (verdict is False,                            "judged NOT equivalent"),
        (result.containment is E_Containment.FAIL_STOPPED,
         "test app STOPPED by the fast-fail (not run to natural end)"),
        (result.wall_clock_sec < 10.0,
         "abort came long before the 30 s sleep ended"),
    ])
    _verdict(ok, "early mismatch stopped the chain, fast-fail both ways.")


async def test_association():
    """The same diverging run through both axes. The Judge fast-fails
    to a boolean; the Lawyer runs to the natural end and yields the
    full alignment as ChunkPairs. THE LAW: the reduction over
    ChunkPair.is_equivalent() must equal the Judge's verdict -- for
    the diverging and for the matching case."""
    app_diverging = ("print('alpha')\n"
                     "print('WRONG')\n"
                     "print('gamma')\n")
    app_matching  = ("print('alpha')\n"
                     "print('beta')\n"
                     "print('gamma')\n")
    nominal       = "alpha\nbeta\ngamma\n"

    def chain_of(app, work_dir):
        """RETURN: ChainRun, one-stage run of 'app'."""
        return launch_chain(
            [(Procsitter(ProcsitterConfig(max_wall_clock_sec=10.0), work_dir),
              _argv(app))])

    async def judge(app):
        """RETURN: bool, the Judge's verdict for 'app' against nominal."""
        with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
            _, verdict = await judge_equivalence(
                chain_of(app, work_dir), io.StringIO(nominal),
                Configuration())
            return verdict

    async def lawyer(app):
        """RETURN: (ProcsitterResult, list), test-app record and the
                   ChunkPairs the Lawyer yielded for 'app'."""
        pair_list = []
        with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
            result_list = await judge_association(
                chain_of(app, work_dir), io.StringIO(nominal),
                Configuration(), consumer=pair_list.append)
            return result_list[0], pair_list

    verdict_diverging          = await judge(app_diverging)
    result_d, pair_list_d      = await lawyer(app_diverging)
    reduced_d = all(cp.is_equivalent() for cp in pair_list_d)

    verdict_matching           = await judge(app_matching)
    result_m, pair_list_m      = await lawyer(app_matching)
    reduced_m = all(cp.is_equivalent() for cp in pair_list_m)

    print(f"INSPECT: diverging: Judge = {verdict_diverging}, "
          f"Lawyer pairs = {len(pair_list_d)}, reduced = {reduced_d}")
    print(f"INSPECT: matching:  Judge = {verdict_matching}, "
          f"Lawyer pairs = {len(pair_list_m)}, reduced = {reduced_m}")
    ok = _check([
        (verdict_diverging is False,
         "Judge (is_equivalent): diverging subject -> False"),
        (result_d.containment is E_Containment.OK_COMPLETED,
         "Lawyer (associate) lets the run reach its natural end"),
        (len(pair_list_d) >= 1 and not reduced_d,
         "Lawyer yields the alignment; its reduction is False"),
        (reduced_d == verdict_diverging and reduced_m == verdict_matching,
         "THE LAW: Lawyer's reduction equals Judge's verdict, both cases"),
        (verdict_matching is True and reduced_m is True,
         "matching subject: both axes agree on True"),
    ])
    _verdict(ok, "Judge and Lawyer agree; the alignment reaches the consumer.")


async def test_pype_deterministicalize():
    """The purpose of pype, end to end: the test app PROVOKES and
    REPORTS -- its items arrive in RANDOM order (unseeded shuffle,
    genuinely non-deterministic). The pype stage ANALYZES: it records
    arrivals, reports only the running count, and prints the settled
    SORTED summary. compare JUDGES the deterministicalized stream
    against one fixed nominal. The run is a TWO-STAGE chain;
    the verdict demands BOTH stage records accounted for."""
    app = ("import random\n"
           "items = ['cherry', 'apple', 'durian', 'banana']\n"
           "random.shuffle(items)\n"
           "for item in items:\n"
           "    print('item ' + item)\n"
           "print('done')\n")

    pype_script = (
        'on: <bof> => {\n'
        '    box = []\n'
        '}\n'
        'on: "item" <name = "*"> => {\n'
        '    box.append(name)\n'
        '    print("an item arrived (%d so far)" % len(box))\n'
        '}\n'
        'on: "done" => {\n'
        '    print("items, sorted:")\n'
        '    for name in sorted(box):\n'
        '        print("    " + name)\n'
        '}\n'
        'on: <else> => ignore;\n')

    nominal = ("an item arrived (1 so far)\n"
               "an item arrived (2 so far)\n"
               "an item arrived (3 so far)\n"
               "an item arrived (4 so far)\n"
               "items, sorted:\n"
               "    apple\n"
               "    banana\n"
               "    cherry\n"
               "    durian\n")

    with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
        script_path = os.path.join(work_dir, "settle.pype")
        with open(script_path, "w") as fh:
            fh.write(pype_script)

        # THE GROUND: test app AND pype are supervised system calls --
        # each stage of the chain in its OWN procsitter.
        chain = launch_chain([
            (Procsitter(ProcsitterConfig(max_wall_clock_sec=15.0), work_dir),
             _argv(app)),
            (Procsitter(ProcsitterConfig(max_wall_clock_sec=15.0), work_dir),
             [sys.executable, HWUT_PYPE, script_path]),
        ])
        result_list, verdict = await judge_equivalence(
            chain, io.StringIO(nominal), Configuration())
        test_result, pype_result = result_list

    print(f"INSPECT: stage records = "
          f"test {test_result.containment.name}, "
          f"pype {pype_result.containment.name}; verdict = {verdict}")
    ok = _check([
        (test_result.containment is E_Containment.OK_COMPLETED,
         "test app stage completed"),
        (pype_result.containment is E_Containment.OK_COMPLETED
         and pype_result.exit_code == 0,
         "pype stage completed -- its own attribution record"),
        (verdict is True,
         "non-deterministic order judged equivalent BEHIND the pype stage"),
    ])
    _print_stage_diagnostics("pype", pype_result)
    _verdict(ok, "pype deterministicalized the chain; compare agreed.")


async def test_contained_run():
    """A memory bomb under judgement: the containment kill must unwind
    the whole chain cleanly, and a contained run is never
    equivalent."""
    app     = ("import time\n"
               "print('starting', flush=True)\n"
               "hoard = []\n"
               "while True:\n"
               "    hoard.append(bytearray(4 * 1024 * 1024))\n"
               "    time.sleep(0.01)\n")
    nominal = "starting\nfinished\n"

    with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
        chain = launch_chain(
            [(Procsitter(ProcsitterConfig(max_memory_mb=96,
                                    max_wall_clock_sec=20.0), work_dir),
              _argv(app))])
        result_list, verdict = await judge_equivalence(
            chain, io.StringIO(nominal), Configuration())
        result, = result_list

    print(f"INSPECT: containment = {result.containment.name}, "
          f"verdict = {verdict}")
    ok = _check([
        (result.containment is E_Containment.FAIL_MEMORY_EXCEEDED,
         "containment is MEMORY_EXCEEDED"),
        (verdict is False, "a contained run is never equivalent"),
    ])
    _verdict(ok, "containment kill unwound the judged chain cleanly.")


async def test_output_file():
    """Channels are judged live; FILES are judged post-exit."""
    app     = ("with open('result.txt', 'w') as fh:\n"
               "    fh.write('measurement A\\n')\n"
               "    fh.write('measurement B\\n')\n")
    nominal_good = "measurement A\nmeasurement B\n"
    nominal_bad  = "measurement A\nmeasurement X\n"

    with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
        procsitter = Procsitter(ProcsitterConfig(max_wall_clock_sec=10.0), work_dir)
        result  = await procsitter.run(_argv(app))
        file_path = os.path.join(work_dir, "result.txt")

        verdict_good = await judge_output_file(
            file_path, io.StringIO(nominal_good), Configuration())
        verdict_bad  = await judge_output_file(
            file_path, io.StringIO(nominal_bad), Configuration())
        verdict_absent = await judge_output_file(
            os.path.join(work_dir, "no_such.txt"),
            io.StringIO(nominal_good), Configuration())

    print(f"INSPECT: containment = {result.containment.name}")
    ok = _check([
        (result.containment is E_Containment.OK_COMPLETED,                "test app completed cleanly"),
        (result.stderr_last_100_lines == "", "clean run: empty stderr tail"),
        (verdict_good is True,     "matching file judged equivalent"),
        (verdict_bad is False,     "mismatching file judged NOT equivalent"),
        (verdict_absent is False,  "absent file judged NOT equivalent"),
    ])
    _verdict(ok, "output file judged post-exit against the nominal.")


async def test_spec_channel_and_files():
    """The run specification: stdout judged LIVE, files judged only
    POST-EXIT (a file may change at any moment while the test lives).
    One judgement per subject; a mismatching file is NAMED. The Lawyer
    over the same spec labels ChunkPairs per subject and reduces to
    the same verdicts (THE LAW across the whole specification)."""
    app = ("print('run begins')\n"
           "with open('result.txt', 'w') as fh:\n"
           "    fh.write('measurement A\\n')\n"
           "with open('report.txt', 'w') as fh:\n"
           "    fh.write('total: 7 items\\n')\n"
           "print('run ends')\n")

    def config(work_dir, report_nominal):
        """RETURN: ProcsitterConfigTestRun, THE COMPLETE INPUT: the run and its
                   subjects -- stdout + two files vs. comparators."""
        return ProcsitterConfigTestRun(
            command      = _argv(app),
            procsitter      = Procsitter(ProcsitterConfig(max_wall_clock_sec=10.0),
                                   work_dir),
            channel = Comparator(io.StringIO("run begins\nrun ends\n"),
                                 Configuration()),
            file_db = {
                "result.txt": Comparator(io.StringIO("measurement A\n"),
                                         Configuration()),
                "report.txt": Comparator(io.StringIO(report_nominal),
                                         Configuration()),
            })

    with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
        good = await run_test_app(config(work_dir, "total: 7 items\n"))
    with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
        bad  = await run_test_app(config(work_dir, "total: 999 items\n"))

    label_set = set()
    with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
        lawyer = await run_test_app(
            config(work_dir, "total: 999 items\n"),
            consumer=lambda subject, chunk_pair: label_set.add(subject))

    print(f"INSPECT: good verdicts = "
          f"{sorted(good.subject_verdict_db.items())}")
    print(f"INSPECT: bad  verdicts = "
          f"{sorted(bad.subject_verdict_db.items())}")
    print(f"INSPECT: lawyer labels = {sorted(label_set)}")
    ok = _check([
        (good.verdict is True
         and all(good.subject_verdict_db.values()),
         "all subjects equivalent -> overall verdict True"),
        (bad.verdict is False,
         "one mismatching file -> overall verdict False"),
        (bad.subject_verdict_db["stdout"] is True
         and bad.subject_verdict_db["result.txt"] is True
         and bad.subject_verdict_db["report.txt"] is False,
         "the mismatching subject is NAMED: report.txt"),
        (label_set == {"stdout", "report.txt", "result.txt"},
         "Lawyer labels every ChunkPair with its subject"),
        (lawyer.subject_verdict_db == bad.subject_verdict_db,
         "THE LAW: Lawyer's per-subject reductions equal the Judge's"),
    ])
    _verdict(ok, "channel vs. comparator: every subject judged, named.")


async def test_spec_file_pype():
    """Files can only be deterministicalized AFTER the test terminated
    -- filtering during the run would fail on transients. The file's
    comparator carries a pype stage: post-exit, a one-stage chain
    reads the file (pype INPUT-FILE argument), and compare judges its
    tail. The file's line order is genuinely random; the nominal is
    fixed."""
    app = ("import random\n"
           "items = ['cherry', 'apple', 'durian', 'banana']\n"
           "random.shuffle(items)\n"
           "with open('trace.txt', 'w') as fh:\n"
           "    for item in items:\n"
           "        fh.write('item ' + item + '\\n')\n"
           "    fh.write('done\\n')\n")

    pype_script = (
        'on: <bof> => {\n'
        '    box = []\n'
        '}\n'
        'on: "item" <name = "*"> => {\n'
        '    box.append(name)\n'
        '    print("an item arrived (%d so far)" % len(box))\n'
        '}\n'
        'on: "done" => {\n'
        '    print("items, sorted:")\n'
        '    for name in sorted(box):\n'
        '        print("    " + name)\n'
        '}\n'
        'on: <else> => ignore;\n')

    nominal = ("an item arrived (1 so far)\n"
               "an item arrived (2 so far)\n"
               "an item arrived (3 so far)\n"
               "an item arrived (4 so far)\n"
               "items, sorted:\n"
               "    apple\n"
               "    banana\n"
               "    cherry\n"
               "    durian\n")

    with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
        script_path = os.path.join(work_dir, "settle.pype")
        with open(script_path, "w") as fh:
            fh.write(pype_script)

        config = ProcsitterConfigTestRun(
            command      = _argv(app),
            procsitter      = Procsitter(ProcsitterConfig(max_wall_clock_sec=15.0),
                                   work_dir),
            channel = None,          # stdout drained, unjudged
            file_db = {
                "trace.txt": Comparator(
                    io.StringIO(nominal), Configuration(),
                    pype_procsitter      = Procsitter(
                        ProcsitterConfig(max_wall_clock_sec=15.0), work_dir),
                    pype_command      = [sys.executable, HWUT_PYPE,
                                         script_path]),
            })
        judgement = await run_test_app(config)

    pype_record, = judgement.file_stage_db["trace.txt"]
    print(f"INSPECT: verdicts = "
          f"{sorted(judgement.subject_verdict_db.items())}, "
          f"post-exit pype = {pype_record.containment.name}")
    ok = _check([
        (judgement.subject_verdict_db["trace.txt"] is True,
         "random file order judged equivalent BEHIND post-exit pype"),
        (pype_record.containment is E_Containment.OK_COMPLETED
         and pype_record.exit_code == 0,
         "post-exit pype stage accounted -- its own attribution record"),
        (judgement.verdict is True,
         "overall verdict True"),
    ])
    _print_stage_diagnostics("post-exit pype", pype_record)
    _verdict(ok, "file deterministicalized post-exit, never during the run.")


async def test_stderr_channel():
    """stderr is a CHANNEL like any other -- nominal behavior may be
    defined on it. The spec's 'error_channel' comparator judges it
    LIVE, concurrently with stdout; both feed the fast-fail; a stderr
    mismatch is NAMED like any other subject."""

    async def run(app, subject_db, wall=10.0):
        """RETURN: ProcsitterResultTestRun of 'app' under the subjects (the err
                   pipe follows the configuration automatically)."""
        with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
            return await run_test_app(ProcsitterConfigTestRun(
                command      = _argv(app),
                procsitter      = Procsitter(ProcsitterConfig(max_wall_clock_sec=wall),
                                       work_dir),
                **subject_db))

    def subjects_both(err_nominal):
        """RETURN: dict, subject fields -- stdout AND stderr judged."""
        return dict(
            channel       = Comparator(io.StringIO("to stdout\n"),
                                       Configuration()),
            error_channel = Comparator(io.StringIO(err_nominal),
                                       Configuration()))

    app_ok = ("import sys\n"
              "print('to stdout')\n"
              "print('warning: tolerated', file=sys.stderr)\n")

    good = await run(app_ok, subjects_both("warning: tolerated\n"))
    bad  = await run(app_ok, subjects_both("warning: expected\n"))

    app_hang = ("import sys, time\n"
                "print('to stdout', flush=True)\n"
                "print('warning: WRONG', file=sys.stderr, flush=True)\n"
                "time.sleep(30)\n")
    fast = await run(app_hang, subjects_both("warning: expected\n"),
                     wall=20.0)

    only_err = await run(
        app_ok, dict(error_channel=Comparator(
            io.StringIO("warning: tolerated\n"), Configuration())))

    print(f"INSPECT: good verdicts = "
          f"{sorted(good.subject_verdict_db.items())}")
    print(f"INSPECT: bad  verdicts = "
          f"{sorted(bad.subject_verdict_db.items())}")
    ok = _check([
        (good.verdict is True and str(good.report) == "ok",
         "matching stdout AND stderr -> ok"),
        (bad.subject_verdict_db["stdout"] is True
         and bad.subject_verdict_db["stderr"] is False,
         "stderr mismatch NAMED; stdout stays True"),
        (str(bad.report) == "not-equivalent-with-nominal",
         "brief report: not-equivalent-with-nominal"),
        (fast.stage_result_list[0].containment
             is E_Containment.FAIL_STOPPED
         and fast.stage_result_list[0].wall_clock_sec < 10.0,
         "stderr mismatch FAST-FAILS the run (long before 30 s)"),
        (only_err.verdict is True,
         "stderr-only specification: stdout drained, stderr judged"),
    ])
    _verdict(ok, "stderr judged as a channel, symmetric with stdout.")


async def test_result_classification():
    """E_TestRunResult, THE BRIEF REPORT: 'ok' or the reason of
    failure, one token. Each case provokes one classification;
    test-app reasons outrank pype reasons outrank subject/nominal
    reasons. The pype classifications rest on the captured stderr
    tail of the pype stage's own attribution record."""

    async def classify(app, subjects_of, wall=10.0,
                       command=None, pype_command=None):
        """RETURN: E_TestRunResult, brief report of one judged run.
        'command' overrides the argv (to provoke a launch failure);
        'pype_command' adds a LIVE channel pype stage (to provoke a
        failing determinizer)."""
        with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
            extra = {}
            if pype_command is not None:
                extra["pype_command"] = pype_command
                extra["pype_procsitter"] = Procsitter(
                    ProcsitterConfig(max_wall_clock_sec=wall), work_dir)
            result = await run_test_app(ProcsitterConfigTestRun(
                command      = command if command is not None
                               else _argv(app),
                procsitter      = Procsitter(ProcsitterConfig(max_wall_clock_sec=wall),
                                       work_dir),
                **subjects_of(work_dir), **extra))
            return result.report

    def channel(nominal):
        """RETURN: callable(work_dir) -> dict, channel-only subjects."""
        return lambda work_dir: dict(
            channel=Comparator(io.StringIO(nominal), Configuration()))

    app_alpha = "print('alpha')\n"
    app_file  = "open('trace.txt', 'w').write('item x\\ndone\\n')\n"

    def file_pype_spec(pype_command_of):
        """RETURN: callable(work_dir) -> dict, one file subject with a
                   post-exit pype comparator."""
        def make(work_dir):
            return dict(file_db={"trace.txt": Comparator(
                io.StringIO("irrelevant\n"), Configuration(),
                pype_procsitter = Procsitter(
                    ProcsitterConfig(max_wall_clock_sec=10.0), work_dir),
                pype_command = pype_command_of(work_dir))})
        return make

    def script_pype_spec(script_txt):
        """RETURN: callable(work_dir) -> dict, file subject with a
                   REAL pype interpreter running 'script_txt'."""
        def pype_command_of(work_dir):
            path = os.path.join(work_dir, "s.pype")
            with open(path, "w") as fh:
                fh.write(script_txt)
            return [sys.executable, HWUT_PYPE, path]
        return file_pype_spec(pype_command_of)

    def raw_pype_spec(pype_cmd, wall=10.0):
        """RETURN: callable(work_dir) -> dict, a file subject whose
                   post-exit pype is 'pype_cmd' -- a CONTROLLED command
                   (no hwut_pype needed), capped at 'wall' seconds. Used
                   to provoke the pype-failure classifications directly:
                   a missing interpreter binary, a resource-capped pype,
                   a generic nonzero pype exit."""
        def make(work_dir):
            return dict(file_db={"trace.txt": Comparator(
                io.StringIO("irrelevant\n"), Configuration(),
                pype_procsitter = Procsitter(
                    ProcsitterConfig(max_wall_clock_sec=wall), work_dir),
                pype_command = pype_cmd)})
        return make

    case_list = [
        ("ok",
         await classify(app_alpha, channel("alpha\n")),
         E_TestRunResult.OK),
        ("mismatching line",
         await classify("print('WRONG')\n", channel("alpha\n")),
         E_TestRunResult.NOT_EQUIVALENT_WITH_NOMINAL),
        ("silent test app",
         await classify("pass\n", channel("alpha\n")),
         E_TestRunResult.TEST_APP_NO_OUTPUT),
        ("hanging test app (wall cap 1 s)",
         await classify("import time; time.sleep(30)\n",
                        channel("alpha\n"), wall=1.0),
         E_TestRunResult.TEST_APP_CONTAINED),
        ("nominal path absent",
         await classify(app_alpha, lambda work_dir: dict(
             channel=Comparator("/no/such/nominal.txt", Configuration()))),
         E_TestRunResult.NOMINAL_FILE_NOT_FOUND),
        ("output file absent",
         await classify("pass\n", lambda work_dir: dict(
             file_db={"result.txt":
                      Comparator(io.StringIO("x\n"), Configuration())})),
         E_TestRunResult.OUTPUT_FILE_NOT_FOUND),
        ("test app cannot launch",
         await classify(None, channel("alpha\n"),
                        command=["/no/such/app"]),
         E_TestRunResult.TEST_APP_LAUNCH_FAILED),
        ("live channel pype stage fails",
         await classify(app_alpha, channel("alpha\n"),
                        pype_command=[sys.executable, "-c",
                                      "import sys; sys.exit(1)"]),
         E_TestRunResult.PYPE_FAILED),
        ("file nominal path absent",
         await classify("open('trace.txt','w').write('x\\n')\n",
                        lambda work_dir: dict(file_db={"trace.txt":
                            Comparator("/no/such/file_nominal.txt",
                                       Configuration())})),
         E_TestRunResult.NOMINAL_FILE_NOT_FOUND),
        ("pype interpreter absent",
         await classify(app_file, file_pype_spec(
             lambda work_dir: ["python3", "/no/such/hwut_pype.py",
                               "s.pype"])),
         E_TestRunResult.PYPE_INTERPRETER_NOT_FOUND),
        ("pype interpreter binary missing (launch fails)",
         await classify(app_file, raw_pype_spec(["/no/such/bin/nope"])),
         E_TestRunResult.PYPE_INTERPRETER_NOT_FOUND),
        ("pype stage resource-capped",
         await classify(app_file, raw_pype_spec(
             [sys.executable, "-c", "import time; time.sleep(30)"],
             wall=1.0)),
         E_TestRunResult.PYPE_CONTAINED),
        ("pype generic nonzero exit",
         await classify(app_file, raw_pype_spec(
             [sys.executable, "-c",
              "import sys; sys.stderr.write('boom\\n'); sys.exit(1)"])),
         E_TestRunResult.PYPE_FAILED),
    ]
    if _require_hwut_pype():
        case_list += [
            ("pype script with missing import",
             await classify(app_file, script_pype_spec(
                 'import: "no-such-lib.pype"\n'
                 'on: <else> => ignore;\n')),
             E_TestRunResult.PYPE_FILE_NOT_FOUND),
            ("pype script with syntax error",
             await classify(app_file, script_pype_spec("garbage line\n")),
             E_TestRunResult.PYPE_FILE_SYNTAX_ERROR),
        ]

    ok = True
    for label, got, expected in case_list:
        good_f = (got is expected)
        print(f"  {'OK  ' if good_f else 'FAIL'}: {label:<32} -> {got}")
        ok = ok and good_f
    _verdict(ok, "the brief report names the reason, one token each.")


async def test_resource_usage():
    """The result carries the run's RESOURCE USAGE: cpu time (SUMMED
    over every stage -- WORK adds up), wall clock (elapsed), and peak
    memory (high-water mark). Values are machine-dependent, so the
    checks assert PRESENCE and SIGN only, never magnitudes -- the GOOD
    file stays stable across machines. The application holds memory
    across a watchdog poll so the measurement is deterministic."""
    app = ("import time\n"
           "hold = bytearray(16 * 1024 * 1024)  # 16 MiB held below\n"
           "s = 0\n"
           "for i in range(2_000_000): s += i    # burn a little cpu\n"
           "print('value', s % 7)\n"
           "time.sleep(0.6)  # >= 2 watchdog polls while memory is held\n"
           "print(len(hold))\n")

    with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
        # No judged channel: the run is driven to its natural end and
        # its resource usage is read off the result (stdout drained).
        result = await run_test_app(ProcsitterConfigTestRun(
            command      = _argv(app),
            procsitter      = Procsitter(ProcsitterConfig(max_wall_clock_sec=10.0),
                                   work_dir)))

    print(f"INSPECT: cpu_measured   = {result.cpu_time_sec is not None}")
    print(f"INSPECT: wall_positive  = {result.wall_clock_sec > 0.0}")
    print(f"INSPECT: mem_measured   = {result.peak_memory_mb is not None}")
    ok = _check([
        (result.cpu_time_sec is not None and result.cpu_time_sec >= 0.0,
         "cpu_time_sec reported -- total WORK, summed over stages"),
        (result.wall_clock_sec > 0.0,
         "wall_clock_sec reported -- elapsed time"),
        (result.peak_memory_mb is not None and result.peak_memory_mb > 0.0,
         "peak_memory_mb reported -- high-water mark (psutil present)"),
        (result.cpu_time_sec is None
         or result.cpu_time_sec <= result.wall_clock_sec + 5.0,
         "cpu time is sane against wall clock (single stage)"),
    ])
    _verdict(ok, "the result carries the run's time and memory.")


async def test_stdout_logging():
    """The stdout production, tapped to files -- 'before' and 'after'
    the pype. A log is a plain consumer on a production port (tee); it
    does not touch the verdict. The test app emits items in RANDOM
    order; the pype settles them. So 'before' must hold the raw random
    stream and 'after' the determinized one -- the very stream that is
    judged (identical to it) -- and the two must differ."""
    app = ("import random\n"
           "items = ['cherry', 'apple', 'durian', 'banana']\n"
           "random.shuffle(items)\n"
           "for item in items:\n"
           "    print('item ' + item)\n"
           "print('done')\n")

    pype_script = (
        'on: <bof> => {\n'
        '    box = []\n'
        '}\n'
        'on: "item" <name = "*"> => {\n'
        '    box.append(name)\n'
        '    print("an item arrived (%d so far)" % len(box))\n'
        '}\n'
        'on: "done" => {\n'
        '    print("items, sorted:")\n'
        '    for name in sorted(box):\n'
        '        print("    " + name)\n'
        '}\n'
        'on: <else> => ignore;\n')

    nominal = ("an item arrived (1 so far)\n"
               "an item arrived (2 so far)\n"
               "an item arrived (3 so far)\n"
               "an item arrived (4 so far)\n"
               "items, sorted:\n"
               "    apple\n"
               "    banana\n"
               "    cherry\n"
               "    durian\n")

    with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
        script_path = os.path.join(work_dir, "settle.pype")
        with open(script_path, "w") as fh:
            fh.write(pype_script)
        before_path = os.path.join(work_dir, "raw.log")
        after_path  = os.path.join(work_dir, "final.log")

        config = ProcsitterConfigTestRun(
            command      = _argv(app),
            procsitter      = Procsitter(ProcsitterConfig(max_wall_clock_sec=15.0),
                                   work_dir),
            pype_command = [sys.executable, HWUT_PYPE, script_path],
            pype_procsitter = Procsitter(ProcsitterConfig(max_wall_clock_sec=15.0),
                                   work_dir),
            channel      = Comparator(io.StringIO(nominal), Configuration()),
            stdout_log_before_pype = before_path,
            stdout_log_after_pype  = after_path)
        judgement = await run_test_app(config)

        with open(before_path) as fh: before_text = fh.read()
        with open(after_path)  as fh: after_text  = fh.read()

    raw_lines   = before_text.split()
    raw_items   = sorted(l for l in before_text.splitlines()
                         if l.startswith("item "))
    print(f"INSPECT: verdict = {judgement.verdict}; "
          f"before {len(before_text.splitlines())} lines, "
          f"after {len(after_text.splitlines())} lines; "
          f"before==after: {before_text == after_text}")
    ok = _check([
        (judgement.verdict is True,
         "logging did not disturb the verdict"),
        (after_text == nominal,
         "'after' log holds the DETERMINIZED stream -- what is judged"),
        (raw_items == ["item apple", "item banana",
                       "item cherry", "item durian"]
         and "done" in raw_lines,
         "'before' log holds the app's RAW stdout (all items + done)"),
        (before_text != after_text,
         "raw and determinized streams differ -- the pype did work"),
    ])
    _verdict(ok, "stdout tapped raw and determinized, verdict untouched.")


async def test_associate_full():
    """THE LAWYER over the WHOLE specification at once: a live pype
    channel (stdout determinized before judging), the stderr channel,
    AND a file determinized POST-EXIT -- every subject aligned into
    ChunkPairs by an ASYNC consumer. The determinizers are plain
    'sort' one-liners (no hwut_pype needed). Random input, fixed
    nominals: the Lawyer's per-subject reductions must all be True and
    every subject must be labelled."""
    sort_stdin = ("import sys; "
                  "sys.stdout.write(''.join(sorted(sys.stdin.readlines())))")
    sort_file  = ("import sys; "
                  "sys.stdout.write(''.join(sorted("
                  "open(sys.argv[1]).readlines())))")
    app = ("import sys, random\n"
           "outs = ['gamma', 'alpha', 'beta']\n"
           "random.shuffle(outs)\n"
           "for w in outs:\n"
           "    print(w)\n"
           "print('warn one', file=sys.stderr)\n"
           "print('warn two', file=sys.stderr)\n"
           "rows = ['three', 'one', 'two']\n"
           "random.shuffle(rows)\n"
           "with open('data.txt', 'w') as fh:\n"
           "    for w in rows:\n"
           "        fh.write(w + '\\n')\n")

    labels = set()
    async def consumer(subject_name, chunk_pair):   # ASYNC on purpose
        labels.add(subject_name)

    with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
        config = ProcsitterConfigTestRun(
            command      = _argv(app),
            procsitter      = Procsitter(ProcsitterConfig(max_wall_clock_sec=15.0),
                                   work_dir),
            pype_command = [sys.executable, "-c", sort_stdin],
            pype_procsitter = Procsitter(ProcsitterConfig(max_wall_clock_sec=15.0),
                                   work_dir),
            channel       = Comparator(io.StringIO("alpha\nbeta\ngamma\n"),
                                       Configuration()),
            error_channel = Comparator(io.StringIO("warn one\nwarn two\n"),
                                       Configuration()),
            file_db = {
                "data.txt": Comparator(
                    io.StringIO("one\nthree\ntwo\n"), Configuration(),
                    pype_procsitter = Procsitter(
                        ProcsitterConfig(max_wall_clock_sec=15.0), work_dir),
                    pype_command = [sys.executable, "-c", sort_file])})
        judgement = await run_test_app(config, consumer=consumer)

    file_record, = judgement.file_stage_db["data.txt"]
    print(f"INSPECT: verdicts = "
          f"{sorted(judgement.subject_verdict_db.items())}; "
          f"labels = {sorted(labels)}; "
          f"file pype = {file_record.containment.name}")
    ok = _check([
        (judgement.subject_verdict_db == {"stdout": True, "stderr": True,
                                          "data.txt": True},
         "Lawyer reduced EVERY subject (live pype, stderr, file) to True"),
        (labels == {"stdout", "stderr", "data.txt"},
         "the async consumer saw a ChunkPair for every subject"),
        (file_record.containment is E_Containment.OK_COMPLETED,
         "post-exit file pype accounted -- its own record"),
        (judgement.verdict is True,
         "overall verdict True across all three subjects"),
    ])
    _verdict(ok, "the Lawyer aligns stdout, stderr and files at once.")


async def test_logging_no_pype():
    """Logging WITHOUT a pype stage: 'before' and 'after' both tap the
    SAME production (the test app's stdout is what is judged), so the
    two files hold IDENTICAL bytes -- and neither disturbs the
    verdict."""
    app     = ("print('one')\n"
               "print('two')\n"
               "print('three')\n")
    nominal = "one\ntwo\nthree\n"

    with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
        before_path = os.path.join(work_dir, "raw.log")
        after_path  = os.path.join(work_dir, "final.log")
        config = ProcsitterConfigTestRun(
            command      = _argv(app),
            procsitter      = Procsitter(ProcsitterConfig(max_wall_clock_sec=10.0),
                                   work_dir),
            channel      = Comparator(io.StringIO(nominal), Configuration()),
            stdout_log_before_pype = before_path,
            stdout_log_after_pype  = after_path)
        judgement = await run_test_app(config)
        with open(before_path) as fh: before_text = fh.read()
        with open(after_path)  as fh: after_text  = fh.read()

    print(f"INSPECT: verdict = {judgement.verdict}; "
          f"before==after: {before_text == after_text}")
    ok = _check([
        (judgement.verdict is True,       "logging did not disturb the verdict"),
        (before_text == nominal,          "'before' log holds the app's stdout"),
        (after_text == before_text,
         "no pype stage -> 'after' is the SAME production as 'before'"),
    ])
    _verdict(ok, "with no pype, before and after tap one production.")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Judged test application run: chain + two axes",
        choice_map = {
            "equivalence_ok":          test_equivalence_ok,
            "equivalence_fail_fast":   test_equivalence_fail_fast,
            "association":             test_association,
            "pype_deterministicalize": test_pype_deterministicalize,
            "contained_run":           test_contained_run,
            "output_file":             test_output_file,
            "spec_channel_and_files":  test_spec_channel_and_files,
            "spec_file_pype":          test_spec_file_pype,
            "stderr_channel":          test_stderr_channel,
            "result_classification":   test_result_classification,
            "resource_usage":          test_resource_usage,
            "stdout_logging":          test_stdout_logging,
            "associate_full":          test_associate_full,
            "logging_no_pype":         test_logging_no_pype,
        },
        happy      = "SUCCESS.*",
    ).run()
