"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE MERGE SERVICE -- 'hwut.merge': one subject against one
       nominal, any streams or files, with a semantic merge loop.

DESCRIPTION
       A PLANNER, in the house sense: it wires existing pieces --
       'merge_session' (interaction/port.py) and a viewer
       ('services/lib/viewers.driver_for') -- and adds
       nothing of its own. What git mergetool cannot do, this can:
       equivalence under tolerances, analogies with provenance, and a
       guided merge whose alignment is compare's.

       DELIBERATELY IGNORANT OF THE TEST CORPUS. The service returns or
       writes THE ARTIFACT -- the merged nominal stream; where it lands
       is the caller's decision. Storing into GOOD/ stays Accept's
       affair (README section 10), so the same service merges two
       arbitrary files just as well as it serves a test run.

       THE CLI FACE ('python3 -m vut.services.merge'):

           hwut.merge SUBJECT NOMINAL [-o MERGED] [options]

       CHANNEL DISCIPLINE: the UI renders on STDERR, always; the
       ARTIFACT goes to '-o PATH', or to STDOUT when '-o' is absent.
       So 'app | hwut.merge - GOOD/x.txt > merged' pipes cleanly, and
       the screen never contaminates the artifact. 'SUBJECT' or
       'NOMINAL' may be '-' for stdin (one of them, not both).

       EXIT CODES:  0 the session COMMITTED (artifact written), or a
                      display-only run completed;
                    1 the session CANCELLED -- NOTHING is written, the
                      nominal is untouched;
                    2 the request itself was unusable.
______________________________________________________________________________
"""
import io
import os
import sys
import asyncio
import argparse

#  THE IMPORT CALL. A service face is EXECUTABLE from any directory;
#  run as a plain script it has no package context, so 'config.py' (in
#  THIS directory -- script-mode sys.path[0]) does the walk-up, and the
#  face merely ADOPTS its package (PEP 366). Dead under '-m' or import.
if __package__ in (None, ""):
    import _config
    __package__ = _config.PACKAGE
from ._exit import E_ExitCode  # delayed past _config adoption

from   vut.services.lib.viewers               import (driver_for,
                                  E_DisplayTarget)
from   vut.engine.operations.interaction.port import (merge_session,
                                  E_Intent,
                                  MERGE_ROUND_MAX)
from   ._core              import (read_source,
                                  add_setup_arguments,
                                  setup_from_arguments)


async def merge_text(subject_text, nominal_text, adapter,
                     subject_name="merge", compare_options=None,
                     max_round_n=MERGE_ROUND_MAX):
    """
    RETURN: (str, E_Intent), the merged nominal stream and the intent
            that ended the session.
            (None, E_Intent.CANCEL), the session resolved nothing -- the
            nominal is to be left exactly as it was.

    The service's ONE working form; everything else (files, stdin, the
    CLI) reduces to it. It is 'merge_session' with the service's
    argument order -- the material first, the machinery after.
    """
    import io
    from vut.engine.compare.api import feeder_ui as compare_feeder
    from vut.engine.compare.api import Configuration
    options = compare_options if compare_options is not None \
              else Configuration()
    def align(subject, working):
        """RETURN: AsyncIterable[DisplayInst], the alignment of
        'subject' against 'working', from compare's one door."""
        return compare_feeder.feed(options, io.StringIO(subject),
                                   io.StringIO(working))
    return await merge_session(align, subject_text, nominal_text,
                               adapter, subject_name,
                               max_round_n=max_round_n)


def main(argv=None):
    """
    RETURN: int, the exit code -- 0 committed or display-only done;
            1 cancelled, nothing written; 141 the reader left early;
            2 unusable request.

    Both channels may be pipes (the UI on stderr, the artifact on
    stdout), so a reader that leaves early is an ORDINARY ending, not
    a crash -- the unix answer, quietly.
    """
    import os
    try:
        return _main(argv)
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return E_ExitCode.SIGPIPE


