#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
____________________________________________________________________________

PURPOSE:  PatternFinder -- identfiying tolerance pattern in text lines.

CHOICES:  setup, tolerance_id, do;

The 'PatternFinder' searches patterns in a line of text and produces 
'LineElement'-s. Each line element corresponds to an identified pattern
and the *lexeme* that is matching.

                 PatternFinder.do(string)


setup: 

   setup the tolerance table in the PatterFinder according to configuration
   settings.

tolerance_id:

   verify that each pattern is associated with the correct tolerance_id.

do:
    sample runs of 'PatterFinder.do()', i.e. running the complete pattern 
    finding process.
______________________________________________________________________________
"""
import sys

sys.path.insert(0, "../../../../../")

from   vut.engine.compare.configuration            import ConfigurationPatternFinder
from   vut.engine.compare.tolerance.pattern_finder import PatternFinder
from   vut.engine.compare.tolerance.line_element   import E_ToleranceId


if "--hwut-info" in sys.argv:
    print("Tolerance PatternFinder;")
    print("CHOICES: setup, tolerance_id, do;")
    sys.exit()


def empty_config():
    config = ConfigurationPatternFinder()
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

if "tolerance_id" in sys.argv:
    config                         = empty_config()
    config.analogy_f               = True
    config.numeric_tolerance_ratio = 0.1
    config.equivalent_pattern_list = ["otto", "fritz"]
    pattern_finder                 = PatternFinder(config)
    show(pattern_finder)
    print()
    print("Map:")
    for i, tolerance in enumerate(pattern_finder.table):
        if tolerance.id == E_ToleranceId.EQUIVALENCE_PATTERN:
            print("  [%i] %s %s" % (i, tolerance.id.name, tolerance.pattern_index))
        else:
            print("  [%i] %s" % (i, tolerance.id.name))

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

