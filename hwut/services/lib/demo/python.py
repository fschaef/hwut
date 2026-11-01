"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.demo.python' IS RETIRED (services E-217): the demonstration
         comes with the test writing support of its language, and
         'hwut.support python <dir>' writes both. This face only says so.

Called with anything but '--help', it is refused by name, with that remedy.

EXIT STATUS (E-1, services/_exit.py):
    0  OK       '--help', this page
    2  REFUSED  every other call
______________________________________________________________________________
"""
import sys

from ..cmdline import face_parser, usage_of
from ..._exit  import E_ExitCode

NAME         = "hwut.demo.python"
RETIRED_TEXT = ("'hwut.demo.python' is retired: the demonstration comes with "
                "the test writing support of its language => "
                "'hwut.support python <dir>'")


PARSER = face_parser(NAME, "Retired: says 'hwut.support python <dir>'.",
                     wish_f=False, word_help="the directory once named",
                     word_metavar="<dir>")
USAGE  = usage_of(PARSER, {"word": True})
HELP   = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
         + "\n" + USAGE


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode.OK, for '--help' -- this page.
            E_ExitCode.REFUSED, else -- the retirement said, with its
            remedy.
    """
    write = write or print
    argv  = sys.argv[1:] if argv is None else list(argv)
    if "--help" in argv:
        from ..._core import man_page
        write(man_page(NAME, HELP))
        return E_ExitCode.OK
    write("REFUSED: %s" % RETIRED_TEXT)
    return E_ExitCode.REFUSED


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded(NAME, main))
