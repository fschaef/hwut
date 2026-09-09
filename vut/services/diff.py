"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE DIFF SERVICE -- 'hwut.diff': display how two streams
       compare, how the store's candidates compare to their nominals,
       or how compare READS one stream.

DESCRIPTION
       THE SIBLING OF 'hwut.accept.interactive' (lib/accept/interactive.py),
       deliberately homogeneous:
       the same TUI renderer, the same rows, marks, notes and banner --
       an author moves between the two without relearning the picture.
       What differs is the QUESTION asked:

           hwut.diff SUBJECT NOMINAL      how do these two FILES
                                          compare? (the VERDICT view:
                                          marks say what DID differ)
           hwut.diff FILE                 how does compare READ this
                                          stream? (the READING view:
                                          marks say what CAN vary --
                                          '{numeric}', '~analogy~',
                                          '<pattern>', '!binding!',
                                          '|nothing|')
           hwut.diff [<wish>] [<test> [<choice>]] ...
                                          THE STORE FORM (E-50): every
                                          case the wish selects whose
                                          stdout candidate differs from
                                          its nominal -- judged NOW by
                                          compare's engine under the
                                          choice's own setup, not by the
                                          book's memory. More than one:
                                          a CHECKLIST first, in the
                                          terminal; '--all' or '--yes'
                                          skips it. One: straight to
                                          the view. None: EMPTY.

       WHICH FORM. Two words that both name existing files are the
       file form. One word naming an existing file WITHOUT an '@hwut'
       block is the reading form. Anything else -- a test application,
       a test and a choice, a wish option, '--directory' -- is the
       store form, in the directory entered by a path word (E-47) or
       said by '--directory', the tree below the cwd otherwise.

       THE READING IS THE INTERPRETATION MADE VISIBLE: which elements
       the reading (compare's 'reading/') lexed as numerics, analogies,
       patterns, bindings, visible nothings, and which regions frame
       them. It is produced by feeding the stream against ITSELF --
       every pair equivalent BY CONSTRUCTION, so nothing but the
       interpretation shows. No second feeder, no second door: the one
       association serves both questions.

       DISPLAY ONLY. This service never merges and never writes an
       artifact -- the rendering IS the product, so it goes to STDOUT
       (the interactive accept renders on stderr). Editing and
       accepting belong to 'hwut.accept.interactive'.

       EXIT CODES (the diff convention):
                    0 equivalent -- no differing pair (or: a reading
                      was displayed; or: the store form found nothing
                      differing);
                    1 at least one differing pair was shown;
                    2 the request itself was unusable;
                    3 the store form selected no case.
______________________________________________________________________________
"""
import io
import sys
import asyncio
import argparse

#  THE IMPORT CALL -- see _config.py: it (this directory) does the
#  walk-up; the face adopts its package (PEP 366). Dead under '-m'.
if __package__ in (None, ""):
    import _config
    __package__ = _config.PACKAGE
from ._exit import E_ExitCode  # delayed past _config adoption

from   vut.engine.operations.interaction.port import deliver
from   vut.services.lib.viewers.tui           import TuiDisplay
from   vut.engine.compare.api                 import feeder_ui as compare_feeder
from   ._core              import (read_source,
                                  add_setup_arguments,
                                  setup_from_arguments)
from   ._cases             import select, differing_keys, choose
from   vut.engine.orchestrator.plan.wish import parse_wish, WishError


async def compare_view(subject_text, nominal_text, adapter,
                       subject_name="compare", compare_options=None):
    """
    RETURN: int, the count of DIFFERING pairs the display carried --
            0 is equivalence, by the Lawyer/Judge agreement law.

    ONE ALIGNMENT, obtained at compare's own door and handed to the
    port's delivery loop; the adapter renders it. The verdict is read
    off the rendering's own count, not derived a second way.
    """
    from vut.engine.compare.api import Configuration
    if compare_options is None: compare_options = Configuration()
    await deliver(compare_feeder.feed(compare_options,
                                      io.StringIO(subject_text),
                                      io.StringIO(nominal_text)),
                  adapter, subject_name)
    return adapter.bad_pair_n


async def reading_view(text, adapter, subject_name="reading",
                       compare_options=None, write=None):
    """
    RETURN: True,  the reading was displayed.
            False, the text's REGION FRAMING is broken and could not be
                   read; the reason is written, naming the line.

    Self-feeding makes every pair equivalent by construction, so the
    rendering shows pure interpretation: what was lexed as what, and
    which regions frame it. (The adapter should be a reading-marking
    one; this function does not police it.)

    THE ONE FAULT A CALLER MUST CATCH ('compare/api.py') IS CAUGHT
    HERE, for every road that shows a reading -- 'hwut.diff' and
    'hwut.play' alike. A text whose framing does not parse is a text
    this face cannot show, and saying so IS the answer; raised
    through, it reaches the person as a traceback, which tells them
    the framework broke when it was their text that could not be
    read. The VERDICT road states the same law in its own words
    ('consume/equivalence_check.py').
    """
    from vut.engine.compare.api import Configuration, RegionSyntaxError
    if write is None: write = print
    if compare_options is None: compare_options = Configuration()
    try:
        await deliver(compare_feeder.feed(compare_options,
                                          io.StringIO(text),
                                          io.StringIO(text)),
                      adapter, subject_name)
    except RegionSyntaxError as error:
        write("REFUSED: the region framing of this text is broken --")
        write("    %s" % error)
        write("Region framing ('##! <handler>', '####') is read in every")
        write("text. A text that CONTAINS such lines as content cannot")
        write("be shown under the reading until it can be switched off.")
        return False
    return True


def main(argv=None):
    """
    RETURN: int, the exit code -- 0 equivalent or reading displayed;
            1 differing; 141 the reader left early; 2 unusable request.

    THE PIPE IS THE DESIGN ('hwut.diff A B | head'), so a reader
    that leaves early is an ORDINARY ending, not a crash: the unix
    answer, quietly, with the shell's own SIGPIPE code.
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

    Two file words ask the comparison question; one file word without
    an '@hwut' block asks the reading question; anything else asks
    the STORE. The rendering goes to STDOUT -- it is the product.
    """
    if argv is None: argv = sys.argv[1:]
    try:
        wish, rest_list = parse_wish(list(argv))
    except WishError as error:
        sys.stderr.write("REFUSED: %s\n" % error)
        return E_ExitCode.REFUSED
    wish_said_f = rest_list != list(argv)

    parser = argparse.ArgumentParser(
        prog="hwut.diff",
        description="Display how two streams compare, how the store's "
                    "candidates compare to their nominals, or -- with "
                    "one file -- how compare READS a stream. Rendering "
                    "on stdout; exit 0 equivalent, 1 differing.")
    parser.add_argument("word", nargs="*",
                        help="SUBJECT NOMINAL (two files, '-' for stdin "
                             "once); FILE (its reading); or a test, a "
                             "test and a choice, and any wish word")
    parser.add_argument("--reading", action="store_true",
                        help="mark by tolerance kind (the reading view) "
                             "even in a two-stream comparison")
    parser.add_argument("--plain", action="store_true",
                        help="no colors, even on a tty")
    parser.add_argument("-y", "--side-by-side", action="store_true",
                        help="two columns: subject LEFT, nominal RIGHT")
    parser.add_argument("--width", type=int, default=None,
                        help="the two-column rendering's width "
                             "(default: the terminal's)")
    parser.add_argument("--directory", default=None,
                        help="store form: ONE test directory (default: "
                             "the tree below the cwd)")
    parser.add_argument("--all", action="store_true",
                        help="store form: every differing case, no "
                             "checklist")
    parser.add_argument("--yes", action="store_true",
                        help="store form: as '--all' (for scripts)")
    add_setup_arguments(parser)
    arguments = parser.parse_args(rest_list)
    setup     = setup_from_arguments(arguments)
    word_list = arguments.word

    adapter = TuiDisplay(out       = sys.stdout,
                         color_f   = False if arguments.plain else None,
                         merge_f   = False,
                         reading_f = arguments.reading,
                         side_by_side_f = arguments.side_by_side,
                         width     = arguments.width)

    if _file_form_f(word_list, wish_said_f, arguments.directory):
        if word_list.count("-") > 1:
            parser.error("only one of SUBJECT and NOMINAL may be '-': "
                         "stdin is one stream, not two")
        if len(word_list) == 1:
            adapter.reading_f = True
            shown_f = asyncio.run(
                reading_view(read_source(word_list[0]), adapter,
                             subject_name=word_list[0],
                             compare_options=setup,
                             write=lambda line: sys.stderr.write(line + "\n")))
            return E_ExitCode.OK if shown_f else E_ExitCode.FAULT
        bad_pair_n = asyncio.run(compare_view(
            read_source(word_list[0]), read_source(word_list[1]),
            adapter, subject_name=word_list[0], compare_options=setup))
        return E_ExitCode.OK if bad_pair_n == 0 else E_ExitCode.FAULT

    #  THE STORE FORM. The selection is the same block every
    #  store-reading face runs ('services/_cases.py'); the verdict per
    #  case is compare's, measured now.
    err = lambda text: sys.stderr.write(text + "\n")
    selected, code = select(wish, word_list,
                            arguments.directory or ".",
                            arguments.directory is not None, err, USAGE)
    if selected is None: return code
    if not selected.where_list:
        err("EMPTY: the wish selects no case")
        return E_ExitCode.EMPTY
    key_list, judged_n = differing_keys(selected, err)
    if not key_list:
        err("nothing differs: %d case(s) judged, every candidate "
            "equivalent to its nominal" % judged_n)
        return E_ExitCode.OK
    chosen = choose(key_list, err, sys.stdin.readline,
                    all_f=arguments.all, yes_f=arguments.yes)
    if not chosen:
        err("NOTE: nothing shown")
        return E_ExitCode.OK
    for key in chosen:
        options = key.setup if not _setup_said_f(arguments) else setup
        asyncio.run(compare_view(key.subject_text, key.nominal_text,
                                 adapter, subject_name=key.label,
                                 compare_options=options))
    return E_ExitCode.FAULT


USAGE = ("usage: hwut.diff SUBJECT NOMINAL | FILE | [<wish>] "
         "[<test> [<choice>]] [--directory D] [--all] [-y] [--width N] "
         "[--plain]")


def _file_form_f(word_list, wish_said_f, directory):
    """
    RETURN: True,  the words name FILES to compare or to read: two
                   existing files, or one existing file without an
                   '@hwut' block; no wish word, no '--directory'.
            False, the words are the store's.
    """
    import os
    if wish_said_f or directory is not None: return False
    if len(word_list) == 2:
        return all(w == "-" or os.path.isfile(w) for w in word_list)
    if len(word_list) == 1:
        word = word_list[0]
        if word == "-": return True
        if not os.path.isfile(word): return False
        from vut.engine.orchestrator.exploration.reader import read_header
        try:
            spec, _ = read_header(io.open(word, encoding="utf-8").read(),
                                  word)
        except (OSError, UnicodeDecodeError):
            return True
        return spec is None
    return False


def _setup_said_f(arguments):
    """RETURN: bool, True where a compare setup flag was given on the
    line -- it then overrides the choice's own setup in the store
    form."""
    return any(getattr(arguments, name, None) is not None
               for name in ("numeric", "pattern", "nothing"))


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ._exit import guarded
    sys.exit(guarded("hwut.diff", main))
