"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
_______________________________________________________________________________

PURPOSE: Difftool command line

______________________________________________________________________________
"""
import sys

sys.path.insert(0, "../../../../..")

from   vut.user_interface.difference_display.console.TEST.cases import *
if "--hwut-info" in sys.argv:
    print("Display Scenariosr;")
    print("CHOICES: PLAIN, ERRORS_AND_TOLERATED, ERRORS, ANALOGIES, ANALOGIES_ERRORS_ONLY, ANALOGIES_DEFINITIONS_ONLY;")
    # Call with 'GO' on command line to interact with a TUI
    sys.exit()

config = Configuration()
config.pattern_finder.numeric_tolerance_ratio      = 0.01
config.pattern_finder.equivalent_pattern_list      = ["rot|orange", "Röslein|Tülplein"]
config.pattern_finder.visible_nothing_pattern_list = [", hm,", ", wtf,", "\(who cares\)"]

subject_txt = """eins
orange
gleich
gleicher
gleichest
absolut gleich
auch gleich
((frieda))
((frieda))
((berta))
"""

nominal_txt = """zwei
rot
gleich
gleicher
gleichest
absolut gleich
auch gleich
((heinz))
((albert))
((albert))
"""

choice = sys.argv[1]

mode = {
    "PLAIN":                      E_LinePairSelectionMode.PLAIN                                     ,
    "ERRORS_AND_TOLERATED":       E_LinePairSelectionMode.ERRORS_AND_TOLERATED,
    "ERRORS":                     E_LinePairSelectionMode.ERRORS,
    "ANALOGIES":                  E_LinePairSelectionMode.ANALOGIES,
    "ANALOGIES_ERRORS_ONLY":      E_LinePairSelectionMode.ANALOGIES_ERRORS_ONLY,
    "ANALOGIES_DEFINITIONS_ONLY": E_LinePairSelectionMode.ANALOGIES_DEFINITIONS_ONLY
}[choice]

print("(*) verbosity level 0")
test(subject_txt, nominal_txt, mode=mode, both=False, level=0)

print("(*) verbosity level 1")
test(subject_txt, nominal_txt, mode=mode, both=False, level=1)

print("(*) verbosity level 2")
test(subject_txt, nominal_txt, mode=mode, both=False, level=2)

