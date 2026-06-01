"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Bootstrap module for tests in this directory.

Walks upward from this file until it finds the 'vut' package directory, then
inserts its parent onto sys.path so absolute 'from vut.engine.temporal_logic...'
imports resolve when a test is run as a plain script (as HWUT runs it). Also
inserts this TEST directory so sibling test-only modules (fake_luau_oracle,
hwut_runner_shim) import by bare name.

Import FIRST in every test file, before any vut import.
______________________________________________________________________________
"""
import os
import sys

_here = os.path.abspath(os.path.dirname(__file__))
_cur  = _here
while True:
    if os.path.basename(_cur) == "vut":
        sys.path.insert(0, os.path.dirname(_cur))
        break
    parent = os.path.dirname(_cur)
    if parent == _cur:
        raise RuntimeError("config.py: 'vut' not found above %s" % _here)
    _cur = parent

if _here not in sys.path:
    sys.path.insert(0, _here)
