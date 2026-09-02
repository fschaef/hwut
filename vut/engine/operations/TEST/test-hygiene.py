#! /usr/bin/env python3
#
# @hwut {
#     title      = "The component's hygiene, checked rather than remembered"
#     choices    = ["good_files", "no_crash", "no_orphans",
#                   "return_first", "token_ranks"]
#     eq-pattern = ["SUCCESS.*"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE COMPONENT'S HYGIENE -- checked, not remembered.

    UNIT     the component's own source and its GOOD files.

    WHY IT EXISTS
             three defects recurred during construction, each caught by
             a person's eye and each capable of recurring silently:

                 an ENVIRONMENT VALUE frozen into a GOOD file -- a
                 duration, a process id, a temporary path. The suite then
                 passes on one machine and fails on the next, or passes
                 half the time on one.

                 a PUBLIC NAME declared and never used. It reads as
                 capability and is only description; an audit finds it, a
                 caller never does.

                 a REPORT TOKEN with no rank in the precedence table,
                 which would make the reason that speaks arbitrary.

             NOTE, and it caught itself here: this test prints NO COUNTS.
             A count of files or names is a measurement the suite itself
             changes, so an oracle holding one would need re-baselining
             every time the component grew. It states the CLAIM and names
             only what offends.

             A rule enforced by attention is a rule that breaks again.
             These are the same rules, enforced by the suite.
______________________________________________________________________________
"""
import ast
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.operations.result import E_TestRunResult      # noqa E402
from   vut.engine.bookkeeper.api    import GOOD_OWNED_FILE_TUPLE  # noqa E402
import vut.engine.operations.report    as     report_module        # noqa E402

COMPONENT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

#  The tests live where their units live: every package carries its own
#  TEST/. Hygiene is the COMPONENT's, so its walks cover them all --
#  nvim's lua corpus excepted, as everywhere (it is the client's own).
_WALK_SKIP = {"nvim", "__pycache__", "OUT"}


def _test_directory_list():
    """RETURN: list[str], every TEST directory of the component."""
    found = []
    for directory, directory_list, _ in os.walk(COMPONENT):
        directory_list[:] = [d for d in directory_list
                             if d not in _WALK_SKIP]
        if os.path.basename(directory) == "TEST":
            found.append(directory)
            directory_list[:] = []          # a TEST holds no further TEST
    return sorted(found)


def _good_file_list():
    """RETURN: list[(str, str)], (basename, full path) of every GOOD
    file of the component, across all its TEST directories."""
    pair_list = []
    for test_directory in _test_directory_list():
        good = os.path.join(test_directory, "GOOD")
        if not os.path.isdir(good): continue
        #  THE BOOKKEEPER'S OWN FILES ARE NOT ORACLES: the book and the
        #  register stand in GOOD/ too, and are skipped by asking the
        #  door what it owns -- never by a list kept here.
        pair_list += ((name, os.path.join(good, name))
                      for name in os.listdir(good)
                      if name not in GOOD_OWNED_FILE_TUPLE)
    return sorted(pair_list)

#  Shapes an environment chooses. A test may READ any of them; what
#  reaches a GOOD file must be a statement that holds on every machine.
ENVIRONMENT_SHAPE = [
    (r"/tmp/\S+",                    "a temporary path"),
    (r"\bpid[ =]\d+",                "a process id"),
    (r"\(\d+\.\d+ ?s\)",             "a measured duration"),
    (r"0x[0-9a-f]{6,}",              "an address"),
    (r"\b\d{4}-\d{2}-\d{2}T\d{2}:",  "a timestamp"),
]


def _check(pair_list):
    """RETURN: True, every claim held; False, at least one did not."""
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def _verdict(ok, sentence):
    """RETURN: None. Prints the one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


def _module_list():
    """RETURN: list[str], the component's own source files -- the root
    modules AND the subpackages' (provision/, services/). TEST and the
    display clients are not the component's modules and stay out."""
    SKIP      = {"TEST", "nvim", "__pycache__"}
    path_list = []
    for directory, directory_list, file_list in os.walk(COMPONENT):
        directory_list[:] = [d for d in directory_list if d not in SKIP]
        path_list += (os.path.join(directory, name)
                      for name in file_list
                      if name.endswith(".py")
                      and not name.startswith("__"))
    return sorted(path_list)


def test_good_files_are_machine_free():
    """A GOOD FILE STATES A CLAIM, NEVER A MEASUREMENT. Anything the
    environment chose -- a path, a pid, a duration, an address, a clock
    -- makes the oracle true of one machine instead of true of the
    behaviour."""
    offence_list = []
    for name, path in _good_file_list():
        text = open(path, encoding="utf-8").read()
        for pattern, what in ENVIRONMENT_SHAPE:
            found = re.search(pattern, text)
            if found:
                offence_list.append((name, what, found.group(0)[:30]))

    print("INSPECT: every GOOD file, scanned for every environment shape")
    for name, what, sample in offence_list:
        print("         %s carries %s: %r" % (name, what, sample))
    if not offence_list:
        print("         none carries one")
    ok = _check([
        (not offence_list,
         "no GOOD file freezes a value the environment chose"),
    ])
    _verdict(ok, "every oracle is true of the behaviour, not of a machine.")


