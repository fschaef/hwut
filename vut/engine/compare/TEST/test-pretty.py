#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Testing the .__pretty__() - print member function.

DESCRIPTION:

Testing pretty printing of 'ChunkPair', which is the only
object communicated through the main API.
                                                   
The receiver of an object through the main API, shall be able to reflect on the
objects contents conveniently. Thus, all objects communicated through the main
API shall provide a pretty print functionality through a member function:

            def __pretty__(self):
                ...

An object providing this operator can be transformed into a nice-looking
string by means of 

            vut.engine.pretty.do(object)

The requirements on the return value of '__pretty__()' are described in the
aforementioned module.
______________________________________________________________________________
"""
import sys
from   io import StringIO
sys.path.insert(0, "../../../../")

import vut.engine.pretty                as     pretty
from   vut.engine.compare.configuration import Configuration
import vut.engine.compare.main          as     main


if "--hwut-info" in sys.argv:
    print("ChunkPair.description()")
    sys.exit()

config = Configuration()
config.pattern_finder.analogy_f               = True
config.pattern_finder.whitespace_f            = True
config.pattern_finder.backslash_f             = False
config.pattern_finder.numeric_tolerance_ratio = 0.1
config.pattern_finder.equivalent_pattern_list = ["number|Zahl"]

def test(table):
    subject_line_list = [ x for x, y in table ]
    nominal_line_list = [ y for x, y in table ]
    subject = StringIO("\n".join(subject_line_list))
    nominal = StringIO("\n".join(nominal_line_list))
    print()
    print("=> ")
    print()
    line_association_chunk_list = list(main.associate(config, subject, nominal))
    for chunk in line_association_chunk_list:
        print(pretty.do(chunk))
    print()


# Test wether a failed analogy does not clear the analogies of 'good' lines.
test([
     ["((A)) is good.",             "((1)) is good."],
     ["((A)) is bad.",              "((2)) is not so good."],
     ["4711 ((is)) ((a)) number.",  "4712 ((ist)) ((eine)) Zahl."],
])


