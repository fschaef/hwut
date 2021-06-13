"""SPDX-Linces: MIT; Project VUT; (C) Frank-Rene Schaefer
_______________________________________________________________________________

PURPOSE: Difftool command line

______________________________________________________________________________
"""
import sys

sys.path.insert(0, "../../../../..")

import vut.engine.compare.main                            as     compare
from   vut.engine.compare.configuration                   import Configuration
import vut.user_interface.difference_display.console.main as     console
import vut.system.terminal                                as     terminal

from   io import StringIO

config = Configuration()
config.pattern_finder.numeric_tolerance_ratio = 0.01
config.pattern_finder.equivalent_pattern_list = ["hanna|bertha", "martha|annie"]

def test(subject_txt, nominal_txt):
    global config
    subject = StringIO(subject_txt)
    nominal = StringIO(nominal_txt)

    terminal.set_size_fixed(10, 80)
    print("------------------------------------------------------------------------")
    console.display(compare.line_associations(config, subject, nominal))


if True:
    test(".123456789.123456789.123456789.123456789\n",
         ".123456789\n"
         "Nasselsenes\n")

    test(".123456789.123456789.123456789.123456789\n"
         "((1)) 4711 hanna martha\n"
         "Bonjour le monde",
         ".123456789.123456789.123456789.123456789\n"
         "((2)) 4712 bertha annie\n"
         "Nasselsenes\n"
         "Bonjour le monde")
    test("||||\n"
         "Ach was muß man oft von bösen\n"
         "Kindern hören oder lesen\n"
         "Wie zum Beispiel hier von diesen\n"
         "Welche Max und Moritz hießen\n"
         "||||\n",
         "||||\n"
         "Kindern hören oder lesen\n"
         "Ach was muß man oft von bösen\n"
         "Welche Max und Moritz hießen\n"
         "Wie zum Beispiel hier von diesen\n"
         "||||\n")

