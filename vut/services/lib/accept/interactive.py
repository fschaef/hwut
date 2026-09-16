"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE INTERACTIVE ACCEPT -- 'hwut.accept.interactive': the cases a
       wish selects whose candidate differs from its nominal, shown one
       by one, edited by hand where wanted, and ACCEPTED on commit --
       through accept's own door, books and all (E-51).

           hwut.accept.interactive [<wish>] [<test> [<choice>]] ...
                                   [--directory=<path>] [--all] [--force]
                                   [--console] [-y] [--width N] [--plain]
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
       differing case: the CHECKLIST first; '--all'/'--force' skip it.
       THE CHECKLIST IS RE-ENTERED after every round and its '[X]'
       says HANDLED -- what this session has already worked, and will
       not offer again -- not 'selected'.

       ASPIRANTS STAND FIRST (B-14). A test the book knows with no
       nominal is an ASPIRANT -- playable, not runnable -- and this
       door is where it becomes a member. It opens on the mirror
       'accept_first' builds, the banner says 'aspirant', and what the
       report says of it is BLESSED, never accepted: there was no pole
       to reconcile with (E-51/E-59).

       PER CASE, ONE SESSION: the view ('-y' two columns, subject
       LEFT, nominal RIGHT), then [e]dit / [c]ommit / [q]uit. Quit
       leaves the case exactly as it stood and goes on to the next.

       '--console' asks for the line-based session; without it, where
       the screen cannot run -- no terminal, no 'prompt_toolkit' -- the
       line-based session runs and ONE note says why (E-79).

       ON A TERMINAL the keyed tier runs and F1 prints the keymap --
       the table itself, so it cannot go stale. Both panes hold ONE
       viewport, so they stay level however far down the author goes;
       'h'/'l' move the view sideways; '/' and '?' open a search line
       that the keymap yields to while it is open. A subject section
       already taken is SPENT: it stands on a grey-green band, no cursor
       reaches it and no range intersects it (E-63). '--plain' reaches
       this tier too.

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
from . import engine
from vut.services.lib.cmdline import parse_or_refuse
from .engine import merge_text, MERGE_ROUND_MAX  # noqa: F401 (E-51's names)
import argparse

from   vut.services.lib.viewers               import (driver_for,
                                                      E_DisplayTarget)
from   vut.engine.operations.interaction.port import (merge_session,
                                                      E_Intent,
                                                      MERGE_ROUND_MAX)
from   vut.engine.orchestrator.plan.wish      import parse_wish, WishError
from   vut.services._cases                    import (select,
                                                      differing_keys)
from   vut.services.lib.checklist             import Checklist
from   vut.services._core                     import (add_setup_arguments,
                                                      setup_from_arguments)
from   vut.services._exit                     import E_ExitCode
from   vut.services.accept                    import (token_terminated_f,
                                                      stderr_spoke_db,
                                                      stderr_decision)

USAGE = ("usage: hwut.accept.interactive [<wish>] [<test> [<choice>]] "
         "[--directory=<path>] [--all] [--force] [--console] [-y] "
         "[--width N] [--plain] [--editor E] [--stderr-tol]")


#  What a value IS (E-81): True, a path follows; a tuple, the words.
ARG_DB = {"--directory": True, "--editor": True}


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
        #  NO ABBREVIATION (E-81): '--forc' was measured to RUN as
        #  '--force'; a word not in the table is refused, and suggested.
        allow_abbrev=False,
        description="Show each differing case, edit, and ACCEPT on "
                    "commit -- through hwut.accept's own door.")
    parser.add_argument("word", nargs="*",
                        help="a test, a test and a choice, any wish word")
    parser.add_argument("--directory", default=None,
                        help="ONE test directory (default: the tree "
                             "below the cwd)")
    parser.add_argument("--all", action="store_true",
                        help="every differing case, no checklist")
    parser.add_argument("-f", "--force", action="store_true",
                        help="every differing case, no checklist, the "
                             "subject taken whole -- for scripts")
    parser.add_argument("--plain", action="store_true",
                        help="no colors, even on a tty")
    parser.add_argument("--console", action="store_true",
                        help="the line-based session, not the screen")
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
    arguments, completion_f = parse_or_refuse(parser, rest_list, err, ARG_DB)
    if completion_f:      return E_ExitCode.OK
    if arguments is None: return E_ExitCode.REFUSED
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
    editor_argv = None
    if arguments.editor is not None:
        import shlex
        editor_argv = shlex.split(arguments.editor)

    #  THE ENGINE IS SHARED (E-59): 'hwut.accept' reaches the same loop
    #  where a nominal stands. Neither door owns it, so a rule about
    #  promotion cannot hold at one and not the other.
    adapter = engine.adapter_for(editor_argv=editor_argv,
                                 plain_f=arguments.plain,
                                 side_by_side_f=arguments.side_by_side,
                                 width=arguments.width,
                                 console_f=arguments.console
                                           or arguments.force,
                                 err=err)
    #  ONE CASE PER ASK, and the checklist remembers what was handed
    #  over. The loop ends on None and on nothing else.
    checklist = Checklist(key_list, err, sys.stdin.readline,
                          label_of=lambda key: key.label,
                          all_f=arguments.all or arguments.force)
    chosen_n = 0
    accepted_list, refused_list, left_list = [], [], []
    while True:
        key = checklist.pick()
        if key is None: break
        chosen_n += 1
        accepted, refused, left = engine.run_sessions(
            [key], selected.store_of, adapter, err,
            setup=setup if setup_said_f else None,
            max_round_n=arguments.max_rounds,
            stderr_tol_f=arguments.stderr_tol)
        accepted_list += accepted
        refused_list  += refused
        left_list     += left
    if not chosen_n:
        err("NOTE: nothing accepted")
        return E_ExitCode.OK
    return engine.report(accepted_list, refused_list, left_list,
                         chosen_n, err)


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded("hwut.accept.interactive", main))
