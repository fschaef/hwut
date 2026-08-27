#! /usr/bin/env python3
#
# hwut {
#     title      = "Explorer: carriers, cross-check, resolution"
#     choices    = ["carriers", "defaults", "directory", "faults",
#                   "graph", "resolve"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: The explorer over a real directory: hwut.conf first, the walk,
         both carriers, the cross-check, and resolution.

CHOICES: directory, resolve, carriers, faults, defaults, graph;

DESCRIPTION:

directory  a directory of header files, an hwut.conf with an 'apps'
           entry and 'ignore' globs, and files that are ignored by
           default -- what exists is exactly what should.

resolve    the root is the default, a choice's own value overwrites;
           a SCOPE merges field by field, so a choice that caps the
           timeout keeps the root's other caps; resolution happens
           once, at exploration.

carriers   one file, one carrier: a header-carrying file named under
           'apps' is a TEST DIRECTORY ERROR; so is an 'apps' entry
           naming a file that does not exist. Exploration completes.

faults     a malformed header yields no CTestApp -- refused, not
           guessed at -- and every fault of the directory is reported
           at once, while the healthy files still explore.

graph      'collision' and 'dependency' in targets; a target naming
           what the directory does not offer; a cycle, named as a
           DIRECTORY failure; and '[MISDEP]' reaching every case whose
           dependencies cannot be met -- inside the cycle and beyond
           it.

defaults   the effective value: the record's where the author stated
           one, the owner's default else; the record itself keeps its
           'None' -- the chosen-vs-default distinction survives.

