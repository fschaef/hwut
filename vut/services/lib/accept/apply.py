# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
"""
hwut.accept.apply -- bless what a file names, and nothing else.

    hwut.accept.apply <file> [--directory=<path>]

THE COMPANION OF 'hwut.accept.propose'. Propose writes a file of
targets, each headed by the difference accepting it would make; you
read it, delete or comment out what you disagree with; this face
blesses what is left.

    hwut.run                              produce the candidates
    hwut.accept.propose -o p.txt 5        write what could be blessed
    <read p.txt, delete or '#' out what you disagree with>
    hwut.accept.apply p.txt               bless what is left

-------------------------------------------------------------------
THE FILE
-------------------------------------------------------------------
One target per line:

    <dir>/<test-app> <choice>

The PATH is separated from the NAME, so a target is matched in ITS
directory and nowhere else, and one file spans the whole tree. A
line whose first non-blank character is '#' is SKIPPED, and so is a
blank one -- which is the whole of the format, and how a reader
vetoes. Everything 'hwut.accept.propose' writes above a target is a
comment, so its output is this face's input unedited.

-------------------------------------------------------------------
IT ASKS NOTHING
-------------------------------------------------------------------
THE WORD IS THE TREE'S OWN. 'hwut.sanitize' reports by default and
acts on '--apply'; this face is the same relation under the same word
-- propose says what would happen, apply makes it happen.

'hwut.accept' asks twice before it overwrites a standing nominal: for
'--force', because that is a CHANGE to the thing every later run is
judged against, and then per key, because a person at a terminal may
not have meant it. NEITHER QUESTION HAS ANYTHING LEFT TO ASK HERE.
The file cannot exist unless somebody read the change: propose writes
no target it has not shown, line by line, and you handed the file
back having deleted what you refused. THE READING IS THE CONSENT --
and the editing is the answer to every per-key question, given in
advance and in writing.

So '--force' and '--yes' are both implicit, and neither is offered.
A face that asked again would be asking a reader to confirm what he
had already written down.

-------------------------------------------------------------------
WHAT IT REPORTS
-------------------------------------------------------------------
TWO SECTIONS, in the style a run's report wears -- rule, heading,
rule, content:

    ==========================================================
    EXECUTION:
    ----------------------------------------------------------
     engine/display/TEST
        test-plain.py allgreen ....................  [DONE]
                      words .......................  [DONE]
        test-run.sh   green .......................  [DONE]
     services/TEST
        test-sanitize.sh lock ..................... [ERROR]
    ==========================================================
    REPORT:
    ----------------------------------------------------------
     services/TEST
        test-sanitize.sh lock  missing terminating <hwut-end>
    ==========================================================
    Accepted 3/4

GROUPED AS A RUN GROUPS: the directory once, its cases under it, and a
test application written once however many of its choices stand below
-- the eye reads the choices as belonging to the name above them.
REPORT: wears the shape of a run's HINTS.

The verdicts are RIGHT-ALIGNED -- '[DONE]' and '[ERROR]' END in one
column -- and where a terminal takes colour THE VERDICT ALONE wears
it: green for the one, the same red '[FAIL]' wears for the other. Not
the name, not the dots: a green field the width of the line would say
'this line is good' where what is good is the OUTCOME. So the failures
are found without reading. REPORT: appears only where something
failed, one sentence apiece; 'hwut.tell <test-app> <choice>' has the
rest.

THE REFRESH IS SILENT HERE. A case whose recording is stale is re-run
before it is judged, as always, but this face does not say so: the
verdict says what became of the case, which is what was asked.

EVERY LINE OF THE FILE IS ANSWERED, including a target that matched
nothing -- a name misspelt, a test since removed, a directory not
under this root. A file of fifty targets reads as a column of fifty
verdicts; a paragraph of explanation after each would bury the one
that matters, and 'hwut.tell <test-app> <choice>' has the rest.

-------------------------------------------------------------------
OPTIONS
-------------------------------------------------------------------
    <file>              the targets to bless. Required.
    --directory=<path>  one directory; the whole tree otherwise.
    --help              this text.

EXIT: as 'hwut.accept' -- OK where every named key was blessed, EMPTY
where the file named no target, FAULT where a key was refused,
REFUSED where the file could not be read.
"""
import sys

from vut.services         import accept
from vut.services._exit   import E_ExitCode


def main(argv=None, write=None, read_line=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).

    THE FACE IS A SPELLING, NOT A SECOND ENGINE: the file name is read
    off the command line and handed to 'accept.main' as its
    'script_name', with '--force' and '--yes' added -- the reader
    answered both questions when he edited the file. Every other word
    travels untouched, so '--directory' and the wish mean here exactly
    what they mean there.
    """
    if argv is None:  argv  = sys.argv[1:]
    if write is None: write = print
    if "--help" in argv:
        write(__doc__.strip())
        return E_ExitCode.OK

    #  THE FIRST WORD THAT IS NOT AN OPTION IS THE FILE.
    file_name, rest_list = None, []
    for argument in argv:
        if file_name is None and not argument.startswith("-"):
            file_name = argument
        else:
            rest_list.append(argument)
    if file_name is None:
        write("REFUSED: a file name is required -- the targets to bless")
        write("         (write one with 'hwut.accept.propose -o <file>')")
        return E_ExitCode.REFUSED

    #  NOTHING IS ASKED: the reader saw every change the file proposes
    #  and deleted what he refused, so the standing nominal may be
    #  overwritten ('--force') and no key needs confirming ('--yes').
    return accept.main(rest_list + ["--force", "--yes"], write=write,
                       read_line=read_line, script_name=file_name,
                       brief_f=True)


if __name__ == "__main__":
    sys.exit(main())
