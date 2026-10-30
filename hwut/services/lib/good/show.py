"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.good.link.show' COMMAND LINE -- who shares a GOOD
         (bookkeeper B-32, services E-209).

    hwut.good.link.show [<good-file|directory>...]

    <good.txt>     every '.link' within its root that names it
    <good.link>    the '.txt' it names -- or why it names nothing
    <directory>    every '.link' in it and below, each with what it names
                   (the default: '.')

prints one line per link, 'link -> text', every path from where hwut was
called. What a '.txt' cannot be removed for, this says.

EXIT STATUS: 0 OK (a link was shown), 1 FAULT (a link names nothing it
may), 2 REFUSED (the command line), 3 EMPTY (no link).
______________________________________________________________________________
"""
import sys
from   pathlib import Path

from ..._core                     import usage_line
from ..._exit                     import E_ExitCode
from ....engine.bookkeeper.api    import link_tuple, links_to
from ._good                       import link_text_of, shown

FACE  = "hwut.good.link.show"
USAGE = usage_line("usage: %s" % FACE, ("[<good-file|directory>...]",))

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
    if unknown:
        write("REFUSED: '%s' does not take: %s" % (FACE, ", ".join(unknown)))
        write(USAGE)
        return E_ExitCode.REFUSED

    shown_n, fault_f = 0, False
    for word in argv or ["."]:
        path = Path(word)
        if path.is_dir():
            row_list = [(link, link_text_of(link)) for link in link_tuple(path)]
        elif path.suffix == ".link" and path.is_file():
            row_list = [(path, link_text_of(path))]
        elif path.is_file():
            row_list = [(link, shown(path)) for link in links_to(path)]
            if not row_list:
                write("%s: no link names it" % shown(path))
        else:
            write("REFUSED: '%s': no such file or directory" % word)
            return E_ExitCode.REFUSED
        for link, text in row_list:
            write("%s -> %s" % (shown(link), text))
            fault_f |= text.startswith("(")
        shown_n += len(row_list)
    if fault_f:      return E_ExitCode.FAULT
    if not shown_n:  return E_ExitCode.EMPTY
    return E_ExitCode.OK


if __name__ == "__main__":
    from ..._exit import guarded
    sys.exit(guarded(FACE, main))
