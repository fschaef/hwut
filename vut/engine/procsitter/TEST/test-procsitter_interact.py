#!/usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Verify the composition algebra of the two building blocks:
         the LINK (production -> control edge) and 'tee()' (the
         CONSUMER SUM -- anyone may listen to a production port; one
         voice commands a control port).

DESCRIPTION:

THE TWO AXES: PRODUCTION (stdout; stderr as diagnostic production)
and CONTROL (stdin). Everything here is wiring of Links between
production and control ports of supervised calls -- no further class:

  fan-out    tee(b.feed, c.feed)      consumers ADD
  loop       A -> C, C -> A           the man in the middle
  chain      chain(stages)     the three chain rules

CHOICES:

  tee_copy:        eavesdrop, never steal: tee() duplicates -- the
                   original consumer AND the listener both see the
                   COMPLETE production, byte for byte.
  control_signals: TWO PROCSITTERS interact via production/control:
                   the controller answers the subject's reports with
                   control signals (ping/work/shutdown); both ends
                   supervised, one attribution record each; natural
                   end on both sides.
  pype_interactor: the controller is a PYPE SCRIPT in its own
                   procsitter ('python3 -u': unbuffered, else the
                   answer never arrives) -- the same wiring, nothing
                   special.
  chain_stdin:     chain(stdin_reader=...): recorded input
                   fed into the FIRST stage's control port,
                   transformed along the chain, read at the tail.
  chain_stop_early:CHAIN RULE 2 -- a downstream stage that ends while
                   an upstream still runs STOPS the upstream (SIGPIPE
                   semantics; bounds the in-memory buffers).
  tee_degenerate:  the tee algebra at its borders -- tee(one) is the
                   consumer itself; tee() is the empty sum (discards,
                   the run still completes).

AUTHOR: Frank-Rene Schaefer
"""

import asyncio      # noqa F401  (HwutRunner drives the coroutines)
import logging
import os
import sys
import tempfile

from   config import HwutRunner                                     # noqa F401

from   vut.engine.procsitter.procsitter   import (Procsitter,      # noqa E402
                                                  ProcsitterConfig,
                                                  E_Containment)
from   vut.engine.procsitter.construction import (Link,            # noqa E402
                                                  chain,
                                                  tee)

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


async def _read_all(reader) -> bytes:
    """
    RETURN: bytes, everything 'reader' delivers until EOF.
    """
    box = bytearray()
    while not reader.at_eof():
        box += await reader.read(4096)
    return bytes(box)


async def _interaction(consumer, subject, subject_cmd,
                       controller, controller_cmd):
    """
    RETURN: (ProcsitterResult, ProcsitterResult) -- subject and
            controller records of TWO PROCSITTERS wired in a LOOP of
            Links: the subject's production is tee'd to 'consumer' AND
            to the controller's control port; the controller's
            production answers into the subject's control port. THE
            IDIOM -- pure composition, 'finally' closers hand EOF
            onward whichever end finishes first.
    """
    to_ctrl = Link()     # subject production -> controller control
    back    = Link()     # controller production -> subject control

    async def run_subject():
        try:
            return await subject.run(
                subject_cmd,
                stdout_handler=tee(consumer, to_ctrl.feed),
                stdin_reader  =back.reader)
        finally:
            to_ctrl.close()      # subject gone -> controller sees EOF

    async def run_controller():
        try:
            return await controller.run(controller_cmd,
                                        stdin_reader  =to_ctrl.reader,
                                        stdout_handler=back.feed)
        finally:
            back.close()         # controller gone -> subject stdin EOF

    return await asyncio.gather(run_subject(), run_controller())


# ---------------------------------------------------------------------------

async def test_tee_copy():
    """Eavesdrop, never steal: 'tee()' is the CONSUMER SUM -- the
    original consumer and the added listener both see the COMPLETE
    production, byte for byte. Wired by hand: the summed handler is
    an ordinary 'run()' argument."""
    app = ("print('alpha')\n"
           "print('beta')\n"
           "print('gamma')\n")

    consumer_box = bytearray()
    async def consumer(data):
        consumer_box.extend(data)

    listen = Link()              # the second listener on the production

    async def listener():
        return await _read_all(listen.reader)

    with tempfile.TemporaryDirectory(prefix="vut_tee_") as work_dir:
        procsitter  = Procsitter(ProcsitterConfig(max_wall_clock_sec=10.0), work_dir)
        listen_task = asyncio.create_task(listener())
        result      = await procsitter.run(_argv(app), stdout_handler=tee(consumer, listen.feed))
        listen.close() # producer gone -> listener EOF
        listened    = await listen_task

    expected = b"alpha\nbeta\ngamma\n"
    print(f"INSPECT: consumer = {bytes(consumer_box)!r}")
    print(f"INSPECT: listener = {listened!r}")
    ok = _check([
        (result.containment is E_Containment.OK_COMPLETED, "supervised call completed"),
        (bytes(consumer_box) == expected,                  "original consumer: complete"),
        (listened            == expected,                  "added listener: complete"),
    ])
    _verdict(ok, "the tee copies; nobody is robbed.")


async def test_control_signals():
    """TWO PROCSITTERS interact via stdout and stdin: the subject
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
        subject_result, controller_result = await _interaction(
            consumer,
            Procsitter(ProcsitterConfig(max_wall_clock_sec=15.0), work_dir),
            _argv(subject_app),
            Procsitter(ProcsitterConfig(max_wall_clock_sec=15.0), work_dir),
            _argv(controller_app))

    text = transcript.decode()
    print("INSPECT: subject transcript:")
    for line in text.splitlines():
        print(f"    | {line}")
    ok = _check([
        (subject_result.containment is E_Containment.OK_COMPLETED,
         "subject: own attribution record, clean, natural end"),
        (controller_result.containment is E_Containment.OK_COMPLETED,
         "controller: own attribution record, clean, natural end"),
        (text == "ready\npong\nresult 42\nbye\n",
         "the control dialogue ran to completion, in order"),
    ])
    _verdict(ok, "control signals via stdout/stdin -- two supervised "
                 "calls, one loop.")


