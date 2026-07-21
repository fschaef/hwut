#!/usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Verify the judged test application run: a SandboxSequence
         (supervised calls chained by pipes) whose tail is judged on
         the two axes of compare/main.py.

DESCRIPTION:

RUNNING and JUDGING are separate concerns. RUNNING is the general
SandboxSequence (sandbox.py): supervised calls connected stdout ->
stdin, one attribution record per stage. PIPE-CONSTRUCTION IS THE
INTERFACE in both directions -- between the stages, and toward
compare, which reads the sequence's tail. JUDGING is the two axes:

    judge_equivalence  'is_equivalent' -- THE JUDGE: investigating
                       correctness, quickly; fast-fail.
    judge_association  'associate' -- THE LAWYER: associating subject
                       lines with nominal lines for display.

Every judge_* returns one SandboxResult PER STAGE; every stage must
have completed (or been stopped by the fast-fail) for a verdict to
stand.

CHOICES:

  equivalence_ok:        subject equals nominal
                         -> ((COMPLETED,), True).            [Judge]
  equivalence_fail_fast: an early mismatching line -> compare aborts,
                         the sequence's stop_event kills the test app
                         long before its natural end
                         -> ((STOPPED,), False).             [Judge]
  association:           the same divergence through BOTH axes: the
                         Lawyer yields ChunkPairs to a consumer (run to
                         natural end, no fast-fail); the reduction over
                         ChunkPair.is_equivalent() must equal the
                         Judge's verdict -- THE LAW.  [Judge + Lawyer]
  pype_deterministicalize: a two-stage sequence: test app emitting
                         lines in RANDOM order | pype stage (its OWN
                         supervised call) deterministicalizing them ->
                         verdict True whatever the order was; BOTH
                         stage records COMPLETED.            [Judge]
  contained_run:         a memory bomb under judgement
                         -> ((MEMORY_EXCEEDED,), False); the sequence
                         unwinds cleanly on the kill.        [Judge]
  output_file:           an output FILE judged post-exit.    [Judge]
  spec_channel_and_files: THE RUN SPECIFICATION: channel vs.
                         comparator -- stdout judged LIVE, two output
                         files judged POST-EXIT, one judgement record
                         per subject; a mismatching file turns the
                         overall verdict False and is NAMED; the
                         Lawyer over the same spec labels every
                         ChunkPair with its subject and reduces to the
                         same verdicts (THE LAW).   [Judge + Lawyer]
  spec_file_pype:        a file with non-deterministic line order,
                         deterministicalized POST-EXIT by a pype
                         comparator (a one-stage sequence reading the
                         file) -> True; pype's own record accounted.
                                                             [Judge]

