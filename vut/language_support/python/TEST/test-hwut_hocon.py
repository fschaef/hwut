#! /usr/bin/env python3
#
# hwut {
#     title      = "HOCON parser: subset (A), annotated tree"
#     choices    = ["comments", "faults", "numbers", "oneline",
#                   "positions", "quoting", "refused", "scalars",
#                   "structure"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: The HOCON parser against HOCON alone -- no exploration vocabulary
         appears anywhere in this file.

CHOICES: scalars, numbers, quoting, structure, oneline, comments,
         refused, faults, positions;

DESCRIPTION:

scalars    quoted strings with escapes, integers, floats, booleans,
           the spellings of nothing; a value left empty is null.

numbers    every radix, and '_' anywhere between digits as a visual
           helper carried into no value: decimal with sign and
           exponent, hexadecimal, binary, octal, and roman. A sign may
           stand apart from its digits. What spells no number in any
           radix is a string, and a string carries quotes.

quoting    A STRING VALUE IS WRITTEN IN DOUBLE QUOTES. An unquoted
           word that is no bare token is refused, and the message
           shows the word in the quotes it wants. A bare token ends
           at a blank, so no value ever runs into a comment marker or
           into the next key.

structure  nested objects, the brace directly after a key, lists with
           comma and with newline separation, objects inside lists.

oneline    several entries on one line without commas: a bare value
           runs into the next key's binder and gives the key back.

comments   '#' and '//', whole-line and trailing; a comment never
           becomes content.

refused    'include', '${...}', '+=', and triple-quoted strings -- each
           refused BY NAME, never silently misread.

faults     duplicate keys, unterminated strings, unmatched and missing
           braces; the parse completes and reports them all at once.

positions  every key and value knows its file-relative place, offsets
           included -- the line and column an editor shows.
