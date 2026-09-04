#! /usr/bin/env python3
#
# @hwut {
#     title      = "Scenario coverage: every format has a real artefact, and every artefact reads"
#     choices    = ["every_format", "every_artefact"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

SCENARIO COVERAGE (adm/DEVELOPMENT.txt), asked of the registry and the
material together. No instrument measures it, so this test asks the
two questions deliberately:

    every_format    For EVERY registered format -- asked of the
                    registry, never a list written here -- is there at
                    least one real artefact under REAL_PARSING_INPUT/
                    <format>/? A format registered tomorrow enters
                    this test tomorrow, and fails it until somebody
                    witnesses one.

    every_artefact  For every artefact that IS there: does the format
                    it is filed under actually READ it -- absorb at
                    least one point? An artefact a reader cannot parse
                    witnesses nothing. This is the check that would
                    have caught 'verilator/coverage.dat' holding
                    display glyphs where the tool writes control bytes:
                    the file stood there for weeks, and could not be
                    read by the reader it claimed to witness.

WHAT IS AN ARTEFACT, and what is the SOURCE beside it: a directory
holds both, so a reader author can see what produced what. Only files
the format's own 'suffix' names are asked to parse; the '.v', '.rb',
'.adb' beside them are provenance and are not.

FORMATS THAT ARE NOT DIRECTORIES HERE: 'python_coverage', 'go' and
'luacov' witness against fixtures constructed in 'test-readers.py'
(their tools were not at hand). They are named below as GAPS, not
hidden, so the count of formats with a real artefact is honest.
______________________________________________________________________________
"""
import os
import sys

import config                                                   # noqa: F401
from vut.test_writing_support.python.hwut_runner import HwutRunner
from vut.engine.coverage.reader import registered_tuple, framework_of

REAL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "REAL_PARSING_INPUT")


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


#  FORMATS WITHOUT A REAL ARTEFACT, BY NAME. Stated here so the gap is
#  a fact the test knows and prints, not a silence. Closing one means
#  witnessing an artefact and deleting the name.
KNOWN_GAP_SET = frozenset(("python_coverage", "go", "luacov"))


def _artefacts_of(directory, suffix_tuple):
    """RETURN: list[str], the files under 'directory' the format's own
    suffixes name -- its artefacts, as distinct from the sources kept
    beside them."""
    if not os.path.isdir(directory): return []
    return sorted(name for name in os.listdir(directory)
                  if any(name.endswith(s) for s in suffix_tuple))


#  A FORMAT'S DIRECTORY IS ITS READER MODULE'S NAME -- 'cobertura',
#  'lcov', 'gcov' -- because that is what a reader author opens. The
#  format's own 'name' ('cobertura-xml', 'lcov-tracefile') names the
#  artefact kind and is what the record header carries; the module
#  name is where the reader lives. The two are joined through the
#  format object's class, which knows its module.
def _directory_of(fmt):
    """RETURN: str, the REAL_PARSING_INPUT subdirectory for this format
    -- the tail of its reader module's name."""
    return type(fmt).__module__.rsplit(".", 1)[-1]


def _artefact_suffix_tuple(fmt):
    """
    RETURN: tuple[str], what an artefact of this format is called --
            the format's own 'suffix' where it states one (the base-
            class walk collects by it), else what its reader's own
            'read' is known to look for.
    """
    suffix = getattr(fmt, "suffix", None)
    if suffix:
        return (suffix,) if isinstance(suffix, str) else tuple(suffix)
    #  Readers that keep their own 'read' (D-28: gcov, go, lcov, luacov,
    #  python_coverage) state no 'suffix'; their artefact kinds are
    #  fixed by the format and named here once.
    return {"lcov":            (".info",),
            "gcov":            (".gcov",),
            "go":              (".out",),
            "luacov":          (".out", ".report"),
            "python_coverage": (".json",)}.get(_directory_of(fmt), ())


