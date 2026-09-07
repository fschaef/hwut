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
from   datetime import datetime, timezone

from   vut.engine.display.console                    import (HELP as RENDERING_HELP,
                                                             RenderingError,
                                                             console_view,
                                                             parse_rendering)
from   vut.engine.display.console                    import USAGE_TOKEN_TUPLE \
                                                             as RENDERING_TOKEN_TUPLE
from   vut.engine.orchestrator.exploration.task_list import SelectionError
from   vut.engine.orchestrator.exploration.tree_explorer \
                                                    import RootConfMissing
from   vut.services.lib.labels                          import view_at
from   vut.services.lib.labels._file                    import LabelFileError
from   vut.engine.orchestrator.plan.wish             import (HELP as WISH_HELP,
                                                             WishError,
                                                             parse_wish,
                                                             with_targets)
from   vut.engine.orchestrator.run.dispatcher        import test_run_dispatcher_factory
from   vut.engine.orchestrator.exploration.variant   import (name_tuple_of)
from   vut.engine.orchestrator.run.orchestrate       import orchestrator
from   vut.engine.orchestrator.run.strategy          import (DEFAULT_STRATEGY_NAME,
                                                             STRATEGY_DB,
                                                             strategy_of)
from   vut.engine.protocol.summary           import fold
from   vut.engine.orchestrator.plan.wish             import USAGE_TOKEN_TUPLE \
                                                             as WISH_TOKEN_TUPLE
from   ._core                                        import usage_line
from   ._exit                                        import E_ExitCode
from   ._target                                      import entered


USAGE = usage_line("usage: hwut.run",
                    WISH_TOKEN_TUPLE
                    + ("[<file-glob> [choice-glob]...]",
                       "[--no-store]", "[--timing]", "[--jobs=<n>]",
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
    --no-store          the store knob: no subject is recorded under
                        'TMP/store/'. The verdict still enters THE
                        BOOK ('GOOD/result_db.csv'): what the
                        software IS is recorded whether or not what
                        it printed is kept
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


#  How often the consumer wakes to offer the flow the clock. Short
#  enough that a held START appears promptly, long enough to cost
#  nothing.
TICK_SECONDS = 0.25


async def _drive(root, wish, record, worker_max_n, strategy, flow,
                 coverage=None, variant_tuple=(), timing_f=False,
                 event_sink=None, despite_stain_f=False,
                 force_run_f=False,
                 label_view=None, warn=None):
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
                             despite_stain_f=despite_stain_f,
                             force_run_f=force_run_f),
                         worker_max_n=worker_max_n, strategy=strategy,
                         label_view=label_view, warn=warn)
    event_list = []
    #  THE WAKE: a run that merely takes long emits no event, so a
    #  flow holding its START line back would never release it. The
    #  loop therefore wakes on its own and offers the flow the
    #  current instant; a flow that holds nothing does nothing with
    #  it.
    tick = getattr(flow, "on_tick", None)
    while True:
        if tick is None:
            item = await queue.get()
        else:
            try:
                item = await asyncio.wait_for(queue.get(),
                                              timeout=TICK_SECONDS)
            except asyncio.TimeoutError:
                tick(datetime.now(timezone.utc).isoformat())
                continue
        if item is None: return event_list
        event_list.append(item)
        if event_sink is not None: event_sink(item)
        flow.dispatch(item)


def main(argv=None, write=None, write_error=None, demand=None,
         event_sink=None, despite_stain_f=False, force_run_f=False):
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
    if write is None:
        write = print
    if write_error is None:
        def write_error(line):
            print(line, file=sys.stderr)
    try:
        return _main(argv, write, write_error, captured_f, demand,
                     event_sink, despite_stain_f, force_run_f)
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return E_ExitCode.SIGPIPE


