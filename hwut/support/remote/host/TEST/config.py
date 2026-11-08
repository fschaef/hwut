"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Bootstrap module for the tests in this directory: 'hwut_remote'
         (the directory above) and 'HwutRunner' (the directory holding
         'hwut/') put on sys.path. Imports nothing before the walk.
______________________________________________________________________________
"""
import os
import sys

_here = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(_here))                 # support/remote/host
_cur  = _here
while os.path.basename(_cur) != "hwut":
    _parent = os.path.dirname(_cur)
    if _parent == _cur:
        raise RuntimeError("config.py: no directory 'hwut' above '%s'" % _here)
    _cur = _parent
sys.path.insert(0, os.path.dirname(_cur))

from hwut.support.test_writing.python.hwut_runner import HwutRunner  # noqa