def _format_db():
    """
    RETURN: dict, directory name -> (CCoverageFormat, suffix tuple,
            tuple of tool names), one entry per DISTINCT FORMAT --
            many tools write one format, and the criterion is per
            format. The registry is the source of truth for both.
    """
    db = {}
    for tool in registered_tuple():
        fmt = framework_of(tool).format
        key = _directory_of(fmt)
        if key not in db:
            db[key] = (fmt, _artefact_suffix_tuple(fmt), [])
        db[key][2].append(tool)
    return {k: (f, s, tuple(sorted(t))) for k, (f, s, t) in db.items()}


def test_every_format():
    """Every registered format has at least one real artefact."""
    pair_list = []
    db = _format_db()
    print("  %d tools registered, writing %d distinct formats"
          % (len(registered_tuple()), len(db)))
    for name, (fmt, suffix_tuple, tool_tuple) in sorted(db.items()):
        directory = os.path.join(REAL, name)
        found     = _artefacts_of(directory, suffix_tuple)
        tools     = ", ".join(tool_tuple)
        if name in KNOWN_GAP_SET:
            print("  gap : %-12s (%s) no real artefact -- tool not at "
                  "hand; witnesses against a constructed fixture"
                  % (name, tools))
            continue
        pair_list.append(
            (bool(found),
             "%-12s (%s): %s" % (name, tools,
                                 ", ".join(found) if found
                                 else "NO REAL ARTEFACT under %s/" % name)))
    _verdict(_check(pair_list),
             "every format outside the named gaps has a real artefact.")


def _absorbs(fmt, name, path):
    """
    RETURN: [0] bool, the format took at least one point from the file.
            [1] str,  what happened, for the report line.

    ONE FILE, BY THE FORMAT'S OWN SINGLE-FILE ROAD. Formats on the base
    walk (D-28) expose 'absorb'; the two that keep their own 'read' --
    'lcov' merges tracefiles, 'gcov' pairs annotations with '.gcda' --
    expose a per-file parser instead, and that is what is asked here.
    Both roads are the format's own; neither is a shortcut this test
    invented.
    """
    if name == "lcov":
        from vut.engine.coverage.readers.lcov import count_db_of
        with open(path, encoding="utf-8", newline="") as fh:
            count_db = count_db_of(fh.read())
        return bool(count_db), "parsed %d file(s)" % len(count_db)
    if name == "gcov":
        from vut.engine.coverage.readers.gcov import read_annotated
        with open(path, encoding="utf-8", newline="") as fh:
            source, line_db = read_annotated(fh.read())
        #  THE 'Source:' HEADER MAY BE ABSOLUTE -- gcov writes the path
        #  the compiler saw, on the machine it ran on. That is a fact
        #  about the artefact and is what test-readers.py checks is
        #  made relative; here only the NAME is reported, so the
        #  recording machine's directory never enters an oracle.
        return (source is not None and bool(line_db),
                "annotates %s, %d line(s)"
                % (os.path.basename(source) if source else None,
                   len(line_db)))
    accumulator = fmt.empty() if hasattr(fmt, "empty") else {}
    fmt.absorb(accumulator, path)
    return bool(accumulator), ("absorbed" if accumulator
                               else "ABSORBED NOTHING")


def test_every_artefact():
    """Every artefact filed under a format is readable by that format."""
    pair_list = []
    for name, (fmt, suffix_tuple, _tools) in sorted(_format_db().items()):
        directory = os.path.join(REAL, name)
        for artefact in _artefacts_of(directory, suffix_tuple):
            path = os.path.join(directory, artefact)
            try:
                absorbed, note = _absorbs(fmt, name, path)
            except Exception as error:                     # noqa: BLE001
                absorbed = False
                note     = "RAISED %s" % type(error).__name__
            pair_list.append((absorbed, "%-12s %-28s %s"
                                        % (name, artefact, note)))
    _verdict(_check(pair_list),
             "every real artefact is read by the format it is filed under.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Scenario coverage of the real parsing input",
        choice_map = {
            "every_format":   test_every_format,
            "every_artefact": test_every_artefact,
        }).run()
