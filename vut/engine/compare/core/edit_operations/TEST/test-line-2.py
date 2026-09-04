#! /usr/bin/env python3
#
# @hwut {
#     title      = "Lines: Transposition and Visible Nothing"
#     choices    = ["transpose", "visible-nothing"]
# }
#
"""
PURPOSE: Verify Transposition distance scaling and VISIBLE_NOTHING logic.
CHOICES: transpose, visible-nothing;
"""
import sys
from   config import HwutRunner # noqa F401

import vut.engine.compare.core.edit_operations.line as edit_distance_line
from vut.engine.compare.TEST.common import prepare

if "--hwut-info" in sys.argv:
    print("Lines: Transposition and Visible Nothing;")
    print("CHOICES: transpose, visible-nothing;")
    sys.exit()

def test_mseq(a, b):
    # 'prepare' tokenizes strings based on a predefined line_element_db
    subject = tuple(prepare(a))
    nominal = tuple(prepare(b, True))

    cost, edit_list, analogy_db = edit_distance_line.do(subject, nominal)

    print(f"subject: '{a}'")
    print(f"nominal: '{b}'")
    print(f"=> Cost: {cost:.6f}")
    for i, edit in enumerate(edit_list):
        if edit.transpose_ai is not None:
            print(f"[{i}] {edit.id.name} ({edit.transpose_ai})")
        else:
            print(f"[{i}] {edit.id.name}")
    print()

if "transpose" in sys.argv:
    # 1. Adjacent Swap: Distance 1, Cost 0.5
    test_mseq("sn", "ns")

    # 2. Medium Distance Swap: Distance 3, Cost 0.5 * (1 + 0.1 * (3-1)) = 0.6
    test_mseq("sxxn", "nxxs")

    # 3. Maximum Distance for 'cheap' Transpose: Distance 10
    # Cost: 0.5 * (1 + 0.1 * 9) = 0.95
    test_mseq("sxxxxxxxxxn", "nxxxxxxxxxs")

    # 4. Transpose reaches Substitution cost: Distance 11
    # Cost: 0.5 * (1 + 0.1 * 10) = 1.0
    test_mseq("sxxxxxxxxxxn", "nxxxxxxxxxxs")

    # 5. Multiple Transpositions
    test_mseq("snxy", "nsyx")

if "visible-nothing" in sys.argv:
    # 1. Basic Matching and Tolerance
    test_mseq("v", "v")
    test_mseq("v", "V")

    # 2. Basic Insert/Delete
    test_mseq("sv", "s")
    test_mseq("s", "sv")

    # 3. Transpose across a Visible Nothing
    # This checks if distance scaling ignores the 'v' or counts it.
    # 's' and 'n' are separated by 'v' (Index distance 2 -> Cost 0.55)
    test_mseq("svn", "nvs")

    # 4. Multiple Visible Nothings (Cost should stay near 0)
    test_mseq("vvsvv", "s")

    # 5. Complex mixture: Transpose + Visible Nothing deletion
    # Should result in TRANSPOSE (approx 0.5) + GOOD_DELETE (1e-10)
    test_mseq("snv", "ns")

    # 6. Significant change hidden among visible nothings
    # 's' -> 'n' (1.0) with surrounding 'v's
    test_mseq("vsv", "vnv")