AUTHOR: Frank-Rene Schaefer
"""

import asyncio
import io
import logging
import os
import shlex
import sys
import tempfile

from   config import HwutRunner                                     # noqa F401

from   vut.engine.sandbox.sandbox      import (Sandbox,             # noqa E402
                                               SandboxConfig,
                                               SandboxSequence,
                                               E_Containment)
from   vut.engine.sandbox.run_test_app import (judge_equivalence,   # noqa E402
                                               judge_association,
                                               judge_output_file,
                                               judge_test_run,
                                               associate_test_run,
                                               Comparator,
                                               TestRunSpec)
from   vut.engine.compare.configuration import Configuration        # noqa E402

# Child-reap races between the harness's kill discipline and asyncio's
# child watcher may emit spurious warnings ("Unknown child process ...")
# -- harmless, but nondeterministic; the GOOD file must not see them.
logging.getLogger("asyncio").setLevel(logging.ERROR)

PY        = shlex.quote(sys.executable)
ROOT_DIR  = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                         "..", "..", "..", ".."))
HWUT_PYPE = os.path.join(ROOT_DIR, "tools", "hwut_pype", "hwut_pype.py")


def _cmd(app_code: str) -> str:
    """
    RETURN: str, a command line running 'app_code' with this interpreter.
    """
    return f"{PY} -c {shlex.quote(app_code)}"


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
        sequence = SandboxSequence(
            [(Sandbox(SandboxConfig(max_wall_clock_sec=10.0), work_dir),
              _cmd(app))])
        result_list, verdict = await judge_equivalence(
            sequence, io.StringIO(nominal), Configuration())
        result, = result_list

    print(f"INSPECT: containment = {result.containment.name}, "
          f"verdict = {verdict}")
    ok = _check([
        (result.containment is E_Containment.COMPLETED, "test app completed"),
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
        sequence = SandboxSequence(
            [(Sandbox(SandboxConfig(max_wall_clock_sec=20.0), work_dir),
              _cmd(app))])
        result_list, verdict = await judge_equivalence(
            sequence, io.StringIO(nominal), Configuration())
        result, = result_list

    print(f"INSPECT: containment = {result.containment.name}, "
          f"verdict = {verdict}")
    ok = _check([
        (verdict is False,                            "judged NOT equivalent"),
        (result.containment is E_Containment.STOPPED,
         "test app STOPPED by the fast-fail (not run to natural end)"),
        (result.wall_clock_sec < 10.0,
         "abort came long before the 30 s sleep ended"),
    ])
    _verdict(ok, "early mismatch stopped the sequence, fast-fail both ways.")


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

    def sequence(app, work_dir):
        """RETURN: SandboxSequence, one-stage run of 'app'."""
        return SandboxSequence(
            [(Sandbox(SandboxConfig(max_wall_clock_sec=10.0), work_dir),
              _cmd(app))])

    async def judge(app):
        """RETURN: bool, the Judge's verdict for 'app' against nominal."""
        with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
            _, verdict = await judge_equivalence(
                sequence(app, work_dir), io.StringIO(nominal),
                Configuration())
            return verdict

    async def lawyer(app):
        """RETURN: (SandboxResult, list), test-app record and the
                   ChunkPairs the Lawyer yielded for 'app'."""
        pair_list = []
        with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
            result_list = await judge_association(
                sequence(app, work_dir), io.StringIO(nominal),
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
        (result_d.containment is E_Containment.COMPLETED,
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
    against one fixed nominal. The run is a TWO-STAGE SandboxSequence;
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
        # each stage of the sequence in its OWN sandbox.
        sequence = SandboxSequence([
            (Sandbox(SandboxConfig(max_wall_clock_sec=15.0), work_dir),
             _cmd(app)),
            (Sandbox(SandboxConfig(max_wall_clock_sec=15.0), work_dir),
             f"{PY} {shlex.quote(HWUT_PYPE)} {shlex.quote(script_path)}"),
        ])
        result_list, verdict = await judge_equivalence(
            sequence, io.StringIO(nominal), Configuration())
        test_result, pype_result = result_list

    print(f"INSPECT: stage records = "
          f"test {test_result.containment.name}, "
          f"pype {pype_result.containment.name}; verdict = {verdict}")
    ok = _check([
        (test_result.containment is E_Containment.COMPLETED,
         "test app stage completed"),
        (pype_result.containment is E_Containment.COMPLETED
         and pype_result.exit_code == 0,
         "pype stage completed -- its own attribution record"),
        (verdict is True,
         "non-deterministic order judged equivalent BEHIND the pype stage"),
    ])
    _verdict(ok, "pype deterministicalized the sequence; compare agreed.")


async def test_contained_run():
    """A memory bomb under judgement: the containment kill must unwind
    the whole sequence cleanly, and a contained run is never
    equivalent."""
    app     = ("import time\n"
               "print('starting', flush=True)\n"
               "hoard = []\n"
               "while True:\n"
               "    hoard.append(bytearray(4 * 1024 * 1024))\n"
               "    time.sleep(0.01)\n")
    nominal = "starting\nfinished\n"

    with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
        sequence = SandboxSequence(
            [(Sandbox(SandboxConfig(max_memory_mb=96,
                                    max_wall_clock_sec=20.0), work_dir),
              _cmd(app))])
        result_list, verdict = await judge_equivalence(
            sequence, io.StringIO(nominal), Configuration())
        result, = result_list

    print(f"INSPECT: containment = {result.containment.name}, "
          f"verdict = {verdict}")
    ok = _check([
        (result.containment is E_Containment.MEMORY_EXCEEDED,
         "containment is MEMORY_EXCEEDED"),
        (verdict is False, "a contained run is never equivalent"),
    ])
    _verdict(ok, "containment kill unwound the judged sequence cleanly.")


async def test_output_file():
    """Channels are judged live; FILES are judged post-exit."""
    app     = ("with open('result.txt', 'w') as fh:\n"
               "    fh.write('measurement A\\n')\n"
               "    fh.write('measurement B\\n')\n")
    nominal_good = "measurement A\nmeasurement B\n"
    nominal_bad  = "measurement A\nmeasurement X\n"

    with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
        sandbox = Sandbox(SandboxConfig(max_wall_clock_sec=10.0), work_dir)
        result  = await sandbox.run(_cmd(app))
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
        (result.ok,                "test app completed cleanly"),
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

    def spec(report_nominal):
        """RETURN: TestRunSpec, stdout + two files vs. comparators."""
        return TestRunSpec(
            channel = Comparator(io.StringIO("run begins\nrun ends\n"),
                                 Configuration()),
            file_db = {
                "result.txt": Comparator(io.StringIO("measurement A\n"),
                                         Configuration()),
                "report.txt": Comparator(io.StringIO(report_nominal),
                                         Configuration()),
            })

    def sequence(work_dir):
        """RETURN: SandboxSequence, one-stage run of the app."""
        return SandboxSequence(
            [(Sandbox(SandboxConfig(max_wall_clock_sec=10.0), work_dir),
              _cmd(app))])

    with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
        good = await judge_test_run(sequence(work_dir),
                                    spec("total: 7 items\n"))
    with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
        bad  = await judge_test_run(sequence(work_dir),
                                    spec("total: 999 items\n"))

    label_set = set()
    with tempfile.TemporaryDirectory(prefix="vut_run_") as work_dir:
        lawyer = await associate_test_run(
            sequence(work_dir), spec("total: 999 items\n"),
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
    comparator carries a pype stage: post-exit, a one-stage sequence
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

        spec = TestRunSpec(
            channel = None,          # stdout drained, unjudged
            file_db = {
                "trace.txt": Comparator(
                    io.StringIO(nominal), Configuration(),
                    pype_sandbox      = Sandbox(
                        SandboxConfig(max_wall_clock_sec=15.0), work_dir),
                    pype_command_line = f"{PY} {shlex.quote(HWUT_PYPE)} "
                                        f"{shlex.quote(script_path)}"),
            })
        sequence = SandboxSequence(
            [(Sandbox(SandboxConfig(max_wall_clock_sec=15.0), work_dir),
              _cmd(app))])
        judgement = await judge_test_run(sequence, spec)

    pype_record, = judgement.file_stage_db["trace.txt"]
    print(f"INSPECT: verdicts = "
          f"{sorted(judgement.subject_verdict_db.items())}, "
          f"post-exit pype = {pype_record.containment.name}")
    ok = _check([
        (judgement.subject_verdict_db["trace.txt"] is True,
         "random file order judged equivalent BEHIND post-exit pype"),
        (pype_record.containment is E_Containment.COMPLETED
         and pype_record.exit_code == 0,
         "post-exit pype stage accounted -- its own attribution record"),
        (judgement.verdict is True,
         "overall verdict True"),
    ])
    _verdict(ok, "file deterministicalized post-exit, never during the run.")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Judged test application run: SandboxSequence + two axes",
        choice_map = {
            "equivalence_ok":          test_equivalence_ok,
            "equivalence_fail_fast":   test_equivalence_fail_fast,
            "association":             test_association,
            "pype_deterministicalize": test_pype_deterministicalize,
            "contained_run":           test_contained_run,
            "output_file":             test_output_file,
            "spec_channel_and_files":  test_spec_channel_and_files,
            "spec_file_pype":          test_spec_file_pype,
        },
        happy      = "SUCCESS.*",
    ).run()
