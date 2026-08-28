"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Turn the raw region into lines the HOCON parser reads, each line
         carrying the offsets that make every parser position FILE-RELATIVE.

The line record is the PARSER's ('SourceLine'); the knowledge of comment
leaders is HWUT's and stays here. A HOCON parser has no business knowing
that a specification may live inside a C comment.

The region's first line begins at the marker, THE '@' DROPPED: the '@'
is the sigil that FINDS the block in a foreign file, not a part of the
block's own grammar. What reaches the parser reads 'hwut { ... }' in a
source file exactly as it does in a '.conf', so one validator and one
vocabulary serve both. The column offset accounts for the dropped
character, so every parser position stays file-relative. The lines after it share a comment leader -- ' * ', '# ',
'-- ' -- which is their longest common leading prefix. The prefix is
DISCOVERED over those lines, never known from a table; whitespace-only lines
take no part in the discovery and lose at most the prefix's length.

The last line ends at the matching brace; a trailing comment closer after it
(' */') lies outside the region and needs no tolerance of its own.
______________________________________________________________________________
"""
from vut.language_support.python.hwut_hocon import SourceLine


def unwrap(text, region):
    """
    RETURN: list[SourceLine], the region's lines, prefixes stripped,
            offsets carried.

    'text' is the file's raw content; 'region' a detector Region in it.
    """
    #  THE '@' IS DROPPED HERE, and nowhere else: 'region.i_marker'
    #  keeps pointing at it, so a fault names the marker as a person
    #  sees it.
    raw = text[region.i_marker + 1 : region.i_close + 1]
    line_list = raw.split("\n")

    if len(line_list) == 1:
        return [SourceLine(line_list[0], region.line, region.column)]

    prefix = _common_prefix(line_list[1:])
    result = [SourceLine(line_list[0], region.line, region.column)]
    for i, line in enumerate(line_list[1:], start=1):
        n = min(len(prefix), len(line)) if not line.strip() else len(prefix)
        result.append(SourceLine(line[n:], region.line + i, n))
    return result


#  Characters a comment leader cannot contain: where the common prefix
#  reaches one, it has reached CONTENT and is capped there. Keeps '#',
#  '*', '-', '/', ';' and blanks -- the leaders that occur -- while a
#  brace, bracket, quote, letter or digit ends the leader.
_CONTENT_CHARACTER_SET = set('{}[]="\'')


def _common_prefix(line_list):
    """
    RETURN: str, the longest common leading prefix of the lines that carry
            content, capped before the first content character; '' where
            nothing is shared.

    Whitespace-only lines take no part.
    """
    content_list = [line for line in line_list if line.strip()]
    if not content_list: return ""

    prefix = content_list[0]
    for line in content_list[1:]:
        while not line.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix: return ""

    for i, c in enumerate(prefix):
        if c.isalnum() or c in _CONTENT_CHARACTER_SET:
            return prefix[:i]
    return prefix


def plain_lines(text):
    """
    RETURN: list[SourceLine], the whole text as lines with identity
            offsets -- the entry for 'hwut.conf', whose file IS the text.
    """
    return [SourceLine(line, i, 0)
            for i, line in enumerate(text.split("\n"), start=1)]
