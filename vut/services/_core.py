"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       WHAT THE SERVICE FACES SHARE -- 'hwut.accept.interactive' (lib/accept/interactive.py) and
       'hwut.run.diff' (diff.py) speak one argument language.

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


USAGE_WIDTH = 78


def usage_line(prefix, token_tuple, width=USAGE_WIDTH):
    """
    RETURN: str, a wrapped usage block -- 'prefix' ('usage: hwut.run'),
            then the tokens, every continuation line aligned under the
            first token.

    A face states its arguments as a tuple and never places its own
    line breaks, so a keyword added to a shared list ('plan/wish.py':
    USAGE_TOKEN_TUPLE) cannot leave another face's usage line stale.
    """
    indent    = " " * (len(prefix) + 1)
    line_list = []
    line      = prefix
    for token in token_tuple:
        if len(line) + 1 + len(token) > width:
            line_list.append(line)
            line = indent + token
        else:
            line = "%s %s" % (line, token)
    line_list.append(line)
    return "\n".join(line_list)


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
    from vut.engine.compare.api import Configuration
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
