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
import argparse
import asyncio
import os
import sys
from vut.services.lib import preferences
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
from   ._exit                                        import E_ExitCode
from   ._target                                      import entered
from   vut.services.lib.face    import Refused, Fault, FaceError
from   vut.engine.orchestrator.plan.wish import Wish
from   dataclasses import dataclass
from   vut.services.lib.cmdline import (face_parser, usage_of,
                                        parse_or_refuse, did_you_mean)


#  THE STANDARD READER (E-84): the wish, then the rendering words, then
#  this parser. The VALUES of '--jobs' and '--strategy' are checked
#  below, in this face's own words.
PARSER = face_parser("hwut.run", "The tree run, rendered live.",
                     word_help="a test, a test and a choice, a file glob "
                               "and a choice glob",
                     word_metavar="[<file-glob> [choice-glob]...]",
                     shared_token_tuple=RENDERING_TOKEN_TUPLE)
PARSER.add_argument("--no-store", action="store_true")
PARSER.add_argument("--timing", action="store_true")
PARSER.add_argument("--jobs", default=None, metavar="n")
PARSER.add_argument("--strategy", default=None, metavar="name")
PARSER.add_argument("--directory", default=None)
#  TAKEN, NOT ADVERTISED: what the usage line never named.
PARSER.add_argument("--force-run", action="store_true", help=argparse.SUPPRESS)
PARSER.add_argument("--coverage", action="store_true", help=argparse.SUPPRESS)
PARSER.add_argument("--variant", default="", help=argparse.SUPPRESS)
PARSER.add_argument("--dbd", "--directory-by-directory", action="store_true",
                    help=argparse.SUPPRESS)
ARG_DB = {"--directory": True}
USAGE  = usage_of(PARSER, ARG_DB)

