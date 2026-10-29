"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.play' COMMAND LINE -- run one test, show the
         READING of what it produced, under the test's OWN setup
         (disc-4).

    hwut.play <test-app> [<choice>] [--directory=<path>]
    hwut.play --all [<file-glob> [<choice-glob>...]] [--directory=<path>]

IT IS WIRING, NOT MACHINERY. Play is the composition of bricks that
already exist, and owns no ceremony of its own:

    the wish + CTestTaskListQuery   which run is meant
    subject_provision.provider_of   SUBJECT PROVISION, through the ONE
                                    channel (operations disc-2): build,
                                    launch, contain, collect,
                                    canonicalise -- the very provision
                                    a run consumes, asked to execute
                                    ('force_run': a play IS the request
                                    to run now)
    compare's reading               INTERPRETATION: the lexical
                                    analysis, marks by tolerance kind
    TuiDisplay                      DISPLAY

Nothing here re-derives what a run derives. What play shows is what a
run would compare, BY CONSTRUCTION rather than by re-implementation --
which is the only way the answer can be trusted to be the framework's
answer and not this face's.

THE THREE VIEWS, and the default is the one that matters:

    (default)   THE SUBJECT -- what is going to enter the comparator,
                shown under the READING: marks by tolerance kind,
                '{numeric}', '~analogy~', '<pattern>', '!binding!',
                '|nothing|'. This is the picture 'hwut.compare FILE'
                shows, but under the TEST'S setup, not the command
                line's.
    --raw       what came OUT OF THE APPLICATION, before any pype
                touched it. Shown plainly: compare never reads this
                text, so marking it would say a thing that is not so.
    --pyped     what came out of the PYPE, where one stands. Where
                none does, the subject IS the raw stream and the view
                says so rather than printing it twice.

EACH VIEW IS A NAMED REGION, so a reader can tell at a glance which
stream they are looking at:

    ===== <name> ==========================================

THE PYPE VIEW EARNS ITS KEEP: a pype is part of the test application,
an artifact that may contain errors, and therefore part of the oracle
(doc/manual-note-pype-is-part-of-the-oracle.txt).
An author debugging one needs to see what it did to the stream.

PLAY JUDGES NOTHING; IT SHOWS AND RECORDS (services E-165). No nominal
is read, no verdict is reached, no book entry is written. What it ran
is stored as the case's RECORDING, through the channel's own
'record()' -- what 'hwut.run' would have stored, and nothing else.
ONE RECORDING PER CASE: the last of 'hwut.run' and 'hwut.play' to
record it wins, and the recording says which of them it was and when.

'--all' PLAYS EVERY CASE THE WORDS SELECT here -- every case, where no
word is given -- one after the other, each recorded. Without it, words
that name several cases are refused rather than guessed at -- but an
application with several choices, named without one, is ASKED for on
the terminal: a short menu, answered by index or name (E-189).

RECORD, LOOK, BLESS. 'hwut.play' and 'hwut.run' are the only faces
that run a test. 'hwut.diff', 'hwut.merge' and 'hwut.accept' read the
recording and run nothing -- so what is blessed is what was seen:

    hwut.play test-a.py one        run, show, record
    hwut.accept test-a.py one      bless what was recorded

This closes the seam '_core.py' names -- "a service run inside a test
run receives that Configuration object directly". Play is the command
line's way to stand inside.

A RECORDING NEEDS A WHOLE STREAM: a build that failed, an application
that would not launch, a stream cut short are shown and NOT recorded --
a partial subject is never stored as if whole.

EXIT STATUS (E-1, services/_exit.py):
    0  OK       the choice ran and its reading is displayed
    1  FAULT    the build failed, the application would not launch, or
                the tree cannot be read -- what was learnt is shown
    2  REFUSED  the command line cannot be read: no such application,
                no such choice, or a choice not named where the
                application offers several and no terminal can be
                asked; a menu answer that selects nothing
    3  EMPTY    the choice produced no output to read
