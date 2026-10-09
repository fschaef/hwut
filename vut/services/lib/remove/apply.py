# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
"""
hwut.remove.apply -- forget what a file names, and nothing else.

    hwut.remove.apply <file> [--directory=<path>]

THE COMPANION OF 'hwut.remove.propose'. Propose writes a file of test
runs that have lost their ground, each headed by why; you read it,
delete or comment out what you want to KEEP; this face forgets what is
left -- nominals, candidates, book entry and register id, exactly as
'hwut.remove' forgets them, one at a time.

    hwut.remove.propose -o r.txt
    <read r.txt, delete or '#' out what you want to keep>
    hwut.remove.apply r.txt

THE FILE: one target per line, '<dir>/<test-app> [<choice>]'. The PATH
is separated from the NAME so a target is forgotten in ITS directory
and nowhere else; '#' and blank lines are skipped, which is the veto.

THE ASKING IS DONE BY THE READING. 'hwut.remove' asks first because
what it forgets cannot be recovered; here the file cannot exist unless
somebody read what would be forgotten, line by line, and deleted what
he wanted kept. So this face hands every line to 'hwut.remove' with
'--dont-ask' (E-68) itself, and takes no such word of its own.

IT REPORTS as 'hwut.accept.apply' does: 'EXECUTION:' with one line per
target, '[DONE]' or '[ERROR]', then 'REPORT:' with one sentence per
failure, then 'Forgotten <n>/<m>'.

EXIT: OK where every named case was forgotten, FAULT where one could
not be, REFUSED where the file could not be read.
"""
import os
import sys

from vut.services                 import remove, accept
from vut.services._exit           import E_ExitCode
from vut.services.lib             import preferences
from vut.engine.display.word      import CInk
from vut.engine.display.console   import colour_decision


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).

    THE FACE IS A SPELLING: the file's targets are read with accept's
    own reader (one format, one reader) and handed to 'remove.main' ONE
    CASE PER CALL, as 'hwut.remove' reads its words (E-53): one word a
    test, two a test and its choice -- with '--dont-ask' (E-68). What
    remove says is captured; what this face says is the column.
    """
    if argv is None:  argv  = sys.argv[1:]
    if write is None: write = print
    if "--help" in argv:
        from vut.services._core import man_page
        write(man_page("hwut.remove.apply", __doc__.strip()))
        return E_ExitCode.OK

    file_name, rest_list = None, []
    for argument in argv:
        if file_name is None and not argument.startswith("-"):
            file_name = argument
        else:
            rest_list.append(argument)
    if file_name is None:
        write("REFUSED: a file name is required -- the test runs to forget")
        write("         (write one with 'hwut.remove.propose -o <file>')")
        return E_ExitCode.REFUSED
    try:
        entry_list = accept.proposal_targets(file_name)
    except OSError as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    if not entry_list:
        write("NOTE: '%s' names no target -- every line is a comment "
              "or blank" % file_name)
        return E_ExitCode.EMPTY

    #  ONE CASE PER CALL (E-53, E-126): 'hwut.remove' reads one word as
    #  a test and two as a test and its choice, and refuses a third.
    brief_list, worst = [], E_ExitCode.OK
    for where, target in entry_list:
        test, _, choice = target.partition(" ")
        choice = choice.strip()
        argv_  = ["--directory=%s" % (where or "."), "--dont-ask", test] \
                 + ([choice] if choice else [])
        said   = []
        code   = remove.main(argv_, write=said.append)
        failed_f = code not in (E_ExitCode.OK, E_ExitCode.EMPTY)
        reason = next((line.strip() for line in said
                       if line.startswith(("REFUSED", "FAULT"))),
                      "not forgotten") if failed_f else None
        brief_list.append(((where or ".", test, choice),
                           accept.ERROR_TEXT if failed_f
                           else accept.DONE_TEXT, reason))
        if failed_f: worst = code

    brief_list.sort()
    accept.write_brief(brief_list, write,
                       CInk(colour_decision(os.environ, sys.stdout.isatty()),
                            color_of=preferences.load().color),
                       verb="Forgotten")
    return worst


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded("hwut.remove.apply", main))
