"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.demo.python' COMMAND LINE -- a demonstration tree of
         hwut over Python, written where the person says, from any
         installed form (adm/WORK/spec/24-installation-packages.txt).

    hwut.demo.python <dir>

<dir> receives 'hwut-root.conf' and 'TEST/' -- the demonstration of
'demo/python/TEST', its tests and their GOOD files. Then:

    cd <dir>/TEST && hwut --plain

runs green: six test cases, six ok. Nothing outside <dir> is written.

REFUSED where <dir> stands and is not empty: the demonstration lands in
a place of its own, never over what stands.

EXIT STATUS (E-1, services/_exit.py):
    0  OK       the tree written
    2  REFUSED  <dir> missing, not empty or not writable, or the command
                line cannot be read
______________________________________________________________________________
"""
import os
import shutil
import sys

from ..cmdline import face_parser, parse_or_refuse, usage_of
from ..._exit  import E_ExitCode

NAME     = "hwut.demo.python"
LANGUAGE = "python"
SOURCE   = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(
               __file__)), "..", "..", "..", "demo", LANGUAGE, "TEST"))
#  What a run left in the source tree is no part of the demonstration.
LEFT_BEHIND = ("OUT", "TMP", "__pycache__", "hwut-traces*", "hwut.log",
               ".coverage")

PARSER = face_parser(NAME, "Write the demonstration tree over Python.",
                     wish_f=False, word_help="the directory to write",
                     word_metavar="<dir>")
USAGE  = usage_of(PARSER, {"word": True})
HELP   = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
         + "\n" + USAGE


def written(target):
    """
    RETURN: str, the 'TEST' directory written below 'target' -- the
            demonstration's tests and GOOD files, and 'hwut-root.conf'
            beside it -- if success.
    Raises OSError where 'target' cannot be written.
    """
    os.makedirs(target, exist_ok=True)
    test = os.path.join(target, "TEST")
    shutil.copytree(SOURCE, test,
                    ignore=shutil.ignore_patterns(*LEFT_BEHIND))
    #  A WHEEL CARRIES NO MODE BITS: a file that opens with '#!' is a
    #  program, and is made one again.
    for directory, _, name_list in os.walk(test):
        for name in name_list:
            path = os.path.join(directory, name)
            with open(path, "rb") as fh: head = fh.read(2)
            if head == b"#!":
                os.chmod(path, os.stat(path).st_mode | 0o111)
    _documents_repointed(os.path.join(test, "hwut-features.conf"))
    #  THE ROOT IS THE TEMPLATE (services E-25, D-43): the demonstration
    #  stands on the same 'hwut-root.conf' 'hwut.sanitize root' writes,
    #  language table and all -- never on an empty 'hwut { }'.
    from ..._boundary import written as root_written
    root_written(target)
    return test


def _documents_repointed(path):
    """
    RETURN: int, the number of document paths rewritten in the feature
            file 'path' -- every relative one ('../../README.md') made
            absolute as it resolved from the SOURCE directory; 0 where
            the file does not stand.

    A COPY KEEPS ITS REFERENCES (ND1): the paths were relative to
    'demo/python/TEST'; copied elsewhere, 18 of them pointed nowhere.
    """
    import re
    if not os.path.isfile(path): return 0
    with open(path, encoding="utf-8") as fh: text = fh.read()
    count = [0]
    def absolute(match):
        """RETURN: str, the quoted path, absolute from SOURCE."""
        count[0] += 1
        return '"%s"' % os.path.normpath(os.path.join(SOURCE,
                                                      match.group(1)))
    text = re.sub(r'"((?:\.\./)+[^"]*)"', absolute, text)
    with open(path, "w", encoding="utf-8") as fh: fh.write(text)
    return count[0]


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).
    """
    write = write or print
    argv  = sys.argv[1:] if argv is None else list(argv)
    if "--help" in argv:
        from ..._core import man_page
        write(man_page(NAME, HELP))
        return E_ExitCode.OK
    arguments, completion_f = parse_or_refuse(PARSER, argv, write)
    if completion_f:      return E_ExitCode.OK
    if arguments is None or len(arguments.word) != 1:
        if arguments is not None:
            write("REFUSED: '%s' takes one word, the directory to write"
                  % NAME)
        write(USAGE)
        return E_ExitCode.REFUSED
    target = arguments.word[0]
    if os.path.isdir(target) and os.listdir(target):
        write("REFUSED: '%s' is not empty -- name a new directory" % target)
        return E_ExitCode.REFUSED
    if os.path.exists(target) and not os.path.isdir(target):
        write("REFUSED: '%s' stands and is no directory" % target)
        return E_ExitCode.REFUSED
    if not os.path.isdir(SOURCE):
        write("REFUSED: this installation carries no demonstration "
              "('%s' is absent)" % SOURCE)
        return E_ExitCode.REFUSED
    try:
        test = written(target)
    except OSError as error:
        write("REFUSED: '%s' cannot be written: %s" % (target, error))
        return E_ExitCode.REFUSED
    write("WRITTEN: %s -- the demonstration tree over %s"
          % (target, LANGUAGE.capitalize()))
    write("NEXT:    cd %s && hwut --plain" % test)
    return E_ExitCode.OK


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded(NAME, main))
