"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.remove-choice' COMMAND LINE -- ONE CHOICE forgotten,
         the test's other choices standing.

    hwut.remove-choice <test> <choice> [<test> <choice>...]
                       [--yes] [--directory=<path>]

The words are read in PAIRS. Everything else -- what is forgotten, in
what order, what is never touched, the asking -- is 'hwut.remove''s,
whose module this one calls. See 'remove.py'.
______________________________________________________________________________
"""
import sys

from   .remove import main as remove_main, USAGE
from   ._exit  import E_ExitCode

#  The licence line and the rule are the FILE's, not the face's.
HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n\n" + USAGE


def main(argv=None, write=None, read_line=None):
    """
    RETURN: E_ExitCode, 'hwut.remove' read in the CHOICE FORM: the
            words in pairs, and one choice forgotten per pair.

    '--help' is answered HERE: the pair form is what this face's
    reader needs told, and 'remove.py' would tell them the other one.
    """
    if argv is None: argv = sys.argv[1:]
    if "--help" in argv:
        (write or print)(HELP)
        return E_ExitCode.OK
    return remove_main(argv, write, read_line, choice_form_f=True)


if __name__ == "__main__":
    sys.exit(main())
