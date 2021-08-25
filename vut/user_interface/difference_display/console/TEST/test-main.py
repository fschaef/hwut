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
config.pattern_finder.equivalent_pattern_list = ["rot|orange", "Röslein|Tülplein"]

def test(subject_txt, nominal_txt):
    global config
    subject = StringIO(subject_txt)
    nominal = StringIO(nominal_txt)

    print("------------------------------------------------------------------------")
    la = list(compare.line_associations(config, subject, nominal))
    terminal_size.set_size_fixed(10, 200)
    console.display(la, 0)
    console.display(la, 1)
    console.display(la, 3)

    console.display(la, 20)
    console.display(la, 21)
    console.display(la, 22)

    console.display(la, -20)
    console.display(la, -21)
    console.display(la, -22)
    console.display(la, -200)

wrong_txt = \
"""Sah ein Röslein ein Knab stehen
Röslein   auf der   Heiden 
War jung morgenschön
Lief er ganz schnell es von nah zu sehn
Schaut's mit manchen Freuden
Röslein, Tülplein, Röslein orange
((Rose)) auf der ((Wiese))
Numerische tolerance: 4712
"""

good_txt = \
"""
Sah ein Knab ein Röslein stehen
Röslein   auf der   Heiden 
War so jung und morgenschön
Lief er schnell es nah zu sehn
Schaut's mit vielen Freuden
Röslein, Röslein, Röslein orange
((Rose)) auf der ((Heiden))
Numerische tolerance: 4711
"""

# test(wrong_txt * 4, good_txt * 4)
# test(good_txt * 2 + wrong_txt + good_txt, good_txt * 4)
test((wrong_txt+wrong_txt).replace("\n", " "), (good_txt+good_txt).replace("\n", " "))

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

