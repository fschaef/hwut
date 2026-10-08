"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.cov.run', THE COVERAGE RUN (coverage D-38) -- every
         selected test case is run by its coverage tool; what the tool
         leaves is read and stored as a record in hwut's own format.

    hwut.cov.run [<wish>] -o <directory> [--dont-ask]
                 [--variant=<a>,<b>] [--jobs=<n>]
                 [<rendering words>] [--directory=<path>]
    hwut.cov.run --help         this text

THE SIBLING FACES (services E-133): 'hwut.cov.conv.to_humans' shows a
coverage file as text; 'hwut.cov.conv.to_<format>' turns the output
directory into lcov, html, cobertura, jacoco, json, tex or pdf;
'hwut.cov.formats' lists the tools this build reads.

THE OUTPUT DIRECTORY (coverage D-42) is the one place coverage data is
kept. '-o <directory>' names it; it then holds

    test_run_id_db.csv         directory;test;choice;test_run_id
    test_run_group_id_db.csv   the sets of test runs that executed
                               some range together
    <source path>.cover        one file per source file: what could be
                               executed, and what was -- each covered
                               range annotated with the test run, or
                               the group of test runs, that executed it

EVERYTHING IN IT IS REMOVED WHEN THE RUN STARTS -- it holds exactly one
run -- and only where it is empty or was made by a coverage run.
Without '-o' the run ASKS whether './hwut.coverage/' is to be used;
'--dont-ask' takes it unasked; where nobody can be asked the run is
refused.

THE PER-CASE RECORDS ('TMP/store/<test>--<choice>.cover') are what a
single run leaves; they are gathered when the last directory is done
and then removed.

IT IS NOT A TEST RUN. Nothing is compared with 'GOOD/', no verdict is
determined, and 'GOOD/book.csv' is not written.