async def test_pype_interactor():
    """The controller is a PYPE SCRIPT in its own procsitter: the SAME
    wiring as any two-procsitter interaction, nothing special. App
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

        result, pype_result = await _interaction(
            consumer,
            Procsitter(ProcsitterConfig(max_wall_clock_sec=15.0), work_dir),
            _argv(app),
            Procsitter(ProcsitterConfig(max_wall_clock_sec=15.0), work_dir),
            [sys.executable, "-u", HWUT_PYPE, script_path])

    text = transcript.decode()
    print("INSPECT: transcript:")
    for line in text.splitlines():
        print(f"    | {line}")
    ok = _check([
        (result.containment is E_Containment.OK_COMPLETED,                  "app: own attribution record, clean"),
        (pype_result.containment is E_Containment.OK_COMPLETED,
         "pype controller: OWN attribution record, clean"),
        ("got paris" in text,        "first answer injected by pype"),
        ("got 42" in text,           "second answer injected by pype"),
        ("dialogue-done" in text,    "the dialogue reached its end"),
    ])
    _verdict(ok, "a pype script drives the dialogue -- same wiring, "
                 "supervised on both ends.")


async def test_chain_stdin():
    """The chain's control hook: recorded input fed into the FIRST
    stage's control port ('chain(stdin_reader=...)'),
    transformed along the chain, read at the tail."""
    app_upper  = ("import sys\n"
                  "for line in sys.stdin:\n"
                  "    print(line.strip().upper(), flush=True)\n")
    app_prefix = ("import sys\n"
                  "for line in sys.stdin:\n"
                  "    print('* ' + line.strip(), flush=True)\n")

    source = Link()
    await source.feed(b"banana\napple\ncherry\n")
    source.close()

    with tempfile.TemporaryDirectory(prefix="vut_tee_") as work_dir:
        c = chain(
            [(Procsitter(ProcsitterConfig(max_wall_clock_sec=10.0), work_dir),
              _argv(app_upper)),
             (Procsitter(ProcsitterConfig(max_wall_clock_sec=10.0), work_dir),
              _argv(app_prefix))],
            stdin_reader=source.reader)
        tail_bytes  = await _read_all(c.tail.reader)
        record_list = await asyncio.gather(*c.task_tuple)

    text = tail_bytes.decode()
    print("INSPECT: tail:")
    for line in text.splitlines():
        print(f"    | {line}")
    ok = _check([
        (all(r.containment is E_Containment.OK_COMPLETED
             for r in record_list),
         "both stages completed -- one record each"),
        (text == "* BANANA\n* APPLE\n* CHERRY\n",
         "recorded input traversed the whole chain"),
    ])
    _verdict(ok, "the first stage drinks from a link like any other.")


async def test_chain_stop_early():
    """CHAIN RULE 2 -- STOP ON EARLY DEATH. A downstream stage that
    ends while an UPSTREAM stage still runs sets the shared stop_event
    (SIGPIPE semantics; this is what BOUNDS the in-memory buffers). The
    producer would emit forever; the consumer reads three lines and
    exits. The producer must be STOPPED promptly -- not run to its wall
    cap -- and be attributed FAIL_STOPPED, its own record intact."""
    producer = ("import time\n"
                "i = 0\n"
                "while True:\n"
                "    print('line %d' % i, flush=True)\n"
                "    i += 1\n"
                "    time.sleep(0.05)\n")
    consumer = ("import sys\n"
                "n = 0\n"
                "for line in sys.stdin:\n"
                "    n += 1\n"
                "    if n >= 3:\n"
                "        break\n")

    with tempfile.TemporaryDirectory(prefix="vut_tee_") as work_dir:
        c = chain([
            (Procsitter(ProcsitterConfig(max_wall_clock_sec=20.0), work_dir),
             _argv(producer)),
            (Procsitter(ProcsitterConfig(max_wall_clock_sec=20.0), work_dir),
             _argv(consumer))])
        # tail carries the consumer's (empty) production to EOF.
        tail_bytes  = await _read_all(c.tail.reader)
        prod_record, cons_record = await asyncio.gather(*c.task_tuple)

    print(f"INSPECT: producer = {prod_record.containment.name} "
          f"({prod_record.wall_clock_sec:.1f}s), "
          f"consumer = {cons_record.containment.name}")
    ok = _check([
        (cons_record.containment is E_Containment.OK_COMPLETED
         and cons_record.exit_code == 0,
         "consumer read its fill and exited cleanly -- own record"),
        (prod_record.containment is E_Containment.FAIL_STOPPED,
         "producer STOPPED by rule 2 (downstream died first)"),
        (prod_record.wall_clock_sec < 10.0,
         "producer stopped PROMPTLY -- nowhere near its 20 s wall cap"),
        (tail_bytes == b"",
         "the consumer produced nothing; the tail saw a clean EOF"),
    ])
    _verdict(ok, "a chain bounds itself: early death upstream-stops the rest.")


async def test_tee_degenerate():
    """The tee ALGEBRA at its borders. tee() with ONE consumer is that
    consumer -- the complete production reaches it. tee() with ZERO
    consumers is the EMPTY SUM: a valid handler that simply discards,
    and the production is still fully consumed so the run completes.
    Functions add; the empty sum is the identity."""
    app = ("print('a')\nprint('b')\nprint('c')\n")

    seen = bytearray()
    async def one(data):
        seen.extend(data)

    with tempfile.TemporaryDirectory(prefix="vut_tee_") as work_dir:
        r1 = await Procsitter(ProcsitterConfig(max_wall_clock_sec=10.0),
                        work_dir).run(_argv(app), stdout_handler=tee(one))
        r0 = await Procsitter(ProcsitterConfig(max_wall_clock_sec=10.0),
                        work_dir).run(_argv(app), stdout_handler=tee())

    print(f"INSPECT: one-consumer saw {seen.decode()!r}; "
          f"zero -> {r0.containment.name}, one -> {r1.containment.name}")
    ok = _check([
        (seen == b"a\nb\nc\n",
         "tee(one) delivers the COMPLETE production to the single consumer"),
        (r1.containment is E_Containment.OK_COMPLETED,
         "the one-consumer run completed cleanly"),
        (r0.containment is E_Containment.OK_COMPLETED,
         "tee() -- the empty sum -- discards, yet the run completes"),
    ])
    _verdict(ok, "the tee algebra holds at its borders: identity and empty sum.")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The two-way tee: eavesdrop stdout, inject stdin -- "
                     "pure pipe composition",
        choice_map = {
            "tee_copy":         test_tee_copy,
            "control_signals":  test_control_signals,
            "pype_interactor":  test_pype_interactor,
            "chain_stdin":      test_chain_stdin,
            "chain_stop_early": test_chain_stop_early,
            "tee_degenerate":   test_tee_degenerate,
        },
        happy      = "SUCCESS.*",
    ).run()