Machine-chosen paths never enter this output: directories print as '.'.
______________________________________________________________________________
"""
import os
import sys
import shutil
import tempfile
from config import HwutRunner                                # noqa: F401

from vut.engine.orchestrator.exploration.explorer         import explore
from vut.engine.orchestrator.exploration.relation         import effective


def stated(record):
    """RETURN: str, a record's STATED fields only -- 'None' is absence
    and absence prints nothing; '-' where nothing at all is stated."""
    if record is None: return "-"
    text_list = ["%s=%r" % (name, getattr(record, name))
                 for name in record.__dataclass_fields__
                 if getattr(record, name) is not None]
    return "{%s}" % " ".join(text_list) if text_list else "-"


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def build_directory(file_db):
    """RETURN: str, a fresh directory holding 'file_db':
    name -> content."""
    directory = tempfile.mkdtemp(prefix="vut_explore_")
    for name, content in file_db.items():
        with open(os.path.join(directory, name), "w") as fh:
            fh.write(content)
    return directory


def show(result):
    """RETURN: None. Prints an ExplorationResult, paths made
    machine-free."""
    spec = result.app_set.directory_spec
    print("directory keys: on_entry %r ignore %r"
          % (spec.on_entry, spec.ignore))
    for app in result.app_set:
        print("app '%s'  title '%s'  origin %s"
              % (app.source_file, app.title, app.origin.name))
        for name in sorted(app.choice_db,
                           key=lambda n: (n is None, n or "")):
            parameters = app.choice_db[name]
            text_list  = [
                "%s=%s" % (f, stated(getattr(parameters, f))
                              if hasattr(getattr(parameters, f),
                                         "__dataclass_fields__")
                              else repr(getattr(parameters, f)))
                for f in parameters.__dataclass_fields__
                if getattr(parameters, f) is not None]
            print("    choice %-5s %s"
                  % ("-" if name is None else name,
                     "  ".join(text_list) if text_list
                     else "(nothing stated)"))
    for case in sorted(result.app_set.misdep_set,
                       key=lambda c: (c[0], c[1] or "")):
        print("    %-12s %-5s [MISDEP]"
              % (case[0], "-" if case[1] is None else case[1]))
    for fault in result.fault_list:
        print("FAULT %s" % fault)


def test_directory():
    """RETURN: None. Both carriers, ignores at work."""
    banner("a directory of both carriers")
    directory = build_directory({
        "test-parse.py":  '# hwut {\n#     title = "parses"\n'
                          '#     choices = [\"one\", \"two\"]\n# }\n',
        "test-plain.sh":  '# hwut { title = "plain" }\n',
        "notes.txt":      "ignored by default\n",
        "data.json":      "{}\n",
        "test-gen.c":     "int main() { return 0; }\n",
        "skipme.gen":     "configured away\n",
        "hwut.conf":      'hwut {\n'
                          '    ignore = ["*.gen"]\n'
                          '    apps {\n'
                          '        test-gen.c { title = "generated" }\n'
                          '    }\n'
                          '}\n',
    })
    try:     show(explore(directory))
    finally: shutil.rmtree(directory, ignore_errors=True)


def test_resolve():
    """RETURN: None. Root default in, choice overwrite wins."""
    banner("root is the default; a choice overwrites")
    directory = build_directory({
        "test-tol.py": '# hwut {\n'
                       '#     title   = "tolerances"\n'
                       '#     numeric = 0.01\n'
                       '#     pype    = \"strip.pype\"\n'
                       '#     caps    { timeout_sec = 30  network = false }\n'
                       '#     choices {\n'
                       '#         one { }\n'
                       '#         two { numeric = 0.05\n'
                       '#               caps { timeout_sec = 5 } }\n'
                       '#     }\n'
                       '# }\n',
    })
    try:     show(explore(directory))
    finally: shutil.rmtree(directory, ignore_errors=True)


def test_carriers():
    """RETURN: None. The cross-check: one file, one carrier."""
    banner("header AND apps; and a ghost entry")
    directory = build_directory({
        "test-both.py": '# hwut { title = "I have a header" }\n',
        "hwut.conf":    'hwut {\n'
                        '    apps {\n'
                        '        test-both.py  { title = "and an entry" }\n'
                        '        test-ghost.py { title = "no such file" }\n'
                        '    }\n'
                        '}\n',
    })
    try:     show(explore(directory))
    finally: shutil.rmtree(directory, ignore_errors=True)


def test_faults():
    """RETURN: None. Faults accumulate; the healthy still explore."""
    banner("a malformed header beside a healthy one")
    directory = build_directory({
        "test-bad.py":  '# hwut {\n#     title = "bad"\n'
                        '#     numerc = 0.5\n# }\n',
        "test-good.py": '# hwut { title = "good" }\n',
    })
    try:     show(explore(directory))
    finally: shutil.rmtree(directory, ignore_errors=True)


def test_defaults():
    """RETURN: None. Effective values; the record keeps its Nones."""
    banner("effective = chosen, or the owner's default")
    directory = build_directory({
        "test-t.py": '# hwut { title = "T"\n'
                     '#        numeric = 0.25 }\n',
    })
    try:
        result = explore(directory)
        app        = result.app_set.app_db["test-t.py"]
        parameters = app.choice_db[None]
        print("record    numeric %r  comment %r  analogy %r"
              % (parameters.numeric, parameters.comment,
                 parameters.analogy))
        print("effective numeric %r  comment %r  analogy %r"
              % (effective(parameters, "numeric"),
                 effective(parameters, "comment"),
                 effective(parameters, "analogy")))
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_graph():
    """RETURN: None. Targets, an unknown target, a cycle, and the
    reach of [MISDEP]."""
    banner("targets that exist; nothing unreachable")
    directory = build_directory({
        "test-a.py":  '# hwut { title = "A"  choices = [\"one\", \"two\"] }\n',
        "test-b.py":  '# hwut { title = "B" }\n',
        "hwut.conf":  'hwut {\n'
                      '    collision  = ["test-b.py", "test-a.py two"]\n'
                      '    dependency {\n'
                      '        "test-b.py"     = ["test-a.py one"]\n'
                      '        "test-a.py two" = ["test-a.py one"]\n'
                      '    }\n'
                      '}\n',
    })
    try:     show(explore(directory))
    finally: shutil.rmtree(directory, ignore_errors=True)

    banner("a target the directory does not offer")
    directory = build_directory({
        "test-a.py":  '# hwut { title = "A"  choices = [\"one\", \"two\"] }\n',
        "hwut.conf":  'hwut {\n'
                      '    collision  = ["test-ghost.py"]\n'
                      '    dependency {\n'
                      '        "test-a.py one" = ["test-a.py three"]\n'
                      '    }\n'
                      '}\n',
    })
    try:     show(explore(directory))
    finally: shutil.rmtree(directory, ignore_errors=True)

    banner("a cycle, and what hangs off it")
    directory = build_directory({
        "test-a.py":  '# hwut { title = "A" }\n',
        "test-b.py":  '# hwut { title = "B" }\n',
        "test-c.py":  '# hwut { title = "C" }\n',
        "test-d.py":  '# hwut { title = "D" }\n',
        "test-e.py":  '# hwut { title = "E" }\n',
        "hwut.conf":  'hwut {\n'
                      '    dependency {\n'
                      '        "test-a.py" = ["test-c.py"]\n'
                      '        "test-b.py" = ["test-a.py"]\n'
                      '        "test-c.py" = ["test-b.py"]\n'
                      '        "test-d.py" = ["test-a.py"]\n'
                      '        "test-e.py" = ["test-d.py"]\n'
                      '    }\n'
                      '}\n',
    })
    try:     show(explore(directory))
    finally: shutil.rmtree(directory, ignore_errors=True)


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "Explorer: carriers, cross-check, resolution;", {
        "directory": test_directory,
        "resolve":   test_resolve,
        "carriers":  test_carriers,
        "faults":    test_faults,
        "graph":     test_graph,
        "defaults":  test_defaults,
    }).run()
