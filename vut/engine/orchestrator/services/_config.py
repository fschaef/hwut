"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Bootstrap module for DIRECT EXECUTION of the service faces.

The same chicken-and-egg solution as a TEST directory's config.py: run
as a plain script ('python3 .../services/merge.py', from any working
directory) a face has no package context, so nothing 'vut.*' -- and no
relative import -- resolves. This tiny stdlib-only module walks upward
from its own location until it finds the directory named 'vut', inserts
that directory's parent into sys.path, and imports the services
package.

A face then needs only the ADOPTION (PEP 366), two lines guarded by
'run as a script?':

    if __package__ in (None, ""):
        import _config; __package__ = _config.PACKAGE

after which its relative imports resolve exactly as under '-m' or a
normal module import -- where this module is never even loaded.

NOTE: This file imports nothing from vut at module scope until the path
      is set. Script-mode 'sys.path[0]' is THIS directory, so 'import
      _config' finds THIS file deterministically.
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
            "_config.py: could not find directory 'vut' walking up from '%s'"
            % _here
        )
    _cur = _parent

import vut.engine.orchestrator.services                       # noqa: E402,F401

PACKAGE = "vut.engine.orchestrator.services"
