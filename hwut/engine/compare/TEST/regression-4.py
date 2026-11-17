#! /usr/bin/env python3
#  @hwut {
#    title   = "Region framing lines are paired"
#    choices = ["potpourri", "verbatim", "outer"]
#  }
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: A REGION'S FRAMING LINES ('##! <handler>' and '####') ARE LINES OF
         BOTH STREAMS AND MUST BE PAIRED like any other line.

DEFECT (found 2026-11-16, hwut 4e03ee5). For a subject IDENTICAL to its
nominal, 'associate()' yields a LinePair only for the region's CONTENT:

        ##! potpourri          <- no LinePair
        x                      <- LinePair (2, 2)
        ####                   <- no LinePair

The text display does not notice, since it prints the region's header
instead of the framing lines. The keyed screen ('hwut.diff' on a terminal)
builds its pairing from the LinePairs alone; it shows both framing lines as
lines without a partner and says '2 differ' for two equal files.

EXPECTED. Every line of both streams appears in exactly one LinePair; for
equal streams, the pairs are (1,1) (2,2) (3,3), all without a difference.

'outer' is the control: the same three lines without a frame.
______________________________________________________________________________
"""
import io
import sys
import asyncio

import config
from hwut.engine.compare.configuration import Configuration
import hwut.engine.compare.main as main

TEXT_DB = {
    "potpourri": "##! potpourri\nx\n####\n",
    "verbatim":  "##! verbatim\nx\n####\n",
    "outer":     "a\nx\nb\n",
}


async def pair_list_of(text):
    """RETURN: list of (int, int), the (subject, nominal) line numbers of
               every LinePair that 'associate()' yields when 'text' is
               compared with itself; -1 stands for 'no partner'
    """
    pair_list = []
    async for chunk in main.associate(Configuration(), io.StringIO(text),
                                      io.StringIO(text)):
        for line_pair in chunk:
            pair_list.append((line_pair.subject_line_n,
                              line_pair.nominal_line_n))
    return pair_list


def main_function(choice):
    """RETURN: None. Prints the input, then every pair, then the lines of
               either stream that no pair mentions.
    """
    text      = TEXT_DB[choice]
    line_n    = len(text.splitlines())
    pair_list = asyncio.run(pair_list_of(text))

    print("input (subject == nominal):")
    for i, line in enumerate(text.splitlines(), start=1):
        print("    %i: %s" % (i, line))
    print("pairs (subject, nominal):")
    for line_n_s, line_n_n in pair_list:
        print("    (%i, %i)" % (line_n_s, line_n_n))
    unpaired_s = [i for i in range(1, line_n + 1)
                  if i not in {s for s, _ in pair_list}]
    unpaired_n = [i for i in range(1, line_n + 1)
                  if i not in {n for _, n in pair_list}]
    print("subject lines in no pair: %s" % (unpaired_s or "none"))
    print("nominal lines in no pair: %s" % (unpaired_n or "none"))
    print("<hwut-end>")


if __name__ == "__main__":
    main_function(sys.argv[1])
