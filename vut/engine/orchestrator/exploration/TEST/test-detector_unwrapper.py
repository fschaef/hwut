#! /usr/bin/env python3
#
# @hwut {
#     title      = "Detector and unwrapper: no comment syntax known"
#     choices    = ["blank", "dash", "detect", "hash", "head", "offsets",
#                   "single", "star"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: The detector and the unwrapper -- finding the region without
         knowing any language's comment syntax, and stripping the
         discovered leader while carrying the offsets.

CHOICES: detect, star, hash, dash, single, blank, offsets, head;

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
    }).run()
