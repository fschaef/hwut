"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.play' COMMAND LINE -- run one test, show the
         READING of what it produced, under the test's OWN setup
         (disc-4).

    hwut.play <test-app> [<choice>] [--directory=<path>]

IT IS WIRING, NOT MACHINERY. Play is the composition of bricks that
already exist, and owns no ceremony of its own:

    the wish + CTestTaskListQuery   which run is meant
    provision_of(...)               SUBJECT PROVISION: build, launch,
                                    contain, collect, canonicalise --
                                    the very provision a run consumes
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
(engine/display/DISCUSSIONS/todo-2-pype-is-part-of-the-oracle.txt).
An author debugging one needs to see what it did to the stream.

PLAY JUDGES NOTHING AND RECORDS NOTHING; IT RENDERS. No nominal is
read, no verdict is reached, no Bookkeeper is touched, no result is
written. 'hwut.run' is the face that judges and records, and the
distinction is the whole point of this one: an author who wants to
SEE how the framework reads their output must be able to ask without
the asking becoming a result.

This closes the seam '_core.py' names -- "a service run inside a test
run receives that Configuration object directly". Play is the command
line's way to stand inside.

THE STREAM IS NOT KEPT. Nothing is written anywhere: what a run would
store, play shows and forgets. A person who wants the bytes redirects
the rendering.

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
from   ._core                                      import usage_line
from   ._exit                                      import E_ExitCode
from   .compare                                    import reading_view

USAGE = usage_line("usage: hwut.play",
                   ("<test-app>", "[<choice>]", "[--raw]", "[--pyped]",
                    "[--stderr]", "[--plain]",
                    "[--directory=<path>]"))

#  THE REGION BANNER. One shape wherever a stream is named, so a
#  reader never has to work out which picture they are looking at.
BANNER_WIDTH = 62


def banner(name):
    """
    RETURN: str, the region's own line: '===== <name> =====...', padded
            to one width so the regions of one rendering line up.
    """
    head = "===== %s " % name
    return head + "=" * max(BANNER_WIDTH - len(head), 5)

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

    directory = "."
    plain_f   = False
    stderr_f  = False
    raw_f     = False
    pyped_f   = False
    word_list = []
    for argument in argv:
        if   argument == "--plain":  plain_f  = True
        elif argument == "--stderr": stderr_f = True
        elif argument == "--raw":    raw_f    = True
        elif argument == "--pyped":  pyped_f  = True
        elif argument.startswith("--directory="):
            directory = argument[len("--directory="):]
        elif argument.startswith("-"):
            write("REFUSED: 'hwut.play' does not take: %s" % argument)
            write(USAGE)
            return E_ExitCode.REFUSED
        else:
            word_list.append(argument)

    if not word_list or len(word_list) > 2:
        write("REFUSED: 'hwut.play' plays ONE test, and one choice of "
              "it: <test-app> [<choice>]")
        write(USAGE)
        return E_ExitCode.REFUSED
    source_file = word_list[0]
    choice_name = word_list[1] if len(word_list) == 2 else None

    #  ONE ACTION, ONE PLACE ('exploration/selection.py').
    try:
        found  = selection.of_directory(os.path.abspath(directory),
                                        Wish())
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
                                 plain_f, stderr_f, raw_f, pyped_f,
                                 write))
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
    face takes, and 'CTestTaskListQuery' resolves it. So 'hwut.play
    "test-*.sh" one' globs as it does everywhere, and a choice that
    does not stand is refused in the words the whole framework uses.

    REFUSE RATHER THAN GUESS where several stand: playing 'the first'
    RUNS THE AUTHOR'S PROGRAM under a choice nobody asked for, and
    renders an answer to a question nobody put.
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

    if not case_tuple:
        offered = ", ".join(sorted(app_set.app_db)) or "nothing"
        write("REFUSED: nothing here answers '%s'; this directory "
              "offers: %s" % (" ".join(word_list), offered))
        return _REFUSED
    write("REFUSED: '%s' names %d runs, and this face plays ONE: %s"
          % (" ".join(word_list), len(case_tuple),
             ", ".join(_case_name(case) for case in case_tuple)))
    return _REFUSED


def _case_name(case):
    """
    RETURN: str, the run as a person names it: the file, and the
            choice beside it where one stands.
    """
    if case.choice is None: return case.source_file
    return "%s %s" % (case.source_file, case.choice)


async def _play(configuration, choice_name, plain_f, stderr_f,
                raw_f, pyped_f, write):
    """
    RETURN: E_ExitCode, the exit status.

    THE PROVISION DOES EVERYTHING A RUN'S PROVISION DOES -- build,
    launch, contain, collect, canonicalise -- because it IS a run's
    provision ('provision_of'). Play adds no ceremony: it asks for
    the subjects, and renders them.

    THE DIRECTORY IS HELD while the author's program runs. Play
    records nothing, but it RUNS something, and what it runs may
    write -- a concurrent run meeting half-written artifacts would be
    the same fault by another door. The lock is released before the
    rendering, which touches nothing.
    """
    from vut.engine.operations.run.core import provision_of

    #  ASK FOR THE RAW STREAMS TOO: 'keep_raw' is the provision's own
    #  switch ('record_raw'), and the raw stream is the material for
    #  '--raw' and for telling whether a pype touched anything.
    provision = provision_of(configuration, choice_name)
    provision.keep_raw = True

    with MkdirMutex(str(configuration.test_directory)):
        subjects = await provision.provide()

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

    if raw_f:
        write(banner("RAW -- what the application produced"))
        _write_indented(raw_db.get(STDOUT, "") or "(nothing)", write)
        write("")

    if pyped_f:
        pyped = raw_db.get(STDOUT)
        if pyped is None or pyped == text:
            write(banner("PYPED -- no pype stands for this stream"))
            write("    the subject IS the raw stream")
        else:
            write(banner("PYPED -- what the pype produced"))
            _write_indented(text, write)
        write("")

    #  THE SUBJECT, under the READING. The test's own setup governs:
    #  the choice's declared tolerances, resolved exactly as a run
    #  resolves them ('adapter._compare_of'). Where the author
    #  declared none, the plain default stands, and the reading shows
    #  that in its 'setup' line.
    write(banner("SUBJECT -- what enters the comparator"))
    options = _compare_options(configuration, choice_name)
    adapter = TuiDisplay(out=sys.stdout,
                         color_f=False if plain_f else None,
                         merge_f=False, reading_f=True)
    await reading_view(text, adapter,
                       subject_name=_subject_name(configuration,
                                                  choice_name),
                       compare_options=options)

    if stderr_f:
        error_text = subject_db.get(STDERR, "") \
                     or raw_db.get(STDERR, "")
        write("")
        write(banner("STDERR -- shown, never tested (E-5)"))
        #  E-5: stderr is never subject to testing, and play does not
        #  test it. SEEING IS NOT JUDGING -- a face whose purpose is
        #  to show an author what their program produced may show it,
        #  and the banner keeps the two apart.
        _write_indented(error_text or "(nothing)", write)
    return E_ExitCode.OK


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
    sys.exit(main())
