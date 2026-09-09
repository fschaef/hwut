"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.pype' COMMAND LINE -- the pype line-matching filter,
         as a face over 'test_writing_support/hwut_pype'.

    hwut.pype [--trace|--trace-plain] [--pype-dir DIR ...] SCRIPT [INPUT ...]
    hwut.pype --example SCRIPT
    hwut.pype --dry-run SCRIPT

The interpreter owns the language: its parser, its modes, its trace, its
usage line. This face owns the DOOR -- what the shell reads as the whole
verdict -- and nothing else. It reads no option the interpreter reads;
it decides only whether a script was named, and what the interpreter's
answer means in the exit status law.

A '#! /usr/bin/env hwut.pype' she-bang line reaches this face by PATH:
the kernel passes the script path as the first argument, the piped data
arrives on stdin. 'sys.exit(n)' inside a python block of the script
leaves through the interpreter untouched.

EXIT STATUS (E-1, services/_exit.py):
    0  OK       the script ran to completion; '--help' answered
    1  FAULT    the script does not parse, an input file cannot be
               read, or the interpreter reports a fault
    2  REFUSED  no argument names a script that exists, or '--pype-dir'
               stands last with no directory after it
______________________________________________________________________________
"""
import os
import sys

from   vut.services._exit                            import E_ExitCode
from   vut.test_writing_support.hwut_pype.hwut_pype  import USAGE
from   vut.test_writing_support.hwut_pype.hwut_pype  import main \
                                                     as interpreter_main

PROGRAM_NAME = "hwut.pype"


def main(argv, write=print):
    """RETURN: E_ExitCode, OK if the script ran to completion, or '--help'
                           was answered through 'write'.
                           FAULT if the script does not parse, or an input
                           file cannot be read, or the interpreter reports a
                           fault through its own exit.
                           REFUSED if no argument names an existing file
                           (nothing to run), or '--pype-dir' stands last
                           with no directory after it.

    'argv' is the command line without the program's own name. Everything
    but '--help', the presence of a script and a dangling '--pype-dir' is
    handed to the interpreter unchanged, so the interpreter's reading of
    its own options stays the one reading there is; what it refuses at
    the door is a FAULT here, since this face does not read it twice.
    """
    if any(arg in ("-h", "--help") for arg in argv):
        for line in USAGE.split("\n"):
            write(line)
        return E_ExitCode.OK

    if not any(os.path.isfile(arg) for arg in argv):
        print(USAGE, file=sys.stderr)
        return E_ExitCode.REFUSED

    if argv[-1] == "--pype-dir":
        print("pype: --pype-dir requires a directory", file=sys.stderr)
        return E_ExitCode.REFUSED

    status = interpreter_main([PROGRAM_NAME] + list(argv))
    if status == 0: return E_ExitCode.OK
    else:           return E_ExitCode.FAULT


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ._exit import guarded
    sys.exit(guarded("hwut.pype", main, sys.argv[1:]))
