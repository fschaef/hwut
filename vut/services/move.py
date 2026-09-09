"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.move' COMMAND LINE -- the shorthand of
         'hwut.rename' for the uninitiated (E-46).

    hwut.move <app> <app'> [--yes] [--directory=<path>]

is, word for word,

    hwut.rename <app> -to <app'> [--yes] [--directory=<path>]

and nothing more: two words, the second the fresh name -- a name, a
'<path>/<name>', or an existing directory to move INTO. Everything --
what follows, what is refused, the asking -- is 'hwut.rename''s,
whose module this one calls. See 'rename.py'.
______________________________________________________________________________
"""
import sys

from   .rename import main as rename_main, KEYWORD, USAGE
from   ._exit  import E_ExitCode

#  The licence line and the rule are the FILE's, not the face's.
HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n\n" + USAGE


def main(argv=None, write=None, read_line=None):
    """
    RETURN: E_ExitCode, what 'hwut.rename <app> -to <app'>' returns
            for the two bare words of the line; REFUSED where the
            line carries other than two.

    '--help' is answered HERE: the two-word form is what this face's
    reader needs told.
    """
    if argv is None: argv = sys.argv[1:]
    if "--help" in argv:
        (write or print)(HELP)
        return E_ExitCode.OK
    word_list   = [a for a in argv if not a.startswith("-")]
    option_list = [a for a in argv if a.startswith("-")]
    if len(word_list) != 2:
        (write or print)("REFUSED: 'hwut.move' takes two words -- "
                         "'<app> <app'>' -- and %d stand"
                         % len(word_list))
        (write or print)(USAGE)
        return E_ExitCode.REFUSED
    return rename_main([word_list[0], KEYWORD, word_list[1]] + option_list,
                       write, read_line)


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ._exit import guarded
    sys.exit(guarded("hwut.move", main))
