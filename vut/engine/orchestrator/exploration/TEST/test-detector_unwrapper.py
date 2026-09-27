#! /usr/bin/env python3
#
# @hwut {
#     title      = "Detector and unwrapper: no comment syntax known"
#     choices    = ["blank", "dash", "decoration", "detect", "hash", "head",
#                   "offsets", "single", "star"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: The detector and the unwrapper -- finding the region without
         knowing any language's comment syntax, and stripping the
         discovered leader while carrying the offsets.

CHOICES: detect, star, hash, dash, single, blank, offsets, head, decoration;

DESCRIPTION:

detect     the marker found at its first occurrence, anywhere; a file
           without one is not a test application; 'hwut' as a mere word
           (no brace) does not detect; a brace inside a quoted string
           does not end the region.

star       C block comment style, ' * ' leader, trailing '*/' after the
           closing brace lying outside the region.

hash       shell/python style, '# ' leader -- and a HOCON comment INSIDE
           the region surviving the strip.

dash       lua style, '-- ' leader.

single     a single-line region, and a region whose closer is the only
           line after the opener -- the leader must never eat the brace.

blank      a blank line inside the region takes no part in the prefix
           discovery and breaks nothing.

offsets    each unwrapped line names its file line and its stripped
           column count -- the numbers an error message will use.

decoration X-DECORATION: whatever stands before '@hwut {' on its line --
           up to two tokens, each at most 8 characters and without a
           digit, the last glued to the marker unless it is a quote -- is
           the decoration, and is stripped from every following line.
           No language is known: every comment style of the languages
           listed (Frank-Rene, 2026-09-27) is read, as a line comment
           and as a block comment with its opener on the marker's line
           or on the line before; and what must stay out stays out.
