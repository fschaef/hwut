"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
_______________________________________________________________________________

PURPOSE: Terminal - test glueing functionality.

CHOICES: 

AUTHOR: Frank-Rene Schaefer, 2022.
______________________________________________________________________________
"""
import sys

sys.path.insert(0, "../../../..")

from  vut.system.terminal.core      import ConsoleCanvas, LEFT, RIGHT, FIXED, GLUE

if "--hwut-info" in sys.argv:
    print("Terminal: Glueing;")
    print("CHOICES: none, all, mix;")
    # Call with 'GO' on command line to interact with a TUI
    sys.exit()

W = 6

console = ConsoleCanvas()
console.width = W

def print_fe_list(name, fe_list):
    print("%s: (total width: %i)" % (name, sum(fe.width for fe in fe_list)))
    for fe in fe_list:
        print("   width: %s; string: '%s'; alignment: %s; color: %s; toff: %s;" \
              % (fe.width, fe.string, fe.alignment.name, fe.color_code, fe.text_offset))

count = 0
def test(input):
    ++count
    print("(%i)-----------------------" % count)
    print_fe_list("input", input)
    result  = console.fix_glue(input)
    print_fe_list("result", result)

if "none" in sys.argv:
    test([FIXED(" "*(W>>1)), GLUE("*"),    FIXED(" "*(W>>1)) ])
    test([FIXED(" "*W),      GLUE("*")                       ])
    test([                   GLUE("*"),    FIXED(" "*W)      ])
    test([GLUE("<"),         FIXED(" "*W), GLUE(">")         ])
    many = []
    for i in range(W):
        many.append(FIXED(" "))
        many.append(GLUE("*"))
    test(many)

if "all" in sys.argv:
    test([FIXED(""), GLUE("*"), FIXED("")])
    test([FIXED(""), GLUE("*")           ])
    test([           GLUE("*"), FIXED("")])
    test([GLUE("<"), FIXED(""), GLUE(">")])
    many = []
    for i in range(W):
        many.append(FIXED(""))
        many.append(GLUE("*"))
    test(many)

if "mix" in sys.argv:
    test([FIXED("b"), GLUE("*"), FIXED("a")])
    test([FIXED("b"), GLUE("*")           ])
    test([           GLUE("*"), FIXED("a")])
    test([GLUE("<"), FIXED("c"), GLUE(">")])
    many = []
    for i in range(W>>1):
        many.append(FIXED(" "))
        many.append(GLUE("*"))
    test(many)

