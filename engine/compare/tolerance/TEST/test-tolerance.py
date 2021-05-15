#! /usr/bin/env python3
#
# PURPOSE: 'PatternFinder' -- Handling of a set of tolerance concepts.
#
# A tolerance pattern_finder holds information about tolerance concepts and 
# their pattern. It finds patterns in an existing string. With 
#
#              PatternFinder.do(string)
#
# a 'string' can be transformed into a sequence of 'LineElement' objects. Each
# LineElement object relates to a type of tolerance.
#
# Tests: -- finding the first pattern that matches starting from a given
#           position in the string.
#        -- setup the tolerance table in the PatterFinder according to 
#           configuration settings.
#        -- sample runs of 'do', i.e. the complete pattern finding process.
#
# SPDX-Linces: MIT; (C) Frank-Rene Schaefer.
#______________________________________________________________________________
 
import sys
import os
import re

sys.path.insert(0, "../../../../../")

import hwut.engine.compare.engine.core               as     comperator
from   hwut.engine.compare.tolerance.pattern_finder import PatternFinder, _find_first_match
from   hwut.engine.compare.tolerance.match          import E_ToleranceId


if "--hwut-info" in sys.argv:
    print("Tolerance PatternFinder;")
    print("CHOICES: setup, find_first_match, tolerance_id, do;")
    sys.exit()


def empty_config():
    config = comperator.Configuration()
    config.analogy_f               = False
    config.whitespace_f            = False
    config.backslash_f             = False
    config.numeric_tolerance_ratio = 0
    config.equivalent_pattern_list      = []
    return config

def show(pattern_finder):
    print()
    print("size: %i;" % len(pattern_finder.table))
    for tolerance in pattern_finder.table:
        if tolerance.pattern is None: pattern = "None"
        else:                         pattern = tolerance.pattern.pattern
        print("%s -> %s" % (pattern, tolerance.id.name))

if "setup" in sys.argv:
    # Test whether the setting of configuration flags
    # triggers the correct tolerance setup.

    show(PatternFinder(empty_config()))

    config = empty_config()
    config.analogy_f = True
    show(PatternFinder(config))
    
    config = empty_config()
    config.whitespace_f = True
    show(PatternFinder(config))

    config = empty_config()
    config.backslash_f = True
    show(PatternFinder(config))

    config = empty_config()
    config.numeric_tolerance_ratio = True
    show(PatternFinder(config))

    config = empty_config()
    config.equivalent_pattern_list = [ "hallo", "welt" ]
    show(PatternFinder(config))

    config = empty_config()
    config.visible_nothing_pattern_list = [ "nothing", "error" ]
    show(PatternFinder(config))

if "find_first_match" in sys.argv:
    config = empty_config()
    config.equivalent_pattern_list = [ r"hallo", r"welt", r"hallodrio", "happy|funny", "happy|glad", "[0-9]+", "happ" ]
    config.numeric_tolerance_ratio = 0.1
    pattern_finder = PatternFinder(config)
    show(pattern_finder)

    def test(string, i):
        useless = set()
        token             = _find_first_match(pattern_finder.table, string, i, useless)
        tolerance_id      = token.tolerance_id
        pattern_index_set = token.pattern_i_set
        span              = (token.start, token.end)
        if tolerance_id is None:
            print("string: '%s' at %i" % (string, i) + " -> None; useless %s" % useless)
        elif tolerance_id == E_ToleranceId.EQUIVALENCE_PATTERN:
            print("string: '%s' at %i" % (string, i) + " -> %s %s; %s; useless %s" % (tolerance_id.name, sorted(pattern_index_set), span, useless))
        else:
            print("string: '%s' at %i" % (string, i) + " -> %s; %s; useless %s" % (tolerance_id.name, span, useless))

    for text in "hallo", "welti":
        test("%s  " % text, 0)
        test(" %s " % text, 0)
        test("  %s" % text, 0)
        test("%s  " % text, 1)
        test(" %s " % text, 1)
        test("  %s" % text, 1)
        test("%s  " % text, 2)
        test(" %s " % text, 2)
        test("  %s" % text, 2)

    test(" happy", 0)
    test(" hallodrio", 0)
    test("   4711", 0)

if "tolerance_id" in sys.argv:
    config                         = empty_config()
    config.analogy_f               = True
    config.numeric_tolerance_ratio = 0.1
    config.equivalent_pattern_list = ["otto", "fritz"]
    pattern_finder                          = PatternFinder(config)
    show(pattern_finder)
    print()
    print("Map:")
    for i, tolerance in enumerate(pattern_finder.table):
        if tolerance.id == E_ToleranceId.EQUIVALENCE_PATTERN:
            print("  [%i] %s %s" % (i, tolerance.id, tolerance.pattern_index))
        else:
            print("  [%i] %s" % (i, tolerance.id))

if "do" in sys.argv:
    config                              = empty_config()
    config.analogy_f                    = True
    config.numeric_tolerance_ratio      = 1.0
    config.whitespace_f                 = True
    config.equivalent_pattern_list      = [ "hallo" ]
    config.visible_nothing_pattern_list = [ "nothing" ]
    pattern_finder                      = PatternFinder(config)
    show(pattern_finder)

    def test(string):
        print("string: '%s'" % string)
        for match in pattern_finder.do(string):
            print("   %s" % match)

    test("hallo welt 4711")
    test("4711 hallo 4711 nothing")
    test("bonjour ((4711)) le monde")

