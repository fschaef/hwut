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

from  vut.system.terminal.TEST.data import LEFT,  \
                                           RIGHT, \
                                           FIXED, \
                                           CellFormat
from  vut.external.colorama         import init as colorama_init, Fore, Back, Style
from  vut.system.terminal.styled_text import RESET_ALL, E_Alignment, ColorTextList, ColorText
from  vut.system.terminal.cell      import _plain_text_padding,      \
                                           _plain_text_prune

## alignment_list = [E_Alignment.LEFT, E_Alignment.RIGHT, E_Alignment.CENTER]
alignment_list = [E_Alignment.LEFT, E_Alignment.RIGHT]

if "--hwut-info" in sys.argv:
    print("Terminal: Formatting;")
    print("CHOICES: padding-plain, padding-color, prune-plain, prune-color;")
    # Call with 'GO' on command line to interact with a TUI
    sys.exit()

def iterable_plain():
    for width in [0, 1, 2, 3, 4]:
        for content in ["", "a", "ab"]:
            for alignment in alignment_list:
                if width < len(content): continue
                cf = CellFormat(alignment, None, width, content, 0)
                yield cf, content, len(content)

def iterable_color():
    for width in [0, 1, 2, 3, 4]:
        for content in [ColorText(Fore.BLACK, ""), ColorText(Fore.RED, "a"), ColorText(Fore.GREEN, "ab")]:
            for alignment in alignment_list:
                if width < len(content.text): continue
                cf = CellFormat(alignment, Back.WHITE, width, content, 0)
                yield cf, content, len(content.text)

if "padding-plain" in sys.argv:
    for fe, content, total_length in iterable_plain():
        result = _plain_text_padding(fe, total_length, content)
        assert len(result) == fe.width
        print("    :%s: (w: %s; a: %s; t: %s; c: %s)" % (result, fe.width, fe.alignment.name, 
                                                         total_length, len(content)))

if "padding-color" in sys.argv:
    for fe, ct, total_length in iterable_color():
        result = ColorTextList([ct]).padding(fe, total_length)
        assert sum(len(ct.text) for ct in result) == fe.width
        text   = result.render(fe.color_code)
        print("    :%s%s: (w: %s; a: %s; t: %s; c: %s)" % (text, RESET_ALL, fe.width, fe.alignment.name, 
                                                           total_length, len(ct.text)))
def iterable_plain():
    for width in range(5):
        for alignment in alignment_list:
            for text in ["", "a", "ab", "abc", "abcd", "abcde"]:
                yield width, alignment, text

def iterable_color():
    for width in range(5):
        for alignment in alignment_list:
            for content in [ColorText(Fore.BLACK, ""), ColorText(Fore.RED, "a"), ColorText(Fore.GREEN, "ab"), ColorText(Fore.YELLOW, "abc")]:
                yield width, alignment, ColorTextList([content])

if "prune-plain" in sys.argv:
    for width, alignment, text in iterable_plain():
        total_length = len(text)
        result       = _plain_text_prune(total_length, width, alignment, text)
        assert len(result) <= width
        print("    :%s: (w: %s; a: %s; c: %s)" % (result, width, alignment.name, total_length))

if "prune-color" in sys.argv:
    for width, alignment, color_text_list in iterable_color():
        total_length  = sum(len(ct.text) for ct in color_text_list)
        result        = color_text_list.prune(total_length, width, alignment)
        result_length = sum(len(ct.text) for ct in result)

        ## assert result_length <= width, "%s <= %s asserted: result: [%s]" % (result_length, width, list(result))
        fe   = CellFormat(alignment, Back.WHITE, width, color_text_list, 0)
        text = result.render(fe.color_code)
        print("    :%s%s: (w: %s; a: %s; t: %s;)" % (text, RESET_ALL, width, alignment.name, 
                                                     total_length))



