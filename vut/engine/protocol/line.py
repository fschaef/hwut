"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE: THE EVENT LINE -- one event of the vocabulary as ONE LINE a
         human reads and a program parses, the same dict written
         differently (O-23).

    <t>:<kind>:<content>

    <t>         seconds since 'tree-begun', two decimals, ALWAYS first;
                wall time stands once, in tree-begun's content
    <kind>      the vocabulary's kind, as it is
    <content>   ONE of three forms, decided per kind by 'CONTENT_DB'
                -- THE LOG LANGUAGE DEFINITION:

        STRING  the kind's key fields, space-separated (a value with
                a space is "double-quoted"), then ': ', then the
                kind's free text verbatim to the end of the line
                    0.00:fault:other/TEST: line 4: unknown key 'ttile'
                    0.70:refused:suite/TEST "test-c.sh two": no nominal stands
        CSV     the kind's fields as one CSV record, in the table's
                order, required before optional, an absent optional
                empty; quoting is the csv module's
                    0.41:run-ended:suite/TEST,test-a.sh one,TEST,true,ok,,,
        JSON    the kind's fields as one JSON object, for the kinds
                that carry a list or a dict
                    0.71:dir-done:{"directory": "suite/TEST", "good": false, "fail_db": {"test-b.sh": "FAILED"}}

'line_of' and 'event_of' round-trip every kind of the vocabulary with
every field; that is their test. What differs per kind is the table's
choice of FORM; the line's shape is one.
______________________________________________________________________________
"""
import csv
import io
import json
from   datetime   import datetime, timezone, timedelta
from  .vocabulary import KIND_DB, FORMAT

#  THE LOG LANGUAGE DEFINITION: kind -> (form, key fields for STRING).
#  A kind absent here (a newer vocabulary) is written as JSON.
CONTENT_DB = {
    "tree-begun": ("json",   None),
    "dir-begun":  ("csv",    None),
    "frame":      ("csv",    None),
    "run-begun":  ("csv",    None),
    "run-ended":  ("csv",    None),
    "fault":      ("string", ("directory",)),
    "report":     ("string", ("directory",)),
    "refused":    ("string", ("directory", "node")),
    #  NO FREE TEXT: there is one reason a file is silent and the
    #  closing NOTE says it once, so the line carries names alone.
    "silent":     ("csv",    None),
    "dir-done":   ("json",   None),
    "tree-done":  ("csv",    None),
}
#  THE FREE TEXT of a STRING kind.
TEXT_FIELD_DB = {"fault": "text", "report": "text", "refused": "text"}


class LineError(ValueError):
    """A line the grammar cannot read; names the line."""


def _instant_of(text):
    """RETURN: datetime, the ISO-8601 instant, UTC."""
    if text.endswith("Z"): text = text[:-1] + "+00:00"
    instant = datetime.fromisoformat(text)
    if instant.tzinfo is None: instant = instant.replace(tzinfo=timezone.utc)
    return instant


def seconds_since(origin_when, when):
    """RETURN: float, 'when' minus 'origin_when' in seconds; 0.0 where
    either is missing or unreadable."""
    if not origin_when or not when: return 0.0
    try:
        return (_instant_of(when) - _instant_of(origin_when)).total_seconds()
    except ValueError:
        return 0.0


def _field_names(kind):
    """RETURN: list[str], the kind's fields in the table's order,
    required before optional; tree-begun carries 'when' first."""
    required_db, optional_db = KIND_DB.get(kind, ({}, {}))
    names = list(required_db) + list(optional_db)
    return (["when"] + names) if kind == "tree-begun" else names


def _cell(value):
    """RETURN: str, a value as a CSV cell: booleans as true/false,
    None as empty."""
    if value is None:         return ""
    if isinstance(value, bool): return "true" if value else "false"
    return str(value)


def _quoted(text):
    """RETURN: str, a STRING key field: bare, or double-quoted where
    it holds a space or a quote."""
    if text and " " not in text and '"' not in text: return text
    return '"' + text.replace('"', '""') + '"'


def line_of(event, origin_when=None):
    """
    RETURN: str, the event as one line, no newline: '<t>:<kind>:
            <content>', the content in the form 'CONTENT_DB' names
            for the kind.
    """
    kind = event["kind"]
    t    = seconds_since(origin_when, event.get("when"))
    form, key_tuple = CONTENT_DB.get(kind, ("json", None))
    if form == "string":
        text_field = TEXT_FIELD_DB.get(kind)
        head = " ".join(_quoted(str(event.get(k, ""))) for k in key_tuple)
        text = str(event.get(text_field, "")).replace("\n", " ")
        content = "%s: %s" % (head, text)
    elif form == "csv":
        out = io.StringIO()
        csv.writer(out, lineterminator="").writerow(
            [_cell(event.get(name)) for name in _field_names(kind)])
        content = out.getvalue()
    else:
        content = json.dumps({name: event[name] for name in _field_names(kind)
                              if name in event}, ensure_ascii=False)
    return "%.2f:%s:%s" % (t, kind, content)


def event_of(line, origin_when=None):
    """
    RETURN: dict, the event the line spells: 'format', 'kind', the
            fields, 't' (seconds since the origin) and -- where
            'origin_when' is given or the kind is tree-begun --
            'when'.

    Raises LineError where the line is not of the grammar.
    """
    line = line.rstrip("\n")
    part_list = line.split(":", 2)
    if len(part_list) != 3:
        raise LineError("not '<t>:<kind>:<content>': %r" % line)
    t_text, kind, content = part_list
    try:
        t = float(t_text)
    except ValueError:
        raise LineError("'<t>' is not a number: %r" % line)
    if kind not in KIND_DB:
        raise LineError("unknown kind %r: %r" % (kind, line))
    form, key_tuple = CONTENT_DB.get(kind, ("json", None))
    event = {"format": FORMAT, "kind": kind, "t": t}
    if form == "string":
        if ": " not in content:
            raise LineError("a STRING content wants '<keys>: <text>': %r" % line)
        head, text = content.split(": ", 1)
        keys = next(csv.reader([head], delimiter=" ", quotechar='"'))
        if len(keys) != len(key_tuple):
            raise LineError("%d key field(s) wanted, %d found: %r"
                            % (len(key_tuple), len(keys), line))
        for name, value in zip(key_tuple, keys): event[name] = value
        event[TEXT_FIELD_DB[kind]] = text
    elif form == "csv":
        cells = next(csv.reader([content]))
        names = _field_names(kind)
        if len(cells) != len(names):
            raise LineError("%d cell(s) wanted, %d found: %r"
                            % (len(names), len(cells), line))
        required_db, optional_db = KIND_DB[kind]
        for name, cell in zip(names, cells):
            field_type = required_db.get(name, optional_db.get(name, str))
            if cell == "" and name in optional_db: continue
            event[name] = _typed(cell, field_type, line)
    else:
        try:
            event.update(json.loads(content))
        except ValueError as error:
            raise LineError("not JSON: %s: %r" % (error, line))
    if "when" not in event and origin_when is not None:
        event["when"] = (_instant_of(origin_when)
                         + timedelta(seconds=t)).isoformat()
    return event


def _typed(cell, field_type, line):
    """RETURN: the cell as the vocabulary's type for that field."""
    try:
        if field_type is bool: return cell == "true"
        if field_type is int:  return int(cell)
        return cell
    except ValueError:
        raise LineError("%r is not %s: %r" % (cell, field_type.__name__, line))
