"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
_______________________________________________________________________________

PURPOSE: API of compare module

CHOICES: compare, line_associations;

DESCRIPTION:

The main API provides two functions:

    compare(): judges on equivalence of subject and nominal.

    edit_operations(): determines how to transform subject into nominal. This 
                       is to be used for diff-display.

The first function provides a verdict, the second provides line associations.
In this test each function is tested by a specific 'CHOICE'.

This is the outer shell of the compare module. The tests are trivial as the
complexity of the process is hidden in the submodules located in the sub
directory of this module.
______________________________________________________________________________
"""
import sys

sys.path.insert(0, "../../../../")

from   vut.engine.compare.configuration import Configuration
import vut.engine.compare.main          as     main
from   vut.engine.compare.TEST.common   import print_list_sequence_pairs, \
                                               print_friends_pairing_max_result
from   io import StringIO


if "--hwut-info" in sys.argv:
    print("Line Comparison;")
    print("CHOICES: compare, compare-2, associate, associate-2, compare-3, associate-3;")
    sys.exit()

config = Configuration()
config.pattern_finder.analogy_f                    = False
config.pattern_finder.whitespace_f                 = True
config.pattern_finder.backslash_f                  = False
config.pattern_finder.numeric_tolerance_ratio      = 0
config.pattern_finder.equivalent_pattern_list      = []
config.pattern_finder.visible_nothing_pattern_list = ["nothing", "nix"]

def test_core(subject_txt, nominal_txt):
    print("--------------------------------------------------\n")
    print()
    subject = StringIO(subject_txt)
    nominal = StringIO(nominal_txt)
    subject_line_list = subject_txt.splitlines()
    if subject_line_list:
        max_length = max(len(txt) for txt in subject_line_list)
    else:
        max_length = 0
    max_length = max(max_length, 10)
    def space(txt):
        return " " * (max_length - len(txt))
    print_list_sequence_pairs(subject_txt.splitlines(), space, nominal_txt.splitlines(),
                              line_numbers_f=True)
    return subject, nominal

def test_compare(subject_txt, nominal_txt, both_f=False):
    if both_f:
        print("(1)")
    subject, nominal = test_core(subject_txt, nominal_txt)
    print()
    print("=> verdict: %s" % main.compare(config, subject, nominal))
    print()
    if both_f:
        print("(2)")
        nominal, subject = test_core(nominal_txt, subject_txt)
        print()
        print("=> verdict: %s" % main.compare(config, subject, nominal))
        print()

CONFIGURATION_print_only_chunk_type = False
def test_line_associations_core(subject_txt, nominal_txt):
    subject_line_list = subject_txt.splitlines()
    nominal_line_list = nominal_txt.splitlines()
    subject, nominal = test_core(subject_txt, nominal_txt)
    print()
    print("=> ")
    print()
    line_association_chunk_list = list(main.associate(config, subject, nominal))
    for chunk in line_association_chunk_list:
        st, nt = chunk.types()
        print("TYPE:", st.name, nt.name)
        if CONFIGURATION_print_only_chunk_type: continue
        print_friends_pairing_max_result(subject_line_list, nominal_line_list, 0, 
                                         chunk, [], line_offset=-1)
        print()
    print()

def test_line_associations(subject_txt, nominal_txt, both_f=False):
    if both_f:
        print("(1)")
    test_line_associations_core(subject_txt, nominal_txt)
    if both_f:
        print("(2)")
        test_line_associations_core(nominal_txt, subject_txt)

if sys.argv[1].endswith("-3"):
    if "compare-3" in sys.argv:   test = test_compare
    if "associate-3" in sys.argv: test = test_line_associations

    CONFIGURATION_print_only_chunk_type = False
    c0  = "## the comment\n"
    c1  = "der kommentar##\n"
    c2  = "nothing same nix\n"
    c3  = "nix same nothing\n"
    c4  = " \n"

    test(c0     , "",             both_f=True)
    test(c0     , c0,             both_f=True)
    test(c0     , c1,             both_f=True)
    test(c0     , c2,             both_f=True)
    test(c0     , c4,             both_f=True)
    test(c1     , c0 + c2,        both_f=True)
    test(c1     , c1 + c3,        both_f=True)
    test(c1     , c0 + c1 + c2,   both_f=True)
    test(c1 + c2, c0 + c2,        both_f=True)
    test(c4 + c4, "",             both_f=True)

elif sys.argv[1].endswith("-2"):
    if "compare-2" in sys.argv:   test = test_compare
    if "associate-2" in sys.argv: test = test_line_associations

    CONFIGURATION_print_only_chunk_type = True
    p = "||||\nHello\n||||\n"
    l = "Hello\n"

    test(p,          "",         both_f=True)
    test(l,          "",         both_f=True)
    test(l + p,      "",         both_f=True)
    test(l + p,      l,          both_f=True)
    test(l + p,      p,          both_f=True) 
    test(p + l,      p,          both_f=True)
    test(p + l,      l,          both_f=True)
    test(p + p,      p + l,      both_f=True)
    test(p + p,      l + p,      both_f=True)
    test(p + l + p,  p,          both_f=True)
    test(p + l + p,  p + l,      both_f=True)
    test(p + l + p,  l,          both_f=True)
    test(p + l + p,  l + p,      both_f=True)
    test(p + l + p,  l + p + l,  both_f=True)
    test(p + l + p,  p + p + l,  both_f=True)
    test(p + l + p,  p + l + p,  both_f=True)

else:
    if "compare" in sys.argv:   test = test_compare
    if "associate" in sys.argv: test = test_line_associations

    test("Hallo\nWelt", "Hallo\nWelt")
    test("Welt X", "Welt Y")
    test("Hallo\nWorld", "Hallo\nWelt")
    test("Hallo\nWelt 1\nWelt 2", "Hallo\n\nWelt 1\n   \nWelt  2")
    test("Hallo\n||||\nWelt", "Hallo\n||||\nWelt\n||||")
    test("Hallo\n||||\nWelt\n||||", "Hallo\n||||\nWelt")
    test("Hallo\n||||\nWelt\nLe Monde\n||||", "Hallo\n||||\nLe Monde\nWelt\n||||")

    test("Hallo##\n##Welt\nGood", "##Hello\nWorld##\nGood")
    test("||||\nHallo##\n##Welt\nGood\n||||", "||||\n##Hello\nWorld##\nGood\n||||")

    test("Hallo\nWelt",                 "||||\nHello\nWorld\n||||")
    test("||||\nHello\nLe Monde\n||||", "||||\nHello\nWorld\n||||")

