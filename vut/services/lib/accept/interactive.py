"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE INTERACTIVE ACCEPT -- 'hwut.accept.interactive': the cases a
       wish selects whose candidate differs from its nominal, shown one
       by one, edited by hand where wanted, and ACCEPTED on commit --
       through accept's own door, books and all (E-51).

           hwut.accept.interactive [<wish>] [<test> [<choice>]] ...
                                   [--directory=<path>] [--all] [--yes]
                                   [-y] [--width N] [--plain]
                                   [--editor E] [--max-rounds N]
                                   [--stderr-tol]

DESCRIPTION
       'hwut.accept' refuses a case whose nominal stands ('merge
       required') unless '--force' says: overwrite the pole with what
       the run printed. THIS face is the third answer: look at the
       difference, take the candidate's line here, the nominal's
       there, edit, and commit what YOU decided. The commit IS the
       acceptance: 'store.accept', the register, the book's
       acceptance note -- the same three writes 'hwut.accept' makes,
       so the three records agree (E-41).

       THE CANDIDATE STAYS AS THE RUN LEFT IT. What was printed is
       evidence; what was accepted is the nominal. A partial
       acceptance -- three of five differing lines taken -- leaves a
       candidate that still differs, and the next 'hwut.run' says so:
       that is the story of a partial accept, not a bug in it.

       WHAT IS SELECTED is measured, not remembered ('services/
       _cases.py'): compare's engine judges each candidate against
       its nominal under the choice's own setup, now. More than one
       differing case: the CHECKLIST first; '--all'/'--yes' skip it.
       A case with no nominal yet is not this face's: a first blessing
       is 'hwut.accept's.

       PER CASE, ONE SESSION: the view ('-y' two columns, subject
       LEFT, nominal RIGHT), then [e]dit / [c]ommit / [q]uit. Quit
       leaves the case exactly as it stood and goes on to the next.

       REFUSED AT COMMIT, with 'hwut.accept's own words: a stained
       choice (a test that switches results has no pole), a text
       without the closing token (never COMPLETED, R-70), a choice
       whose stderr spoke and nothing tolerates it ('--stderr-tol').

       UI ON STDERR, like every session face; stdout stays clean.

       EXIT: OK where every chosen case was accepted or quit on
       purpose; FAULT where a commit was refused; EMPTY where the wish
       selected nothing; REFUSED where the words cannot be read.
______________________________________________________________________________
"""
import io
import sys
import asyncio
import argparse

from   vut.services.lib.viewers               import (driver_for,
                                                      E_DisplayTarget)
from   vut.engine.operations.interaction.port import (merge_session,
                                                      E_Intent,
                                                      MERGE_ROUND_MAX)
from   vut.engine.orchestrator.plan.wish      import parse_wish, WishError
from   vut.services._cases                    import (select,
                                                      differing_keys,
                                                      choose)
from   vut.services._core                     import (add_setup_arguments,
                                                      setup_from_arguments)
from   vut.services._exit                     import E_ExitCode
from   vut.services.accept                    import (token_terminated_f,
                                                      stderr_spoke_db,
                                                      stderr_decision)

USAGE = ("usage: hwut.accept.interactive [<wish>] [<test> [<choice>]] "
         "[--directory=<path>] [--all] [--yes] [-y] [--width N] "
         "[--plain] [--editor E] [--stderr-tol]")


async def merge_text(subject_text, nominal_text, adapter,
                     subject_name, compare_options,
                     max_round_n=MERGE_ROUND_MAX):
    """
    RETURN: (str, E_Intent), the merged nominal stream and the intent
            that ended the session.
            (None, E_Intent.CANCEL), the session resolved nothing.

    'merge_session' with the alignment from compare's one door under
    this choice's options.
    """
    from vut.engine.compare.api import feeder_ui as compare_feeder
    from vut.engine.compare.api import Configuration
    options = compare_options if compare_options is not None \
              else Configuration()
    def align(subject, working):
        """RETURN: AsyncIterable[DisplayInst], the alignment of
        'subject' against 'working'."""
        return compare_feeder.feed(options, io.StringIO(subject),
                                   io.StringIO(working))
    return await merge_session(align, subject_text, nominal_text,
                               adapter, subject_name,
                               max_round_n=max_round_n)


def main(argv=None):
    """
    RETURN: E_ExitCode, per the module purpose.
    """
    if argv is None: argv = sys.argv[1:]
    err = lambda t: sys.stderr.write(t + "\n")
    try:
        wish, rest_list = parse_wish(list(argv))
    except WishError as error:
        err("REFUSED: %s" % error)
        return E_ExitCode.REFUSED

    parser = argparse.ArgumentParser(
        prog="hwut.accept.interactive",
        description="Show each differing case, edit, and ACCEPT on "
                    "commit -- through hwut.accept's own door.")
    parser.add_argument("word", nargs="*",
                        help="a test, a test and a choice, any wish word")
    parser.add_argument("--directory", default=None,
                        help="ONE test directory (default: the tree "
                             "below the cwd)")
    parser.add_argument("--all", action="store_true",
                        help="every differing case, no checklist")
    parser.add_argument("--yes", action="store_true", help="as '--all'")
    parser.add_argument("--plain", action="store_true",
                        help="no colors, even on a tty")
    parser.add_argument("-y", "--side-by-side", action="store_true",
                        help="two columns: subject LEFT, nominal RIGHT")
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--editor", default=None,
                        help="editor command (default: $VISUAL, $EDITOR, "
                             "'vi')")
    parser.add_argument("--max-rounds", type=int, default=MERGE_ROUND_MAX)
    parser.add_argument("--stderr-tol", "--stderr-tolerated",
                        dest="stderr_tol", action="store_true",
                        help="accept although stderr spoke")
    add_setup_arguments(parser)
    arguments = parser.parse_args(rest_list)
    setup_said_f = any(getattr(arguments, n, None) is not None
                       for n in ("numeric", "pattern", "nothing"))
    setup = setup_from_arguments(arguments)

    #  '--directory=<path>' as every accept face spells it, too.
    selected, code = select(wish, arguments.word,
                            arguments.directory or ".",
                            arguments.directory is not None, err, USAGE)
    if selected is None: return code
    if not selected.where_list:
        err("EMPTY: the wish selects no case")
        return E_ExitCode.EMPTY
    key_list, judged_n = differing_keys(selected, err)
    if not key_list:
        err("nothing to accept: %d case(s) judged, every candidate "
            "equivalent to its nominal" % judged_n)
        return E_ExitCode.OK
    chosen = choose(key_list, err, sys.stdin.readline,
                    all_f=arguments.all, yes_f=arguments.yes)
    if not chosen:
        err("NOTE: nothing accepted")
        return E_ExitCode.OK

    editor_argv = None
    if arguments.editor is not None:
        import shlex
        editor_argv = shlex.split(arguments.editor)
    adapter = driver_for(E_DisplayTarget.TUI,
                         out         = sys.stderr,
                         input_f     = input,
                         editor_argv = editor_argv,
                         color_f     = False if arguments.plain else None,
                         merge_f     = True,
                         side_by_side_f = arguments.side_by_side,
                         width       = arguments.width)

    accepted_list, refused_list, left_list = [], [], []
    for key in chosen:
        store = selected.store_of(key.where)
        options = setup if setup_said_f else key.setup
        text, intent = asyncio.run(merge_text(
            key.subject_text, key.nominal_text, adapter, key.label,
            options, max_round_n=arguments.max_rounds))
        if intent is not E_Intent.COMMIT or text is None:
            left_list.append(key); continue
        reason = _refusal(store, key, text, arguments.stderr_tol, err)
        if reason is not None:
            refused_list.append((key, reason)); continue
        #  THE THREE WRITES OF AN ACCEPTANCE, as 'hwut.accept' makes
        #  them (E-41): the nominal, the register, the book.
        store.accept(key.test, key.choice, "stdout", text)
        store.bookkeeper.note_accept(key.test, key.choice)
        accepted_list.append(key)

    err("")
    err("=" * 78)
    err("ACCEPTED  %d of %d" % (len(accepted_list), len(chosen)))
    err("-" * 78)
    for key in accepted_list:         err("    accepted       %s" % key.label)
    for key, reason in refused_list:  err("    refused        %s -- %s"
                                          % (key.label, reason))
    for key in left_list:             err("    left alone     %s" % key.label)
    err("=" * 78)
    return E_ExitCode.FAULT if refused_list else E_ExitCode.OK


def _refusal(store, key, text, stderr_tol_f, err):
    """
    RETURN: str, why this text may NOT become the nominal -- in
            'hwut.accept's words; None where it may.
    """
    if store.bookkeeper.stain(key.test, key.choice) is not None:
        return "a stained choice has no pole to declare"
    if not token_terminated_f(text):
        return "the closing token '<hwut-end>' is not the last line " \
               "-- a stream that never COMPLETED is not promotable"
    class _Case:
        source_file = key.test; choice = key.choice
    spoke_db = stderr_spoke_db(store, [_Case()])
    if spoke_db:
        refused = stderr_decision(store, spoke_db, stderr_tol_f, err)
        if refused: return "stderr spoke and nothing tolerates it " \
                           "('--stderr-tol')"
    return None


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded("hwut.accept.interactive", main))
