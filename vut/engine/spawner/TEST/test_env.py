"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Test bootstrap - puts the 'vut' package on sys.path.

Every test file in this directory imports this module FIRST, before any
'vut.*' import:

    import test_env  # noqa: F401

The import has a side effect and no surface: it walks upward from this
file until it finds the directory named 'vut' and inserts that
directory's PARENT onto sys.path, so that 'import vut.engine.spawner...'
resolves no matter where the test is invoked from.

This module is pure standard library on purpose - it must work BEFORE
the 'vut' package is importable, so it cannot itself import from 'vut'.
It is excluded from coverage (see hwut-info.dat).
________________________________________________________________________________
"""
import os
import sys


def _insert_project_path(root_dir_name: str = "vut") -> None:
    """RETURN: None.

    Walks upward from this file's directory until a directory named
    'root_dir_name' is found, and inserts that directory's PARENT onto
    sys.path - so 'import <root_dir_name>...' resolves.

    A no-op (silent) if no such ancestor exists: the package may already
    be importable via an installed location or a pre-set PYTHONPATH.
    """
    cur = os.path.abspath(os.path.dirname(__file__))
    while True:
        if os.path.basename(cur) == root_dir_name:
            parent = os.path.dirname(cur)
            if parent not in sys.path:
                sys.path.insert(0, parent)
            return
        nxt = os.path.dirname(cur)
        if nxt == cur:
            return                          # reached filesystem root
        cur = nxt


_insert_project_path("vut")
