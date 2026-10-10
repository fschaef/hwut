"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.affected' -- THE SERVICE FACE: a change goes in, the test
         runs that executed it come out.

    hwut.affected [--cov-dir DIR | --records DIR] [--diff FILE|-]
                  [-p N] [-b|--bare]

       SHALLOW WIRING. The face itself is the coverage component's
       ('engine/coverage/affected.py', reached through its door); this
       module gives it the services' guard and the launcher a module to
       name ('bin/hwut.affected').
______________________________________________________________________________
"""
import sys

from vut.engine.coverage.api import affected_main
from vut.services._exit      import guarded


HELP_STR = """\
hwut.affected -- a change goes in, the test runs that executed it come
out: read from the output of 'hwut.cov.run'.

usage: hwut.affected [--cov-dir DIR] [--diff FILE|-] [-p N] [-b|--bare]

    --cov-dir DIR     the output directory of 'hwut.cov.run'; unstated,
                      './hwut.coverage'. ('--records DIR': a directory of
                      kept per-case records instead.)
    --diff FILE|-     the change, a unified diff made at the root the
                      coverage run walked; unstated or '-', stdin
    -p N              leading path components to strip, as 'patch -p';
                      1 where unstated ('git diff' writes 'a/', 'b/')
    -b, --bare        the runs alone, as wishlist lines; the note goes to
                      stderr:  hwut.affected -b > w.txt
                               hwut.run --wishlist w.txt

The runs named CERTAINLY executed the changed lines. A run absent may
still be affected. Exit: 0 runs named; 3 none; 2 refused.
"""


def main(argv=None):
    """
    RETURN: int, the exit code of 'hwut.affected': 0, runs are named;
            3, nothing executed the change; 2, the request cannot be
            answered -- no coverage output, an unreadable diff, an
            unknown word.
    """
    if argv is None: argv = sys.argv[1:]
    if "--help" in argv or "-h" in argv:
        from vut.services._core import man_page
        print(man_page("hwut.affected", HELP_STR))
        return 0
    return affected_main(["hwut.affected"] + list(argv))


if __name__ == "__main__":
    sys.exit(guarded("hwut.affected", main))