______________________________________________________________________________
"""
import asyncio
import os
import sys

from ..viewers.tui import TuiDisplay
from ....engine.orchestrator.exploration import selection
from   hwut.engine.orchestrator.exploration.tree_explorer \
                                                   import RootConfMissing
from ....engine.orchestrator.run.adapter import (
                                                       test_configuration_of)
from ....engine.orchestrator.plan import confinement
from   hwut.engine.orchestrator.exploration.task_list \
                                                   import SelectionError
from   hwut.engine.orchestrator.exploration.task_list_query \
                                                   import CTestTaskListQuery
from ....engine.orchestrator.plan.wish import (Wish,
                                                           with_targets)
from ....auxiliary.directory_mutex import (DirectoryBusy,
                                                           MkdirMutex)
from ..._exit import E_ExitCode
from ..._target import entered
from .diff import reading_view
from ..cmdline import (face_parser, usage_of,
                                        parse_or_refuse, did_you_mean)
from ....engine.orchestrator.exploration import printer
from ...report import (painted, color_wanted_f,
                                   ANSI_TITLE)

#  THE STANDARD READER (E-84). Play takes no wish: ONE test, one choice.
PARSER = face_parser("hwut.play", "Run one choice now and show it.",
                     wish_f=False,
                     word_help="the test application, and a choice",
                     word_metavar="<test-app> [<choice>]")
for _name in ("--raw", "--pyped", "--stderr", "--plain", "--all"):
    PARSER.add_argument(_name, action="store_true")
PARSER.add_argument("--directory", default=None)
ARG_DB = {"--directory": True}
USAGE  = usage_of(PARSER, ARG_DB)

#  THE REGION BANNER. One shape wherever a stream is named, so a
#  reader never has to work out which picture they are looking at.
BANNER_WIDTH = 62


def banner(name, color_f=False):
    """
    RETURN: str, the region's own line: '===== <name> =====...', padded
            to one width so the regions of one rendering line up --
            and, where 'color_f', the whole line on ORANGE, the band
            the HWUT page has always used for a heading (E-69, whose
            colours these are).

    THE WHOLE WIDTH IS PAINTED, rules included: a band that stopped at
    the word would be a coloured word, not a band, and the point of the
    band is that an eye scrolling back finds the section without
    reading anything.
    """
    head = "===== %s " % name
    line = head + "=" * max(BANNER_WIDTH - len(head), 5)
    return painted(line, ANSI_TITLE, color_f)

HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n" + USAGE

STDOUT = "stdout"
STDERR = "stderr"


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).

    'write' takes one line at a time; 'print' where none is given. The
    RENDERING goes to stdout as compare's does -- the picture is the
    product, so it is not a line stream this face composes.
    """
    if write is None: write = print
    if argv is None:  argv  = sys.argv[1:]
    if "--help" in argv:
        from ..._core import man_page
        write(man_page("hwut.play", HELP))
        return E_ExitCode.OK

    arguments, completion_f = parse_or_refuse(PARSER, argv, write, ARG_DB)
    if completion_f:      return E_ExitCode.OK
    if arguments is None:
        write(USAGE)
        return E_ExitCode.REFUSED
    directory = arguments.directory or "."
    plain_f   = arguments.plain
    stderr_f  = arguments.stderr
    raw_f     = arguments.raw
    pyped_f   = arguments.pyped
    word_list = arguments.word
    all_f     = arguments.all

    #  A TEST NAMED BY PATH IS ENTERED ('services/_target.py', E-47).
    found = entered(word_list, directory, write, USAGE)
    if found is None: return E_ExitCode.REFUSED
    directory, word_list = found
    if all_f:
        return _play_all(directory, word_list, plain_f, stderr_f, raw_f,
                         pyped_f, write)
    if not word_list or len(word_list) > 2:
        write("REFUSED: 'hwut.play' plays ONE test, and one choice of "
              "it: <test-app> [<choice>]")
        write(USAGE)
        return E_ExitCode.REFUSED
    source_file = word_list[0]
    choice_name = word_list[1] if len(word_list) == 2 else None

    #  ONE ACTION, ONE PLACE ('exploration/selection.py').
    try:
        #  'base_f=True': the channel needs the Store over the book --
        #  to decide against the candidate path, and to write the
        #  recording (E-165).
        found  = selection.of_directory(os.path.abspath(directory),
                                        Wish(), base_f=True)
    except RootConfMissing as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    result = found.result_db["."]
    if not _faults_spare(found.fault_tuple, result.app_set, (source_file,),
                         write):
        return E_ExitCode.FAULT

    case = _settled_case(result.app_set, source_file, choice_name,
                         directory, write)
    if case is _REFUSED: return E_ExitCode.REFUSED
    choice_name   = case.choice
    #  AN UNENFORCEABLE CAP REFUSES THE PLAY (exploration R-80): a play
    #  RUNS the application, as unconfined as a run would.
    reason = confinement.refusal_of(result.app_set, case.source_file,
                                    choice_name)
    if reason is not None:
        for line in confinement.refusal_line_list(
                        case.source_file if choice_name is None
                        else "%s %s" % (case.source_file, choice_name),
                        reason):
            write(line)
        return E_ExitCode.REFUSED
    configuration = test_configuration_of(
                        result.app_set.app_db[case.source_file],
                        os.path.abspath(directory),
                        language_setup=result.app_set.directory_spec
                                             .language_setup,
                        free_disk_min_mb=result.app_set.directory_spec
                                               .free_disk_min_mb)
    try:
        return asyncio.run(_play(configuration, choice_name,
                                 found.bookkeeper_db["."],
                                 plain_f, stderr_f, raw_f, pyped_f,
                                 write,
                                 case=case,
                                 app=result.app_set.app_db[case.source_file],
                                 directory_spec=result.app_set.directory_spec))
    except DirectoryBusy as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED


