"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Bootstrap module for tests in this directory.

This file is the chicken-and-egg solution: HwutRunner.insert_project_path()
cannot be used to locate HwutRunner itself, because importing it requires
sys.path to be set up first. So this tiny stdlib-only module does the
bootstrap by walking upward from its own location until it finds a directory
named 'vut/', then inserts that directory's parent into sys.path.

After 'import config' (as the first import in a test file), all of:

    from vut.language_support.python.hwut_runner import HwutRunner
    from vut.engine.procsitter.procsitter              import ...

work normally.

NOTE: This file imports nothing from vut. It is excluded from coverage
      and from test discovery via 'hwut-info.dat'.
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
    _parent = os.path.dirname(_cur)
    if _parent == _cur:
        raise RuntimeError(
            "config.py: could not find directory 'vut' walking up from '%s'"
            % _here
        )
    _cur = _parent

#  THE WALK'S FINDING, EXPORTED. Tests that reach a SIBLING component
#  (e.g. hwut_pype) take the vut directory from here instead of
#  counting '..' -- a hop count is a silent hostage to the layout, and
#  it is this file that knows where 'vut' is.
VUT_DIRECTORY = _cur

from vut.language_support.python.hwut_runner import HwutRunner # noqa E401
