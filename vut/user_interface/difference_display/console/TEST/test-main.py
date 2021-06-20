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
import vut.system.terminal_size                           as     terminal_size

from   io import StringIO

config = Configuration()
config.pattern_finder.numeric_tolerance_ratio = 0.01
config.pattern_finder.equivalent_pattern_list = ["hanna|bertha", "martha|annie"]

def test(subject_txt, nominal_txt):
    global config
    subject = StringIO(subject_txt)
    nominal = StringIO(nominal_txt)

    terminal_size.set_size_fixed(10, 100)
    print("------------------------------------------------------------------------")
    console.display(compare.line_associations(config, subject, nominal))


if False:
    test(".123456789.123456789.123456789.123456789\n",
         ".123456789\n")

test("Sah   ein Röslein 4711 Knab stehen\n"
     "Heiden auf der blühenden Röslein\n",
     "Sah ein   Knab 4712 schönes Röslein stehen\n"
     "Röslein auf der Heiden\n")

if False:
    test("||||\n"
         "Ach was darf man oft von bösen\n"
         "Gören hören oder lesen\n"
         "Wie zum Beispiel hier von denen\n"
         "Welche Moritz und Max hießen\n"
         "||||\n",
         "||||\n"
         "Kindern hören oder lesen\n"
         "Ach was muß man oft von bösen\n"
         "Welche Max und Moritz hießen\n"
         "Wie zum Beispiel hier von diesen\n"
         "Die anstatt durch weise Lehren\n"
         "Sich zum Guten zu bekehren\n"
         "||||\n")