def _faults_spare(fault_tuple, app_set, wanted_tuple, write):
    """
    RETURN: bool, True if the play may go on -- no fault, or every fault
            names ANOTHER test file than those of 'wanted_tuple' (each
            such fault is written as 'FAULT: ...', with the word that
            the file is not played);
            False, else -- a fault of the directory itself ('hwut.conf'),
            one that names no file, or one naming a test asked for:
            written, with 'nothing played'.

    ONE FAULT SPOILS WHAT IT NAMES, NOT ITS NEIGHBOURS (Q2, services
    E-184): a test whose header does not parse cannot be played, and
    says so; the test beside it can, as 'hwut.run' runs it.
    """
    if not fault_tuple: return True
    readable = {app.source_file for app in app_set} if app_set else set()
    spoiling = []
    for fault in fault_tuple:
        file = getattr(fault, "file", None)
        if not file or file.endswith(".conf") or file in readable \
           or any(os.path.basename(file) == os.path.basename(wanted)
                  for wanted in wanted_tuple):
            spoiling.append(fault)
    for fault in fault_tuple: write("FAULT: %s" % fault)
    if spoiling:
        write("nothing played: a directory that cannot be fully read "
              "cannot say what it offers")
        return False
    for file in sorted({fault.file for fault in fault_tuple}):
        write("NOT PLAYED: %s -- it cannot be read" % file)
    return True


def _play_all(directory, word_list, plain_f, stderr_f, raw_f, pyped_f,
              write):
    """
    RETURN: E_ExitCode, the worst of the cases played: OK where every
            case the words select was played and recorded; FAULT where
            one could not be, or a test of the directory could not be
            read (it is named, the rest is played); REFUSED where the selection cannot be
            made; EMPTY where it selects nothing.

    '--all' PLAYS EVERY CASE THE WORDS SELECT, in this directory, one
    after the other -- the short form ('<file-glob> [<choice-glob>...]')
    or nothing for every case here. ASKED FOR, NOT GUESSED: without it a
    word that names several cases is refused (see '_settled_case'). It
    is how a directory of new cases gets its first recordings before
    'hwut.accept' (E-165; the writers' D-36).
    """
    try:
        found = selection.of_directory(os.path.abspath(directory),
                                       Wish(), base_f=True)
    except RootConfMissing as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    result = found.result_db["."]
    if not _faults_spare(found.fault_tuple, result.app_set, (), write):
        return E_ExitCode.FAULT
    #  WHAT COULD NOT BE READ IS NOT PLAYED, AND THE ENDING SAYS SO (Q2):
    #  the readable cases are played all the same.
    unreadable_f = bool(found.fault_tuple)
    wish  = with_targets(Wish(), word_list) if word_list else Wish()
    query = CTestTaskListQuery(wish, directory=".",
                               root=os.path.abspath(directory))
    try:
        case_tuple = tuple(query.get_test_cases(result.app_set))
    except SelectionError as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    if not case_tuple:
        write("EMPTY: the words select no case here")
        return E_ExitCode.EMPTY
    worst = E_ExitCode.OK
    #  SEVERAL CASES, ONE FRAME (E-204): 'on_entry' once before the
    #  first, 'on_exit' once after the last -- as a run frames them.
    here           = os.path.abspath(directory)
    directory_spec = result.app_set.directory_spec
    try:
        asyncio.run(frame(directory_spec, here, "on_entry", write))
    except DirectoryBusy as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    try:
        worst = _play_each(case_tuple, result, found, directory,
                           plain_f, stderr_f, raw_f, pyped_f, write)
    finally:
        asyncio.run(frame(directory_spec, here, "on_exit", write))
    if worst is E_ExitCode.REFUSED: return worst
    if unreadable_f: worst = E_ExitCode.FAULT
    return worst


