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

if "--hwut-info" in sys.argv:
    print("Display Modes: Comparison, Analogy Error;")
    print("CHOICES: similar, padding, potpourri, mix, analogy;")

config = Configuration()
config.pattern_finder.numeric_tolerance_ratio = 0.01
config.pattern_finder.equivalent_pattern_list = ["rot|orange", "Röslein|Tülplein"]

def test_core(subject_txt, nominal_txt, offset, mode):
    global config
    terminal_width  = 80
    terminal_height = 30
    subject = StringIO(subject_txt)
    nominal = StringIO(nominal_txt)

    print()
    print("|" + "=" * (terminal_width -2) + "|")
    la = list(compare.line_associations(config, subject, nominal))

    if True:
        terminal_size.set_size_fixed(terminal_height, terminal_width)
        canvas = console.ConsoleCanvasDiff(la)
        canvas.set_mode(mode)
        canvas.prepare_data()
        canvas._display_LineAssociations()
    else:
        terminal_size.set_size_fixed(terminal_height, terminal_width)
        canvas.set_mode(mode)
        console.do(la)

def test(subject_txt, nominal_txt, offset=0, mode=console.E_DiffMode.PLAIN):
    test_core(subject_txt, nominal_txt, offset, mode)
    test_core(nominal_txt, subject_txt, offset, mode)

subject_txt = \
"""Sah ein Röslein 1.005 Knab stehen
Röslein auf der     ((Wiese))
War jung morgenschön
Lief er ganz schnell es von nah zu sehn
Schaut's mit 1000 Freuden
Röslein, Tülplein, Röslein orange
Röslein auf der ((Wiese))
"""

nominal_txt = \
"""
Sah ein Knab 1 Röslein stehen
Röslein   auf der   ((Heiden))
War so jung und morgenschön
Lief er schnell es nah zu sehn
Schaut's mit vielen Freuden
Röslein, Röslein, Röslein rot
Röslein auf der ((Heiden))
"""

subject_modified_txt = \
"""Sah ein Röslein ein Knab stehen
Röslein   auf der   Heiden 
War jung morgenschön
Röslein, Tülplein, Röslein orange
"""

analogy_subject = \
"""
Knabe sprach: ((wir)) breche ((dich)),
((Röslein)) ((auf)) der ((Wiese))!
((Röslein)) sprach: Ich steche ((dich)),
daß du ewig denkst an mich,
und ((wir)) will's nicht leiden.
((Röslein)), ((Röslein)), ((Tülplein)) rot,
((Röslein)) ((unter)) der ((Wiese)).
"""

analogy_nominal = \
"""
Knabe sprach: ((ich)) breche ((dich)),
((Röslein)) ((auf)) der ((Heiden))!
((Röslein)) sprach: Ich steche ((dich)),
daß du ewig denkst an mich,
und ((ich)) will's nicht leiden.
((Röslein)), ((Röslein)), ((Röslein)) rot,
((Röslein)) ((auf)) der ((Heiden)).
"""

mix_subject = \
"""
Zwei
Vier
Fünf
"""

mix_nominal = \
"""
Eins
Zwei
Drei
Vier
Fünf
"""

nominal_error_txt = \
"""
eins
zwei
drei
vier
fuenf
sechs
sieben
acht 
neun
zehn
elf
zwölf
dreizehn
vierzehn
fuenfzehn
sechzehn
siebzehn
achtzehn
neunzehn
zwanzig
einundzwanzig
zweiundzwanzig
"""

subject_error_txt = \
"""
eins           !!
zwei           !!
drei
vier           !!
fuenf
sechs
sieben         !!
acht 
neun
zehn
elf            !!
zwölf
dreizehn
vierzehn
fuenfzehn
sechzehn       !!
siebzehn
achtzehn
neunzehn
zwanzig
einundzwanzig
zweiundzwanzig !!
"""

if "similar" in sys.argv:
    # Testing all kinds of similarity
    test(subject_txt, nominal_txt)

elif "padding" in sys.argv:
    test(subject_modified_txt, nominal_txt)

elif "potpourri" in sys.argv:
    test("||||\n"
         + subject_modified_txt 
         + "||||\n",
         "||||\n"
         + nominal_txt
         + "||||\n")

elif "mix" in sys.argv:
    test(mix_subject
         + "||||\n"
         + mix_subject 
         + "||||\n"
         + mix_subject,
         mix_nominal
         + "||||\n"
         + mix_nominal
         + "||||\n"
         + mix_nominal)

elif "analogy" in sys.argv:
    test(analogy_subject, analogy_nominal, mode=console.E_DiffMode.ANALOGIES)

elif "error" in sys.argv:
    test(subject_error_txt, nominal_error_txt, mode=console.E_DiffMode.ERRORS)

