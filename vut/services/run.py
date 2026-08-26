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
    --timing                    keep the RUN'S CADENCE beside each
                                candidate: the delta time per line, in
                                seconds. An analyst aid, and what
                                'hwut.stability' reads. Refused beside
                                '--coverage': one measurement at a time
    --coverage                  the DEMAND (coverage D-19): every test
                                is built and run for coverage, every
                                completed run harvested; what
                                'hwut.cov <wish>' says
    --variant=<a>[,<b>...]      the VARIANT selection (E-9): one
                                alternative per variant group, merged
                                over the base configuration. Two
                                alternatives of ONE group, or a name
                                no group declares, are refused
    --jobs=<n>                  the host-global bound on work standing
                                at once, across every directory;
                                unbounded else
    --strategy=<name>           when a directory starts: linear (one
                                after another, in walk order; the
                                default), successor (the next starts
                                while the current runs), parallel (all
                                at once)
    --dbd --directory-by-directory
                                '--strategy=linear'
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

from   vut.engine.display.console                    import (HELP as RENDERING_HELP,
                                                             RenderingError,
                                                             console_view,
                                                             parse_rendering)
from   vut.engine.display.console                    import USAGE_TOKEN_TUPLE \
                                                             as RENDERING_TOKEN_TUPLE
from   vut.engine.orchestrator.exploration.task_list import SelectionError
from   vut.engine.orchestrator.plan.wish             import (HELP as WISH_HELP,
                                                             WishError,
                                                             parse_wish)
from   vut.engine.orchestrator.run.dispatcher        import test_run_dispatcher_factory
from   vut.engine.orchestrator.exploration.variant   import (name_tuple_of,
                                                             VariantError)
from   vut.engine.orchestrator.run.orchestrate       import orchestrator
from   vut.engine.orchestrator.run.strategy          import (DEFAULT_STRATEGY_NAME,
                                                             STRATEGY_DB,
                                                             strategy_of)
from   vut.engine.orchestrator.run.summary           import fold
from   vut.engine.orchestrator.plan.wish             import USAGE_TOKEN_TUPLE \
                                                             as WISH_TOKEN_TUPLE
from   ._core                                        import usage_line
from   ._exit                                        import E_ExitCode


USAGE = usage_line("usage: hwut.run",
                    WISH_TOKEN_TUPLE
                    + ("[--no-store]", "[--timing]", "[--jobs=<n>]",
                       "[--strategy=<name>]")
                        + RENDERING_TOKEN_TUPLE
                        + ("[--directory=<path>]",))

HELP = """hwut.run -- the tree run, rendered live

    hwut.run            runs everything the tree below the root
                        offers: per directory its frame, its builds,
                        its sessions, its tests

""" + WISH_HELP + """

EXECUTION
    --directory=<path>  the root to run below; the current one else
    --no-store          the store knob: no subject is recorded
    --timing            keep the run's cadence beside each candidate
    --jobs=<n>          the host-global bound on work standing at
                        once, across every directory; unbounded where
                        absent
    --strategy=<name>   when a directory's run starts:
                            linear     one after another, in walk
                                       order (the default)
                            successor  the next directory starts while
                                       the current one still runs
                            parallel   all at once
    --dbd               '--strategy=linear'
    --directory-by-directory

""" + RENDERING_HELP + """

EXIT STATUS
    0   every test green, no fault met
    1   a test failed, or a fault was met; the report still printed
    2   the command line cannot be read: unknown option, malformed
        wish, a directory that does not exist
    3   the command line reads, and asks for nothing: a wish that
        selects no test, a tree holding no test directory

OTHER
    --help              this text"""


async def _drive(root, wish, record, worker_max_n, strategy, flow,
                 coverage=None, variant_tuple=(), timing_f=False,
                 event_sink=None, despite_stain_f=False):
    """
    RETURN: list[dict], the whole report stream, rendered LIVE through
            'flow' as each event arrived; the closing 'None' consumed,
            not kept.

    Raises what determination raises -- 'orchestrator()' refuses
    BEFORE the first event.
    """
    queue = orchestrator(root, wish,
                         test_run_dispatcher_factory(
                             record=record, coverage=coverage,
                             variant_tuple=variant_tuple,
                             timing_f=timing_f,
                             despite_stain_f=despite_stain_f),
                         worker_max_n=worker_max_n, strategy=strategy)
    event_list = []
    while True:
        item = await queue.get()
        if item is None: return event_list
        event_list.append(item)
        if event_sink is not None: event_sink(item)
        flow.dispatch(item)


def main(argv=None, write=None, write_error=None, demand=None,
         event_sink=None, despite_stain_f=False):
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

    'despite_stain_f' runs a STAINED choice anyway -- 'hwut.stability'
    proving what it disqualified. No command line reaches it: a stain
    is answered by proof or by removal, never by asking again.

    'event_sink' takes each report event as it arrives, beside the
    rendering. THE STREAM IS THE RUN'S TRUTH (O-4) and whoever wants
    the whole folds it; this is the seam a FACE ABOVE THIS ONE folds
    at -- 'hwut.stability' does. None: nobody is listening.
    """
    captured_f = write is not None
    if write is None:       write       = print
    if write_error is None: write_error = \
        lambda line: print(line, file=sys.stderr)
    try:
        return _main(argv, write, write_error, captured_f, demand,
                     event_sink, despite_stain_f)
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return E_ExitCode.SIGPIPE


def _main(argv, write, write_error, captured_f, demand=None,
          event_sink=None, despite_stain_f=False):
    """
    RETURN: E_ExitCode -- 'main' without the pipe guard.

    'demand' is a CoverageConfig a FACE hands in for '--coverage' --
    the seam through which 'hwut.cov' and its tests state the tool
    until '--variant' selects it from the configuration (todo-13).
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
    coverage     = None
    variant_text = ""
    timing_f     = False
    worker_max_n = None
    strategy     = strategy_of(DEFAULT_STRATEGY_NAME)
    unknown      = []
    for argument in rest_list:
        if   argument.startswith("--directory="):
            directory = argument[len("--directory="):]
        elif argument == "--no-store":  record   = False
        elif argument == "--timing":    timing_f = True
        elif argument == "--coverage":
            from vut.engine.coverage.configuration import CoverageConfig
            coverage = demand if demand is not None else CoverageConfig()
        elif argument.startswith("--variant="):
            variant_text = argument[len("--variant="):]
        elif argument in ("--dbd", "--directory-by-directory"):
            strategy = strategy_of("linear")
        elif argument.startswith("--strategy="):
            name = argument[len("--strategy="):]
            if name not in STRATEGY_DB:
                write("REFUSED: '--strategy' takes one of %s, not '%s'"
                      % (", ".join(sorted(STRATEGY_DB)), name))
                write(USAGE)
                return E_ExitCode.REFUSED
            strategy = strategy_of(name)
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
    #  ONE MEASUREMENT AT A TIME (coverage D-3): a coverage run's times
    #  are the instrumentation's, not the test's, and a cadence read
    #  from it would be a lie. Refused at the door, never silently
    #  preferred.
    if timing_f and coverage is not None:
        write("REFUSED: '--timing' and '--coverage' cannot both stand: "
              "a coverage run's times are the instrumentation's")
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
            _drive(directory, wish, record, worker_max_n, strategy,
                   flow, coverage, name_tuple_of(variant_text),
                   timing_f, event_sink, despite_stain_f))
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
