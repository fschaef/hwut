#! /usr/bin/env python3
#
# @hwut {
#     title      = "The tolerance proposals: discrepancies in, proposal out."
#     choices    = ["applied", "blanks", "classes", "edit", "example",
#                   "in-force", "none", "nothing", "numeric"]
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE PROPOSAL GENERATOR (intend 21, section 4), fed with what the
         screen is fed: compare's own alignment of a subject against a
         nominal, the line pairs collected as the driver collects them.

    example    the case ruled on 2026-09-26: a number, a word with context
    classes    one word per class, and a built class
    numeric    the largest deviation + 10%; beyond 1 a pattern takes it;
               a nominal 0 proposes nothing
    blanks     'whitespace = true' only where whitespace is off
    nothing    a word on one side only
    in-force   what stands is not proposed again, and is kept in the line
    none       nothing differs: nothing is proposed
    applied    every proposal uncommented, compare asked again -- once with
               the eq_patterns BY CLASS, once BY EDIT OPERATIONS: what is
               still standing is printed; the proposals are ideas, and
               this choice records how far each reaches
    edit       the edit-operation pattern beside the class one, word pair
               by word pair
______________________________________________________________________________
"""
import asyncio
import io
import re
import sys

from vut.engine.compare.api                 import feeder_ui, Configuration
from vut.services.lib.viewers.keyed         import report
from vut.services.lib.viewers.keyed.proposal import proposal_db


def pair_list_of(subject, nominal, configuration=None):
    """RETURN: list[report.Pair], compare's line pairs for the two texts,
               as the keyed driver collects them."""
    configuration = configuration or Configuration()
    async def collect():
        """RETURN: list[report.Pair], the delivery's line pairs."""
        result = []
        async for item in feeder_ui.feed(configuration, io.StringIO(subject),
                                         io.StringIO(nominal)):
            if hasattr(item, "line_n_s"):
                result.append(report.Pair(item.line_n_s, item.line_n_n,
                                          tuple(item.cells_s),
                                          tuple(item.cells_n)))
        return result
    return asyncio.run(collect())


def show(subject, nominal, configuration=None, **in_force):
    """RETURN: list[str], the proposal lines, after printing the two texts
               and the lines."""
    for tag, text in (("OUTPUT", subject), ("GOOD", nominal)):
        for line in text.splitlines(): print("   %-6s | %s" % (tag, line))
    db = proposal_db(pair_list_of(subject, nominal, configuration), **in_force)
    print("   ->")
    if not db: print("     (no proposal)")
    for key, line_list in db.items():
        print("     [%s]" % key)
        for line in line_list: print("       %s" % line)
    return db


def test_example():
    print("-- the case ruled on 2026-09-26")
    show("time: 12.51 ms  id=ab12;\n", "time: 12.00 ms  id=zz7;\n")


def test_classes():
    print("-- a word per class; the whole word first, then the middle")
    show("at 2026-09-26 12:01:07 pid 0x1f in /tmp/a/b as done\n",
         "at 2026-01-02 09:00:00 pid 0xFF in /var/x as fail\n")
    print("\n-- context kept literal, the middle classed; 'identifier' only")
    print("   where no context is shared")
    show("v=1.5e3 run=done n=17\n", "v=2.25 run=fail n=4000\n")


def test_numeric():
    print("-- the largest deviation, + 10%, rounded up")
    show("a 3\nb 12.51\nc v12\n", "a 4\nb 12.00\nc v13\n")
    print("\n-- a deviation that would need a ratio above 1: a pattern")
    show("took 3 s\n", "took 700 s\n")
    print("\n-- a nominal 0 has no relative deviation")
    show("x 5\n", "x 0\n")


def test_blanks():
    print("-- whitespace on (the default): compare already takes blanks")
    show("a   b\n", "a b\n")
    print("\n-- whitespace off: proposed")
    configuration = Configuration()
    configuration.pattern_finder.whitespace_f = False
    show("a   b\n", "a b\n", configuration, whitespace_f=False)


def test_nothing():
    print("-- a word on one side only, with the blanks after it")
    show("x WARN y\n", "x y\n")
    show("x y\n", "x NOTE y\n")


def test_in_force():
    print("-- the ratio in force already takes the deviation")
    show("a 3\n", "a 4\n", numeric_ratio=0.3)
    print("\n-- a pattern in force is kept in the line, not proposed again")
    configuration = Configuration()
    configuration.pattern_finder.equivalent_pattern_list = ["zz[0-9]+"]
    show("id=ab12; k=zz1\n", "id=zz7; k=zz99\n", configuration,
         pattern_list=["zz[0-9]+"])


def test_none():
    print("-- nothing differs")
    show("same 1\n", "same 1\n")


def test_applied():
    print("-- every proposal applied: which lines still differ")
    subject = ("time: 12.51 ms  id=ab12;\n"
               "at 2026-09-26 12:01:07 pid 0x1f in /tmp/a/b took 3 s\n"
               "x WARN y\n"
               "count 3\n")
    nominal = ("time: 12.00 ms  id=zz7;\n"
               "at 2026-01-02 09:00:00 pid 0xFF in /var/x took 700 s\n"
               "x y\n"
               "count 4\n")
    db = show(subject, nominal)
    for label in ("by class", "by edit operations"):
        configuration = Configuration()
        finder = configuration.pattern_finder
        for line in [each for key in db for each in db[key]]:
            match = re.match(r"# (numeric_ratio|eq_pattern|nothing) *= (\S+|\[.*\])(?:    # (.*))?$",
                             line)
            if match is None: continue
            key, value, note = match.groups()
            if key == "numeric_ratio":
                finder.numeric_tolerance_ratio = float(value)
                continue
            if key == "eq_pattern" and note and label not in note: continue
            text_list = [t.replace('\\\\', '\\')
                         for t in re.findall(r'"((?:[^"\\]|\\.)*)"', value)]
            if key == "eq_pattern": finder.equivalent_pattern_list = text_list
            else:                   finder.visible_nothing_pattern_list = text_list
        print("\n   compare, asked again, the eq_patterns %s:" % label)
        for pair in pair_list_of(subject, nominal, configuration):
            bad_n = sum(1 for cell in tuple(pair.cells_s) + tuple(pair.cells_n)
                        if not cell.relation_id.name.startswith("OK_"))
            print("     OUTPUT %i: %s" % (pair.line_n_s,
                                          "equivalent" if bad_n == 0
                                          else "%i element(s) differ" % bad_n))


def test_edit():
    print("-- word pair by word pair: by class | by edit operations")
    from vut.services.lib.viewers.keyed.proposal import pattern_of, edit_pattern_of
    for word_s, word_n in (("id=ab12;", "id=zz7;"), ("v1.2.3-rc1", "v1.4.3-rc2"),
                           ("2026-09-26", "2026-01-02"), ("run=done", "run=fail"),
                           ("/tmp/a/b", "/var/x"), ("0x1f", "0xFF"),
                           ("build-4711", "build-815"), ("Alpha", "beta")):
        print("   %-12s %-12s | %-28s | %s" % (word_s, word_n,
                                                pattern_of(word_s, word_n),
                                                edit_pattern_of(word_s, word_n)))


CHOICE_DB = {
    "example":  test_example,
    "classes":  test_classes,
    "numeric":  test_numeric,
    "blanks":   test_blanks,
    "nothing":  test_nothing,
    "in-force": test_in_force,
    "none":     test_none,
    "applied":  test_applied,
    "edit":     test_edit,
}

choice = sys.argv[1] if len(sys.argv) > 1 else "example"
CHOICE_DB[choice]()
print("<hwut-end>")