def _play_each(case_tuple, result, found, directory,
               plain_f, stderr_f, raw_f, pyped_f, write):
    """
    RETURN: E_ExitCode, OK where every case played; FAULT where one was
            refused by its caps or did not play; REFUSED where the
            directory was busy.
    """
    worst = E_ExitCode.OK
    for case in case_tuple:
        name = case.source_file if case.choice is None \
               else "%s %s" % (case.source_file, case.choice)
        reason = confinement.refusal_of(result.app_set, case.source_file,
                                        case.choice)
        if reason is not None:
            for line in confinement.refusal_line_list(name, reason):
                write(line)
            worst = E_ExitCode.FAULT
            continue
        app = result.app_set.app_db[case.source_file]
        configuration = test_configuration_of(
                            app, os.path.abspath(directory),
                            language_setup=result.app_set.directory_spec
                                                 .language_setup,
                            free_disk_min_mb=result.app_set.directory_spec
                                                   .free_disk_min_mb)
        try:
            code = asyncio.run(_play(configuration, case.choice,
                                     found.bookkeeper_db["."],
                                     plain_f, stderr_f, raw_f, pyped_f,
                                     write, case=case, app=app,
                                     directory_spec=result.app_set
                                                          .directory_spec,
                                     frame_f=False))
        except DirectoryBusy as error:
            write("REFUSED: %s" % error)
            return E_ExitCode.REFUSED
        if code is not E_ExitCode.OK: worst = E_ExitCode.FAULT
    return worst


#  The sentinel a settled run is not.
_REFUSED = object()


def _settled_case(app_set, source_file, choice_name, directory,
                  write):
    """
    RETURN: CTestCase, the ONE run the words name.
            '_REFUSED' where they name none, or several -- said by
            name, with what stands listed.

    THE SELECTION IS THE WISH'S, not this face's: the words become the
    1.0 short form ('wish.with_targets'), the same sugar every other
    face takes, and 'CTestTaskListQuery' resolves it. So 'hwut.play
    "test-*.sh" one' globs as it does everywhere, and a choice that
    does not stand is refused in the words the whole framework uses.

    REFUSE RATHER THAN GUESS where several stand: playing 'the first'
    RUNS THE AUTHOR'S PROGRAM under a choice nobody asked for, and
    renders an answer to a question nobody put.

    A REFUSAL ABOUT ONE APPLICATION IS ANSWERED IN ITS CHOICES. Naming
    an application that offers several, and naming a choice it does not
    offer, are both questions ABOUT THAT APPLICATION; both are answered
    with the choices it reports. The directory's roster of files is the
    answer only where the application itself is not there.
    """
    word_list = [source_file] if choice_name is None \
                else [source_file, choice_name]
    wish  = with_targets(Wish(), word_list)
    query = CTestTaskListQuery(wish, directory=".",
                               root=os.path.abspath(directory))
    try:
        case_tuple = tuple(query.get_test_cases(app_set))
    except SelectionError as error:
        write("REFUSED: %s" % error)
        return _REFUSED
    if len(case_tuple) == 1: return case_tuple[0]

    #  THE APPLICATION IS ANSWERED IN ITS OWN CHOICES. Where the words
    #  name ONE application that exists, the question is about THAT
    #  application, and the answer that helps is the list of choices it
    #  reports -- not a list of runs with the file name repeated on
    #  every one, and not the directory's whole roster of files.
    app = app_set.app_db.get(source_file)
    if app is not None:
        choice_list = _choice_list(app)
        if choice_name is None and case_tuple:
            #  A CHOICE IS NOT MANDATORY: a test with one meaningful run
            #  declares none and plays without one. This one declares
            #  several, and one of them is to be named -- ASKED where a
            #  person is at the terminal (services E-189), refused where
            #  nobody is: a pipe has no one to answer.
            if sys.stdin.isatty():
                return _chosen_on_console(source_file, choice_list,
                                          case_tuple, write)
            write("REFUSED: '%s' has %d choices: %s -- name one, or "
                  "'--all'"
                  % (source_file, len(choice_list),
                     ", ".join(choice_list)))
            return _REFUSED
        if choice_name is not None and not case_tuple:
            write("REFUSED: choice '%s' not supported; '%s' reports %d "
                  "choice(s): %s%s"
                  % (choice_name, source_file, len(choice_list),
                     ", ".join(choice_list) or "none",
                     did_you_mean(choice_name, choice_list,
                                  among_listed_f=True)))
            return _REFUSED

    if not case_tuple:
        offered = ", ".join(sorted(app_set.app_db)) or "nothing"
        write("REFUSED: nothing here answers '%s'; this directory "
              "offers: %s%s"
              % (" ".join(word_list), offered,
                 did_you_mean(source_file, sorted(app_set.app_db),
                              among_listed_f=True)))
        return _REFUSED
    write("REFUSED: '%s' names %d runs, and this face plays ONE: %s"
          % (" ".join(word_list), len(case_tuple),
             ", ".join(_case_name(case) for case in case_tuple)))
    return _REFUSED