______________________________________________________________________________
"""
import sys
from config import HwutRunner                                # noqa: F401

from vut.engine.orchestrator.exploration.source_file_detector import detect
from vut.engine.orchestrator.exploration.unwrapper         import unwrap


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def show(text):
    """RETURN: None. Detects and unwraps 'text'; prints every line with
    its offsets."""
    region = detect(text)
    if region is None:
        print("no region")
        return
    print("marker at %d:%d" % (region.line, region.column))
    for line in unwrap(text, region):
        print("line %2d  stripped %d  |%s|"
              % (line.line, line.column_offset, line.text))


def test_detect():
    """RETURN: None. Presence, absence, word-only, brace in string."""
    banner("found, first occurrence")
    show("code code\n/* @hwut { title = \"T\" } */\nmore code\n")
    banner("absent")
    show("no marker anywhere\n")
    banner("the word alone, no brace")
    show("this line mentions hwut in prose\nreal code\n")

    banner("a BARE 'hwut {' is not a marker")
    #  THE '@' IS PART OF THE MARKER: a bare 'hwut {' occurs in
    #  prose, in a README, in a shell line that calls the tool, and
    #  every such occurrence would otherwise make the file a test
    #  application by accident.
    show('# the config block reads  hwut { title = "T" }\ncode\n')
    banner("a brace inside a string does not close the region")
    show('# @hwut {\n#     title = "closer } inside"\n# }\n')


def test_head():
    """RETURN: None. E-95, a REGRESSION: the marker is a declaration and
               stands in the file's HEAD, first word of its line after a
               comment lead. Reported: a 'script' log ('typescript') in
               a TEST directory, recording a screen that showed a test's
               header, became the test 'typescript' in 'hwut.report'."""
    banner("the reported file: a 'script' log quoting a header deep in")
    show("Script started on 2026-09-16 22:39:54+02:00 [COMMAND=\"hwut.accept\"]\n"
         + "\x1b[?1049h screen noise\n" * 6
         + "    #! /bin/bash\n    # @hwut { title = \"basic\" }\n    echo hi\n"
         + "Script done on 2026-09-16 22:40:49+02:00\n")
    banner("a header in the first lines, but INSIDE prose: not a marker")
    show("see the header:  @hwut { title = \"q\" }\n")
    banner("a header in a string: not a marker")
    show('print("@hwut { title = 1 }")\n')
    banner("every lead the tree uses, in the head: a marker")
    for lead in ("#", "//", "--", ";", "*", "/*"):
        show("%s @hwut { title = \"T\" }\n" % lead)
    banner("the marker after a shebang and a blank comment line")
    show("#! /usr/bin/env python3\n#\n# @hwut {\n#     title = \"T\"\n# }\n")
    banner("the marker on line 9: past the head, not a marker")
    show("# a\n" * 8 + "# @hwut { title = \"late\" }\n")


def test_star():
    """RETURN: None. ' * ' leader; '*/' outside the region."""
    banner("star leader")
    show('/* @hwut {\n'
         ' *     title = "Parser corner cases"\n'
         ' *     build = "make"\n'
         ' * } */\n'
         'int main() { return 0; }\n')


def test_hash():
    """RETURN: None. '# ' leader; an inner HOCON comment survives."""
    banner("hash leader")
    show('#! /usr/bin/env python3\n'
         '# @hwut {\n'
         '#     title = "T"\n'
         '#     # a comment INSIDE the specification\n'
         '#     tolerance { numeric_ratio = 0.01 }\n'
         '# }\n'
         'import sys\n')


def test_dash():
    """RETURN: None. '-- ' leader."""
    banner("dash leader")
    show('-- @hwut {\n'
         '--     title = "T"\n'
         '-- }\n'
         'print("lua")\n')


def test_single():
    """RETURN: None. One line; and opener plus lone closer."""
    banner("everything on one line")
    show('/* @hwut { title = "T" } */\n')
    banner("lone closer: the leader must not eat the brace")
    show('/* @hwut { title = "T"\n'
         ' * } */\n')


def test_blank():
    """RETURN: None. A blank line inside the region."""
    banner("blank line takes no part")
    show('# @hwut {\n'
         '#     title = "T"\n'
         '\n'
         '#     tolerance { numeric_ratio = 0.5 }\n'
         '# }\n')


LINE_TRIGGER_LIST = ("//", "#", ";", "--", "%", "'", "REM", "!", '"', "\\",
                     "@", "|", "\u235d", "NB.", "/", "dnl", '.\\"', "@c",
                     "..", "*>", "///", "//!", "##", "#'", "-- |")
BLOCK_LIST = (("/*", "*/"), ("/+", "+/"), ("(*", "*)"), ("{", "}"),
              ("{-", "-}"), ("--[[", "]]"), ("#|", "|#"), ("#=", "=#"),
              ("#[", "]#"), ("<#", "#>"), ("%{", "%}"), ("=begin", "=end"),
              ("=pod", "=cut"), ("#[[", "]]"), ("#cs", "#ce"), ("(:", ":)"),
              ("(", ")"), ('"', '"'), ("<!--", "-->"), ("comment", ";"),
              ("co", "co"), ("/**", "*/"), ("(**", "*)"), ('"""', '"""'))


def _read_f(text):
    """RETURN: str, 'read' where the header gives title 'T' and the one
               choice 'a'; else what went wrong."""
    from vut.engine.orchestrator.exploration import reader
    if detect(text) is None: return "NOT DETECTED"
    spec, fault_list = reader.read_header(text, "x")
    if spec is None or fault_list:
        return "NOT READ: %s" % (fault_list[0].message if fault_list else "-")
    if spec.title != "T" or list(spec.choice_db) != ["a"]: return "READ WRONG"
    return "read"


def test_decoration():
    """RETURN: None. X-DECORATION over the comment styles of the listed
               languages, and what must stay out."""
    banner("line triggers: the decoration on every line")
    for m in LINE_TRIGGER_LIST:
        text = ('%s @hwut {\n%s     title = "T"\n%s     choices = ["a"]\n'
                '%s }\nbody\n' % (m, m, m, m))
        print("  %-8s %s" % (m, _read_f(text)))
    banner("block comments: opener on the marker's line / on the line before")
    for o, c in BLOCK_LIST:
        same = '%s @hwut {\n    title = "T"\n    choices = ["a"]\n} %s\nbody\n' % (o, c)
        own  = '%s\n@hwut {\n    title = "T"\n    choices = ["a"]\n}\n%s\nbody\n' % (o, c)
        print("  %-14s %-6s %s" % (o + " " + c, _read_f(same), _read_f(own)))
    banner("a C block with ' * ' lines under a '/**' opener")
    print("  %s" % _read_f('/** @hwut {\n *   title = "T"\n *   choices = ["a"]\n * }\n */\n'))
    banner("a marker glued to its trigger")
    print("  %s" % _read_f('#@hwut {\n#  title = "T"\n#  choices = ["a"]\n# }\n'))
    banner("what stays out")
    for label, text in (
        ("a numbered screen log",   '   1 # @hwut {\n   2 #   title = "T"\n   3 # }\n'),
        ("three words of prose",    'see the header @hwut { title = "T" }\n'),
        ("a quoted marker",         "the block '@hwut { }' declares\n"),
        ("a token of nine",         'REMARKABLE @hwut { title = "T" }\n'),
        ("a string in code",        'print("@hwut { title = 1 }")\n')):
        region = detect(text)
        print("  %-24s %s" % (label, "stays out" if region is None
                              else "DETECTED at %d:%d" % (region.line, region.column)))


def test_offsets():
    """RETURN: None. The region deep in a file: line numbers are the
    file's, columns count what was stripped."""
    banner("offsets, region at line 4")
    show('line one\n'
         'line two\n'
         'line three\n'
         '/* @hwut {\n'
         ' *     title = "T"\n'
         ' * } */\n')


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "Detector and unwrapper: no comment syntax known;", {
        "detect":  test_detect,
        "star":    test_star,
        "hash":    test_hash,
        "dash":    test_dash,
        "single":  test_single,
        "blank":   test_blank,
        "offsets": test_offsets,
        "head":    test_head,
        "decoration": test_decoration,
    }).run()