______________________________________________________________________________
"""
import sys
from config import HwutRunner                                # noqa: F401

from vut.language_support.python.hwut_hocon import (parse, SourceLine,
                                                      ScalarNode, ListNode,
                                                      ObjectNode)


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def lines(text, line_offset=0, column_offset=0):
    """RETURN: list[SourceLine], 'text' split, offsets applied
    uniformly."""
    return [SourceLine(line, i + line_offset, column_offset)
            for i, line in enumerate(text.split("\n"), start=1)]


def show(node, indent=0):
    """RETURN: None. Prints the annotated tree, positions included."""
    pad = "    " * indent
    if isinstance(node, ObjectNode):
        print("%s{ at %s" % (pad, node.position))
        for entry in node.entry_list:
            print("%s  key '%s' at %s ->"
                  % (pad, entry.key, entry.key_position))
            show(entry.node, indent + 1)
        print("%s}" % pad)
    elif isinstance(node, ListNode):
        print("%s[ at %s" % (pad, node.position))
        for item in node.item_list:
            show(item, indent + 1)
        print("%s]" % pad)
    else:
        print("%s%r (%s) at %s"
              % (pad, node.value, type(node.value).__name__,
                 node.position))


def run(label, text, line_offset=0, column_offset=0):
    """RETURN: None. Parses 'text' and prints tree and faults."""
    banner(label)
    document, fault_list = parse(
        lines(text, line_offset, column_offset), "f.hocon")
    show(document)
    for fault in fault_list:
        print("FAULT %s" % fault)


def test_scalars():
    """RETURN: None. Every scalar shape."""
    run("scalars",
        'a = bare\n'
        'b = "quoted \\"x\\" and \\n"\n'
        'c = 42\n'
        'd = -3.14\n'
        'e = 1e-6\n'
        'f = true\n'
        'g = no\n'
        'h = make %.exe\n'
        'i: "colon-bound"\n'
        'j = null\n'
        'k = nihil\n'
        'l =\n')


def test_numbers():
    """RETURN: None. Every radix, the helper, and the split sign."""
    run("decimal, with sign and exponent",
        'a = 42\n'
        'b = -0.12\n'
        'c = +7e212\n'
        'd = 6.02e23\n'
        'e = .5\n')
    run("the visual helper enters no value",
        'a = 1_000\n'
        'b = 7_000.5_5\n')
    run("hexadecimal, binary, octal",
        'a = 0xDEAD_BEEF\n'
        'b = 0b0111_11_01\n'
        'c = 0o3124\n'
        'd = 0XFF\n'
        'e = -0b1010\n')
    run("roman",
        'a = 0rIV\n'
        'b = 0rMCMLXXXIV\n'
        'c = -0rX\n')
    run("a sign standing apart from its digits",
        'a = - 0.12\n'
        'b = + 7\n'
        'c = - 0xFF\n')
    run("what spells no number is a string, and carries quotes",
        'a = 1.2.3\n'
        'b = 0x\n'
        'c = 0b012\n'
        'd = 1__0\n'
        'e = 0rIIII\n'
        'f = 0rVX\n')
    run("no arithmetic: this language computes nothing",
        'a = 5 - 1\n')


def test_quoting():
    """RETURN: None. The quoted string, and the unquoted word."""
    run("quoted: blanks, comment markers and binders are content",
        'a = "make %.exe"\n'
        'b = "not # a comment"\n'
        'c = "x = y"\n'
        'd = "yes"\n')
    run("unquoted: refused, and shown in the quotes it wants",
        'a = make\n'
        'b = strip.pype\n'
        'c = [one, two]\n'
        'd = 1\n')


def test_structure():
    """RETURN: None. Objects, lists, nesting."""
    run("nesting and key-brace",
        'outer {\n'
        '    inner = { deep = 1 }\n'
        '    braced { x = 2 }\n'
        '}\n')
    run("lists",
        'commas   = [one, two, three]\n'
        'newlines = [\n'
        '    1\n'
        '    2\n'
        ']\n'
        'objects  = [ { a = 1 }, { a = 2 } ]\n'
        'empty    = []\n')


def test_oneline():
    """RETURN: None. Entries sharing a line, without commas."""
    run("two entries, one line, no comma",
        'caps { timeout_sec = 30  network = false }\n')
    run("a quoted value with blanks, beside a following key",
        'a { build = "make %.exe"  timeout_sec = 5 }\n')
    run("three entries, one line",
        'x { a = 1  b = "two"  c = { d = 3 } }\n')


def test_comments():
    """RETURN: None. Both comment forms, whole-line and trailing."""
    run("comments",
        '# whole line\n'
        'a = 1   # trailing\n'
        '// slashes too\n'
        'b = 2   // trailing slashes\n'
        'c = bare value # comment cut\n')


def test_refused():
    """RETURN: None. The four constructs that do not exist here."""
    run("refused, each by name",
        'include "other.conf"\n'
        'a = ${outside.value}\n'
        'b += appended\n'
        'c = """triple"""\n'
        'd = survives\n')


def test_faults():
    """RETURN: None. Faults accumulate; the parse completes."""
    run("faults accumulate",
        'a = 1\n'
        'a = 2\n'
        'b = "unterminated\n'
        '}\n'
        'c {\n'
        '    d = 3\n')


def test_positions():
    """RETURN: None. Offsets carried: the same text reported at its
    place in a larger file, as an unwrapped header would be."""
    text = ('hwut {\n'
            '    title = "T"\n'
            '}')
    run("plain: as its own file", text)
    run("offset: same text, region begins at line 40, 3 columns "
        "stripped", text, line_offset=39, column_offset=3)


if __name__ == "__main__":
    HwutRunner(sys.argv, "HOCON parser: subset (A), annotated tree;", {
        "scalars":   test_scalars,
        "numbers":   test_numbers,
        "quoting":   test_quoting,
        "structure": test_structure,
        "oneline":   test_oneline,
        "comments":  test_comments,
        "refused":   test_refused,
        "faults":    test_faults,
        "positions": test_positions,
    }).run()