def _chosen_on_console(source_file, choice_list, case_tuple, write):
    """
    RETURN: CTestCase, the run of the choice the person selected from a
            short menu on the console -- by its index or its name -- if
            success;
            '_REFUSED', else: an empty answer, the end of input, or a
            word that selects no choice -- said, nothing played.

    THE MENU 'hwut_runner' ONCE KEPT (services E-189): the choices as the
    application reports them, numbered from 0, one line read.
    """
    write("Select choice of %s:" % source_file)
    for index, name in enumerate(choice_list):
        write("(%d) %s" % (index, name))
    try:
        answer = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        write("")                   # the prompt's line is closed
        answer = ""
    if answer.isdecimal() and int(answer) < len(choice_list):
        answer = choice_list[int(answer)]
    for case in case_tuple:
        if case.choice == answer: return case
    write("REFUSED: '%s' selects no choice of '%s' -- nothing played"
          % (answer, source_file))
    return _REFUSED


def _choice_list(app):
    """
    RETURN: list[str], the choices an application reports, in the order
            its header states them -- 'choice_db' keeps that order, and
            the order an author wrote is the order he will look for.

            [], where the application has no choices at all: its one
            run is nameless, and 'None' is not a word anybody types.
    """
    return [name for name in app.choice_db if name is not None]


def _case_name(case):
    """
    RETURN: str, the run as a person names it: the file, and the
            choice beside it where one stands.
    """
    if case.choice is None: return case.source_file
    return "%s %s" % (case.source_file, case.choice)


def _stream_whole_f(subjects, configuration, choice_name):
    """
    RETURN: bool, True if the standard output ends with the closing
            token '<hwut-end>' (R-70) as testified by WHOEVER ENDS IT --
            the pype script where a pype owns the stream (its '<eof>'
            handler), the application else -- or no standard output is
            among the subjects to testify;
            False, else -- an empty stream, or one cut short (ND6).

    WHO TESTIFIES IS R-70's ('consume/terminal.py'): a pype'd
    application must NOT print the token, so its RAW stream never holds
    it; the piped subject is read. MEASURED before (D-71): every test
    naming 'pype = ...' in its header said NOT RECORDED. A plain stream
    is read RAW where kept -- the subject may have been canonicalised.
    """
    from ..._accept_common import token_terminated_f
    from ....engine.operations.consume.terminal import pype_owned_f
    raw_db = subjects.raw_db or {}
    if STDOUT in raw_db and not pype_owned_f(configuration, choice_name):
        return token_terminated_f(raw_db[STDOUT])
    if STDOUT not in subjects.reader_db: return True
    return token_terminated_f(subjects.reader_db[STDOUT].open().read())


async def _handler(directory_spec, directory, role, env, note_list,
                   run_name=None):
    """
    RETURN: None. The directory's handler 'role' -- 'on_entry',
            'on_exit', 'on_before_test', 'on_after_test' -- run as
            'hwut.run' runs it ('directory_script', E-204), where the
            directory's 'hwut.conf' states one. No verdict (E-158): an
            end other than exit 0 is appended to 'note_list' as the
            NOTE a run closes with -- '<role> of <run_name>' for a
            handler around a test run, as the run says it.
    """
    if directory_spec is None: return
    command = getattr(directory_spec, role, None)
    if not command: return
    from ....engine.orchestrator.run import directory_script
    how = await directory_script.run(directory_spec, str(directory),
                                     command, env)
    if how is not None:
        said = role if run_name is None else "%s of %s" % (role, run_name)
        note_list.append("NOTE  %s %s: %s" % (said, how, command))


