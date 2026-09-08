#! /usr/bin/env python3
#
# @hwut {
#     title      = "The event line: one grammar, every kind, round trip"
#     choices    = ["roundtrip", "quoting", "refused"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
THE EVENT LINE (O-23): '<t>:<kind>:<content>' -- the same dict the
console renders, written as one line a human reads; the content a
string message, a CSV record or a JSON object, by the log language
definition ('CONTENT_DB').

    roundtrip   every kind of the vocabulary, with every field it can
                carry, through 'line_of' and back through 'event_of':
                the dict comes back whole (t aside, when derived)
    quoting     the three forms: a STRING kind's key with a space is
                double-quoted and its text runs verbatim to the end;
                a CSV kind's cell with a comma or a quote is quoted
                by the csv rules, an absent optional is empty; a JSON
                kind carries its list or dict; 't' first, two decimals
    refused     what is not of the grammar is named: no brackets, no
                '+t', a bare key, an unbalanced quote
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile
import config                                                     # noqa F401
from   config import HwutRunner                                   # noqa E402
from   vut.engine.protocol.vocabulary import KIND_DB, event       # noqa E402
from   vut.engine.protocol.line       import (line_of, event_of,  # noqa E402
                                              LineError, TEXT_FIELD_DB)

ORIGIN = "2026-09-07T13:17:02+00:00"
LATER  = "2026-09-07T13:17:02.412000+00:00"

_SAMPLE = {str: "sample text", int: 7, bool: True,
           list: ["a", "b c"], dict: {"k": "v", "test-b.sh": "FAILED"}}


def _check(pair_list):
    """RETURN: bool, True where every (condition, text) held; each printed."""
    ok = True
    for condition, text in pair_list:
        print("  %s: %s" % ("OK  " if condition else "FAIL", text))
        ok = ok and condition
    return ok


def _full(kind):
    """RETURN: dict, an event of that kind with EVERY field, required
    and optional, filled with a sample of its type."""
    required_db, optional_db = KIND_DB[kind]
    field_db = {}
    for name, field_type in list(required_db.items()) + list(optional_db.items()):
        field_db[name] = _SAMPLE[field_type]
    return event(kind, ORIGIN if kind == "tree-begun" else LATER, **field_db)


def test_roundtrip():
    """Every kind, every field, there and back."""
    pair_list = []
    for kind in sorted(KIND_DB):
        original = _full(kind)
        line     = line_of(original, ORIGIN)
        back     = event_of(line, ORIGIN)
        print("  %s" % line)
        same = all(back.get(k) == v for k, v in original.items() if k != "when")
        pair_list.append((same and abs(back["t"] - (0.0 if kind == "tree-begun" else 0.41)) < 0.001,
                          "%s: the dict comes back whole; t = %s" % (kind, back.get("t"))))
    pair_list.append((event_of(line_of(_full("fault"), ORIGIN), ORIGIN)["when"].startswith("2026-09-07T13:17:02.41"),
                      "'when' is derived from the origin and t"))
    ok = _check(pair_list)
    print("SUCCESS: one grammar, %d kinds, round trip" % len(KIND_DB))
    return ok


def test_quoting():
    """The three forms."""
    e = event("run-ended", LATER, directory="a/TEST", node="x y", node_kind="TEST",
              good=False, verdict="test-failed", cause='say "no"',
              report="tail, with ] inside")
    line = line_of(e, ORIGIN)
    print("  " + line)
    back = event_of(line, ORIGIN)
    r  = event("refused", LATER, directory="suite/TEST", node="test-c.sh two",
               text="no nominal: stands, really")
    rl = line_of(r, ORIGIN); rb = event_of(rl, ORIGIN)
    print("  " + rl)
    d  = event("dir-done", LATER, directory="s", good=True, fail_db={})
    dl = line_of(d, ORIGIN)
    print("  " + dl)
    ok = _check([
        (line.startswith("0.41:run-ended:"), "'t' first, two decimals, then the kind"),
        ('"say ""no"""' in line, "a CSV cell with a quote is quoted the csv way"),
        (line.endswith(",") and back.get("detail") is None, "an absent optional is an empty cell, and reads back absent"),
        (back["report"] == "tail, with ] inside" and back["good"] is False, "the cells read back typed"),
        ('"test-c.sh two": ' in rl, "a STRING key with a space is double-quoted"),
        (rb["text"] == "no nominal: stands, really" and rb["node"] == "test-c.sh two",
         "the text runs verbatim to the end, colons and commas and all"),
        (dl.endswith('"fail_db": {}}') and event_of(dl)["fail_db"] == {}, "a JSON kind carries its dict, empty included"),
    ])
    print("SUCCESS: three forms, one line shape, lossless")
    return ok


def test_refused():
    """What the grammar refuses, by name."""
    pair_list = []
    for bad in ("fault other/TEST: text", "x:fault:a: text", "0.10:nosuch:a: b",
                "0.10:fault:no-colon-text", "0.10:run-ended:a,b", "0.10:dir-done:{not json"):
        try:
            event_of(bad); pair_list.append((False, "%r read?!" % bad))
        except LineError as error:
            print("  %-34r -> %s" % (bad, error))
            pair_list.append((True, "%r refused" % bad))
    ok = _check(pair_list)
    print("SUCCESS: a line that is not of the grammar is named")
    return ok


if __name__ == "__main__":
    HwutRunner(argv=sys.argv, title="The event line", choice_map={
        "roundtrip": test_roundtrip, "quoting": test_quoting,
        "refused": test_refused}).run()
