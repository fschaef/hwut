"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.about' -- what this is, which version, and where it
         stands on this machine (services E-138).

    hwut.about              the page: the version, the licence, the
                            home; then THIS INSTALLATION -- where the
                            package stands, the Python that runs it,
                            the platform, and a checksum of its
                            source files, as a reference
    hwut.about --version    the version alone, one bare line, for a
                            script to read
    hwut.about --help       this text

IT NEEDS NO TREE: it is asked before a tree exists, and in a bug report
from a directory that is in none.

THE VERSION STANDS IN ONE PLACE, 'adm/version.py'; this face reads it
and states none of its own.
______________________________________________________________________________
"""
import os
import platform
import sys

import vut.adm.version         as     version
from   vut.services._exit      import E_ExitCode

NAME    = "hwut.about"
USAGE   = "usage: %s [--version] | --help" % NAME
HELP    = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
          + "\n\n" + USAGE
TITLE   = "tolerant golden-master testing"
LICENCE = "MIT"
AUTHOR  = "(C) Frank-Rene Schaefer"
HOME    = "https://github.com/fschaef/hwut"


def package_directory():
    """
    RETURN: str, the absolute directory of the 'vut' package this face
                 was loaded from -- the installation a person is asking
                 about, symbolic links resolved.
    """
    return os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def about_line_list():
    """
    RETURN: list[str], the page, line by line: what hwut is and its
            version, licence, author and home; then the facts of THIS
            installation.

    A MACHINE'S WORD STANDS ON A LINE OF ITS OWN, last on it: the path,
    the interpreter and the platform differ by machine, and nothing to
    their right or below them moves with their length.
    """
    return ["HWUT %s -- %s" % (version.string, TITLE),
            "",
            "    version    %s" % version.string,
            "    licence    %s" % LICENCE,
            "    author     %s" % AUTHOR,
            "    home       %s" % HOME,
            "",
            "THIS INSTALLATION",
            "",
            "    package    %s" % package_directory(),
            "    python     %s" % platform.python_version(),
            "    run by     %s" % sys.executable,
            "    platform   %s" % sys.platform,
            "    sources    %s" % source_checksum()]


def source_checksum():
    """RETURN: str, '<n> files, sha256 <16 hex digits>' -- the reference
               of THIS installation's source: every '*.py' of the
               package and every launcher in 'bin/', test directories
               left out, each by its path from the package and its
               bytes, in sorted order. Two installations that print the
               same line run the same source.
    """
    import hashlib
    root      = package_directory()
    path_list = []
    for directory, name_list, file_list in os.walk(root):
        name_list[:] = sorted(n for n in name_list
                              if n not in ("TEST", "__pycache__")
                              and not n.startswith("."))
        launcher_f = os.path.basename(directory) == "bin"
        path_list.extend(os.path.join(directory, f) for f in sorted(file_list)
                         if f.endswith(".py")
                         or (launcher_f and f.startswith("hwut")))
    digest = hashlib.sha256()
    for path in path_list:
        digest.update(os.path.relpath(path, root).encode("utf-8") + b"\0")
        with open(path, "rb") as fh: digest.update(fh.read())
        digest.update(b"\0")
    return "%d files, sha256 %s" % (len(path_list), digest.hexdigest()[:16])


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode (E-1): OK with the page or the bare version
            written
            REFUSED, where a word stands that the face does not take

    'write' takes one line of text; 'print' where none is given.
    """
    if write is None: write = print
    if argv is None:  argv = sys.argv[1:]
    if "--help" in argv or "-h" in argv:
        from vut.services._core import man_page
        write(man_page(NAME, HELP))
        return E_ExitCode.OK
    if argv == ["--version"]:
        write(version.string)
        return E_ExitCode.OK
    if argv:
        write("REFUSED: '%s' does not take: %s" % (NAME, " ".join(argv)))
        write(USAGE)
        return E_ExitCode.REFUSED
    for line in about_line_list(): write(line)
    return E_ExitCode.OK


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from vut.services._exit import guarded
    sys.exit(guarded(NAME, main, sys.argv[1:]))
