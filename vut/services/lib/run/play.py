"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.run.play' COMMAND LINE -- run one test, show the
         READING of what it produced, under the test's OWN setup
         (disc-4).

    hwut.run.play <test-app> [<choice>] [--save] [--directory=<path>]

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
(adm/WORK/gathered/06-todo-2-pype-is-part-of-the-oracle.txt).
An author debugging one needs to see what it did to the stream.

PLAY JUDGES NOTHING; IT RENDERS. No nominal is read, no verdict is
reached, no result is written. 'hwut.run' is the face that judges and
records, and the distinction is the whole point of this one: an author
who wants to SEE how the framework reads their output must be able to
ask without the asking becoming a result.

    --save      the subjects are ALSO stored as the run's candidates,
                through the channel's own 'record()' -- what
                'hwut.run' would have stored, and nothing else: no
                verdict, no book entry. This is a NEW test's entrance:
                'hwut.run.play --save', look, then 'hwut.accept'. Without
                it nothing is written anywhere.

This closes the seam '_core.py' names -- "a service run inside a test
run receives that Configuration object directly". Play is the command
line's way to stand inside.

THE STREAM IS NOT KEPT unless '--save' says so: what a run would
store, play shows and forgets. A person who wants the bytes redirects
the rendering, or saves the candidate.

EXIT STATUS (E-1, services/_exit.py):
    0  OK       the choice ran and its reading is displayed
    1  FAULT    the build failed, the application would not launch, or
                the tree cannot be read -- what was learnt is shown
    2  REFUSED  the command line cannot be read: no such application,
                no such choice, or a choice not named where the
                application offers several
    3  EMPTY    the choice produced no output to read
