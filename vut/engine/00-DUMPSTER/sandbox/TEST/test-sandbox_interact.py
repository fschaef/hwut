#!/usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Verify THE TWO-WAY TEE (SandboxTee): eavesdrop a supervised
         call's stdout (the original consumer still sees everything),
         inject into its stdin. THE TEE IS THE WHOLE FEATURE -- no
         convenience function; every scenario below is PIPE
         COMPOSITION with 'Sandbox.run()' as it stands.

DESCRIPTION:

The flagship scenario is TWO SANDBOXES INTERACTING via stdout and
stdin: a CONTROLLER providing control signals for the process under
test, each end its own supervised call, wired in a loop through the
tee. The idiom (also in the SandboxTee docstring):

    async def run_subject():
        try:     return await subject.run(cmd,
                     stdout_handler=tee.stdout_handler,
                     stdin_reader  =tee.stdin_reader)
        finally: tee.tap.close()     # subject gone -> controller EOF

    async def run_controller():
        try:     return await controller.run(ctrl_cmd,
                     stdin_reader   =tee.tap.reader,
                     stdout_handler =tee.inject.feed)
        finally: tee.inject.close()  # controller gone -> stdin EOF

    await asyncio.gather(run_subject(), run_controller())

More sophisticated pipe-interaction scenarios (a controller riding a
judged or pype-ed run, tees inside sequences) come LATER; the tee is
the complete building block for them.

CHOICES:

  tee_copy:        eavesdrop, never steal: the original consumer AND
                   the tap both see the COMPLETE stdout, byte for
                   byte.
  control_signals: TWO SANDBOXES interact via stdout/stdin: the
                   controller answers the subject's reports with
                   control signals (ping/work/shutdown); both ends
                   supervised, one attribution record each; natural
                   end on both sides.
  pype_interactor: the controller is a PYPE SCRIPT in its own sandbox
                   ('python3 -u': unbuffered, else the answer never
                   arrives) -- the same wiring, nothing special.
  sequence_stdin:  SandboxSequence(stdin_reader=...): recorded input
                   fed into the FIRST stage of a pipeline,
                   transformed along the chain, read at the tail.

AUTHOR: Frank-Rene Schaefer
"""

import asyncio      # noqa F401  (HwutRunner drives the coroutines)
import logging
import os
import shlex
import sys
import tempfile

from   config import HwutRunner                                     # noqa F401

from   vut.engine.sandbox.sandbox import (Sandbox,                  # noqa E402
                                          SandboxConfig,
                                          SandboxPipe,
                                          SandboxSequence,
                                          SandboxTee)

logging.getLogger("asyncio").setLevel(logging.ERROR)

PY        = shlex.quote(sys.executable)
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


async def _read_all(reader) -> bytes:
    """
    RETURN: bytes, everything 'reader' delivers until EOF.
    """
    box = bytearray()
    while not reader.at_eof():
        box += await reader.read(4096)
    return bytes(box)


async def _interaction(tee, subject, subject_cmd,
                       controller, controller_cmd):
    """
    RETURN: (SandboxResult, SandboxResult) -- subject and controller
            records of TWO SANDBOXES wired in a loop through 'tee':
            subject stdout -> tap -> controller stdin; controller
            stdout -> inject -> subject stdin. THE IDIOM -- pure pipe
            composition, 'finally' closers hand EOF onward whichever
            end finishes first.
    """
    async def run_subject():
        try:
            return await subject.run(subject_cmd,
                                     stdout_handler=tee.stdout_handler,
                                     stdin_reader  =tee.stdin_reader)
        finally:
            tee.tap.close()      # subject gone -> controller sees EOF

    async def run_controller():
        try:
            return await controller.run(controller_cmd,
                                        stdin_reader  =tee.tap.reader,
                                        stdout_handler=tee.inject.feed)
        finally:
            tee.inject.close()   # controller gone -> subject stdin EOF

    return await asyncio.gather(run_subject(), run_controller())


# ---------------------------------------------------------------------------

async def test_tee_copy():
    """Eavesdrop, never steal: the tee duplicates -- the original
    consumer and the tap both see the COMPLETE stdout. Wired by hand:
    the tee's faces are ordinary 'run()' arguments."""
    app = ("print('alpha')\n"
           "print('beta')\n"
           "print('gamma')\n")

    consumer_box = bytearray()
    async def consumer(data):
        consumer_box.extend(data)

    tee = SandboxTee(stdout_handler=consumer)
    tee.inject.close()           # nothing to inject: stdin EOF at once

    async def eavesdropper():
        return await _read_all(tee.tap.reader)

    with tempfile.TemporaryDirectory(prefix="vut_tee_") as work_dir:
        sandbox   = Sandbox(SandboxConfig(max_wall_clock_sec=10.0),
                            work_dir)
        eaves_task = asyncio.create_task(eavesdropper())
        result     = await sandbox.run(_cmd(app),
                                       stdout_handler=tee.stdout_handler,
                                       stdin_reader  =tee.stdin_reader)
        tee.tap.close()          # subject gone -> eavesdropper EOF
        tap_bytes  = await eaves_task

    expected = b"alpha\nbeta\ngamma\n"
    print(f"INSPECT: consumer = {bytes(consumer_box)!r}")
    print(f"INSPECT: tap      = {tap_bytes!r}")
    ok = _check([
        (result.ok,                       "supervised call completed"),
        (bytes(consumer_box) == expected, "original consumer: complete"),
        (tap_bytes           == expected, "eavesdropper's tap: complete"),
    ])
    _verdict(ok, "the tee copies; nobody is robbed.")


