"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FACES OF AN INSTALLED hwut (adm/WORK/spec/24). In a clone
         every face is a two-line shim in 'bin/' running 'python3 -m
         <module>'; an installation's launcher cannot carry a path, so
         each face is an entry point that lands HERE and runs the module
         the shim names, as '__main__' -- exactly what '-m' does.

    face_module_db()   face name -> module, read off the shims in a clone,
                       or off '_launch_db' (written by the package build)
                       where no shim stands
    main()             the entry point of every installed face
______________________________________________________________________________
"""
import os
import re
import sys

BIN = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(
          __file__)), "..", "bin"))
_MODULE_RE = re.compile(r"python3\s+(?:-I\s+)?-m\s+([A-Za-z0-9_.]+)")


def shim_module_db(bin_directory=BIN):
    """
    RETURN: dict, face name -> module, for every 'hwut' and 'hwut.*' shim
            in 'bin_directory' that runs 'python3 -m <module>'.
            {}, where the directory holds none.
    """
    result = {}
    try:
        name_list = os.listdir(bin_directory)
    except OSError:
        return result
    for name in name_list:
        if not (name == "hwut" or name.startswith("hwut.")): continue
        try:
            with open(os.path.join(bin_directory, name)) as fh:
                m = _MODULE_RE.search(fh.read())
        except (OSError, UnicodeDecodeError):
            continue
        if m is not None: result[name] = m.group(1)
    return result


def face_module_db():
    """
    RETURN: dict, face name -> module, of this installation: the shims
            where they stand (a clone), the build's '_launch_db' else.
    """
    result = shim_module_db()
    if result: return result
    try:
        from ._launch_db import FACE_MODULE_DB
    except ImportError:
        return {}
    return dict(FACE_MODULE_DB)


def main():
    """
    RETURN: never -- the face's module runs as '__main__' and its exit is
            the process's. A name no face carries ends with status 2,
            said on stderr.
    """
    import runpy
    name = os.path.basename(sys.argv[0])
    module = face_module_db().get(name)
    if module is None:
        sys.stderr.write("REFUSED: '%s' is no face of hwut\n" % name)
        sys.exit(2)
    sys.argv[0] = name
    runpy.run_module(module, run_name="__main__", alter_sys=True)
