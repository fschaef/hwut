"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.run' COMMAND LINE -- the tree run made visible. It
         explores below the root, determines what the wish states,
         runs it through the real dispatcher, and renders the report
         stream live in the tier-1 plain console form (display/).

    hwut.run                    everything the tree offers
    --fail --pass --since=<point> --until=<point> --glob <target>
                                the selection wish, as in 'hwut.plan'
    --directory=<path>          the root to run below; the current
                                directory else
    --no-store                  the store knob: no subject recorded
    --jobs=<n>                  the per-directory bound on work
                                standing at once; unbounded else
    -v --verbose                every event as it arrives
    --plain                     the default rendering, statable
    --quiet                     the closing blocks alone
    --silent                    nothing on stdout; faults on stderr
    --colour / --no-colour      enforcement over the colour gates
    --help                      this text

EXIT STATUS (E-1, services/_exit.py):
    0  every test green, no fault met
    1  a test failed, or a fault was met
    2  the command line cannot be read
    3  the command line reads, and asks for nothing
______________________________________________________________________________
"""
import asyncio
import os
import sys

from ...display.console            import (RenderingError,
                                           console_view,
                                           parse_rendering)
from ..exploration.task_list       import SelectionError
from ..plan.wish                   import WishError, parse_wish
from ..run.dispatcher              import test_run_dispatcher_factory
from ..run.orchestrate             import orchestrator
from ..run.summary                 import fold
from ._exit                        import E_ExitCode


USAGE = "usage: hwut.run [--fail] [--pass] [--since=<point>] " \
        "[--until=<point>]\n" \
        "                [--glob <target>]... [--no-store] " \
        "[--jobs=<n>]\n" \
        "                [-v|--verbose|--plain|--quiet|--silent]\n" \
        "                [--colour|--no-colour] [--directory=<path>]"

HELP = """hwut.run -- the tree run, rendered live

    hwut.run            runs everything the tree below the root
                        offers: per directory its frame, its builds,
                        its sessions, its tests

SELECTION -- the wish; the words of 'hwut.plan'
    --fail --pass --since=<point> --until=<point> --glob <target>
                        keywords of different kinds are AND'ed; the
                        globs OR'ed among themselves

EXECUTION
    --directory=<path>  the root to run below; the current one else
    --no-store          the store knob: no subject is recorded
    --jobs=<n>          the per-directory bound on work standing at
                        once; unbounded where absent

RENDERING -- one tier, the flags mutually exclusive
    -v, --verbose       every event as it arrives, the swallowed ones
                        included
    --plain             the default: the flow, the DIRECTORIES
                        roll-call, FAILURES last; statable redundantly
    --quiet             no flow; the closing blocks alone
    --silent            nothing on stdout; the exit status is the
                        whole report -- faults still go to stderr,
                        prefixed and nicknamed as in the flow

COLOUR -- decided once, at the door
    --colour            enforcement: on, over every gate, NO_COLOR
                        included
    --no-colour         off, always
    (neither)           on only where stdout is a terminal, NO_COLOR
                        and CI are unset, and TERM claims a capability

EXIT STATUS
    0   every test green, no fault met
    1   a test failed, or a fault was met; the report still printed
    2   the command line cannot be read: unknown option, malformed
        wish, a directory that does not exist
    3   the command line reads, and asks for nothing: a wish that
        selects no test, a tree holding no test directory

OTHER
    --help              this text"""


async def _drive(root, wish, record, worker_max_n, flow):
    """
    RETURN: list[dict], the whole report stream, rendered LIVE through
            'flow' as each event arrived; the closing 'None' consumed,
            not kept.

    Raises what determination raises -- 'orchestrator()' refuses
    BEFORE the first event.
    """
    queue = orchestrator(root, wish,
                         test_run_dispatcher_factory(record=record),
                         worker_max_n=worker_max_n)
    event_list = []
    while True:
        item = await queue.get()
        if item is None: return event_list
        event_list.append(item)
        flow.dispatch(item)


def main(argv=None, write=None, write_error=None):
    """
    RETURN: E_ExitCode, the exit status of the run (E-1): OK where
            every test stood and no fault was met, FAULT where one
            failed or one was met, REFUSED where the command line
            cannot be read, EMPTY where it reads and asks for nothing,
            SIGPIPE where the reader hung up.

    'write' takes one line at a time; 'print' where none is given, so
    a suite captures the face without a process -- a captured face is
    never a terminal, so its colour gate is shut unless '--colour'
    enforces. 'write_error' likewise, for the SILENT tier's faults;
    stderr where none is given.
    """
    captured_f = write is not None
    if write is None:       write       = print
    if write_error is None: write_error = \
        lambda line: print(line, file=sys.stderr)
    try:
        return _main(argv, write, write_error, captured_f)
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return E_ExitCode.SIGPIPE


def _main(argv, write, write_error, captured_f):
    """
    RETURN: E_ExitCode -- 'main' without the pipe guard.
    """
    if argv is None: argv = sys.argv[1:]
    if "--help" in argv:
        write(HELP)
        return E_ExitCode.OK

    try:
        wish, rest_list = parse_wish(argv)
    except WishError as error:
        write("REFUSED: %s" % error)
        write(USAGE)
        return E_ExitCode.REFUSED

    try:
        rendering_wish, rest_list = parse_rendering(rest_list)
    except RenderingError as error:
        write("REFUSED: %s" % error)
        write(USAGE)
        return E_ExitCode.REFUSED

    directory    = "."
    record       = None
    worker_max_n = None
    unknown      = []
    for argument in rest_list:
        if   argument.startswith("--directory="):
            directory = argument[len("--directory="):]
        elif argument == "--no-store":  record  = False
        elif argument.startswith("--jobs="):
            text = argument[len("--jobs="):]
            if not text.isdigit() or int(text) < 1:
                write("REFUSED: '--jobs' takes a positive integer, "
                      "not '%s'" % text)
                write(USAGE)
                return E_ExitCode.REFUSED
            worker_max_n = int(text)
        else:
            unknown.append(argument)
    if unknown:
        write("REFUSED: 'hwut.run' does not take: %s"
              % ", ".join(sorted(unknown)))
        write(USAGE)
        return E_ExitCode.REFUSED
    if not os.path.isdir(directory):
        write("REFUSED: the directory '%s' does not exist"
              % directory)
        write(USAGE)
        return E_ExitCode.REFUSED
    #  The machinery walks and launches below an ABSOLUTE root; the
    #  wire's paths stay relative to it either way.
    directory = os.path.abspath(directory)

    #  The face knows its own sink; display knows what a terminal is
    #  worth. Tier, ink and width are decided there, once.
    tty_f = (not captured_f) and sys.stdout.isatty()
    flow  = console_view(rendering_wish, write, write_error,
                         os.environ, tty_f)
    try:
        event_list = asyncio.run(
            _drive(directory, wish, record, worker_max_n, flow))
    except SelectionError as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    flow.tail()

    summary = fold(event_list)
    fail_n  = summary.fail_n if summary.fail_n is not None else 0
    if summary.fault_tuple or summary.good_f is False or fail_n > 0 \
       or (event_list and summary.good_f is None):
        return E_ExitCode.FAULT
    if not summary.verdict_db:
        return E_ExitCode.EMPTY
    return E_ExitCode.OK


if __name__ == "__main__":
    sys.exit(main())