IT IS RENDERED AS A RUN IS (display D-40): the same flow, DIRECTORIES,
HINTS and RESULTS, by the same renderer, in the coverage run's own
vocabulary --

    [REC]       the run left a record, gathered into the output
    [NO REC]    it left none; the word before the badge says why, and
                HINTS says it in full ('engine/display/
                coverage_reason.py')

-- and it takes the rendering words 'hwut.run' takes ('--quiet',
'--silent', '--plain', '--brief', '--log <file>', ...).

THE OUTPUT DIRECTORY IS THE PRODUCT. A case without a record is named here
and, for 'hwut.help', in 'TMP/hwut-traces-coverage.csv' (D-41).

THE EXIT STATUS (E-1): OK where every selected case left a record,
FAULT where one did not or a fault was met, REFUSED where the command
line cannot be read or the output directory may not be emptied, EMPTY
where the wish selects nothing.
______________________________________________________________________________
"""
import asyncio
import os
import sys
import time

from   vut.engine.display.console                    import (
           RenderingError, console_view, parse_rendering)
from   vut.engine.display.console                    import USAGE_TOKEN_TUPLE \
                                                         as RENDERING_TOKEN_TUPLE
from   vut.engine.display.coverage_reason            import COVERAGE_VOCABULARY
from   vut.engine.display.plain                      import E_Tier
from   vut.engine.coverage.api                       import (
           DEFAULT_DIRECTORY_NAME, OutputRefused, gather, prepared)
from   vut.engine.protocol.summary                   import fold
from   vut.services.lib                              import preferences

from   vut.engine.orchestrator.exploration.task_list import SelectionError
from   vut.engine.orchestrator.exploration.tree_explorer \
                                                     import RootConfMissing
from   vut.engine.orchestrator.exploration.variant   import name_tuple_of
from   vut.engine.orchestrator.plan.wish             import (parse_wish,
                                                             with_targets,
                                                             WishError)
from   vut.engine.orchestrator.run.coverage_dispatcher \
                                 import coverage_run_dispatcher_factory
from   vut.engine.orchestrator.run.orchestrate       import orchestrator
from   vut.services.run                              import optional_log_writer
from   vut.services._exit                            import E_ExitCode
from   vut.engine.orchestrator.plan.confinement import uncapped_refusal_f
from   vut.services._target                          import entered
from   vut.services.lib.cmdline                      import (face_parser,
                                                             usage_of,
                                                             parse_or_refuse)
from   vut.services.lib.labels                       import view_at
from   vut.services.lib.labels._file                 import LabelFileError

NAME   = "hwut.cov.run"
HELP   = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip()
PARSER = face_parser(NAME, "The coverage run.",
                     word_help="a test, a test and a choice, a file glob "
                               "and a choice glob",
                     word_metavar="[<file-glob> [choice-glob]...]",
                     shared_token_tuple=RENDERING_TOKEN_TUPLE)
PARSER.add_argument("-o", "--output", default=None, metavar="directory")
PARSER.add_argument("--dont-ask", action="store_true")
PARSER.add_argument("--jobs", default=None, metavar="n")
PARSER.add_argument("--variant", default="", metavar="a,b")
PARSER.add_argument("--directory", default=None)
ARG_DB = {"--directory": True, "--output": True}
USAGE  = usage_of(PARSER, ARG_DB)


async def _drive(root, wish, factory, worker_max_n, label_view, flow):
    """
    RETURN: list[dict], the whole report stream, rendered LIVE through
            'flow' as each event arrived.

    Raises what determination raises -- 'orchestrator()' refuses
    BEFORE the first event.
    """
    queue = orchestrator(root, wish, factory, worker_max_n=worker_max_n,
                         label_view=label_view)
    event_list = []
    while True:
        event = await queue.get()
        if event is None: return event_list
        event_list.append(event)
        flow.dispatch(event)


def exit_code_of(summary):
    """
    RETURN: E_ExitCode of a coverage run whose event stream folded to
            'summary' (E-1): FAULT where a fault was met or a case is
            without a record, REFUSED where a case was not run for
            want of an enforceable cap, EMPTY where no case was
            selected, OK else.
    """
    if summary.fault_tuple or summary.fail_n \
       or summary.good_f is False:
        return E_ExitCode.FAULT
    #  AN UNENFORCEABLE CAP REFUSES (exploration R-80), as on the run.
    if any(uncapped_refusal_f(text)
           for text in summary.refused_db.values()):
        return E_ExitCode.REFUSED
    if not summary.verdict_db: return E_ExitCode.EMPTY
    return E_ExitCode.OK


def _refused(write, message):
    """RETURN: E_ExitCode.REFUSED, the refusal and the usage written."""
    write("REFUSED: %s" % message)
    write(USAGE)
    return E_ExitCode.REFUSED


def output_directory_of(stated, dont_ask_f, ask):
    """
    RETURN: str, the output directory of this run: the one stated; the
            default './hwut.coverage' where none is stated and either
            '--dont-ask' stands or the person asked said yes.
            None, where none is stated and the answer was no, or
            nobody can be asked ('ask' is None).
    """
    if stated: return stated
    default = os.path.join(os.getcwd(), DEFAULT_DIRECTORY_NAME)
    if dont_ask_f: return default
    if ask is None: return None
    answer = ask("no '-o <directory>': gather coverage data in '%s'? "
                 "Everything in it is removed. [y/N] " % default)
    return default if answer.strip().lower() in ("y", "yes") else None


def main(argv=None, write=None, demand=None, write_error=None, ask=None):
    """
    RETURN: E_ExitCode (E-1): OK where every selected case left a
            record, FAULT where one did not or a fault was met,
            REFUSED where the command line cannot be read, EMPTY where
            the wish selects nothing.

    'write' takes one line of text; 'print' where none is given -- a
    captured face is never a terminal. 'write_error' likewise, for the
    SILENT tier's faults; stderr where none is given. 'demand' is the
    CoverageConfig of the run, where a caller states one; None reads
    as the default demand. 'ask' puts one question to a person and
    answers with the line typed; where none is given, the terminal is
    asked where one stands and nobody where the face is captured.
    """
    started_at = time.monotonic()
    captured_f = write is not None
    if write is None: write = print
    if write_error is None:
        def write_error(line):
            print(line, file=sys.stderr)
    if argv is None:  argv = sys.argv[1:]

    if "--help" in argv or "-h" in argv:
        write(HELP)
        return E_ExitCode.OK
    try:
        wish, rest_list = parse_wish(argv)
    except WishError as error:
        return _refused(write, str(error))
    try:
        rendering_wish, rest_list = parse_rendering(rest_list)
    except RenderingError as error:
        return _refused(write, str(error))
    arguments, completion_f = parse_or_refuse(PARSER, rest_list, write,
                                              ARG_DB)
    if completion_f: return E_ExitCode.OK
    if arguments is None:
        write(USAGE)
        return E_ExitCode.REFUSED

    worker_max_n = os.cpu_count() or 1
    if arguments.jobs is not None:
        if not arguments.jobs.isdigit() or int(arguments.jobs) < 1:
            return _refused(write, "'--jobs' takes a positive integer, "
                                   "not '%s'" % arguments.jobs)
        worker_max_n = int(arguments.jobs)

    found = entered(arguments.word, arguments.directory or ".", write,
                    USAGE)
    if found is None: return E_ExitCode.REFUSED
    directory, word_list = found
    if not os.path.isdir(directory):
        return _refused(write, "the directory '%s' does not exist"
                               % directory)
    directory = os.path.abspath(directory)

    tty_f = (not captured_f) and sys.stdout.isatty()
    if ask is None and tty_f and sys.stdin.isatty(): ask = input
    output = output_directory_of(arguments.output, arguments.dont_ask, ask)
    if output is None:
        return _refused(write, "no output directory: state '-o "
                               "<directory>', or '--dont-ask' for './%s/'"
                               % DEFAULT_DIRECTORY_NAME)
    try:
        output = prepared(output, directory)
    except OutputRefused as refusal:
        return _refused(write, str(refusal))
    run_list = []

    factory = coverage_run_dispatcher_factory(
                  demand=demand,
                  variant_tuple=name_tuple_of(arguments.variant),
                  root=directory, run_list=run_list)
    with optional_log_writer(rendering_wish.log_path,
                             write_error) as write_log:
        flow = console_view(rendering_wish, write, write_error,
                            os.environ, tty_f, write_log=write_log,
                            color_of=preferences.load().color,
                            root=directory, started_at=started_at,
                            vocabulary=COVERAGE_VOCABULARY)
        try:
            event_list = asyncio.run(
                _drive(directory, with_targets(wish, word_list), factory,
                       worker_max_n, view_at(directory), flow))
        except (RootConfMissing, SelectionError) as error:
            write("REFUSED: %s" % error)
            return E_ExitCode.REFUSED
        except LabelFileError as error:
            write("FAULT: %s" % error)
            return E_ExitCode.FAULT
        flow.tail()
    #  THE FINAL GATHERING (D-42): every record of this run folded into
    #  the output directory; the per-case records then go.
    try:
        run_n, source_n, outside_list = gather(output, run_list)
    except OutputRefused as refusal:
        write("FAULT: %s" % refusal)
        return E_ExitCode.FAULT
    finally:
        for _, _, _, path in run_list:
            try:            os.remove(path)
            except OSError: pass
    if rendering_wish.tier is not E_Tier.SILENT:
        for source in outside_list:
            write("NOTE: '%s' lies outside '%s'; not gathered"
                  % (source, directory))
        write("COVERAGE DATA: %s -- %i test run(s), %i source file(s)"
              % (output, run_n, source_n))
    return exit_code_of(fold(event_list))


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from vut.services._exit import guarded
    sys.exit(guarded(NAME, main, sys.argv[1:]))