______________________________________________________________________________
"""
import asyncio
import os
import sys

from   vut.services.lib.viewers.tui                import TuiDisplay
from   vut.engine.orchestrator.exploration          import selection
from   vut.engine.orchestrator.exploration.tree_explorer \
                                                   import RootConfMissing
from   vut.engine.orchestrator.run.adapter         import (
                                                       test_configuration_of)
from   vut.engine.orchestrator.exploration.task_list \
                                                   import SelectionError
from   vut.engine.orchestrator.exploration.task_list_query \
                                                   import CTestTaskListQuery
from   vut.engine.orchestrator.plan.wish           import (Wish,
                                                           with_targets)
from   vut.auxiliary.directory_mutex               import (DirectoryBusy,
                                                           MkdirMutex)
from   vut.services._exit                          import E_ExitCode
from   vut.services._target                        import entered
from   vut.services.lib.run.diff                   import reading_view
from   vut.services.lib.cmdline import (face_parser, usage_of,
                                        parse_or_refuse, did_you_mean)
from   vut.engine.orchestrator.exploration import printer
from   vut.services.report import (painted, color_wanted_f,
                                   ANSI_TITLE)

#  THE STANDARD READER (E-84). Play takes no wish: ONE test, one choice.
PARSER = face_parser("hwut.run.play", "Run one choice now and show it.",
                     wish_f=False,
                     word_help="the test application, and a choice",
                     word_metavar="<test-app> [<choice>]")
for _name in ("--raw", "--pyped", "--stderr", "--plain", "--save"):
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
        write(HELP)
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
    save_f    = arguments.save
    word_list = arguments.word

    #  A TEST NAMED BY PATH IS ENTERED ('services/_target.py', E-47).
    found = entered(word_list, directory, write, USAGE)
    if found is None: return E_ExitCode.REFUSED
    directory, word_list = found
    if not word_list or len(word_list) > 2:
        write("REFUSED: 'hwut.run.play' plays ONE test, and one choice of "
              "it: <test-app> [<choice>]")
        write(USAGE)
        return E_ExitCode.REFUSED
    source_file = word_list[0]
    choice_name = word_list[1] if len(word_list) == 2 else None

    #  ONE ACTION, ONE PLACE ('exploration/selection.py').
    try:
        #  'base_f=True': the channel needs the Store over the book --
        #  to decide against the candidate path, and to write one on
        #  '--save'. Nothing is written without that word.
        found  = selection.of_directory(os.path.abspath(directory),
                                        Wish(), base_f=True)
    except RootConfMissing as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    result = found.result_db["."]
    if found.fault_tuple:
        for fault in found.fault_tuple: write("FAULT: %s" % fault)
        write("nothing played: a directory that cannot be fully read "
              "cannot say what it offers")
        return E_ExitCode.FAULT

    case = _settled_case(result.app_set, source_file, choice_name,
                         directory, write)
    if case is _REFUSED: return E_ExitCode.REFUSED
    choice_name   = case.choice
    configuration = test_configuration_of(
                        result.app_set.app_db[case.source_file],
                        os.path.abspath(directory),
                        language_setup=result.app_set.directory_spec
                                             .language_setup)
    try:
        return asyncio.run(_play(configuration, choice_name,
                                 found.bookkeeper_db["."],
                                 plain_f, stderr_f, raw_f, pyped_f,
                                 save_f, write,
                                 case=case,
                                 app=result.app_set.app_db[case.source_file]))
    except DirectoryBusy as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED


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
    face takes, and 'CTestTaskListQuery' resolves it. So 'hwut.run.play
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
            write("REFUSED: no choice specified; '%s' reports %d "
                  "choice(s): %s"
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


async def _play(configuration, choice_name, bookkeeper, plain_f,
                stderr_f, raw_f, pyped_f, save_f, write,
                case=None, app=None):
    """
    RETURN: E_ExitCode, the exit status.

    THE PROVISION DOES EVERYTHING A RUN'S PROVISION DOES -- build,
    launch, contain, collect, canonicalise -- because it IS a run's
    provision, obtained through the one channel ('subject_provision',
    'force_run': play means run now). Play adds no ceremony: it asks
    for the subjects, and renders them; with '--save' it also hands
    them to the channel's 'record()', which stores what a run stores.

    THE DIRECTORY IS HELD while the author's program runs, and while
    the candidates are written. What runs may write -- a concurrent
    run meeting half-written artifacts would be the same fault by
    another door. The lock is released before the rendering, which
    touches nothing.
    """
    from vut.engine.operations           import subject_provision
    from vut.engine.operations.session   import store_of

    store = store_of(configuration, bookkeeper)
    #  ASK FOR THE RAW STREAMS TOO: the raw stream is the material for
    #  '--raw' and for telling whether a pype touched anything.
    #  THE LIVE PANE (E-83): every raw line reaches the screen as the
    #  program writes it, under a LIVE banner, where a person is
    #  watching -- a terminal, not '--plain' into a pipe. The reading
    #  follows once the pype has seen the whole stream; a pyped line
    #  cannot be read before that.
    live_f = color_wanted_f(plain_f, None, sys.stdout) and not plain_f
    banner_color_f = live_f
    def live_line(line):
        """RETURN: None. One raw line, on the screen now."""
        sys.stdout.write("    " + line)
        sys.stdout.flush()
    tap = live_line if live_f else None
    if live_f: write(banner("LIVE", banner_color_f))
    provision, _ = subject_provision.provider_of(configuration, store,
                                                 choice_name,
                                                 force_run=True,
                                                 keep_raw=True,
                                                 on_raw_line=tap)

    with MkdirMutex(str(configuration.test_directory)):
        subjects = await provision.provide()
        if save_f and subjects is not None:
            recorded_db = subject_provision.record(store, configuration,
                                                   choice_name, provision,
                                                   wanted=True)
            if recorded_db is None:
                write("NOTE: nothing saved -- the provision did not "
                      "complete, and a partial subject is never "
                      "stored as if whole")
            else:
                write("SAVED: %s" % ", ".join(
                    store.candidate_path(configuration.key_name,
                                         choice_name, name).name
                    for name in sorted(recorded_db)))

    if subjects is None:
        write("FAULT: nothing was provided -- the build failed, or "
              "the application would not launch")
        _write_provision_report(provision, write)
        return E_ExitCode.FAULT

    subject_db = {name: nominal.open().read()
                  for name, nominal in subjects.reader_db.items()}
    raw_db     = subjects.raw_db or {}

    text = subject_db.get(STDOUT, "")
    if not text.strip() and not raw_db.get(STDOUT, "").strip():
        write("EMPTY: the choice produced no output to read")
        return E_ExitCode.EMPTY

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
            printer.case_text(case,
                              origin_db=getattr(app, "origin_db", None),
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
    #  THE READING IS THE PRODUCT: a text this face could not read is
    #  a FAULT, not an OK with a refusal printed in the middle of it.
    return E_ExitCode.OK if shown_f else E_ExitCode.FAULT


def _write_provision_report(provision, write):
    """
    RETURN: None. What the provision said about its own failure --
            the report it named, and every target it could not build.

    Play holds no opinion about a failed build: in a run it is a
    failing TEST; here it is simply the reason there is nothing to
    play, and the provision's own words say why.
    """
    record = getattr(provision, "last_provided", None)
    report = getattr(record, "report", None) if record is not None \
             else None
    if report is not None:
        write("    %s" % getattr(report, "value", report))


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
    from   vut.services._exit import guarded
    sys.exit(guarded("hwut.run.play", main))
