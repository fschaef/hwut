"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.cov.formats' -- the table of coverage tools, formats and
         aliases this build READS, the measures each format carries
         beside the lines, and the tools hwut DRIVES with the formats
         each offers -- generated from the registry (coverage
         RATIONALE D-13, D-26, D-46, D-49).

    hwut.cov.formats            the table. Which tool serves a language
                                is not the registry's to say: it stands
                                in 'language-setup' of 'HWUT_ROOT/setup.conf'
    hwut.cov.formats --help     this text

The registry is the ONE author of the table; a machine that lacks a
tool is refused BY NAME against this list.
______________________________________________________________________________
"""
import sys

from ....engine.coverage.api import (callable_tuple, format_named,
                                     framework_of, registered_tuple)
from ..._exit import E_ExitCode

NAME  = "hwut.cov.formats"
USAGE = "usage: %s | --help" % NAME
HELP  = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip()


def formats_text():
    """
    RETURN: str, one table read from the registry and written nowhere
            else: every tool this build READS with its format and, for
            an alias, the reader it reads through. WHICH TOOL SERVES A
            LANGUAGE is not the registry's to say (coverage D-26): it
            stands in 'language-setup' of the tree's 'HWUT_ROOT/setup.conf'.
    """
    readable  = set(registered_tuple())
    line_list = ["TOOLS READ BY THIS BUILD",
                 "  %-18s %-24s %-14s %s" % ("tool", "format",
                                             "reads through", "measures")]
    for tool in sorted(readable):
        reader  = framework_of(tool)
        through = getattr(reader, "through", None)
        line_list.append("  %-18s %-24s %-14s %s"
                         % (tool, reader.source_format,
                            through.name if through is not None else "-",
                            _measures(reader.format)))
    line_list += ["", "TOOLS HWUT DRIVES -- the 'coverage' a language may "
                      "name; '*' the default 'format'",
                  "  %-18s %-24s %s" % ("tool", "format", "measures")]
    for tool in callable_tuple():
        reader = framework_of(tool)
        for i, name in enumerate(reader.offered_format_tuple):
            line_list.append("  %-18s %-24s %s"
                             % (tool if i == 0 else "",
                                name + ("*" if i == 0 else ""),
                                _measures(format_named(name))))
    line_list += ["", "'measures': what a record of that format carries.",
                  "The tool per language stands in "
                  "'language-setup' of 'HWUT_ROOT/setup.conf'."]
    return "\n".join(line_list)


def _measures(fmt):
    """RETURN: str, what a record of the format carries: 'lines', then
    every measure its reader seats beside them (coverage D-49)."""
    return ", ".join(("lines",) + tuple(fmt.measure_tuple))


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode (E-1): OK with the table written, REFUSED where
            an argument was given -- the face takes none.

    'write' takes one line of text; 'print' where none is given.
    """
    if write is None: write = print
    if argv is None:  argv = sys.argv[1:]
    if "--help" in argv or "-h" in argv:
        from ..._core import man_page
        write(man_page(NAME, HELP, usage=USAGE))
        return E_ExitCode.OK
    if argv:
        write("REFUSED: %s takes no argument" % NAME); write(USAGE)
        return E_ExitCode.REFUSED
    write(formats_text())
    return E_ExitCode.OK


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded(NAME, main, sys.argv[1:]))