def test_no_good_file_holds_a_crash():
    """AN ORACLE THAT SAYS 'THIS CRASHES' IS STILL AN ORACLE, and the
    suite will pass on it forever as long as the crash is reproducible.

    It happened here: a GOOD file was baselined while its test was
    failing to import, and froze a traceback. The suite went green.
    A GOOD file must end in the verdict line -- or, per R-70, in the
    terminal token '<hwut-end>' with the verdict line directly above
    it -- and hold no traceback.

    A TRAP FOR ANY SELF-INSPECTING TEST: baseline it through a temporary
    file. Redirecting straight into its own GOOD file truncates that file
    before this reads it, and the empty file is then recorded as the
    offence.
    """
    offence_list = []
    for name, path in _good_file_list():
        text = open(path, encoding="utf-8").read()
        if "Traceback (most recent call last)" in text:
            offence_list.append((name, "a traceback"))
            continue
        last = [l for l in text.rstrip("\n").split("\n") if l.strip()]
        if last and last[-1] == "<hwut-end>":
            last = last[:-1]                       # R-70: the token ends
                                                   # the STREAM; the
                                                   # verdict ends the TEST
        if not last:
            offence_list.append((name, "no output at all"))
        elif not (last[-1].startswith("SUCCESS:")
                  or last[-1].startswith("FAILURE:")):
            offence_list.append((name, "does not end in a verdict line"))

    print("INSPECT: every GOOD file, for a crash or a missing verdict")
    for name, what in offence_list:
        print("         %s: %s" % (name, what))
    if not offence_list:
        print("         every one ends in its verdict, none holds a crash")
    ok = _check([
        (not offence_list,
         "no oracle records a crash instead of a behaviour"),
    ])
    _verdict(ok, "a green suite is not the same as a working one.")


def _public_name_db():
    """
    RETURN: dict, public name -> the module that defines it.

    Public means: a module-level class or function whose name does not
    begin with an underscore.
    """
    name_db = {}
    for path in _module_list():
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in tree.body:
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef,
                                     ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_"): continue
            name_db[node.name] = os.path.basename(path)
    return name_db


def test_no_name_without_a_consumer():
    """A CAPABILITY WITH NO CONSUMER IS NOT BUILT, IT IS DESCRIBED.

    Four such names accumulated during construction -- an envelope, a
    context manager, a property, a configuration field -- each reading as
    capability and each used by nothing. An audit found them; no caller
    ever would have.
    """
    name_db  = _public_name_db()
    body     = "\n".join(open(p, encoding="utf-8").read()
                         for p in _module_list())
    tests    = "\n".join(
        open(os.path.join(test_directory, name), encoding="utf-8").read()
        for test_directory in _test_directory_list()
        for name in sorted(os.listdir(test_directory))
        if name.startswith("test-") and name.endswith(".py"))

    orphan_list = []
    for name, module in sorted(name_db.items()):
        uses = len(re.findall(r"\b%s\b" % re.escape(name), body)) - 1
        if uses > 0:                     continue        # used by the code
        if re.search(r"\b%s\b" % re.escape(name), tests): continue  # by a test
        orphan_list.append((name, module))

    print("INSPECT: every public name of the component")
    for name, module in orphan_list:
        print("         no consumer: %s (%s)" % (name, module))
    if not orphan_list:
        print("         every one has a consumer, in the code or a test")
    ok = _check([
        (not orphan_list,
         "no public name is declared without something that uses it"),
    ])
    _verdict(ok, "what is declared is used, or it is not declared.")


def test_every_failure_token_is_ranked():
    """A REPORT TOKEN WITH NO RANK would make the reason that speaks
    arbitrary. A new token must be PLACED among the others, and this
    fails the day one is added without placing it."""
    unranked = [token.name for token in E_TestRunResult
                if token is not E_TestRunResult.OK
                and token not in report_module._RANK]
    print("INSPECT: every failure token of the vocabulary")
    print("         unranked: %s" % (unranked or "none"))
    ok = _check([
        (not unranked,
         "every failure token has a place in the precedence table"),
    ])
    _verdict(ok, "no reason speaks by accident of ordering.")


def test_every_public_name_says_what_it_returns():
    """The convention: a docstring OPENS with what the thing returns, so
    a reader knows the answer before the explanation. Checked because a
    convention nobody checks is a convention that decays."""
    offence_list = []
    for path in _module_list():
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("__"): continue
            text = ast.get_docstring(node)
            if text is None:
                offence_list.append((node.name, os.path.basename(path),
                                     "no docstring"))
            elif not text.lstrip().startswith("RETURN:"):
                offence_list.append((node.name, os.path.basename(path),
                                     "does not open with RETURN:"))
    print("INSPECT: every function of the component")
    for name, module, why in offence_list:
        print("         %s (%s): %s" % (name, module, why))
    if not offence_list:
        print("         every one opens with what it returns")
    ok = _check([
        (not offence_list,
         "every function states its return before its explanation"),
    ])
    _verdict(ok, "the answer comes before the argument.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The component's hygiene, checked rather than remembered",
        choice_map = {
            "good_files":   test_good_files_are_machine_free,
            "no_orphans":   test_no_name_without_a_consumer,
            "no_crash":     test_no_good_file_holds_a_crash,
            "token_ranks":  test_every_failure_token_is_ranked,
            "return_first": test_every_public_name_says_what_it_returns,
        },
        happy      = "SUCCESS.*",
    ).run()
