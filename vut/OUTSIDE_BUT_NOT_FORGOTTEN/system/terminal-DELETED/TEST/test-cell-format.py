#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
_______________________________________________________________________________

PURPOSE: Terminal - test formatting

CHOICES: padding-plain, padding-color, prune-plain, prune-color;

Text comes in two types: plain strings and tuples of (color, string). 
For both types functions exist for padding, pruning.  

AUTHOR: Frank-Rene Schaefer, 2022.
______________________________________________________________________________
"""
import sys

sys.path.insert(0, "../../../..")

from   vut.system.terminal.TEST.data   import LEFT, RIGHT, FIXED
from   vut.system.terminal.styled_text import RESET_ALL, E_Alignment, CellFormat, ColorTextList, ColorText
from   vut.external.colorama           import Fore, Back
import vut.system.terminal.plain_text  as plain_text

## alignment_list = [E_Alignment.LEFT, E_Alignment.RIGHT, E_Alignment.CENTER]
alignment_list = [E_Alignment.LEFT, E_Alignment.RIGHT]

if "--hwut-info" in sys.argv:
    print("Terminal: Formatting;")
    print("CHOICES: padding-plain, padding-color, prune-plain, prune-color;")
    # Call with 'GO' on command line to interact with a TUI
    sys.exit()

def iterable_plain():
    for width in range(5):
        for alignment in alignment_list:
            for text in ["", "a", "ab", "abc", "abcd"]:
                cf = CellFormat(
                    width       = width,
                    alignment   = alignment,
                    color_code  = "",
                    text_offset = 0,
                )
                yield cf, text

if "padding-plain" in sys.argv:
    for cf, text in iterable_plain():
        result = plain_text.render(cf, text)
        assert len(result) == cf.width
        print(f":{result}: (w={cf.width}, a={cf.alignment.name})")


def iterable_color():
    for width in range(5):
        for alignment in alignment_list:
            for ct in [
                ColorText(Fore.RED, "a"),
                ColorText(Fore.GREEN, "ab"),
                ColorText(Fore.YELLOW, "abc"),
            ]:
                cf = CellFormat(
                    width       = width,
                    alignment   = alignment,
                    color_code  = Back.WHITE,
                    text_offset = 0,
                )
                yield cf, ColorTextList([ct])

if "padding-color" in sys.argv:
    for cf, ctl in iterable_color():
        formatted = ctl.format(cf)
        text = formatted.render(cf.color_code)
        print(f":{text}{RESET_ALL}: (w={cf.width}, a={cf.alignment.name})")

if "prune-plain" in sys.argv:
    for cf, text in iterable_plain():
        total_length = len(text)
        result = plain_text.prune(total_length, cf.width, cf.alignment, text)
        assert len(result) <= cf.width
        print("    :%s: (w: %s; a: %s; c: %s)"
			  % (result, cf.width, cf.alignment.name, total_length))

if "prune-color" in sys.argv:
    for cf, color_text_list in iterable_color():
        total_length  = len(color_text_list)
        result        = color_text_list.prune(total_length, cf.width, cf.alignment)
        result_length = len(result)

        assert result_length <= cf.width, (
            f"{result_length} <= {cf.width} asserted: result={list(result)}"
        )

        text = result.render(cf.color_code)
        print(
            "    :%s%s: (w: %s; a: %s; t: %s;)"
            % (text, RESET_ALL, cf.width, cf.alignment.name, total_length)
        )

if "fixed" in sys.argv:
    for cell in [FIXED("", "By"), FIXED("a", "By"), FIXED("ab", "By")]:
        print(cell.render())
