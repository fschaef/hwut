"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.good.rebase' COMMAND LINE -- every link naming one
         '.txt' names another (bookkeeper B-32, services E-209).

    hwut.good.rebase <linked.txt> <new-base.txt>

Every '.link' within the root that names <linked.txt> is written anew to
name <new-base.txt>. <linked.txt> itself is not touched: no link names it
any more, so it may be removed, moved or changed as any other GOOD.

WHAT IS REFUSED, by name, and then nothing is written: a word that is no
'.txt' in a GOOD/; the same file twice; a new base beyond the root; a link
that would come to name its own case (the new base is that link's case).

EXIT STATUS: 0 OK, 2 REFUSED, 3 EMPTY (no link names <linked.txt>).
______________________________________________________________________________
"""
import os
import sys
from   pathlib import Path

from ..._core                     import usage_line
from ..._exit                     import E_ExitCode
from ....engine.bookkeeper.api    import (LinkFault, boundary_fault, links_to,
                                          text_path_of, write_link)
from ._good                       import in_good_f, shown

FACE  = "hwut.good.rebase"
USAGE = usage_line("usage: %s" % FACE, ("<linked.txt>", "<new-base.txt>"))

HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n" + USAGE


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).
    """
    if write is None: write = print
    if argv is None:  argv  = sys.argv[1:]
    if "--help" in argv:
        from ..._core import man_page
        write(man_page(FACE, HELP))
        return E_ExitCode.OK
    if len(argv) != 2 or any(word.startswith("-") for word in argv):
        write("REFUSED: '%s' wants the linked '.txt' and its new base" % FACE)
        write(USAGE)
        return E_ExitCode.REFUSED
    old, new = Path(argv[0]), Path(argv[1])
    for path in (old, new):
        if not (path.is_file() and path.suffix == ".txt" and in_good_f(path)):
            write("REFUSED: '%s' is no '.txt' in a GOOD/" % shown(path))
            return E_ExitCode.REFUSED
    if os.path.samefile(str(old), str(new)):
        write("REFUSED: '%s' twice -- nothing would change" % shown(old))
        return E_ExitCode.REFUSED

    link_tuple = links_to(old)
    if not link_tuple:
        write("NOTE: no link names '%s' -- nothing to rebase" % shown(old))
        return E_ExitCode.EMPTY
    refusal_list = []
    for link in link_tuple:
        fault = boundary_fault(link.parent, new.parent)
        if fault:
            refusal_list.append("'%s' -> '%s': %s" % (shown(link), shown(new), fault))
        elif os.path.abspath(str(text_path_of(link))) == os.path.abspath(str(new)):
            refusal_list.append("'%s' would name its own case" % shown(link))
    if refusal_list:
        for line in refusal_list: write("REFUSED: %s" % line)
        write("NOTE: nothing was rebased")
        return E_ExitCode.REFUSED
    for link in link_tuple:
        try:
            write_link(link, new)
        except LinkFault as fault:          # checked above; said, never lost
            write("FAULT: %s" % fault)
            return E_ExitCode.FAULT
        write("REBASED  %s -> %s  (was %s)" % (shown(link), shown(new), shown(old)))
    return E_ExitCode.OK


if __name__ == "__main__":
    from ..._exit import guarded
    sys.exit(guarded(FACE, main))
