"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE MERGE SERVICE -- 'hwut merge': one subject against one
       nominal, any streams or files, with a semantic merge loop.

DESCRIPTION
       A PLANNER, in the house sense: it wires existing pieces --
       'merge_session' (feed.py) and a driver ('driver_for') -- and adds
       nothing of its own. What git mergetool cannot do, this can:
       equivalence under tolerances, analogies with provenance, and a
       guided merge whose alignment is compare's.

       DELIBERATELY IGNORANT OF THE TEST CORPUS. The service returns or
       writes THE ARTIFACT -- the merged nominal stream; where it lands
       is the caller's decision. Storing into GOOD/ stays Accept's
       affair (README section 10), so the same service merges two
       arbitrary files just as well as it serves a test run.

       THE CLI FACE ('python3 -m vut.engine.test_run.merge'):

           hwut merge SUBJECT NOMINAL [-o MERGED] [options]

       CHANNEL DISCIPLINE: the UI renders on STDERR, always; the
       ARTIFACT goes to '-o PATH', or to STDOUT when '-o' is absent.
       So 'app | hwut merge - GOOD/x.txt > merged' pipes cleanly, and
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
import sys
import asyncio
import argparse

from   vut.engine.test_run.feed    import (merge_session, driver_for,
                                           E_DisplayTarget, E_Intent,
                                           MERGE_ROUND_MAX)
from   vut.engine.test_run.service import (read_source,
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
    return await merge_session(compare_options, subject_text, nominal_text,
                               adapter, subject_name,
                               max_round_n=max_round_n)


def main(argv=None):
    """
    RETURN: int, the exit code -- 0 committed or display-only done;
            1 cancelled, nothing written; 2 unusable request.

    The CLI face. It builds the TUI driver on STDERR, runs the session,
    and writes the artifact ONLY on COMMIT -- to '-o PATH', or stdout.
    """
    parser = argparse.ArgumentParser(
        prog="hwut merge",
        description="Merge a subject stream against a nominal stream, "
                    "with semantic tolerance. UI on stderr; the merged "
                    "nominal on -o PATH or stdout, and ONLY on commit.")
    parser.add_argument("subject",
                        help="the subject stream: a file path, or '-' "
                             "for stdin")
    parser.add_argument("nominal",
                        help="the nominal stream: a file path, or '-' "
                             "for stdin")
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
        return 0
    if intent is not E_Intent.COMMIT or text is None:
        return 1
    if arguments.out is None:
        sys.stdout.write(text)
    else:
        with io.open(arguments.out, "w", encoding="utf-8") as file_handle:
            file_handle.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
