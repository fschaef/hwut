#! /usr/bin/env python3
#
# @hwut {
#     title      = "Line Comparison"
#     choices    = ["associate", "associate-2", "associate-3", "compare",
#                   "compare-2", "compare-3", "numbers"]
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
_______________________________________________________________________________

PURPOSE: API of compare module

CHOICES: compare, line_associations, numbers;

DESCRIPTION:

The main API provides two functions:

    compare(): judges on equivalence of subject and nominal.

    edit_operations(): determines how to transform subject into nominal. This
                       is to be used for diff-display.

The first function provides a verdict, the second provides line associations.

'numbers': A NUMBER IS ALWAYS A NUMBER (C-11). Under a ratio of 0
the verdict is 'equal VALUES' -- '1.0' is '1', '0.000' is '0.0' -- and a
number glued to a word ('4.5s', 'x86') is no number. A ratio above 0
widens the band and changes nothing else.
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
import asyncio


if "--hwut-info" in sys.argv:
    print("Line Comparison;")
    print("CHOICES: compare, compare-2, associate, associate-2, compare-3, associate-3, numbers;")
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

async def test_compare(subject_txt, nominal_txt, both_f=False):
    if both_f:
        print("(1)")
    subject, nominal = test_core(subject_txt, nominal_txt)
    print()
    print("=> verdict: %s" % await main.is_equivalent(config, subject, nominal))
    print()
    if both_f:
        print("(2)")
        nominal, subject = test_core(nominal_txt, subject_txt)
        print()
        print("=> verdict: %s" % await main.is_equivalent(config, subject, nominal))
        print()

CONFIGURATION_print_only_chunk_type = False
async def test_line_associations_core(subject_txt, nominal_txt):
    subject_line_list = subject_txt.splitlines()
    nominal_line_list = nominal_txt.splitlines()
    subject, nominal = test_core(subject_txt, nominal_txt)
    print()
    print("=> ")
    print()
    async for chunk in main.associate(config, subject, nominal):
        st, nt = chunk.types()
        print("TYPE:", st.name, nt.name)
        if CONFIGURATION_print_only_chunk_type: continue
        print_friends_pairing_max_result(subject_line_list, nominal_line_list, 0,
                                         chunk, [], line_offset=-1)
        print()
    print()

async def test_line_associations(subject_txt, nominal_txt, both_f=False):
    if both_f: print("(1)")
    await test_line_associations_core(subject_txt, nominal_txt)

    if both_f:
        print("(2)")
        await test_line_associations_core(nominal_txt, subject_txt)

if sys.argv[1].endswith("-3"):
    if "compare-3" in sys.argv:   test = test_compare
    if "associate-3" in sys.argv: test = test_line_associations

    CONFIGURATION_print_only_chunk_type = False
    c0  = "## the comment\n"
    c1  = "der kommentar##\n"
    c2  = "nothing same nix\n"
    c3  = "nix same nothing\n"
    c4  = " \n"

    asyncio.run(test(c0     , "",             both_f=True))
    asyncio.run(test(c0     , c0,             both_f=True))
    asyncio.run(test(c0     , c1,             both_f=True))
    asyncio.run(test(c0     , c2,             both_f=True))
    asyncio.run(test(c0     , c4,             both_f=True))
    asyncio.run(test(c1     , c0 + c2,        both_f=True))
    asyncio.run(test(c1     , c1 + c3,        both_f=True))
    asyncio.run(test(c1     , c0 + c1 + c2,   both_f=True))
    asyncio.run(test(c1 + c2, c0 + c2,        both_f=True))
    asyncio.run(test(c4 + c4, "",             both_f=True))

