"""SPDX-Linces: MIT; Project VUT; (C) Frank-Rene Schaefer
_______________________________________________________________________________

PURPOSE: Difftool command line

______________________________________________________________________________
"""
import sys

sys.path.insert(0, "../../../../..")

from   vut.user_interface.difference_display.console.TEST.cases import *
import vut.engine.compare.main                                  as     compare
from   vut.engine.compare.configuration                         import Configuration
from   vut.engine.compare.engine.line_association_chunk_list    import LineAssociationChunkList
import vut.user_interface.difference_display.console.main       as     console
from   vut.user_interface.difference_display.console.canvas     import ConsoleCanvasDiff, E_DiffMode
import vut.system.terminal_size                                 as     terminal_size

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
    if "GO" in sys.argv:
        subject = StringIO(subject_txt)
        nominal = StringIO(nominal_txt)

        la = list(compare.line_associations(config, subject, nominal))
        console.diff(LineAssociationChunkList(la))

    elif "GONE" in sys.argv:
        subject = StringIO(subject_txt)
        nominal = StringIO(nominal_txt)

        la = list(compare.line_associations(config, subject, nominal))
        console.merge(LineAssociationChunkList(la))
    else:
        test_core(subject_txt, nominal_txt, offset, mode, level)
        if both:
            test_core(nominal_txt, subject_txt, offset, mode, level)

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

