"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
Bootstrap: add 'vut' parent and this dir to sys.path. Import FIRST in tests.

Mirrors parser/TEST/config.py: walks upward to the 'vut' package root so
'vut.engine.temporal_logic...' imports resolve, and puts this directory on the
path so a sibling FakeLuauOracle (the parser's test oracle, reused here) is
importable.
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

# The parser's test oracle is the neutral stand-in for the Luau oracle; pass 2
# tests parse real source with it, exactly as the parser tests do.
_parser_test = os.path.normpath(os.path.join(_here, "..", "..", "parser", "TEST"))
if _parser_test not in sys.path:
    sys.path.insert(0, _parser_test)

from vut.language_support.python.hwut_runner import HwutRunner  # noqa: F401, E402