async def frame(directory_spec, directory, role, write):
    """
    RETURN: None. The directory's 'on_entry' or 'on_exit', alone, under
            the directory's lock -- for a play of SEVERAL cases, framed
            once ('--all'); its NOTE written at once.
    """
    if directory_spec is None: return
    note_list = []
    with MkdirMutex(str(directory)):
        await _handler(directory_spec, directory, role, None, note_list)
    for line in note_list: write(line)


async def _play(configuration, choice_name, bookkeeper, plain_f,
                stderr_f, raw_f, pyped_f, write,
                case=None, app=None, directory_spec=None, frame_f=True):
    """
    RETURN: E_ExitCode, the exit status.

    THE DIRECTORY'S HANDLERS RUN AS IN A RUN (E-204): 'on_entry' first
    and 'on_exit' last where 'frame_f' (a play of one case),
    'on_before_test' and 'on_after_test' around the case, all under the
    directory's lock. 'directory_spec' None: no handler runs.

    THE PROVISION DOES EVERYTHING A RUN'S PROVISION DOES -- build,
    launch, contain, collect, canonicalise -- because it IS a run's
    provision, obtained through the one channel ('subject_provision',
    'force_run': play means run now). Play adds no ceremony: it asks
    for the subjects, hands them to the channel's 'record()', which
    stores what a run stores, as the recording of 'hwut.play' (E-165),
    and renders them.

    THE DIRECTORY IS HELD while the author's program runs, and while
    the candidates are written. What runs may write -- a concurrent
    run meeting half-written artifacts would be the same fault by
    another door. The lock is released before the rendering, which
    touches nothing.
    """
    from ....engine.operations import subject_provision
    from ....engine.operations.session import store_of

    store = store_of(configuration, bookkeeper)
    #  ASK FOR THE RAW STREAMS TOO: the raw stream is the material for
    #  '--raw' and for telling whether a pype touched anything.
    #  THE LIVE PANE (E-83): every raw line reaches the screen as the
    #  program writes it, under a LIVE banner, where a person is
    #  watching -- a terminal, not '--plain' into a pipe. The reading
    #  follows once the pype has seen the whole stream; a pyped line
    #  cannot be read before that.
    #  WATCHED is a terminal; PAINTED is the colour decision on top of it
    #  -- 'NO_COLOR' leaves the pane and paints nothing (the book's D-27).
    live_f = not plain_f and sys.stdout.isatty()
    banner_color_f = color_wanted_f(plain_f, None, sys.stdout)
    def live_line(line):
        """RETURN: None. One raw line, on the screen now."""
        sys.stdout.write("    " + line)
        sys.stdout.flush()
    tap = live_line if live_f else None
    #  A BUILT APPLICATION IS BUILT FIRST (session B.1): the build tool
    #  decides what is out of date. Play is the face that RECORDS a
    #  case's first recording (E-165), so it builds as a run builds --
    #  MEASURED 2026-10-22 before: play never built, and a compiled test
    #  played only where 'hwut.run' or 'hwut.accept' had built it.
    if configuration.build is not None:
        from ....engine.operations.build_action import build
        with MkdirMutex(str(configuration.test_directory)):
            outcome = await build(configuration)
        if not outcome.succeeded:
            write("FAULT: the build failed (%s)%s"
                  % (outcome.report.value,
                     "" if not outcome.missing_target_list else
                     " -- missing: %s"
                     % ", ".join(outcome.missing_target_list)))
            #  THE BUILD'S OWN WORD (operations todo-21, law 1): its
            #  exit, containment and the first line of what it said.
            if getattr(outcome, "record", None) is not None:
                from ....engine.operations.diagnosis import explain_record
                for line in explain_record(outcome.record, label="build"):
                    write("  " + line)
            write("NOT RECORDED: the run did not complete, and a partial "
                  "subject is never stored as if whole")
            return E_ExitCode.FAULT
    if live_f: write(banner("LIVE", banner_color_f))
    provision, _ = subject_provision.provider_of(configuration, store,
                                                 choice_name,
                                                 force_run=True,
                                                 keep_raw=True,
                                                 on_raw_line=tap)

    from ....engine.orchestrator.run import directory_script
    note_list = []
    here      = configuration.test_directory
    app_name  = case.source_file if case is not None \
                else configuration.key_name
    helper_env = directory_script.helper_env(app_name, choice_name)
    run_name  = app_name if choice_name is None \
                else "%s %s" % (app_name, choice_name)
    with MkdirMutex(str(here)):
        if frame_f:
            await _handler(directory_spec, here, "on_entry", None,
                           note_list)
        try:
            await _handler(directory_spec, here, "on_before_test",
                           helper_env, note_list, run_name)
            try:
                subjects = await provision.provide()
                recorded_db = None
                cut_short_f = subjects is not None \
                              and not _stream_whole_f(subjects,
                                                      configuration,
                                                      choice_name)
                if subjects is not None and not cut_short_f:
                    recorded_db = subject_provision.record(
                                      store, configuration, choice_name,
                                      provision, wanted=True,
                                      by="hwut.play")
            finally:
                await _handler(directory_spec, here, "on_after_test",
                               helper_env, note_list, run_name)
        finally:
            if frame_f:
                await _handler(directory_spec, here, "on_exit", None,
                               note_list)
    #  WHAT WAS RECORDED IS SAID AT THE END, where the reader's eye is
    #  after the reading: the recording 'hwut.accept' will bless.
    def recorded_note():
        """RETURN: None. The handlers' NOTEs, then the recording's line,
        or why there is none."""
        for line in note_list: write(line)
        if recorded_db:
            #  THE TAG NAMES WHAT WAS PLAYED (E-168): 'hwut.accept
            #  --digest=<tag>' blesses this recording and no other.
            from ..._accept_common import digest_tag
            path_list = [store.candidate_path(configuration.key_name,
                                              choice_name, name)
                         for name in sorted(recorded_db)]
            write("RECORDED: %s (digest: %s)"
                  % (", ".join(path.name for path in path_list),
                     digest_tag(path_list)))
        elif cut_short_f:
            #  THE STREAM'S OWN TESTIMONY IS MISSING (ND6, R-70): the
            #  help promised it -- a stream cut short is shown, and NOT
            #  recorded.
            write("NOT RECORDED: the stream did not end with "
                  "'<hwut-end>' -- empty, or cut short; a partial "
                  "subject is never stored as if whole")
        else:
            write("NOT RECORDED: the run did not complete, and a partial "
                  "subject is never stored as if whole")

    if subjects is None:
        write("FAULT: nothing was provided -- the build failed, or "
              "the application would not launch")
        _write_diagnosis(configuration, choice_name, provision, {}, write)
        recorded_note()
        return E_ExitCode.FAULT

    subject_db = {name: nominal.open().read()
                  for name, nominal in subjects.reader_db.items()}
    raw_db     = subjects.raw_db or {}

    text = subject_db.get(STDOUT, "")
    if not text.strip() and not raw_db.get(STDOUT, "").strip():
        #  AN EMPTY ANSWER IS NEVER REPORTED EMPTY (operations todo-21,
        #  law 1): with it, the call, what PATH resolved, the exit code,
        #  the containment and the other channel.
        launch_failed_f = _launch_failed_f(provision)
        if launch_failed_f:
            #  THE HELP'S WORD (ND2): an application that would not
            #  launch is a FAULT, exit 1 -- not an empty answer.
            write("FAULT: the application would not launch")
        else:
            write("EMPTY: the choice produced no output to read")
        _write_diagnosis(configuration, choice_name, provision,
                         {STDOUT: raw_db.get(STDOUT, "") or text,
                          STDERR: subject_db.get(STDERR, "")
                                  or raw_db.get(STDERR, "")}, write)
        recorded_note()
        return E_ExitCode.FAULT if launch_failed_f else E_ExitCode.EMPTY

    if live_f: write("")
    if raw_f:
        write(banner("RAW", banner_color_f))
        _write_indented(raw_db.get(STDOUT, "") or "(nothing)", write)
        write("")

    if pyped_f:
        pyped = raw_db.get(STDOUT)
        if pyped is None or pyped == text:
            write(banner("PYPED", banner_color_f))
            write("    no pype stands for this stream -- the subject "
                  "IS the raw stream")
        else:
            write(banner("PYPED", banner_color_f))
            _write_indented(text, write)
        write("")

    #  THE CONFIGURATION, IN THE SPECIFICATION LANGUAGE. Not a
    #  paraphrase and not a table: the very shape an author writes in
    #  'hwut.conf' or an '@hwut' block, printed by the one printer that
    #  knows it ('exploration/printer.case_text'), so what he is shown
    #  he can paste back. RESOLVED -- the application's defaults and
    #  the directory's folded in -- because the question a player asks
    #  is 'under what rules did THIS run', not 'what did I type'.
    if case is not None:
        write(banner("CONFIGURATION", banner_color_f))
        _write_indented(
            #  THE ORIGINS OF THIS CHOICE: 'origin_db' maps a choice to
            #  its origins (configuration_tree). MEASURED 2026-10-24: the
            #  whole map was handed down -- every parameter missed its
            #  place comment, and a choice named like a key ('same')
            #  crashed the face with an AttributeError.
            printer.case_text(case,
                              origin_db=(getattr(app, "origin_db", None)
                                         or {}).get(case.choice, {}),
                              provenance_f=True),
            write)
        write("")

    #  THE OUTPUT, under the READING. The test's own setup governs:
    #  the choice's declared tolerances, resolved exactly as a run
    #  resolves them ('adapter._compare_of'). Where the author
    #  declared none, the plain default stands, and the reading shows
    #  that in its 'setup' line.
    write(banner("OUTPUT", banner_color_f))
    options = _compare_options(configuration, choice_name)
    adapter = TuiDisplay(out=sys.stdout,
                         color_f=False if plain_f else None,
                         merge_f=False, reading_f=True)
    shown_f = await reading_view(text, adapter,
                                 subject_name=_subject_name(configuration,
                                                            choice_name),
                                 compare_options=options, write=write)

    if stderr_f:
        error_text = subject_db.get(STDERR, "") \
                     or raw_db.get(STDERR, "")
        write("")
        write(banner("STDERR", banner_color_f))
        #  E-5: stderr is never subject to testing, and play does not
        #  test it. SEEING IS NOT JUDGING -- a face whose purpose is
        #  to show an author what their program produced may show it,
        #  and the banner keeps the two apart.
        _write_indented(error_text or "(nothing)", write)
    if cut_short_f:
        #  WHY IT WAS CUT SHORT (ND3): a cap that killed it, its exit, its
        #  stderr -- the provision's own record, as for an empty answer.
        _write_diagnosis(configuration, choice_name, provision, {}, write)
    write("")
    recorded_note()
    #  THE READING IS THE PRODUCT: a text this face could not read is
    #  a FAULT, not an OK with a refusal printed in the middle of it --
    #  and so is a stream that could not be recorded (ND6).
    return E_ExitCode.OK if shown_f and not cut_short_f \
           else E_ExitCode.FAULT