HELP = """hwut.run -- the tree run, rendered live

    hwut.run            runs everything the tree below the root
                        offers: per directory its frame, its builds,
                        its sessions, its tests

""" + WISH_HELP + """

EXECUTION
    --directory=<path>  the root to run below; the current one else
    --no-store          the store knob: no subject is recorded under
                        'TMP/store/'. The verdict still enters THE
                        BOOK ('GOOD/book.csv'): what the
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
                 coverage=None, 
                 variant_tuple=(), 
                 timing_f=False,
                 event_sink=None, 
                 despite_stain_f=False,
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
                             record          = record, coverage=coverage,
                             variant_tuple   = variant_tuple,
                             timing_f        = timing_f,
                             despite_stain_f = despite_stain_f,
                             force_run_f     = force_run_f),
                         worker_max_n = worker_max_n, strategy=strategy,
                         label_view   = label_view, warn=warn)
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


@dataclass(frozen=True)
class Request:
    """WHAT WAS ASKED of 'hwut.run' (E-101): the wish, where to walk,
    and how to execute -- no argv, no rendering (which is the page's,
    not the run's)."""
    directory:     str         = "."
    #  the wish
    fail_f:        bool        = False
    pass_f:        bool        = False
    since_spec:    str | None  = None
    until_spec:    str | None  = None
    glob_tuple:    tuple       = ()
    exclude_tuple: tuple       = ()
    dir_tuple:     tuple       = ()
    exclude_dir_tuple: tuple   = ()
    wishlist_f:    bool        = False
    label_spec:    str | None  = None
    language_tuple:tuple       = ()
    faster_than_ms:int | None  = None
    unaccepted_f:  bool        = False
    #  the execution
    record:        bool | None = None
    worker_max_n:  int | None  = None
    strategy_name: str         = DEFAULT_STRATEGY_NAME
    variant_text:  str         = ""
    timing_f:      bool        = False
    coverage_f:    bool        = False
    despite_stain_f: bool      = False
    force_run_f:   bool        = False


@dataclass(frozen=True)
class Tally:
    """WHAT THE RUN CAME TO (E-102): the fold of its own event stream."""
    case_n:      int = 0
    fail_n:      int = 0
    fault_tuple: tuple = ()
    good_f:      bool | None = None
    empty_f:     bool = False


class _NoFlow:
    """The renderer of a run nobody watches: every event accepted, none
    drawn. 'do' runs with this unless a face hands in its display."""

    def dispatch(self, item): pass
    def tail(self):           pass


def request_of(wish, directory, **field_db):
    """RETURN: Request, a Wish, a directory and the execution words as
               plain fields."""
    return Request(directory         = directory,
                   fail_f            = bool(wish.fail_f),      pass_f = bool(wish.pass_f),
                   since_spec        = wish.since_spec,        until_spec = wish.until_spec,
                   glob_tuple        = tuple(wish.glob_tuple),
                   exclude_tuple     = tuple(wish.exclude_tuple),
                   dir_tuple         = tuple(wish.dir_tuple),
                   exclude_dir_tuple = tuple(wish.exclude_dir_tuple),
                   wishlist_f        = bool(wish.wishlist_f),  label_spec = wish.label_spec,
                   language_tuple    = tuple(wish.language_tuple),
                   faster_than_ms    = wish.faster_than_ms,
                   unaccepted_f      = bool(wish.unaccepted_f),
                   **field_db)


def wish_of(request):
    """RETURN: Wish, the engine's, as 'request' states it."""
    return Wish(fail_f            = request.fail_f,
                pass_f            = request.pass_f,
                since_spec        = request.since_spec, until_spec=request.until_spec,
                glob_tuple        = tuple(request.glob_tuple),
                exclude_tuple     = tuple(request.exclude_tuple),
                dir_tuple         = request.dir_tuple,
                exclude_dir_tuple = request.exclude_dir_tuple,
                wishlist_f        = request.wishlist_f,
                label_spec        = request.label_spec,
                language_tuple    = request.language_tuple,
                faster_than_ms    = request.faster_than_ms,
                unaccepted_f      = request.unaccepted_f)


def do(request, sink=None, flow=None, demand=None, write=None):
    """
    RETURN: Tally, the fold of the run's own event stream (O-4).

    EVERY EVENT REACHES 'sink' AS IT HAPPENS (E-102) -- plain dicts, as
    'engine/protocol' writes them. 'flow' is a RENDERER a face hands in
    ('hwut.run' its console view); without one the run is silent, which
    is what a library caller wants.

    RAISES: Refused, where no root conf stands above the directory or
            the wish names what the tree does not hold; Fault, where a
            label file cannot be read.

    IT NEVER PRINTS. 'write' reaches the machinery that must say a word
    of its own (a build's own output); 'print' is never called here.
    """
    directory = request.directory or "."
    if not os.path.isdir(directory):
        raise Refused("REFUSED: the directory '%s' does not exist" % directory)
    directory = os.path.abspath(directory)
    coverage  = None
    if request.coverage_f:
        from vut.engine.coverage.api import CoverageConfig
        coverage = demand if demand is not None else CoverageConfig()
    try:
        label_view = view_at(directory)
    except RootConfMissing as error:
        raise Refused("REFUSED: %s" % error) from error
    except LabelFileError as error:
        raise Fault("FAULT: %s" % error) from error
    try:
        event_list = asyncio.run(
            _drive(directory, 
                   wish_of(request), 
                   request.record,
                   request.worker_max_n or (os.cpu_count() or 1),
                   strategy_of(request.strategy_name),
                   flow if flow is not None else _NoFlow(),
                   coverage, name_tuple_of(request.variant_text),
                   request.timing_f, sink, request.despite_stain_f,
                   request.force_run_f, label_view,
                   write if write is not None else (lambda line: None)))
    except RootConfMissing as error:
        raise Refused("REFUSED: %s" % error) from error
    except SelectionError as error:
        raise Refused("REFUSED: %s" % error) from error
    summary = fold(event_list)
    fail_n  = summary.fail_n if summary.fail_n is not None else 0
    return Tally(case_n      = len(summary.verdict_db),
                 fail_n      = fail_n,
                 fault_tuple = tuple(str(f) for f in summary.fault_tuple),
                 good_f      = summary.good_f,
                 empty_f     = not summary.verdict_db)


def exit_code_of(tally):
    """RETURN: E_ExitCode, what a run that came to 'tally' exits with
               (E-1) -- the one place the rule stands."""
    if tally.fault_tuple or tally.good_f is False or tally.fail_n > 0 \
       or (tally.case_n and tally.good_f is None):
        return E_ExitCode.FAULT
    if tally.empty_f: return E_ExitCode.EMPTY
    return E_ExitCode.OK


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
    arguments, completion_f = parse_or_refuse(PARSER, rest_list, write,
                                              ARG_DB)
    if completion_f:      return E_ExitCode.OK
    if arguments is None:
        write(USAGE)
        return E_ExitCode.REFUSED
    directory    = arguments.directory or "."
    if arguments.no_store: record   = False
    timing_f     = arguments.timing
    if arguments.force_run: force_run_f = True
    if arguments.coverage:
        from vut.engine.coverage.api import CoverageConfig
        coverage = demand if demand is not None else CoverageConfig()
    variant_text = arguments.variant
    if arguments.dbd: strategy = strategy_of("linear")
    if arguments.strategy is not None:
        name = arguments.strategy
        if name not in STRATEGY_DB:
            write("REFUSED: '--strategy' takes one of %s, not '%s'%s"
                  % (", ".join(sorted(STRATEGY_DB)), name,
                     did_you_mean(name, sorted(STRATEGY_DB),
                                  among_listed_f=True)))
            write(USAGE)
            return E_ExitCode.REFUSED
        strategy = strategy_of(name)
    if arguments.jobs is not None:
        text = arguments.jobs
        if not text.isdigit() or int(text) < 1:
            write("REFUSED: '--jobs' takes a positive integer, "
                  "not '%s'" % text)
            write(USAGE)
            return E_ExitCode.REFUSED
        worker_max_n = int(text)
    #  THE SHORT FORM OF HWUT 1.0: 'hwut.run test-app.sh one' -- sugar
    #  for a wish glob, globbing allowed in both members
    #  ('wish.desugar_positional').
    word_list    = arguments.word
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
    wish = with_targets(wish, word_list)

    #  The face knows its own sink; display knows what a terminal is
    #  worth. Tier, ink and width are decided there, once.
    tty_f = (not captured_f) and sys.stdout.isatty()

    #  THE LOG IS THE FACE'S FILE, opened here and closed here, and
    #  only where '--log <file>' named one (O-24). Display says what
    #  belongs in it; a renderer that opened files would hold a
    #  resource it cannot promise to release. A log that cannot be
    #  opened is a fault about the log, not a reason to lose the run:
    #  the flow goes on without it.
    log_file = None
    if rendering_wish.log_path:
        try:
            log_file = open(rendering_wish.log_path, "w",
                            encoding="utf-8")
        except OSError as error:
            write_error("FAULT: the log '%s' cannot be written (%s); "
                        "the run goes on without it"
                        % (rendering_wish.log_path, error))
    write_log = None if log_file is None \
                else lambda line: print(line, file=log_file)

    request = request_of(wish, directory,
                         record          = record, 
                         worker_max_n    = worker_max_n,
                         strategy_name   = strategy.name,
                         variant_text    = variant_text, timing_f=timing_f,
                         coverage_f      = coverage is not None,
                         despite_stain_f = despite_stain_f,
                         force_run_f     = force_run_f)
    try:
        flow = console_view(rendering_wish, write, write_error,
                            os.environ, tty_f, write_log=write_log,
                            color_of=preferences.load().color)
        #  THE DISPLAY IS A CONSUMER (E-102): 'do' runs and hands every
        #  event to whoever listens; this face hands in its console
        #  view as the renderer and 'event_sink' as the sink beside it.
        try:
            tally = do(request, sink=event_sink, flow=flow, demand=demand,
                       write=write)
        except FaceError as error:
            write(error.said)
            return error.code
        flow.tail()
    finally:
        if log_file is not None: log_file.close()

    return exit_code_of(tally)


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ._exit import guarded
    sys.exit(guarded("hwut.run", main))
