#! /usr/bin/env python3
#
# @hwut {
#     title      = "The person's preferences: two files, one colour vocabulary"
#     choices    = ["defaults", "faults", "overlay", "project", "vocabulary"]
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'services/lib/preferences.py' (services E-78, E-82), over the
         vocabulary of 'engine/display/colour.py'.

    defaults    every role the installation's 'bin/.hwut.conf' states, in
                both forms a reader takes it -- and the escapes of the run,
                the report and the reading, which must be the ones those
                readers drew before the table existed
    overlay     '~/.hwut.conf' over the default, key by key: what the
                person states wins, everything else stays
    faults      a person's file that is wrong never stops anything: the
                default stands for what was ignored, and ONE note says
                where and why
    vocabulary  every kind of colour word, and what is not one
    project     a project's 'hwut.conf' refuses a preference by name

No home directory of the machine running this is read: each choice points
'HOME' at a directory of its own.
______________________________________________________________________________
"""
import os
import sys
import shutil
import tempfile

from   config import HwutRunner                                  # noqa F401,E402
from   vut.services.lib import preferences                     # noqa: E402

os.environ["HOME"] = tempfile.mkdtemp(prefix="hwut-home-")


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def loaded(user_text):
    """RETURN: (Preferences, list[str]) -- the preferences with
               'user_text' as '~/.hwut.conf' (none where None), and the
               notes the load wrote."""
    path = os.path.join(os.environ["HOME"], ".hwut.conf")
    if os.path.exists(path): os.unlink(path)
    if user_text is not None:
        with open(path, "w", encoding="utf-8") as fh: fh.write(user_text)
    note_list = []
    result = preferences.load(user_path=path,
                              default=preferences.default_path(),
                              err=note_list.append)
    home = os.environ["HOME"]
    return result, [n.replace(home, "~") for n in note_list]


def test_defaults():
    """RETURN: None. The shipped table, role by role."""
    prefs, note_list = loaded(None)
    print("    notes: %s" % (note_list or "none"))
    for role in sorted(prefs.color_db):
        color = prefs.color(role)
        print("    %-24s %-28s sgr %-22s pt %s"
              % (role, repr(color), repr(preferences.sgr(color)),
                 repr(preferences.toolkit_style(color))))

    banner("the escapes the readers drew before the table")
    from vut.engine.display.word import CInk
    ink = CInk(True)
    for name, code in (("ok", "32"), ("fail", "38;5;196"),
                       ("tag_ok", "97;42"), ("tag_fail", "97;48;5;196"),
                       ("tag_undecided", "30;43"), ("warn", "33"),
                       ("start", "34"), ("dim", "2"), ("bold", "1"),
                       ("dir_band", "97;48;5;208"),
                       ("block_error", "1;97;48;5;196"),
                       ("ground_ok", "97;42"), ("ground_skip", "30;43"),
                       ("ground_fail", "97;48;5;196"),
                       ("directory", "38;5;208")):
        drawn = getattr(ink, name)("x")
        print("    run    %-14s %-5s" % (name, drawn == "\x1b[%smx\x1b[0m" % code))
    from vut.services.report import painted
    for role, code in (("report.title", "30;48;5;208"),
                       ("report.ok", "30;48;5;40"),
                       ("report.fail", "97;48;5;160")):
        drawn = painted("x", role, True)
        print("    report %-14s %-5s" % (role[7:], drawn == "\x1b[%smx\x1b[0m" % code))
    for role, code in (("element.numeric", "36"), ("element.analogy", "33"),
                       ("element.pattern", "32"), ("element.binding", "35"),
                       ("element.nothing", "2"), ("verdict.subject", "31"),
                       ("verdict.nominal", "34"), ("verdict.tolerated", "33")):
        print("    tui    %-18s %s" % (role, preferences.sgr(prefs.color(role)) == code))


def test_overlay():
    """RETURN: None. The person's keys win; the rest stays."""
    prefs, note_list = loaded(
        'hwut {\n'
        '    colors {\n'
        '        element { numeric = "bold bright-cyan"  string = "white" }\n'
        '        keyed   { spent = "none" }\n'
        '    }\n'
        '}\n')
    print("    notes: %s" % (note_list or "none"))
    for role in ("element.numeric", "element.string", "element.analogy",
                 "keyed.spent", "keyed.marker"):
        print("    %-18s %r" % (role, prefs.color(role)))

    banner("no person's file: the default, whole")
    prefs, note_list = loaded(None)
    print("    element.numeric    %r   notes: %s"
          % (prefs.color("element.numeric"), note_list or "none"))


def test_faults():
    """RETURN: None. What is ignored, and what is said about it."""
    for label, text in (
        ("an unknown role",
         'hwut { colors { element { numerc = "red" } } }\n'),
        ("an unknown colour word",
         'hwut { colors { verdict { subject = "purple" } } }\n'),
        ("a colour that is not a string",
         'hwut { colors { verdict { subject = 31 } } }\n'),
        ("an operational key",
         'hwut { tolerance { numeric_ratio = 0.1 } }\n'),
        ("a block that is not 'hwut'",
         'colors { verdict { subject = "red" } }\n'),
        ("a file that does not parse",
         'hwut { colors { verdict { subject = "red" }\n'),
    ):
        banner(label)
        prefs, note_list = loaded(text)
        for note in note_list: print("    %s" % note)
        print("    verdict.subject    %r" % prefs.color("verdict.subject"))


def test_vocabulary():
    """RETURN: None. Word by word."""
    for color in ("red", "bright-red", "bg-red", "bg-bright-red",
                  "c256:208", "bg256:208", "#2e3b32", "bg#2E3B32",
                  "bold", "dim", "italic", "underline", "reverse",
                  "none", "", "bold none cyan",
                  "purple", "c256:256", "bg#12345", "bright-", "#zzzzzz"):
        bad = preferences.word_list_valid(color)
        if bad is not None:
            print("    %-18r unknown word %r" % (color, bad))
            continue
        print("    %-18r sgr %-22r pt %r"
              % (color, preferences.sgr(color),
                 preferences.toolkit_style(color)))

    banner("paint")
    print("    %r" % preferences.paint("x", "cyan"))
    print("    %r" % preferences.paint("x", "none"))


def test_project():
    """RETURN: None. A project file refuses a preference by name."""
    from vut.engine.orchestrator.exploration import reader
    _, _, fault_list = reader.read_conf(
        'hwut {\n    colors { element { numeric = "red" } }\n}\n', "hwut.conf")
    for fault in fault_list: print("    %s" % fault)
    _, fault_list = reader.read_header(
        '# @hwut {\n#     title = "t"\n#     colors { }\n# }\n', "test-x.py")
    for fault in fault_list: print("    %s" % fault)


if __name__ == "__main__":
    try:
        HwutRunner(
            argv       = sys.argv,
            title      = "The person's preferences: two files, one colour vocabulary",
            choice_map = {
                "defaults":   test_defaults,
                "faults":     test_faults,
                "overlay":    test_overlay,
                "project":    test_project,
                "vocabulary": test_vocabulary,
            }).run()
    finally:
        shutil.rmtree(os.environ["HOME"], ignore_errors=True)