def _main(argv, write, write_error, captured_f, demand=None,
          event_sink=None, despite_stain_f=False, force_run_f=False):
    """
    RETURN: E_ExitCode -- 'main' without the pipe guard.

    'demand' is a CoverageConfig a FACE hands in for '--coverage' --
    the seam through which 'hwut.cov' and its tests state the tool
    until '--variant' selects it from the configuration (todo-13).
    """
    if argv is None:
        argv = sys.argv[1:]
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
    #  THE DEFAULT BOUND IS THE MACHINE'S OWN: more work standing at
    #  once than the host has cores buys no throughput and costs
    #  every test its share of the timing. '--jobs' overrides, above
    #  or below -- the policy lives HERE, at the door a person reads,
    #  and never inside 'CBudget', where 'None' honestly means 'no
    #  bound at all'.
    worker_max_n = os.cpu_count() or 1
    strategy     = strategy_of(DEFAULT_STRATEGY_NAME)
    unknown      = []
    word_list    = []
    for argument in rest_list:
        if   argument.startswith("--directory="):
            directory = argument[len("--directory="):]
        elif argument == "--no-store":  record   = False
        elif argument == "--timing":    timing_f = True
        elif argument == "--force-run": force_run_f = True
        elif argument == "--coverage":
            from vut.engine.coverage.api import CoverageConfig
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
        elif argument.startswith("-"):
            unknown.append(argument)
        else:
            #  THE SHORT FORM OF HWUT 1.0: 'hwut.run test-app.sh one'
            #  -- sugar for a wish glob, globbing allowed in both
            #  members ('wish.desugar_positional').
            word_list.append(argument)
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
    #  A TEST NAMED BY PATH IS ENTERED ('services/_target.py', E-47).
    found = entered(word_list, directory, write, USAGE)
    if found is None: return E_ExitCode.REFUSED
    directory, word_list = found
    if not os.path.isdir(directory):
        write("REFUSED: the directory '%s' does not exist"
              % directory)
        write(USAGE)
        return E_ExitCode.REFUSED
    #  The machinery walks and launches below an ABSOLUTE root; the
    #  wire's paths stay relative to it either way.
    directory = os.path.abspath(directory)

    wish = with_targets(wish, word_list)

    #  THE LABEL VIEW, built at the tree's boundary before anything
    #  runs: the silence must be determined, or refused, at the door.
    try:
        label_view = view_at(directory)
    except RootConfMissing as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    except LabelFileError as error:
        write("FAULT: %s" % error)
        return E_ExitCode.FAULT

    #  The face knows its own sink; display knows what a terminal is
    #  worth. Tier, ink and width are decided there, once.
    tty_f = (not captured_f) and sys.stdout.isatty()

    #  THE LOG IS THE FACE'S FILE, opened here and closed here.
    #  Display says a log stands and what belongs in it; a renderer
    #  that opened files would hold a resource it cannot promise to
    #  release. A log that cannot be opened is a fault about the log,
    #  not a reason to lose the run: the marginalia fall back to
    #  stderr, which is where '--no-log' puts them anyway.
    log_file = None
    if not rendering_wish.no_log_f:
        try:
            log_file = open(rendering_wish.log_path, "w",
                            encoding="utf-8")
        except OSError as error:
            write_error("FAULT: the log '%s' cannot be written (%s); "
                        "faults and notes go to stderr"
                        % (rendering_wish.log_path, error))
            log_file = None
    write_log = None if log_file is None \
                else lambda line: print(line, file=log_file)

    try:
        flow = console_view(rendering_wish, write, write_error,
                            os.environ, tty_f, write_log=write_log)
        try:
            event_list = asyncio.run(
                _drive(directory, wish, record, worker_max_n, strategy,
                       flow, coverage, name_tuple_of(variant_text),
                       timing_f, event_sink, despite_stain_f, force_run_f,
                       label_view, write))
        except RootConfMissing as error:
            write("REFUSED: %s" % error)
            return E_ExitCode.REFUSED
        except SelectionError as error:
            write("REFUSED: %s" % error)
            return E_ExitCode.REFUSED
        flow.tail()
    finally:
        if log_file is not None: log_file.close()

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