async def test_control_signals():
    """TWO SANDBOXES interact via stdout and stdin: the subject
    REPORTS, the controller answers with CONTROL SIGNALS -- ping,
    work, shutdown. Each end is its own supervised call with its own
    attribution record; the dialogue ends NATURALLY on both sides.
    The transcript (the subject's stdout) stays fully visible to the
    original consumer -- the tee eavesdrops, it does not steal."""
    subject_app = ("import sys\n"
                   "print('ready', flush=True)\n"
                   "for line in sys.stdin:\n"
                   "    signal = line.strip()\n"
                   "    if   signal == 'ping':     print('pong', flush=True)\n"
                   "    elif signal == 'work':     print('result 42', flush=True)\n"
                   "    elif signal == 'shutdown':\n"
                   "        print('bye', flush=True)\n"
                   "        break\n")

    controller_app = ("import sys\n"
                      "for line in sys.stdin:\n"
                      "    report = line.strip()\n"
                      "    if   report == 'ready':     print('ping', flush=True)\n"
                      "    elif report == 'pong':      print('work', flush=True)\n"
                      "    elif report == 'result 42': print('shutdown', flush=True)\n"
                      "    elif report == 'bye':       break\n")

    transcript = bytearray()
    async def consumer(data):
        transcript.extend(data)

    with tempfile.TemporaryDirectory(prefix="vut_tee_") as work_dir:
        tee = SandboxTee(stdout_handler=consumer)
        subject_result, controller_result = await _interaction(
            tee,
            Sandbox(SandboxConfig(max_wall_clock_sec=15.0), work_dir),
            _cmd(subject_app),
            Sandbox(SandboxConfig(max_wall_clock_sec=15.0), work_dir),
            _cmd(controller_app))

    text = transcript.decode()
    print("INSPECT: subject transcript:")
    for line in text.splitlines():
        print(f"    | {line}")
    ok = _check([
        (subject_result.ok,
         "subject: own attribution record, clean, natural end"),
        (controller_result.ok,
         "controller: own attribution record, clean, natural end"),
        (text == "ready\npong\nresult 42\nbye\n",
         "the control dialogue ran to completion, in order"),
    ])
    _verdict(ok, "control signals via stdout/stdin -- two supervised "
                 "calls, one loop.")


