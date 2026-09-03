"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE: 'spawn' -- ONE SUPERVISED CALL, synchronously, in the shape
         'subprocess.run' answers (E-28).

Every test application and every pype runs under the procsitter; a
test of the framework that runs a command of its own should get the
same supervision, and above all the same ANSWER to a command that
cannot be launched: a record that says so, not an exception out of the
test. 'subprocess.run' raises 'PermissionError' for a she-bang whose
interpreter lacks its execute bit and 'FileNotFoundError' for one that
names nothing; here both are 'FAIL_LAUNCH', with 'returncode' None
and the reason on 'stderr'.

It lives beside the procsitter, not in the test-writing support: the
support is SEALED (imports nothing of this tree), and a test that
wants the supervisor asks the supervisor.
______________________________________________________________________________
"""
from vut.engine.procsitter.procsitter   import (Procsitter,
                                                ProcsitterConfig,
                                                E_Containment)
from vut.engine.procsitter.construction import Link

import asyncio
import os

class CSpawned:
    """WHAT A SUPERVISED CALL ANSWERED, in the shape 'subprocess.run'
    answers so that a test reads it the same way -- and one thing more:
    a call that could not be LAUNCHED is an answer, not an exception.

    'returncode'  the call's own exit code; None where the supervisor
                  ended it or it never started
    'stdout'      str
    'stderr'      str; on a failed launch, the reason -- the command,
                  and what the system said
    'containment' the supervisor's word, 'E_Containment'
    """
    __slots__ = ("returncode", "stdout", "stderr", "containment")

    def __init__(self, returncode, stdout, stderr, containment):
        self.returncode  = returncode
        self.stdout      = stdout
        self.stderr      = stderr
        self.containment = containment

    def launched_f(self):
        """RETURN: bool, True where the command started at all."""
        from vut.engine.procsitter.procsitter import E_Containment
        return self.containment is not E_Containment.FAIL_LAUNCH


def spawn(argv, input=None, cwd=None, env=None, max_wall_clock_sec=60.0,
          capture_output=True, text=True):
    """
    RETURN: CSpawned, the answer of running 'argv' UNDER THE PROCSITTER
            -- the same supervision every test application and every
            pype gets from the framework (E-27). A command that cannot
            be launched -- not found, not executable, a she-bang that
            names nothing runnable -- comes back with 'returncode' None
            and the reason on 'stderr', never as a traceback out of the
            test.

    'input' is fed on stdin, closed after. 'capture_output' and 'text'
    are accepted so that a 'subprocess.run' call site reads unchanged;
    output is always captured, always text.
    """
    async def go():
        out, err = [], []
        async def take_out(data): out.append(data)
        async def take_err(data): err.append(data)
        source = Link()
        if input is not None:
            await source.feed(input.encode("utf-8") if isinstance(input, str)
                              else input)
        source.close()
        config = ProcsitterConfig(max_wall_clock_sec=max_wall_clock_sec,
                                  env=env)
        record = await Procsitter(config, cwd or os.getcwd()).run(
                     [str(a) for a in argv],
                     stdout_handler=take_out, stderr_handler=take_err,
                     stdin_reader=source.reader)
        return record, b"".join(out), b"".join(err)

    record, out, err = asyncio.run(go())
    stdout = out.decode("utf-8", errors="replace")
    stderr = err.decode("utf-8", errors="replace")
    if record.containment is E_Containment.FAIL_LAUNCH:
        stderr = ("LAUNCH FAILED: %s -- not found, not executable, or a "
                  "she-bang naming nothing runnable\n"
                  % " ".join(str(a) for a in argv))
    return CSpawned(record.exit_code, stdout, stderr, record.containment)

