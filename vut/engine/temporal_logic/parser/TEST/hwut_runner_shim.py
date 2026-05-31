"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

Minimal HwutRunner stand-in for this standalone delivery.

The real VUT 'HwutRunner' lives at vut.language_support.python.hwut_runner and
parses the test docstring for '--hwut-info'. This shim reproduces only what the
delivered tests use: dispatch of a chosen run-function by name, and a
'--hwut-info' listing built from the title and choice_map. Replace with the
real runner inside the VUT tree.
______________________________________________________________________________
"""
import sys


class HwutRunner:
    """Dispatches one named choice to its run-function, or prints --hwut-info."""
    def __init__(self, argv, title, choice_map):
        """RETURN: None. Holds argv, the suite title, and name->callable map."""
        self.argv       = argv
        self.title      = title
        self.choice_map = choice_map

    def run(self):
        """RETURN: None. Runs the selected choice or prints the info listing.

        With '--hwut-info' prints the title and one line per choice. With a
        choice name runs its function. With no argument lists the choices on
        stderr and exits non-zero.
        """
        args = self.argv[1:]
        if args and args[0] == "--hwut-info":
            print(self.title)
            for name in self.choice_map:
                print(name)
            return
        if not args or args[0] not in self.choice_map:
            sys.stderr.write("choices: %s\n" % ", ".join(self.choice_map))
            sys.exit(1)
        self.choice_map[args[0]]()
