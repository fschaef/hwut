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
                                          terminal; '--all' skips it.
                                          One: straight to the view.
                                          None: EMPTY.

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
       artifact. WHERE A PERSON SITS AT A TERMINAL it opens the keyed
       SCREEN of 'hwut.accept.interactive' for looking only: the same
       panes and element colours, moving and searching, 'q' to go on
       (services E-79). '--console' -- and a pipe, or a machine without
       'prompt_toolkit', where one NOTE says so -- gives the TEXT
       display on STDOUT instead, where the rendering IS the product.
       Editing and accepting belong to 'hwut.accept.interactive'.

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
from   vut.services.lib.cmdline               import parse_or_refuse
from   vut.services.lib.viewers               import (driver_for,
                                                      E_DisplayTarget,
                                                      keyed_absent_reason,
                                                      fallback_note)
from   vut.engine.compare.api                 import feeder_ui as compare_feeder
from   ._core              import (read_source,
                                  add_setup_arguments,
                                  setup_from_arguments)
from   ._cases             import select, differing_keys
from   .lib.checklist      import Checklist
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
    await _viewed(adapter, subject_name, subject_text, nominal_text)
    return adapter.bad_pair_n


async def _viewed(adapter, subject_name, subject_text, nominal_text):
    """RETURN: None. Where the adapter is a SCREEN (the keyed view), it
               is opened now on what was delivered; a text display has
               already written everything."""
    view = getattr(adapter, "view", None)
    if view is not None: await view(subject_name, subject_text, nominal_text)


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
    await _viewed(adapter, subject_name, text, text)
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
        #  NO ABBREVIATION (E-81): '--forc' was measured to RUN as
        #  '--force'; a word not in the table is refused, and suggested.
        allow_abbrev=False,
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
    parser.add_argument("--console", action="store_true",
                        help="the text display on stdout, not the "
                             "screen")
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
    add_setup_arguments(parser)
    if "--yes" in rest_list:
        #  E-57: one word for 'do not ask'. Refused BY NAME so a script
        #  that still says it is told, not silently given the default.
        sys.stderr.write("REFUSED: '--yes' is gone (E-57) -- '--all' is "
                         "the one word for 'no checklist'\n")
        return E_ExitCode.REFUSED
    #  THE VOCABULARY IS THE PARSER'S (E-81): the refusal's suggestion
    #  and the completion table are read off it; 'ARG_DB' says what a
    #  value is.
    arguments, completion_f = parse_or_refuse(
        parser, rest_list, lambda t: sys.stderr.write(t + "\n"), ARG_DB)
    if completion_f:      return E_ExitCode.OK
    if arguments is None: return E_ExitCode.REFUSED
    setup     = setup_from_arguments(arguments)
    word_list = arguments.word

    adapter = display_for(arguments,
                          lambda text: sys.stderr.write(text + "\n"))

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
    #  THE SAME MENU AND THE SAME LOOP as 'hwut.accept.interactive'
    #  (E-67). Here 'handled' means VIEWED: the face that shows a case
    #  has done with it what this face does.
    checklist = Checklist(key_list, err, sys.stdin.readline,
                          label_of=lambda key: key.label,
                          all_f=arguments.all)
    shown_n = 0
    while True:
        key = checklist.pick()
        if key is None: break
        shown_n += 1
        options = key.setup if not _setup_said_f(arguments) else setup
        asyncio.run(compare_view(key.subject_text, key.nominal_text,
                                 adapter, subject_name=key.label,
                                 compare_options=options))
    if not shown_n:
        err("NOTE: nothing shown")
        return E_ExitCode.OK
    return E_ExitCode.FAULT


USAGE = ("usage: hwut.diff SUBJECT NOMINAL | FILE | [<wish>] "
         "[<test> [<choice>]] [--directory D] [--all] [--console] [-y] "
         "[--width N] [--plain]")


#  What a value IS (E-81): True, a path follows; a tuple, the words.
ARG_DB = {"--directory": True}


def display_for(arguments, err):
    """
    RETURN: DisplayAdapter, where the comparison is shown -- the keyed
            SCREEN, for looking only, where a person sits at a terminal;
            the TEXT display on stdout under '--console', or where the
            screen cannot run, which ONE note on 'err' then says
            (services E-79).
    """
    color_f = False if arguments.plain else None
    if not arguments.console:
        reason = keyed_absent_reason((sys.stdin, sys.stdout))
        if reason is None:
            return driver_for(E_DisplayTarget.KEYS, color_f=color_f,
                              view_only_f=True)
        err(fallback_note(reason))
    return TuiDisplay(out            = sys.stdout,
                      color_f        = color_f,
                      merge_f        = False,
                      reading_f      = arguments.reading,
                      side_by_side_f = arguments.side_by_side,
                      width          = arguments.width)


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