async def test_pype_interactor():
    """The controller is a PYPE SCRIPT in its own sandbox: the SAME
    wiring as any two-sandbox interaction, nothing special. App
    stdout is pype's stdin; pype's printed reactions are the app's
    stdin ('python3 -u': unbuffered -- a buffered answer never
    arrives)."""
    app = ("import sys\n"
           "print('ask: capital-of-france', flush=True)\n"
           "a1 = sys.stdin.readline().strip()\n"
           "print('got ' + a1, flush=True)\n"
           "print('ask: six-times-seven', flush=True)\n"
           "a2 = sys.stdin.readline().strip()\n"
           "print('got ' + a2, flush=True)\n"
           "print('dialogue-done', flush=True)\n")

    pype_script = ('on: "capital-of-france" => {\n'
                   '    print("paris")\n'
                   '}\n'
                   'on: "six-times-seven" => {\n'
                   '    print("42")\n'
                   '}\n'
                   'on: <else> => ignore;\n')

    if not _require_hwut_pype(): return
    transcript = bytearray()
    async def consumer(data):
        transcript.extend(data)

    with tempfile.TemporaryDirectory(prefix="vut_tee_") as work_dir:
        script_path = os.path.join(work_dir, "answers.pype")
        with open(script_path, "w") as fh:
            fh.write(pype_script)

        tee = SandboxTee(stdout_handler=consumer)
        result, pype_result = await _interaction(
            tee,
            Sandbox(SandboxConfig(max_wall_clock_sec=15.0), work_dir),
            _cmd(app),
            Sandbox(SandboxConfig(max_wall_clock_sec=15.0), work_dir),
            f"{PY} -u {shlex.quote(HWUT_PYPE)} {shlex.quote(script_path)}")

    text = transcript.decode()
    print("INSPECT: transcript:")
    for line in text.splitlines():
        print(f"    | {line}")
    ok = _check([
        (result.ok,                  "app: own attribution record, clean"),
        (pype_result.ok,
         "pype controller: OWN attribution record, clean"),
        ("got paris" in text,        "first answer injected by pype"),
        ("got 42" in text,           "second answer injected by pype"),
        ("dialogue-done" in text,    "the dialogue reached its end"),
    ])
    _verdict(ok, "a pype script drives the dialogue -- same wiring, "
                 "supervised on both ends.")


async def test_sequence_stdin():
    """The composition hook: recorded input fed into the FIRST stage
    of a pipeline ('stdin_reader'), transformed along the chain, read
    at the tail."""
    app_upper  = ("import sys\n"
                  "for line in sys.stdin:\n"
                  "    print(line.strip().upper(), flush=True)\n")
    app_prefix = ("import sys\n"
                  "for line in sys.stdin:\n"
                  "    print('* ' + line.strip(), flush=True)\n")

    source = SandboxPipe()
    await source.feed(b"banana\napple\ncherry\n")
    source.close()

    with tempfile.TemporaryDirectory(prefix="vut_tee_") as work_dir:
        sequence = SandboxSequence(
            [(Sandbox(SandboxConfig(max_wall_clock_sec=10.0), work_dir),
              _cmd(app_upper)),
             (Sandbox(SandboxConfig(max_wall_clock_sec=10.0), work_dir),
              _cmd(app_prefix))],
            stdin_reader=source.reader)
        tail_bytes  = await _read_all(sequence.tail.reader)
        record_list = await sequence.collect()

    text = tail_bytes.decode()
    print("INSPECT: tail:")
    for line in text.splitlines():
        print(f"    | {line}")
    ok = _check([
        (all(r.ok for r in record_list),
         "both stages completed -- one record each"),
        (text == "* BANANA\n* APPLE\n* CHERRY\n",
         "recorded input traversed the whole pipeline"),
    ])
    _verdict(ok, "the first stage drinks from a pipe like any other.")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The two-way tee: eavesdrop stdout, inject stdin -- "
                     "pure pipe composition",
        choice_map = {
            "tee_copy":        test_tee_copy,
            "control_signals": test_control_signals,
            "pype_interactor": test_pype_interactor,
            "sequence_stdin":  test_sequence_stdin,
        },
        happy      = "SUCCESS.*",
    ).run()
