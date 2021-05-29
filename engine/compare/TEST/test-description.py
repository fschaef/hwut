#! /usr/bin/env python3
"""SPDX-Linces: MIT; Project UT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Testing the description member.

DESCRIPTION:

Objects which are communicated to the outside, provide a '.description()'
function. This is a data structure, which can be pretty printed by the
'description.format()' function.  The receiver of an object through an API,
shall be able to reflect on the objects contents conveniently. 

The entry point for '.description()' is: 

              LineAssociationChunk.description()
______________________________________________________________________________
"""
import sys

sys.path.insert(0, "../../../../")

import ut.engine.pretty              as     pretty
import ut.engine.compare.engine.core as     comperator
import ut.engine.compare.main        as     main
from   ut.engine.compare.TEST.common import print_list_sequence_pairs, \
                                            print_friends_pairing_max_result
from   io import StringIO



if "--hwut-info" in sys.argv:
    print("LineAssociationChunk.description()")
    sys.exit()

config = comperator.Configuration()
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
    line_association_chunk_list = list(main.line_associations(config, subject, nominal))
    for chunk in line_association_chunk_list:
        print(pretty.do(chunk))
    print()


# Test wether a failed analogy does not clear the analogies of 'good' lines.
test([
     ["((A)) is good.",             "((1)) is good."],
     ["((A)) is bad.",              "((2)) is not so good."],
     ["4711 ((is)) ((a)) number.",  "4712 ((ist)) ((eine)) Zahl."],
])


