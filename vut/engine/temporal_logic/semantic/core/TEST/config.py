"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
Bootstrap: add the 'vut' package parent and this dir to sys.path. Import FIRST.

The core/ test bootstrap. Unlike semantic/TEST/config.py it pulls in NO parser
oracle: core tests build their tables by HAND (Scope/Symbol/ModuleProxy) and run
the general join, touching nothing in the rule-language (filler) layer. This is
the seam made visible -- a core test imports only semantic/core/.
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
