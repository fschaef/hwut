"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE EVENT VOCABULARY -- the shape of what the report queue
         carries (O-2, O-3). One flat JSON-able dict per event; the
         table below IS the format, and 'format_text()' prints it for
         the outside world.

THE STABILITY PROMISE: fields are only ever ADDED; a kind is never
removed and its stated fields never change meaning. A consumer must
ignore an unknown kind and unknown fields, and must treat an unknown
'verdict' as not-ok. 'FORMAT' rises only where that promise cannot
hold.

Kinds are plain ASCII strings, at most 9 bytes, unique -- a consumer
MAY zero-pad one into an integer and switch on it; the wire stays
legible.
______________________________________________________________________________
"""

FORMAT = 1

#  Everything that leads to the executability of a test IS the test
#  (O-3): 'run-ended' therefore names WHY in 'verdict', and 'cause'
#  names the node whose breaking failed this one. The verdict words
#  are OPEN under the add-only promise.
VERDICT_TUPLE = ("ok", "test-failed", "build-failed", "launch-failed",
                 "unsupported", "misdep", "unaccepted")

#  kind -> (required {field: type}, optional {field: type}).
#  'when' is on EVERY event and stated once below the table.
KIND_DB = {
    "tree-begun": ({"directory_list": list}, {}),
    "dir-begun":  ({"directory": str, "node_n": int}, {}),
    "frame":      ({"directory": str, "role": str, "good": bool}, {}),
    "run-begun":  ({"directory": str, "node": str,
                    "node_kind": str}, {}),
    "run-ended":  ({"directory": str, "node": str, "node_kind": str,
                    "good": bool, "verdict": str}, {"cause": str,
                                                    "report": str,
                                                    "detail": str}),
    "fault":      ({"directory": str, "text": str}, {}),
    "report":     ({"directory": str, "text": str}, {}),
    "refused":    ({"directory": str, "node": str, "text": str}, {}),
    "dir-done":   ({"directory": str, "good": bool,
                    "fail_db": dict}, {}),
    "tree-done":  ({"good": bool, "fail_n": int}, {"meta_n": int,
                                                     "skip_n": int}),
}

_FIELD_TEXT_DB = {
    "when":           "ISO-8601 UTC instant of the event",
    "directory":      "the test directory, RELATIVE to the root, "
                      "'/'-separated",
    "directory_list": "every test directory of the tree, walk order",
    "node_n":         "how many nodes the directory's plan holds",
    "role":           "'on_entry' or 'on_exit'",
    "good":           "true where the thing stood",
    "node":           "the plan node's name, e.g. 'test-a.py one', "
                      "'build[make test-a.py]'",
    "node_kind":      "'TEST', 'BUILD' or 'SESSION'",
    "verdict":        "WHY it ended so: " + ", ".join(VERDICT_TUPLE)
                      + ", ... (open; unknown reads not-ok)",
    "cause":          "the node whose breaking failed this one; "
                      "absent else",
    "detail":         "the report's numbers, where it has them: which "
                      "cap, the cap, the peak (O-19); absent else",
    "report":         "the operation's own word for WHY (open list, "
                      "e.g. 'pype-failed', 'test-app-stalled'); "
                      "absent where nothing finer than the verdict "
                      "is known",
    "text":           "one line, verbatim; on 'refused': WHY the node "
                      "named was not run (E-41)",
    "fail_db":        "node name -> terminal state, the failures "
                      "alone",
    "fail_n":         "how many nodes failed, tree-wide",
    "skip_n":         "how many cases the wish did not want -- present in "
                      "the tree, not selected, not run; the SKIPPED of the "
                      "closing bar",
    "meta_n":         "how many cases the standard label 'meta' hid from "
                      "a wish that named no label -- excluded, not run, "
                      "not refused; stated once in the closing numbers",
}


def format_text():
    """
    RETURN: str, the format description -- the promise, then every
            kind with its fields, required first, optional marked.
    """
    line_list = [
        "REPORT STREAM, format %d" % FORMAT,
        "",
        "One JSON object per event. Every event carries 'format' "
        "(int),",
        "'kind' (str) and 'when' (%s)." % _FIELD_TEXT_DB["when"],
        "After 'tree-done' one null closes the stream. A 'run-ended'",
        "may arrive WITHOUT a 'run-begun': a node that never",
        "dispatched -- [MISDEP], or failed by its supporter -- ends",
        "without starting.",
        "",
        "THE PROMISE: fields are only ever added; a kind is never",
        "removed. Ignore unknown kinds and fields; an unknown",
        "'verdict' reads not-ok. Kinds are ASCII, <= 9 bytes, unique:",
        "a consumer may zero-pad one into an integer.",
        "",
    ]
    for kind in KIND_DB:
        required_db, optional_db = KIND_DB[kind]
        line_list.append(kind)
        for name, field_type in required_db.items():
            line_list.append("    %-16s %-6s %s"
                             % (name, field_type.__name__,
                                _FIELD_TEXT_DB[name]))
        for name, field_type in optional_db.items():
            line_list.append("    %-16s %-6s (optional) %s"
                             % (name, field_type.__name__,
                                _FIELD_TEXT_DB[name]))
        line_list.append("")
    return "\n".join(line_list).rstrip() + "\n"


def event(kind, when, **field_db):
    """
    RETURN: dict, one event of the vocabulary: 'format', 'kind' and
            'when' beside the given fields.

    Raises AssertionError for a kind the table does not carry, a
    required field missing or badly typed, or a field the kind does
    not know -- the EMITTER is ours and a wrong event is a defect,
    named here, not a riddle at a consumer.
    """
    assert kind in KIND_DB, "unknown event kind '%s'" % kind
    required_db, optional_db = KIND_DB[kind]
    for name, field_type in required_db.items():
        assert name in field_db, \
               "'%s' misses its field '%s'" % (kind, name)
        assert isinstance(field_db[name], field_type), \
               "'%s': field '%s' is %s, not %s" \
               % (kind, name, type(field_db[name]).__name__,
                  field_type.__name__)
    for name in field_db:
        assert name in required_db or name in optional_db, \
               "'%s' does not know a field '%s'" % (kind, name)
    return dict(format=FORMAT, kind=kind, when=when, **field_db)
