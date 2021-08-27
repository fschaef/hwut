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

def test_core(subject_txt, nominal_txt, offset=0):
    global config
    terminal_width = 80
    subject = StringIO(subject_txt)
    nominal = StringIO(nominal_txt)

    print("|" + "-" * (terminal_width -2) + "|")
    la = list(compare.line_associations(config, subject, nominal))
    terminal_size.set_size_fixed(10, terminal_width)
    console.display(la, offset)

def test(subject_txt, nominal_txt, offset=0):
    test_core(subject_txt, nominal_txt, offset)
    test_core(nominal_txt, subject_txt, offset)

subject_txt = \
"""Sah ein Röslein ein Knab stehen
Röslein auf der     Heiden 
War jung morgenschön
Lief er ganz schnell es von nah zu sehn
Schaut's mit manchen Freuden
Röslein, Tülplein, Röslein orange
((Rose)) auf der ((Wiese))
Numerische tolerance: 4712
"""

nominal_txt = \
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
subject_modified_txt = \
"""Sah ein Röslein ein Knab stehen
Röslein   auf der   Heiden 
War jung morgenschön
Röslein, Tülplein, Röslein orange
"""

if "similar" in sys.argv:
    # Testing all kinds of similarity
    test(subject_txt, nominal_txt)

elif "padding" in sys.argv:
    test(subject_modified_txt, nominal_txt)

elif "potpourri" in sys.argv:
    test("||||\n"
         + subject_txt + subject_modified_txt 
         + "||||\n",
         "||||\n"
         + nominal_txt * 2
         + "||||\n")

