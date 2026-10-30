"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.good.isolate' COMMAND LINE -- a linked case gets its
         own '.txt' again (bookkeeper B-32, services E-209).

    hwut.good.isolate <good-file|directory>...

    <good.link>    replaced by a copy of the '.txt' it names
    <good.txt>     every '.link' within its root that names it is
                   replaced by a copy of it; the '.txt' itself stays
    <directory>    every '.link' in it and below

The book is not touched: the case was accepted, and its GOOD says the same
as before -- now in a file of its own. After it, 'hwut.accept' and
'hwut.merge' write the case as any other.

EXIT STATUS: 0 OK, 1 FAULT (a link names nothing it may: left as it
stands, named), 2 REFUSED (the command line), 3 EMPTY (no link).
______________________________________________________________________________
"""
import sys
from   pathlib import Path

from ..._core                     import usage_line
from ..._exit                     import E_ExitCode
from ....engine.bookkeeper.api    import LinkFault, link_tuple, links_to
from ._good                       import isolated, link_text_of, shown

FACE  = "hwut.good.isolate"
USAGE = usage_line("usage: %s" % FACE, ("<good-file|directory>...",))

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
    unknown = [word for word in argv if word.startswith("-")]
    if unknown or not argv:
        if unknown:
            write("REFUSED: '%s' does not take: %s" % (FACE, ", ".join(unknown)))
        else:
            write("REFUSED: '%s' wants a link, a text or a directory" % FACE)
        write(USAGE)
        return E_ExitCode.REFUSED

    link_list = []
    for word in argv:
        path = Path(word)
        if   path.is_dir():                              link_list.extend(link_tuple(path))
        elif path.suffix == ".link" and path.is_file():  link_list.append(path)
        elif path.is_file():                             link_list.extend(links_to(path))
        else:
            write("REFUSED: '%s': no such file or directory" % word)
            return E_ExitCode.REFUSED
    if not link_list:
        write("NOTE: no link -- nothing to isolate")
        return E_ExitCode.EMPTY
    fault_f = False
    for link in link_list:
        text = link_text_of(link)
        try:
            own = isolated(link)
        except LinkFault as fault:
            write("FAULT: %s -- left as it stands" % fault)
            fault_f = True
            continue
        write("ISOLATED  %s  (a copy of %s; the link is gone)" % (shown(own), text))
    return E_ExitCode.FAULT if fault_f else E_ExitCode.OK


if __name__ == "__main__":
    from ..._exit import guarded
    sys.exit(guarded(FACE, main))