def _write_diagnosis(configuration, choice_name, provision, channel_db,
                     write):
    """
    RETURN: None. THE DIAGNOSIS of the provision that answered nothing
            (operations todo-21, 'diagnosis.explain'): the call from the
            one source, what PATH resolved when it was made, every
            supervised call's containment, exit and stderr tail, the
            report token, and -- where 'channel_db' holds them -- the
            channels with the wrong-channel hint. A hint, never a
            verdict.

    MEASURED (audit r10, C-1): this face said "EMPTY" and nothing else,
    and its report helper read a field the delivery does not carry, so
    even the token never reached the screen.
    """
    from ....engine.operations.diagnosis import explain
    delivered = getattr(provision, "last_provided", None)
    record    = getattr(delivered, "provision", None)
    if record is None: return
    write("")
    for line in explain(configuration, choice_name, record,
                        channel_db or None).rstrip("\n").splitlines():
        write(line)


def _launch_failed_f(provision):
    """
    RETURN: bool, True if the provision's record says the application
            did not launch (report 'test-app-launch-failed');
            False, else -- or where no record stands.
    """
    delivered = getattr(provision, "last_provided", None)
    record    = getattr(delivered, "provision", None)
    report    = getattr(record, "report", None)
    return getattr(report, "value", report) == "test-app-launch-failed"


def _compare_options(configuration, choice_name):
    """
    RETURN: Configuration (compare's), the tolerances THIS choice
            declares; None where it declares none, which lets
            'reading_view' stand up the plain default.
    """
    choice = configuration.choice_db.get(choice_name)
    return None if choice is None else getattr(choice, "compare", None)


def _subject_name(configuration, choice_name):
    """
    RETURN: str, what the rendering calls the stream: the source file,
            and the choice beside it where one stands.
    """
    if choice_name is None: return configuration.source_file
    return "%s %s" % (configuration.source_file, choice_name)


def _write_indented(text, write):
    """
    RETURN: None. The text, four spaces in, line by line.
    """
    for line in str(text).splitlines(): write("    %s" % line)


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded("hwut.play", main))
