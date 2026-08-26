"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.rename-choice' COMMAND LINE -- ONE CHOICE renamed,
         the test's other choices standing.

    hwut.rename-choice <test> <old> <new> [<test> <old> <new>...]
                       [--yes] [--directory=<path>]

The words are read in TRIPLES. Everything else -- what follows the new
name, in what order, what is never touched, the collision refusal, the
asking -- is 'hwut.rename''s, whose module this one calls. See
'rename.py'.
______________________________________________________________________________
"""
import sys

from   .rename import main as rename_main, USAGE
from   ._exit  import E_ExitCode

#  The licence line and the rule are the FILE's, not the face's.
HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n\n" + USAGE


def main(argv=None, write=None, read_line=None):
    """
    RETURN: E_ExitCode, 'hwut.rename' read in the CHOICE FORM: the
            words in triples, one choice renamed per triple.

    '--help' is answered HERE: the triple form is what this face's
    reader needs told, and 'rename.py' would tell them the other one.
    """
    if argv is None: argv = sys.argv[1:]
    if "--help" in argv:
        (write or print)(HELP)
        return E_ExitCode.OK
    return rename_main(argv, write, read_line, choice_form_f=True)


if __name__ == "__main__":
    sys.exit(main())