def _main(argv):
    """
    RETURN: int, the exit code -- 'main' without the pipe guard.

    It builds the TUI driver on STDERR, runs the session, and writes
    the artifact ONLY on COMMIT -- to '-o PATH', or stdout.
    """
    parser = argparse.ArgumentParser(
        prog="hwut.merge",
        description="Merge a subject stream against a nominal stream, "
                    "with semantic tolerance. UI on stderr; the merged "
                    "nominal on -o PATH or stdout, and ONLY on commit.")
    parser.add_argument("subject",
                        help="the subject stream: a file path, or '-' "
                             "for stdin")
    parser.add_argument("nominal", nargs="?", default=None,
                        help="the nominal stream: a file path, or '-' "
                             "for stdin. OMITTED: the STORE FORM -- the "
                             "first word names a TEST, the store supplies "
                             "candidate and nominal (see --choice, "
                             "--directory)")
    parser.add_argument("--choice", default=None,
                        help="store form: the test's choice")
    parser.add_argument("--directory", default=".",
                        help="store form: the TEST directory "
                             "(default: '.')")
    parser.add_argument("-o", "--out", default=None,
                        help="where a COMMIT's artifact is written "
                             "(default: stdout)")
    parser.add_argument("--display-only", action="store_true",
                        help="present the comparison once; no merge, "
                             "nothing written")
    parser.add_argument("--plain", action="store_true",
                        help="no colors, even on a tty")
    parser.add_argument("--editor", default=None,
                        help="editor command (default: $VISUAL, $EDITOR, "
                             "'vi'); the nominal's file path is appended")
    parser.add_argument("--max-rounds", type=int, default=MERGE_ROUND_MAX,
                        help="the session's round cap (default: %i)"
                             % MERGE_ROUND_MAX)
    add_setup_arguments(parser)
    arguments = parser.parse_args(argv)
    setup     = setup_from_arguments(arguments)

    if arguments.subject == "-" and arguments.nominal == "-":
        parser.error("only one of SUBJECT and NOMINAL may be '-': stdin "
                     "is one stream, not two")

    if arguments.nominal is None:
        #  THE STORE FORM. One word names a TEST; the store supplies
        #  both streams -- and SUBJECT PROVISION says whether they may
        #  be used (operations disc-2, production=False: this face
        #  never executes). A stale or absent recording is refused
        #  with the step that decided, exactly as 'hwut.accept'
        #  refuses: a merge over what the PREVIOUS text printed would
        #  bless the wrong evidence one screen later.
        from vut.engine.bookkeeper.api import Bookkeeper
        from vut.engine.operations            import subject_provision
        test      = arguments.subject
        book      = Bookkeeper(arguments.directory)
        candidate = book.candidate_path(test, arguments.choice, "stdout")
        nominal   = book.nominal_path(test, arguments.choice, "stdout")

        class _Bare:
            build       = None
            source_file = os.path.join(arguments.directory, test)
        decision = subject_provision.decide(_Bare, str(candidate),
                                            production=False)
        if decision.what is not subject_provision.E_Decision.RECORDED:
            sys.stderr.write("REFUSED: %s --\n    %s%s\n"
                             "re-run the test ('hwut.run'), then merge.\n"
                             % (decision.because, test,
                                "" if arguments.choice is None
                                else " " + arguments.choice))
            return E_ExitCode.FAULT
        try:
            with io.open(str(nominal), encoding="utf-8") as fh:
                nominal_text = fh.read()
        except OSError:
            sys.stderr.write("REFUSED: no nominal stands for '%s'%s -- "
                             "there is nothing to merge AGAINST.\n"
                             "A first nominal is 'hwut.accept's to "
                             "create, not a merge's.\n"
                             % (test, "" if arguments.choice is None
                                     else " '" + arguments.choice + "'"))
            return E_ExitCode.FAULT
        with io.open(str(candidate), encoding="utf-8") as fh:
            subject_text = fh.read()
        #  THE ARTIFACT NEVER LANDS IN GOOD/ BY THIS FACE's HAND: a
        #  merged nominal committed here goes to '-o'/stdout, and
        #  BECOMES the nominal only through 'hwut.accept' -- the one
        #  way a nominal comes to exist, books and all.
    else:
        subject_text = read_source(arguments.subject)
        nominal_text = read_source(arguments.nominal)

    editor_argv = None
    if arguments.editor is not None:
        import shlex
        editor_argv = shlex.split(arguments.editor)

    adapter = driver_for(E_DisplayTarget.TUI,
                         out         = sys.stderr,
                         input_f     = input,
                         editor_argv = editor_argv,
                         color_f     = False if arguments.plain else None,
                         merge_f     = not arguments.display_only)

    text, intent = asyncio.run(merge_text(
        subject_text, nominal_text, adapter,
        subject_name    = arguments.subject,
        compare_options = setup,
        max_round_n     = arguments.max_rounds))

    if arguments.display_only:
        return E_ExitCode.OK
    if intent is not E_Intent.COMMIT or text is None:
        return E_ExitCode.FAULT
    if arguments.out is None:
        sys.stdout.write(text)
    else:
        with io.open(arguments.out, "w", encoding="utf-8") as file_handle:
            file_handle.write(text)
    return E_ExitCode.OK


if __name__ == "__main__":
    sys.exit(main())
