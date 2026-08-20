"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE COMPARE SERVICE -- 'hwut.compare': display the comparison,
       or display the READING of one stream.

DESCRIPTION
       THE SIBLING OF 'hwut.merge' (merge.py), deliberately homogeneous:
       the same TUI renderer, the same rows, marks, notes and banner --
       an author moves between the two without relearning the picture.
       What differs is the QUESTION asked:

           hwut.compare SUBJECT NOMINAL    how do these two streams
                                           compare? (the VERDICT view:
                                           marks say what DID differ)

           hwut.compare FILE               how does compare READ this
                                           stream? (the READING view:
                                           marks say what CAN vary --
                                           '{numeric}', '~analogy~',
                                           '<pattern>', '!binding!',
                                           '|nothing|')

       THE READING IS THE INTERPRETATION MADE VISIBLE: which elements
       the reading (compare's 'reading/') lexed as numerics, analogies,
       patterns, bindings, visible nothings, and which regions frame
       them. It is produced by feeding the stream against ITSELF --
       every pair equivalent BY CONSTRUCTION, so nothing but the
       interpretation shows. No second feeder, no second door: the one
       association serves both questions.

       DISPLAY ONLY. This service never merges and never writes an
       artifact -- the rendering IS the product, so it goes to STDOUT
       (unlike merge.py, whose stdout carries the artifact). Editing
       belongs to 'hwut.merge'.

       EXIT CODES (the diff convention):
                    0 equivalent -- no differing pair (or: a reading
                      was displayed);
                    1 at least one differing pair;
                    2 the request itself was unusable.
______________________________________________________________________________
"""
import io
import sys
import asyncio
import argparse

#  THE IMPORT CALL -- see merge.py: __config.py (this directory) does the
#  walk-up; the face adopts its package (PEP 366). Dead under '-m'.
if __package__ in (None, ""):
    import _config
    __package__ = _config.PACKAGE
from ._exit import E_ExitCode  # delayed past _config adoption

from   vut.engine.operations.interaction.feed import feed_down
from   vut.engine.operations.interaction.tui  import TuiDisplay
from   ._core              import (read_source,
                                  add_setup_arguments,
                                  setup_from_arguments)


async def compare_view(subject_text, nominal_text, adapter,
                       subject_name="compare", compare_options=None):
    """
    RETURN: int, the count of DIFFERING pairs the display carried --
            0 is equivalence, by the Lawyer/Judge agreement law.

    One DOWN generation through the display door ('feed_down'); the
    adapter renders it. The verdict is read off the rendering's own
    count, not derived a second way.
    """
    from ...compare.configuration import Configuration
    if compare_options is None: compare_options = Configuration()
    await feed_down(compare_options,
                    io.StringIO(subject_text), io.StringIO(nominal_text),
                    adapter, subject_name)
    return adapter.bad_pair_n


async def reading_view(text, adapter, subject_name="reading",
                       compare_options=None):
    """
    RETURN: None. Displays the READING of 'text': the stream fed
            against ITSELF, marks by tolerance kind.

    Self-feeding makes every pair equivalent by construction, so the
    rendering shows pure interpretation: what was lexed as what, and
    which regions frame it. (The adapter should be a reading-marking
    one; this function does not police it.)
    """
    from ...compare.configuration import Configuration
    if compare_options is None: compare_options = Configuration()
    await feed_down(compare_options,
                    io.StringIO(text), io.StringIO(text),
                    adapter, subject_name)


def main(argv=None):
    """
    RETURN: int, the exit code -- 0 equivalent or reading displayed;
            1 differing; 141 the reader left early; 2 unusable request.

    THE PIPE IS THE DESIGN ('hwut.compare A B | head'), so a reader
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

    Two positionals ask the comparison question; one positional asks
    the reading question. The rendering goes to STDOUT -- it is the
    product.
    """
    parser = argparse.ArgumentParser(
        prog="hwut.compare",
        description="Display how two streams compare -- or, with one "
                    "argument, how compare READS a stream. Rendering on "
                    "stdout; exit 0 equivalent, 1 differing.")
    parser.add_argument("subject",
                        help="the subject stream: a file path, or '-' "
                             "for stdin")
    parser.add_argument("nominal", nargs="?", default=None,
                        help="the nominal stream: a file path, or '-' "
                             "for stdin; ABSENT = display the READING "
                             "of SUBJECT instead of a comparison")
    parser.add_argument("--reading", action="store_true",
                        help="mark by tolerance kind (the reading view) "
                             "even in a two-stream comparison")
    parser.add_argument("--plain", action="store_true",
                        help="no colors, even on a tty")
    add_setup_arguments(parser)
    arguments = parser.parse_args(argv)
    setup     = setup_from_arguments(arguments)

    if arguments.subject == "-" and arguments.nominal == "-":
        parser.error("only one of SUBJECT and NOMINAL may be '-': stdin "
                     "is one stream, not two")

    reading_f = arguments.reading or arguments.nominal is None
    adapter   = TuiDisplay(out       = sys.stdout,
                           color_f   = False if arguments.plain else None,
                           merge_f   = False,
                           reading_f = reading_f)

    if arguments.nominal is None:
        asyncio.run(reading_view(read_source(arguments.subject), adapter,
                                 subject_name=arguments.subject,
                                 compare_options=setup))
        return E_ExitCode.OK

    bad_pair_n = asyncio.run(compare_view(
        read_source(arguments.subject), read_source(arguments.nominal),
        adapter, subject_name=arguments.subject, compare_options=setup))
    return E_ExitCode.OK if bad_pair_n == 0 else E_ExitCode.FAULT


if __name__ == "__main__":
    sys.exit(main())
