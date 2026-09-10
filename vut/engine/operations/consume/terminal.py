"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE TERMINAL TOKEN (R-70) -- '<hwut-end>' as the last
         non-empty line of a subject stream says: THE STREAM IS
         COMPLETE, by the testimony of whoever ends it.

WHO ENDS A STREAM:
    a PYPE-D stream        the pype script, from its '<eof>' handler
                           -- the test application MUST NOT produce
                           the token (it cannot place it safely) and
                           never has to; an absent token criticises
                           the PYPE SCRIPT (hwut_pype MANUAL).
    a PLAIN stream         the application itself; HwutRunner, the
                           reference implementation, emits it as a
                           choice's last act.

THE NOMINAL DECIDES PARTICIPATION: where the nominal ends in the
token, the subject must; where it does not, no check stands -- the
migration needs no switch, no key, anywhere ('hwut.renovate' appends
tokens to nominals).

The token is CONTENT: compared, stored, displayed; the compare
framework knows no plumbing. Completeness and CONTAINMENT are
orthogonal: the token is the stream's testimony, 'killed' is the
killer's (procsitter); neither substitutes for the other.
______________________________________________________________________________
"""

TERMINAL_TOKEN = "<hwut-end>"


def ends_in_terminal(reader):
    """
    RETURN: bool, whether the stream's last NON-EMPTY line is the
            terminal token -- trailing blank lines after it carry no
            information and are forgiven.

    The reader is consumed and closed.
    """
    last = None
    try:
        for line in reader:
            stripped = line.rstrip("\r\n")
            if stripped: last = stripped
    finally:
        close = getattr(reader, "close", None)
        if close is not None: close()
    return last == TERMINAL_TOKEN


#  THE UNACCEPTED REGION (compare C-9): '##! unaccepted' opens a stretch
#  nobody has judged. The '!' is what makes it a region and not a
#  comment; the name is read as the scanner reads a shebang -- the
#  first word after '##!', case as written.
def carries_unaccepted_f(reader):
    """
    RETURN: bool, whether the stream opens an 'unaccepted' region
            anywhere -- a line '##! unaccepted' (optionally followed by
            parameters). The reader is consumed and closed.
    """
    try:
        for line in reader:
            stripped = line.strip()
            if not stripped.startswith("##!"): continue
            word_list = stripped[3:].split()
            if word_list and word_list[0] == "unaccepted": return True
        return False
    finally:
        close = getattr(reader, "close", None)
        if close is not None: close()
