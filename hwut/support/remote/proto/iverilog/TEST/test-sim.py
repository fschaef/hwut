#! /usr/bin/env python3
#
# @hwut {
#     title   = "Adder in simulation"
#     choices = [ "adder" ]
#     build   { framework = "make"  executable = "TMP/uut.vvp" }
#     execute = "python3 test-sim.py"
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE WRITER'S TEST (README 19): Chapter 11's adder, in simulation.
         The build compiles the agent and the adder ('make'); the test opens
         a hub on the simulator, resets the UUT and applies three vectors.

The writer never sees a token, a CRC, a byte order or a recovery. The wait
contract is a row; everything else the session knows is a '##' line.
______________________________________________________________________________
"""
import os
import sys

#  The writer puts support/remote/host on PYTHONPATH; the prototype, standing
#  in the tree, finds it three directories up.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "..", "host"))

from hwut.support.test_writing.python.hwut_runner import HwutRunner  # noqa
from hwut_remote import create_hub                                   # noqa

VECTORS = [(0x03, 0x04), (0xff, 0x01), (0xff, 0xff)]


def note(text):
    """RETURN: None. A '##' line: not compared."""
    print("##", text)


def adder():
    """RETURN: None. Reset, the contract, three vectors."""
    image = int(open("TMP/image_id").read(), 16)
    with create_hub("launch", config_file="sim.conf", note=note,
                    image_id=image) as hub:
        hub.reset()
        print(hub.contract())
        print("## stim = a[15:8] b[7:0]   report = sum[8:0]")
        for x, y in VECTORS:
            print(f"{x:02x}{y:02x} {hub.vector((x << 8) | y):03x}")


HwutRunner(sys.argv, "Adder in simulation;", {"adder": adder}).run()