elif sys.argv[1] == "numbers":
    async def verdict_of(ratio, subject_txt, nominal_txt):
        """RETURN: None. One line: the ratio, both texts, the verdict."""
        config.pattern_finder.numeric_tolerance_ratio = ratio
        verdict = await main.is_equivalent(config, StringIO(subject_txt),
                                           StringIO(nominal_txt))
        print("    ratio %-5g %-16r %-16r => %s"
              % (ratio, subject_txt, nominal_txt, verdict))

    for ratio, subject_txt, nominal_txt in (
        #  equal values, however written
        (0,    "value 1.0",    "value 1"),
        (0,    "value 0.000",  "value 0.0"),
        (0,    "value -0",     "value 0"),
        (0,    "value 1e3",    "value 1000"),
        (0,    "value 007",    "value 7"),
        (0,    "t=.5 s",       "t=0.50 s"),
        #  different values
        (0,    "value 1",      "value 2"),
        (0,    "value 3.140",  "value 3.141"),
        #  a number against a word
        (0,    "value 1",      "value one"),
        #  glued to a word: text, compared as text
        (0,    "took 4.5s",    "took 4.50s"),
        (0,    "cpu x86",      "cpu x86.0"),
        #  THE SIGN IS THE NUMBER'S (C-12), either sign
        (0,    "value +3",     "value 3"),
        (0,    "value -3",     "value +3"),
        (0,    "t=+0.0",       "t=-0"),
        (0,    "x +1e-3",      "x 0.001"),
        #  after a digit the sign is the number's; the blank still differs
        (0,    "1+2",          "1 +2"),
        #  the band, and only the band, is what the ratio adds
        (0.01, "value 3.140",  "value 3.141"),
        (0.01, "value 100",    "value 102"),
    ):
        asyncio.run(verdict_of(ratio, subject_txt, nominal_txt))
    config.pattern_finder.numeric_tolerance_ratio = 0

    print("\n    THE LEXED NUMBERS, the sign included where it is one:")
    from vut.engine.compare.reading.pattern_finder import PatternFinder
    finder = PatternFinder(config.pattern_finder)
    for text in ("x -3.5 +3.5", "=+7 =-7", "(+2) ++2 --2", "+1e-3",
                 "1+2 1-2", "2026-09-15", "a+1 a-1"):
        print("    %-14r %s" % (text, " ".join(
            "%s:%s" % (e.tolerance_id.name[:3], e._string)
            for e in finder.do(text) if e.tolerance_id.name != "SEPERATOR")))

elif sys.argv[1].endswith("-2"):
    if "compare-2" in sys.argv:   test = test_compare
    if "associate-2" in sys.argv: test = test_line_associations

    CONFIGURATION_print_only_chunk_type = True
    p = "##! potpourri\nHello\n####\n"
    q = "Hello\n"

    asyncio.run(test(p,          "",         both_f=True))
    asyncio.run(test(q,          "",         both_f=True))
    asyncio.run(test(q + p,      "",         both_f=True))
    asyncio.run(test(q + p,      q,          both_f=True))
    asyncio.run(test(q + p,      p,          both_f=True))
    asyncio.run(test(p + q,      p,          both_f=True))
    asyncio.run(test(p + q,      q,          both_f=True))
    asyncio.run(test(p + p,      p + q,      both_f=True))
    asyncio.run(test(p + p,      q + p,      both_f=True))
    asyncio.run(test(p + q + p,  p,          both_f=True))
    asyncio.run(test(p + q + p,  p + q,      both_f=True))
    asyncio.run(test(p + q + p,  q,          both_f=True))
    asyncio.run(test(p + q + p,  q + p,      both_f=True))
    asyncio.run(test(p + q + p,  q + p + q,  both_f=True))
    asyncio.run(test(p + q + p,  p + p + q,  both_f=True))
    asyncio.run(test(p + q + p,  p + q + p,  both_f=True))

else:
    if "compare" in sys.argv:   test = test_compare
    if "associate" in sys.argv: test = test_line_associations

    asyncio.run(test("Hallo\nWelt", "Hallo\nWelt"))
    asyncio.run(test("Welt X", "Welt Y"))
    asyncio.run(test("Hallo\nWorld", "Hallo\nWelt"))
    asyncio.run(test("Hallo\nWelt 1\nWelt 2", "Hallo\n\nWelt 1\n   \nWelt  2"))
    asyncio.run(test("Hallo\n##! potpourri\nWelt\n####", "Hallo\n##! potpourri\nWelt\n####"))
    asyncio.run(test("Hallo\n##! potpourri\nWelt\n####", "Hallo\n##! potpourri\nWelt\n####"))
    asyncio.run(test("Hallo\n##! potpourri\nWelt\nLe Monde\n####", "Hallo\n##! potpourri\nLe Monde\nWelt\n####"))

    asyncio.run(test("Hallo##\n##Welt\nGood", "##Hello\nWorld##\nGood"))
    asyncio.run(test("##! potpourri\nHallo##\n##Welt\nGood\n####", "##! potpourri\n##Hello\nWorld##\nGood\n####"))

    asyncio.run(test("Hallo\nWelt",                 "##! potpourri\nHello\nWorld\n####"))
    asyncio.run(test("##! potpourri\nHello\nLe Monde\n####", "##! potpourri\nHello\nWorld\n####"))


#  THE STREAM COMPLETED (R-70).
print("<hwut-end>")
