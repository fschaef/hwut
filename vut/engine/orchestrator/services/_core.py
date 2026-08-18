"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       WHAT THE SERVICE FACES SHARE -- 'hwut.merge' (merge.py) and
       'hwut.compare' (compare.py) speak one argument language.

DESCRIPTION
       The two mini-apps are HOMOGENEOUS by design: same stream
       arguments ('-' is stdin), same compare-SETUP flags, same
       renderer underneath. What they share lives here, once.

       THE SETUP FLAGS cover the setup an author reaches for at the
       command line:

           --numeric RATIO      numeric tolerance, relative [0..1]
           --pattern REGEX      an equivalence pattern (repeatable)
           --nothing PATTERN    a visible-nothing pattern (repeatable)

       Richer setups -- constraints, region parameters, marker changes
       -- belong to a test's OWN compare configuration (README 3), not
       to command-line flags; a service run inside a test run receives
       that Configuration object directly.
______________________________________________________________________________
"""
import io
import sys


def read_source(path):
    """
    RETURN: str, the stream behind 'path' -- the file's content, or
            stdin's when 'path' is '-'.
    """
    if path == "-":
        return sys.stdin.read()
    with io.open(path, "r", encoding="utf-8") as file_handle:
        return file_handle.read()


def add_setup_arguments(parser):
    """
    RETURN: None. Adds the shared compare-SETUP flags to 'parser' --
            one place, so the two faces cannot drift apart.
    """
    parser.add_argument("--numeric", type=float, default=None,
                        metavar="RATIO",
                        help="numeric tolerance, relative [0..1] "
                             "(default: the setup's own, 0 = exact)")
    parser.add_argument("--pattern", action="append", default=None,
                        metavar="REGEX",
                        help="an equivalence pattern: two elements "
                             "matching it are equivalent (repeatable)")
    parser.add_argument("--nothing", action="append", default=None,
                        metavar="PATTERN",
                        help="a visible-nothing pattern: a matching "
                             "element reads as nothing (repeatable)")


def setup_from_arguments(arguments):
    """
    RETURN: Configuration, compare's setup with the shared flags
            applied; the plain default setup when none was given.
    """
    from ...compare.configuration import Configuration
    configuration = Configuration()
    if arguments.numeric is not None:
        configuration.pattern_finder.numeric_tolerance_ratio = \
                                                        arguments.numeric
    if arguments.pattern is not None:
        configuration.pattern_finder.equivalent_pattern_list = \
                                                        list(arguments.pattern)
    if arguments.nothing is not None:
        configuration.pattern_finder.visible_nothing_pattern_list = \
                                                        list(arguments.nothing)
    return configuration
