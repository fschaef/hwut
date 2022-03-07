"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
_______________________________________________________________________________

PURPOSE: Termina - test formatting

______________________________________________________________________________
"""
import sys

sys.path.insert(0, "../../../..")

from  vut.system.terminal.TEST.data import *
from  vut.system.terminal.core      import _color_reset_all
from  vut.system.terminal.cell      import _plain_text_padding, \
                                           _plain_text_prune, \
                                           _color_text_list_padding, \
                                           _color_text_list_prune, \
                                           _color_text_list_apply, \
                                           E_Alignment

if "--hwut-info" in sys.argv:
    print("Terminal: Formatting;")
    print("CHOICES: padding-plain, padding-color, prune-plain, prune-color;")
    # Call with 'GO' on command line to interact with a TUI
    sys.exit()

def iterable_plain():
    for width in [0, 1, 2, 3, 4]:
        for content in ["", "a", "ab"]:
            for alignment in [E_Alignment.LEFT, E_Alignment.RIGHT, E_Alignment.CENTER]:
                if width < len(content): continue
                cf = CellFormat(alignment, None, width, content, 0)
                yield cf, content, len(content)

def iterable_color():
    for width in [0, 1, 2, 3, 4]:
        for content in [(Fore.BLACK, ""), (Fore.RED, "a"), (Fore.GREEN, "ab")]:
            for alignment in [E_Alignment.LEFT, E_Alignment.RIGHT, E_Alignment.CENTER]:
                if width < len(content[1]): continue
                cf = CellFormat(alignment, Back.WHITE, width, content, 0)
                yield cf, content, len(content[1])

if "padding-plain" in sys.argv:
    for fe, content, total_length in iterable_plain():
        result = _plain_text_padding(fe, total_length, content)
        assert len(result) == fe.width
        print("    :%s: (w: %s; a: %s; t: %s; c: %s)" % (result, fe.width, fe.alignment.name, 
                                                         total_length, len(content)))

if "padding-color" in sys.argv:
    for fe, content, total_length in iterable_color():
        result = _color_text_list_padding(fe, total_length, [content])
        assert sum(len(txt) for color, txt in result) == fe.width
        text   = _color_text_list_apply(fe, result)
        print("    :%s%s: (w: %s; a: %s; t: %s; c: %s)" % (text, _color_reset_all, fe.width, fe.alignment.name, 
                                                           total_length, len(content)))
def iterable_plain():
    for width in range(5):
        for alignment in [E_Alignment.LEFT, E_Alignment.RIGHT, E_Alignment.CENTER]:
            for text in ["", "a", "ab", "abc", "abcd", "abcde"]:
                yield width, alignment, text

def iterable_color():
    for width in range(5):
        for alignment in [E_Alignment.LEFT, E_Alignment.RIGHT, E_Alignment.CENTER]:
            for content in [(Fore.BLACK, ""), (Fore.RED, "a"), (Fore.GREEN, "ab"), (Fore.YELLOW, "abc")]:
                yield width, alignment, [content]

if "prune-plain" in sys.argv:
    for width, alignment, text in iterable_plain():
        total_length = len(text)
        result       = _plain_text_prune(total_length, width, alignment, text)
        assert len(result) <= width
        print("    :%s: (w: %s; a: %s; c: %s)" % (result, width, alignment.name, total_length))


if "prune-color" in sys.argv:
    for width, alignment, color_text_list in iterable_color():
        total_length  = sum(len(txt) for c, txt in color_text_list)
        result        = _color_text_list_prune(total_length, width, alignment, color_text_list)
        result_length = sum(len(txt) for c, txt in result)

        assert result_length <= width, "%s <= %s asserted: result: [%s]" % (result_length, width, list(result))
        fe   = CellFormat(alignment, Back.WHITE, width, color_text_list, 0)
        text = _color_text_list_apply(fe, result)
        print("    :%s%s: (w: %s; a: %s; t: %s;)" % (text, _color_reset_all, width, alignment.name, 
                                                     total_length))



