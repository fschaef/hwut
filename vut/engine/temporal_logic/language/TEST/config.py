"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
Bootstrap for language-layer tests: add the 'vut' parent and this dir to
sys.path. Import FIRST in every language/TEST test. These tests exercise the
rule-file GRAMMAR and its binding to the core engine (the OUTER language layer):
the grammar compiles LL(2)-clean under the core, and every LANGUAGE.txt
construct parses. The grammar-agnostic machinery is tested in core/*/TEST.
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
