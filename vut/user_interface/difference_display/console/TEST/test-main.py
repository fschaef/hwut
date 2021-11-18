"""SPDX-Linces: MIT; Project VUT; (C) Frank-Rene Schaefer
_______________________________________________________________________________

PURPOSE: Difftool command line

______________________________________________________________________________
"""
import sys

sys.path.insert(0, "../../../../..")

import vut.engine.compare.main                               as     compare
from   vut.engine.compare.configuration                      import Configuration
from   vut.engine.compare.engine.line_association_chunk_list import LineAssociationChunkList
import vut.user_interface.difference_display.console.main    as     console
from   vut.user_interface.difference_display.console.canvas  import ConsoleCanvasDiff, E_DiffMode
import vut.system.terminal_size                              as     terminal_size

from   io import StringIO

if "--hwut-info" in sys.argv:
    print("Display Modes: Comparison, Analogy Error;")
    print("CHOICES: similar, padding, potpourri, mix, analogy, error, error2;")
    # Call with 'GO' on command line to interact with a TUI

config = Configuration()
config.pattern_finder.numeric_tolerance_ratio = 0.01
config.pattern_finder.equivalent_pattern_list = ["rot|orange", "Röslein|Tülplein"]

def test_core(subject_txt, nominal_txt, offset, mode, level):
    global config
    terminal_width  = 80
    terminal_height = 30
    subject = StringIO(subject_txt)
    nominal = StringIO(nominal_txt)

    print()
    print("|" + "=" * (terminal_width -2) + "|")
    la = list(compare.line_associations(config, subject, nominal))

    terminal_size.set_size_fixed(terminal_height, terminal_width)
    canvas = ConsoleCanvasDiff(LineAssociationChunkList(la))
    canvas.set_mode(mode, level)
    canvas._display_content()

def test(subject_txt, nominal_txt, offset=0, mode=E_DiffMode.PLAIN, level=0, both=True):
    if "GO" not in sys.argv:
        test_core(subject_txt, nominal_txt, offset, mode, level)
        if both:
            test_core(nominal_txt, subject_txt, offset, mode, level)
    else:
        subject = StringIO(subject_txt)
        nominal = StringIO(nominal_txt)

        la = list(compare.line_associations(config, subject, nominal))
        console.do(LineAssociationChunkList(la))

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

subject_error2_txt = \
"""
eins
zwei
drei
vier     
fuenf !!
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
achtzehn !!
neunzehn  
zwanzig        
einundzwanzig
zweiundzwanzig
"""

if "similar" in sys.argv:
    # Testing all kinds of similarity
    test(subject_txt, nominal_txt, both=True)

elif "padding" in sys.argv:
    test(subject_modified_txt, nominal_txt, level=2)
    test(subject_modified_txt, nominal_txt, level=1)
    test(subject_modified_txt, nominal_txt, level=0)

elif "potpourri" in sys.argv:
    test("||||\n"
         + subject_modified_txt 
         + "||||\n",
         "||||\n"
         + nominal_txt
         + "||||\n", both=True)

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
         + mix_nominal, both=True)

elif "analogy" in sys.argv:
    test(analogy_subject, analogy_nominal, mode=E_DiffMode.ANALOGIES, level=2)
    test(analogy_subject, analogy_nominal, mode=E_DiffMode.ANALOGIES, level=1)
    test(analogy_subject, analogy_nominal, mode=E_DiffMode.ANALOGIES, level=0)

elif "error" in sys.argv:
    test(subject_error_txt, nominal_error_txt, mode=E_DiffMode.ERRORS, level=2)
    test(subject_error_txt, nominal_error_txt, mode=E_DiffMode.ERRORS, level=1)
    test(subject_error_txt, nominal_error_txt, mode=E_DiffMode.ERRORS, level=0)

elif "error2" in sys.argv:
    test(subject_error2_txt, nominal_error_txt, mode=E_DiffMode.ERRORS, level=2)
    test(subject_error2_txt, nominal_error_txt, mode=E_DiffMode.ERRORS, level=1)
    test(subject_error2_txt, nominal_error_txt, mode=E_DiffMode.ERRORS, level=0)

