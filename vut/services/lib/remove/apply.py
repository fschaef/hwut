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

'--yes' IS IMPLICIT. 'hwut.remove' asks first because what it forgets
cannot be recovered; here the file cannot exist unless somebody read
what would be forgotten, line by line, and deleted what he wanted
kept. THE READING IS THE CONSENT.

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
from vut.engine.display.word      import CInk
from vut.engine.display.console   import colour_decision


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).

    THE FACE IS A SPELLING: the file's targets are read with accept's
    own reader (one format, one reader), grouped by directory, and
    handed to 'remove.main' per directory -- the choice-less ones in
    the plain form, the others in the '<test> <choice>' form -- with
    '--yes'. What remove says is captured; what this face says is the
    column.
    """
    if argv is None:  argv  = sys.argv[1:]
    if write is None: write = print
    if "--help" in argv:
        write(__doc__.strip())
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

    #  GROUPED BY DIRECTORY, then by form: remove takes one directory
    #  per call and reads its words in one of two shapes.
    group_db = {}
    for where, target in entry_list:
        test, _, choice = target.partition(" ")
        group_db.setdefault(where or ".", []).append((test, choice.strip()))

    brief_list, worst = [], E_ExitCode.OK
    for where, case_list in sorted(group_db.items()):
        plain  = [t for t, c in case_list if not c]
        paired = [(t, c) for t, c in case_list if c]
        for word_list, choice_form_f in ((plain, False), (paired, True)):
            if not word_list: continue
            argv_ = ["--directory=%s" % where, "--yes"]
            argv_ += [w for pair in word_list
                      for w in (pair if choice_form_f else (pair,))]
            said = []
            code = remove.main(argv_, write=said.append,
                               choice_form_f=choice_form_f)
            failed_f = code not in (E_ExitCode.OK, E_ExitCode.EMPTY)
            reason = next((line.strip() for line in said
                           if line.startswith(("REFUSED", "FAULT"))),
                          "not forgotten") if failed_f else None
            for pair in word_list:
                test, choice = pair if choice_form_f else (pair, "")
                brief_list.append(((where, test, choice),
                                   accept.ERROR_TEXT if failed_f
                                   else accept.DONE_TEXT, reason))
            if failed_f: worst = code

    brief_list.sort()
    accept.write_brief(brief_list, write,
                       CInk(colour_decision(os.environ, sys.stdout.isatty())),
                       verb="Forgotten")
    return worst


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded("hwut.remove.apply", main))
