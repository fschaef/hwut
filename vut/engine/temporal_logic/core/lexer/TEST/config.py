"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
Bootstrap for core-lexer tests: add the 'vut' parent and this dir to sys.path.
Import FIRST in every core/lexer/TEST test. These tests exercise the
grammar-agnostic lexer (core/lexer/) in isolation -- they do NOT import the rule-file
grammar, which is the outer language layer and belongs to parser/TEST instead.
"""
import os
import sys

_here = os.path.abspath(os.path.dirname(__file__))
_cur = _here
while os.path.basename(_cur) != "vut":
    _cur, prev = os.path.dirname(_cur), _cur
    if _cur == prev:
        raise RuntimeError("config.py: 'vut' not found above %s" % _here)
sys.path.insert(0, os.path.dirname(_cur))

if _here not in sys.path:
    sys.path.insert(0, _here)

from vut.language_support.python.hwut_runner import HwutRunner  # noqa: F401, E402
