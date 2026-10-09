# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
"""
hwut.sanitize.apply -- do the commands a file holds, and nothing else.

    hwut.sanitize.apply <file> [--directory=<path>]

THE COMPANION OF 'hwut.sanitize.propose' (services E-125). Propose
writes a file of commands, '<command> <concerned entity>', block by
block under the problem each heals; you read it, put '#' before or
delete what you do not want done; this face does what is left, in the
order written. The entities are read relative to '--directory', the
current directory where none is given -- the directory the proposal
was written in.

THE FILE IS READ WHOLE BEFORE ANYTHING IS DONE. A line that spells no
command -- an unknown verb, an entity of the wrong length -- REFUSES
THE FILE, by line number, and nothing is done: a proposal edited into
nonsense is not half-applied.

NOTHING IS ASKED. The file cannot exist unless somebody read what
would be done, line by line, and deleted what he did not want. THE
READING IS THE CONSENT, so this face takes no '--dont-ask' (E-68):
there is no question for it to suppress. But the file is not trusted: EVERY COMMAND
JUDGES AGAIN before it acts, exactly as 'hwut.sanitize <command>' does,
and what the tree no longer finds insane is refused or has nothing to
do -- a lock whose holder lives by now, an orphan whose choice came
back.

IT REPORTS as 'hwut.accept.apply' does: 'EXECUTION:' with one line per
command, '[DONE]', '[NOTHING]', '[REFUSED]' or '[ERROR]'; then
'REPORT:' with the reason for every one not done; then 'Done <n>/<m>'.
Last, the re-run trigger: every test application of a directory acted
on is touched.

EXIT: OK where every command was done or had nothing to do, FAULT where
one was refused by the tree or failed, REFUSED where the file cannot be
read or holds a line that spells no command, EMPTY where every line is
a comment or blank.
"""
import os
import sys

from vut.services._exit                   import E_ExitCode
from vut.services.lib.sanitize.command    import (CContext, E_Done,
                                                  line_of_text)

BRIEF_WIDTH = 78


def command_list_of(file_name):
    """
    RETURN: [0] list[CCommand], every command the file holds, in order.
            [1] list[str], one refusal per line that spells no command,
                'line <n>: <why>' -- empty where the file reads.

    Raises OSError where the file cannot be read.
    """
    command_list, refusal_list = [], []
    with open(file_name, encoding="utf-8") as fh:
        for line_n, text in enumerate(fh, start=1):
            command = line_of_text(text)
            if command is None: continue                   # the veto
            if isinstance(command, str):
                refusal_list.append("line %d: %s -- '%s'"
                                    % (line_n, command, text.strip()))
            else:
                command_list.append(command)
    return command_list, refusal_list


def write_brief(pair_list, write):
    """
    RETURN: None. The report, in the two sections a run's report wears
            -- rule, heading, rule, content:

        =====...
        EXECUTION:
        -----...
         remove suite/TEST/TMP/session ................... [DONE]
         remove suite/TEST/TMP/lock ....................... [REFUSED]
        =====...
        REPORT:
        -----...
         remove suite/TEST/TMP/lock   the holder (pid 17) lives
        =====...
        Done 1/2

    'pair_list' is (CCommand, CDone). REPORT: appears only where a
    command was not done; what an act SAID stands indented under its
    line.
    """
    rule_hard, rule_soft = "=" * BRIEF_WIDTH, "-" * BRIEF_WIDTH
    write(rule_hard)
    write("EXECUTION:")
    write(rule_soft)
    for command, done in pair_list:
        mark = "[%s]" % done.outcome
        text = " %s " % command.text()
        write("%s%s %s" % (text, "." * max(3, BRIEF_WIDTH - len(text)
                                               - len(mark) - 1), mark))
        for line in done.said_list:
            write("      %s" % line)
    reason_list = [(c, d) for c, d in pair_list if d.outcome != E_Done.DONE]
    if reason_list:
        write(rule_hard)
        write("REPORT:")
        write(rule_soft)
        width = max(len(c.text()) for c, _ in reason_list)
        for command, done in reason_list:
            write(" %-*s  %s" % (width, command.text(), done.reason))
    write(rule_hard)
    write("Done %d/%d" % (sum(1 for _, d in pair_list
                              if d.outcome == E_Done.DONE), len(pair_list)))


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).
    """
    if argv is None:  argv  = sys.argv[1:]
    if write is None: write = print
    if "--help" in argv:
        from vut.services._core import man_page
        write(man_page("hwut.sanitize.apply", __doc__.strip()))
        return E_ExitCode.OK

    file_name, base = None, "."
    for argument in argv:
        if argument.startswith("--directory="):
            base = argument[len("--directory="):]
        elif file_name is None and not argument.startswith("-"):
            file_name = argument
        else:
            write("REFUSED: 'hwut.sanitize.apply' does not take: %s"
                  % argument)
            return E_ExitCode.REFUSED
    if file_name is None:
        write("REFUSED: a file name is required -- the commands to do")
        write("         (write one with 'hwut.sanitize.propose -o <file>')")
        return E_ExitCode.REFUSED
    if not os.path.isdir(base):
        write("REFUSED: the directory '%s' does not exist" % base)
        return E_ExitCode.REFUSED
    try:
        command_list, refusal_list = command_list_of(file_name)
    except (OSError, UnicodeDecodeError) as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    if refusal_list:
        for refusal in refusal_list:
            write("REFUSED: %s" % refusal)
        write("REFUSED: '%s' -- nothing has been done" % file_name)
        return E_ExitCode.REFUSED
    if not command_list:
        write("NOTE: '%s' names no command -- every line is a comment "
              "or blank" % file_name)
        return E_ExitCode.EMPTY

    context   = CContext(base)
    pair_list = [(command, context.execute(command))
                 for command in command_list]
    write_brief(pair_list, write)
    for line in context.touch():
        write(line)
    return E_ExitCode.OK if all(d.good_f() for _, d in pair_list) \
           else E_ExitCode.FAULT


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded("hwut.sanitize.apply", main))
