"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE LINE ELEMENTS ON THE SCREEN (services E-87) -- what compare
         read in a line, placed onto the line as the screen shows it, and
         what the status bar says about one of them.

DESCRIPTION
       Compare's cells are the line's elements, but NOT the line: its
       leading whitespace is gone ('  indented' arrives as 'indented').
       MEASURED: looking a line up by its exact text missed every
       indented line, which then wore no colour at all. So a line is
       looked up by its STRIPPED text, and the pieces are PLACED onto
       the real text in order; what lies between them is separator.

       A piece carries what the status bar needs: the element kind,
       whether compare found it DIFFERING, and -- for a number -- its
       partner's text, since compare's tolerance is the NOMINAL's:
       a subject number 's' passes against 'n' where |s - n| <= |n|*ratio.

       No 'prompt_toolkit' here: this module is tested without a screen.
______________________________________________________________________________
"""
from collections import namedtuple

Piece = namedtuple("Piece", "kind text differs_f partner")

META_KIND_SET = {"NUMERIC", "ANALOGY", "EQUIVALENCE_PATTERN",
                 "CONSTRAINT_BINDING", "VISIBLE_NOTHING"}
SEPARATOR     = "SEPERATOR"          # compare's own spelling


def key_of(text):
    """RETURN: str, the text a line is looked up by -- stripped, since
               compare's cells carry no leading or trailing blank."""
    return text.strip()


def pieces_of_cells(cell_list, side, other_list=()):
    """RETURN: list[Piece], one per cell of 'side' ('subject' or
               'nominal') -- kind, text, whether compare found it
               differing, and for a number the partner number's text
               from 'other_list' (the other side's cells), else None."""
    partner_db = {}
    if side == "subject":
        for cell in other_list:
            ref = getattr(cell, "subject_ref_i", None)
            if ref is not None: partner_db[ref] = getattr(cell, "nominal", None)
    else:
        for i, cell in enumerate(other_list):
            partner_db[i] = getattr(cell, "subject", None)
    result = []
    for i, cell in enumerate(cell_list):
        relation = getattr(cell, "relation_id", None)
        differs_f = relation is not None \
                    and not relation.name.startswith("OK_")
        if side == "subject":
            partner = partner_db.get(i)
        else:
            ref = getattr(cell, "subject_ref_i", None)
            partner = partner_db.get(ref) if ref is not None else None
        result.append(Piece(cell.tolerance_id.name,
                            getattr(cell, side) or "", differs_f, partner))
    return result


def placed(line_text, piece_list):
    """RETURN: list[Piece], 'piece_list' laid onto 'line_text' in order,
               the text between them as SEPARATOR pieces -- together
               exactly 'line_text'.
               None, where a piece is not found in order: the line is
               then drawn whole, never wrongly split."""
    result, position = [], 0
    for piece in piece_list:
        if not piece.text: continue
        found = line_text.find(piece.text, position)
        if found < 0: return None
        if found > position:
            result.append(Piece(SEPARATOR, line_text[position:found],
                                False, None))
        result.append(piece)
        position = found + len(piece.text)
    if position < len(line_text):
        result.append(Piece(SEPARATOR, line_text[position:], False, None))
    return result


def meta_index_list(piece_list):
    """RETURN: list[int], the pieces the element cursor stops on -- a
               kind that can vary, or a piece compare found differing."""
    return [i for i, piece in enumerate(piece_list)
            if piece.kind in META_KIND_SET or piece.differs_f]


def status_of(piece, side, ratio):
    """RETURN: str, the status bar's sentence on one piece: what it is,
               and what compare allows it or found about it."""
    other = "GOOD" if side == "subject" else "OUTPUT"
    part_list = []
    if piece.kind == "NUMERIC":
        part_list.append("numeric %s: %s" % (piece.text,
                         _numeric_text(piece, side, ratio)))
    elif piece.kind == "ANALOGY":
        part_list.append("analogy %s: may differ, the same way every time"
                         % piece.text)
    elif piece.kind == "EQUIVALENCE_PATTERN":
        part_list.append("pattern %s: equal to what the same pattern "
                         "matches" % piece.text)
    elif piece.kind == "CONSTRAINT_BINDING":
        part_list.append("binding %s: bound by a constraint" % piece.text)
    elif piece.kind == "VISIBLE_NOTHING":
        part_list.append("visible nothing: may be absent")
    else:
        part_list.append("%r" % piece.text)
    if piece.differs_f:
        part_list.append("DIFFERS from %s%s" % (other,
                         " (%s)" % piece.partner if piece.partner else ""))
    return " -- ".join(part_list)


def line_status(piece_list):
    """RETURN: str, the status bar's sentence on a line nothing in which
               is selected: how many elements can vary, how many differ,
               and the keys that step to them.
               '', where the line has none."""
    index_list = meta_index_list(piece_list or ())
    if not index_list: return ""
    count_db = {}
    for i in index_list:
        kind = piece_list[i].kind
        name = {"EQUIVALENCE_PATTERN": "pattern",
                "CONSTRAINT_BINDING": "binding",
                "VISIBLE_NOTHING": "nothing"}.get(kind, kind.lower())
        if kind in META_KIND_SET:
            count_db[name] = count_db.get(name, 0) + 1
    differ_n = sum(1 for i in index_list if piece_list[i].differs_f)
    word_list = ["%i %s" % (n, name) for name, n in sorted(count_db.items())]
    if differ_n: word_list.append("%i differing" % differ_n)
    return "%s -- <w>/<b> step to them" % ", ".join(word_list)


def _numeric_text(piece, side, ratio):
    """RETURN: str, the number's allowance. Compare's rule: a subject
               number passes against nominal 'n' where
               |s - n| <= |n| * ratio -- the interval is the NOMINAL's."""
    anchor = piece.text if side == "nominal" else piece.partner
    try:
        n = float(anchor)
    except (TypeError, ValueError):
        return "compared by value" + ("" if not ratio else
                                      " within %s of GOOD's" % _percent(ratio))
    if not ratio:
        return "compared by value, exactly (ratio 0)"
    epsilon = abs(n) * ratio
    return "tolerated within [%s, %s] (ratio %s)" % (
        _number(n - epsilon), _number(n + epsilon), _percent(ratio))


def _number(x):
    """RETURN: str, 'x' short and exact enough to read."""
    return ("%.6g" % x)


def _percent(ratio):
    """RETURN: str, 'ratio' as a percentage, e.g. '1%'."""
    return ("%.6g" % (ratio * 100)) + "%"
