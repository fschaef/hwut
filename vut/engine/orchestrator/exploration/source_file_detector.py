"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Find the specification region in a source file's raw text.

The region opens at the FIRST occurrence of '@hwut' followed by a brace,
at any position in the file, and closes at the matching brace. No table
of comment syntaxes exists; the text is scanned as it stands.

THE '@' IS PART OF THE MARKER. A bare '@hwut {' occurs in prose, in a
README, in a shell line that calls the tool -- and every such occurrence
would open a region and make the file a test application by accident.
The '@' costs one character and ends the question.

THE '.conf' FILES ARE NOT SOURCE FILES and keep their bare '@hwut {':
they are read whole ('reader.read_conf'), never scanned for a region,
so nothing there can be mistaken for anything else.

The brace matching skips double-quoted strings. A brace inside a HOCON
comment within the region can end the region early; the parse then fails
loudly and 'hwut.parse' shows where.
______________________________________________________________________________
"""
import re

from dataclasses import dataclass

_MARKER_RE = re.compile(r"@hwut\s*\{")

#  THE HEAD OF A FILE (E-95): the marker is a source file's DECLARATION,
#  and a declaration stands at the top. MEASURED across the tree: every
#  test application's marker sits within its first four lines, as the
#  first word of a comment. So the marker is looked for in the first
#  HEAD_LINE_N lines only, and it must be the first word of its line
#  after blanks and a comment lead (#, //, --, ;, *, /*). A file that
#  QUOTES a header deeper in -- a 'script' log of a screen, a README, a
#  mail -- was measured to become a test called by the file's name.
HEAD_LINE_N = 8
_LEAD_RE    = re.compile(r"^[ \t]*(?:#+|//|--|;+|\*+|/\*)?[ \t]*@hwut\s*\{", re.M)


@dataclass(frozen=True, slots=True)
class Region:
    """The specification region inside a file's raw text."""
    i_marker: int     # index of '@' of '@hwut'
    i_open:   int     # index of the opening brace
    i_close:  int     # index of the matching closing brace
    line:     int     # 1-based line of the marker
    column:   int     # 1-based column of the marker


def detect(text):
    """
    RETURN: Region, the specification region if the marker is present and
                    its brace has a match.
            None,   else -- the file is not a test application.
    """
    head  = "".join(text.splitlines(True)[:HEAD_LINE_N])
    match = _LEAD_RE.search(head)
    if match is None: return None
    match = _MARKER_RE.search(text, match.start())

    i_marker = match.start()
    i_open   = match.end() - 1
    i_close  = _matching_brace(text, i_open)
    if i_close is None: return None

    line   = text.count("\n", 0, i_marker) + 1
    column = i_marker - (text.rfind("\n", 0, i_marker) + 1) + 1
    return Region(i_marker, i_open, i_close, line, column)


def _matching_brace(text, i_open):
    """
    RETURN: int,  index of the brace matching the one at 'i_open'.
            None, no match before the end of the text.

    Double-quoted strings are skipped; a backslash escapes inside them.
    """
    depth = 0
    i     = i_open
    n     = len(text)
    while i < n:
        c = text[i]
        if   c == '"':
            i += 1
            while i < n and text[i] != '"':
                if text[i] == "\\": i += 1
                i += 1
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0: return i
        i += 1
    return None
