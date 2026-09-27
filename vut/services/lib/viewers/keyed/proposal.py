"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE TOLERANCE PROPOSALS (intend 21, section 4) -- the differences
         the screen holds in, commented 'tolerance' lines out.

DESCRIPTION
       "Discrepancies in, proposal out. This does not have to be perfect,
       just some idea that the user might pick up." (Frank-Rene)

       A proposal is a COMMENT. The ETPM pane shows the lines below the
       tolerance in force; the author uncomments what he wants and
       presses <F5>. Nothing here is ever applied unasked.

       NUMERIC    every number pair of two words that differ in their
                  numbers alone gives |s - n| / |n|, the tolerance being
                  the NOMINAL's (E-87). The largest, plus ten per cent,
                  rounded UP to three places, is proposed where it
                  exceeds the ratio in force. A pair that would need more
                  than 1 is left to the patterns. The words, not
                  compare's cells, are read: a line compare did not split
                  into elements arrives as ONE cell.
       WORDS      the two line texts are split into words and a line-
                  level diff pairs the words it substitutes. A pair that
                  differs only in numbers the NUMERIC rule covers is left
                  to it. Otherwise the shared prefix and suffix stay
                  LITERAL and the middle becomes a CLASS where both
                  middles are one, else a BUILT class: digits as 0-9,
                  every other character seen as itself, the lengths seen.
                  A prefix or suffix never ends inside a run of digits:
                  'v12' against 'v13' is 'v' and a number, not 'v1' and
                  a digit.
       BLANKS     a line pair equal but for blanks, where 'whitespace' is
                  off, proposes 'whitespace = true'.
       NOTHING    a word on one side only proposes itself, with the
                  blanks after it, for 'nothing' -- MEASURED: 'WARN'
                  alone left the separator after it standing against
                  nothing; 'WARN\\s*' took the pair.
       CHECKED    a pattern stands only where it compiles and matches
                  both words whole.

       The proposals come per KEY ('proposal_db'): the pane prints them
       under the key they would replace. An eq_pattern or nothing
       proposal holds the patterns in force first: uncommenting it keeps
       what stood. 'eq_pattern' has two alternatives where they differ:
       BY CLASS (above) and BY EDIT OPERATIONS ('edit_pattern_of').

       Pure: no screen, no compare; tested on made-up cells.
______________________________________________________________________________
"""
import difflib
import math
import re

HEAD = "# PROPOSALS -- uncomment what you want, then <F5>"

#  THE CLASSES a differing middle is tried against, first match wins.
#  'identifier' only where the pair shares no context: with context the
#  literal part already says what the word is, and a letter class says
#  more than was seen.
CLASS_LIST = (
    ("float",      r"[-+]?[0-9]*\.[0-9]+([eE][-+]?[0-9]+)?"),
    ("integer",    r"[-+]?[0-9]+"),
    ("hex",        r"0[xX][0-9a-fA-F]+"),
    ("date",       r"[0-9]{4}-[0-9]{2}-[0-9]{2}"),
    ("time",       r"[0-9]{2}:[0-9]{2}(:[0-9]{2})?(\.[0-9]+)?"),
    ("path",       r"(/[^ /]+)+/?"),
    ("identifier", r"[A-Za-z_][A-Za-z0-9_]*"),
)

#  "the deviation +10% or so" (Frank-Rene).
MARGIN = 1.1

_NUMBER_RE = re.compile(r"[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?")


def proposal_db(pair_list, numeric_ratio=0.0, pattern_list=(),
                nothing_list=(), whitespace_f=True):
    """
    RETURN: dict, tolerance key -> list[str], the proposal lines for that
            key, every one a comment: the key line(s) first, then the
            lines naming where they came from. The pane prints them
            DIRECTLY UNDER the key they would replace (ruled: "so users
            only have to comment the old and uncomment the new and see
            everything in one place").
            {}, nothing differs in a way a tolerance could take.

    'eq_pattern' has TWO alternatives where they differ (ruled: "one
    proposal that uses edit operations, another one as before"): 'by
    class' -- the classes and the shared context of 'pattern_of' -- and
    'by edit operations' -- the Levenshtein alignment's equal stretches
    literal, what it substitutes classed ('edit_pattern_of').

    'pair_list' holds report.Pair records (line numbers, both cell
    lists) as the screen collected them; 'numeric_ratio', 'pattern_list',
    'nothing_list' and 'whitespace_f' are the tolerance in force.
    """
    numeric_list = []           # (deviation, subject, nominal, line_n_s)
    origin_list  = []           # (line_n_s, subject word, nominal word, by class, by edit)
    nothing_db   = {}           # pattern -> [(line_n_s, word)]
    blank_list   = []           # line_n_s

    for pair in pair_list:
        if pair.line_n_s == -1 or pair.line_n_n == -1: continue
        text_s = _text_of(pair.cells_s, "subject")
        text_n = _text_of(pair.cells_n, "nominal")
        if text_s == text_n: continue
        if _blank_only_f(text_s, text_n):
            if not whitespace_f: blank_list.append(pair.line_n_s)
            continue
        for kind, word_s, word_n in _word_pair_list(text_s, text_n):
            if kind == "nothing":
                pattern = re.escape(word_s) + r"\s*"
                nothing_db.setdefault(pattern, []).append((pair.line_n_s, word_s))
                continue
            deviation_list = _number_deviation_list(word_s, word_n)
            if deviation_list is not None:
                numeric_list.extend(each + (pair.line_n_s,)
                                    for each in deviation_list)
                continue
            by_class = pattern_of(word_s, word_n)
            by_edit  = edit_pattern_of(word_s, word_n)
            if by_class is None and by_edit is None: continue
            origin_list.append((pair.line_n_s, word_s, word_n,
                                by_class, by_edit))

    result = {}
    numeric = _numeric_proposal(numeric_list, numeric_ratio)
    if numeric is not None: result["numeric_ratio"] = numeric
    if origin_list:
        result["eq_pattern"] = _pattern_proposal(origin_list, pattern_list)
        if not result["eq_pattern"]: del result["eq_pattern"]
    if blank_list:
        result["whitespace"] = ["# whitespace = true    # OUTPUT %s: blanks only"
                                % ", ".join(str(n) for n in blank_list)]
    new_list = [p for p in nothing_db if p not in nothing_list]
    if new_list:
        result["nothing"] = ["# nothing = %s"
                             % _hocon_list(list(nothing_list) + new_list)] \
                            + ["#     OUTPUT %i: '%s' on one side only"
                               % (line_n, word)
                               for pattern in new_list
                               for line_n, word in nothing_db[pattern]]
    return result


def proposal_line_list(pair_list, **tolerance_db):
    """RETURN: list[str], 'proposal_db' flattened, key by key, under the
               head line; [] where nothing is proposed."""
    db = proposal_db(pair_list, **tolerance_db)
    return [HEAD] + [line for key in db for line in db[key]] if db else []


def _pattern_proposal(origin_list, pattern_list):
    """RETURN: list[str], the eq_pattern lines: 'by class', 'by edit
               operations' -- one line where both are the same -- each
               holding the patterns in force first, then where they came
               from."""
    by_class = _unique(o[3] for o in origin_list if o[3] is not None)
    by_edit  = _unique(o[4] for o in origin_list if o[4] is not None)
    by_class = [p for p in by_class if p not in pattern_list]
    by_edit  = [p for p in by_edit  if p not in pattern_list]
    result = []
    if by_class and by_class == by_edit:
        result.append("# eq_pattern = %s    # by class and by edit operations"
                      % _hocon_list(list(pattern_list) + by_class))
    else:
        if by_class:
            result.append("# eq_pattern = %s    # by class"
                          % _hocon_list(list(pattern_list) + by_class))
        if by_edit:
            result.append("# eq_pattern = %s    # by edit operations"
                          % _hocon_list(list(pattern_list) + by_edit))
    if not result: return []
    for line_n, word_s, word_n, _, _ in origin_list:
        result.append("#     OUTPUT %i: '%s' vs '%s'" % (line_n, word_s, word_n))
    return result


def _unique(iterable):
    """RETURN: list, the items once each, in first-seen order."""
    result = []
    for item in iterable:
        if item not in result: result.append(item)
    return result


def edit_pattern_of(word_s, word_n):
    """
    RETURN: str, a regular expression matching both words whole, built
            from their Levenshtein alignment ('compare/core/
            edit_operations/string.py' reads the same library): every
            stretch both words share stays LITERAL, every stretch one
            substitutes, inserts or deletes becomes a class with the
            lengths seen. Where both sides of a stretch run through the
            same kinds of character -- letters then digits, say -- each
            run gets its own class: 'ab12' against 'zz7' is
            '[a-z]{2}[0-9]{1,2}', not one class for all.
            None, where the result does not match both words.

    A shared stretch of ONE character between two changed ones is taken
    as coincidence and joins them -- '2026-09-26' against '2026-01-02'
    shares a lone '2' that says nothing.
    """
    from rapidfuzz.distance import Levenshtein
    segment_list = []           # str (shared) | (str, str) (changed)
    for op in Levenshtein.opcodes(word_s, word_n):
        part_s = word_s[op.src_start:op.src_end]
        part_n = word_n[op.dest_start:op.dest_end]
        segment_list.append(part_s if op.tag == "equal" else (part_s, part_n))
    merged = []
    for i, segment in enumerate(segment_list):
        lone_f = isinstance(segment, str) and len(segment) == 1 \
                 and 0 < i < len(segment_list) - 1
        if lone_f: segment = (segment, segment)
        if isinstance(segment, tuple) and merged and isinstance(merged[-1], tuple):
            merged[-1] = (merged[-1][0] + segment[0], merged[-1][1] + segment[1])
        else:
            merged.append(segment)
    pattern = "".join(_escaped(segment) if isinstance(segment, str)
                      else _changed(*segment) for segment in merged)
    try:
        if re.fullmatch(pattern, word_s) and re.fullmatch(pattern, word_n):
            return pattern
    except re.error:
        pass
    return None


def _kind_of(c):
    """RETURN: str, the character's kind: 'd' digit, 'l' lower, 'u'
               upper, or the character itself."""
    if c.isdigit(): return "d"
    if c.isalpha(): return "l" if c.islower() else "u"
    return c


def _runs(text):
    """RETURN: list[(kind, str)], 'text' cut where the kind changes."""
    result = []
    for c in text:
        kind = _kind_of(c)
        if result and result[-1][0] == kind: result[-1] = (kind, result[-1][1] + c)
        else:                                result.append((kind, c))
    return result


_KIND_CLASS_DB = {"d": "[0-9]", "l": "[a-z]", "u": "[A-Z]"}


def _changed(part_s, part_n):
    """RETURN: str, the pattern for one changed stretch -- run by run
               where both sides run through the same kinds, else one
               class for everything seen."""
    runs_s, runs_n = _runs(part_s), _runs(part_n)
    if runs_s and [k for k, _ in runs_s] == [k for k, _ in runs_n]:
        return "".join(_escaped(a) if a == b else
                       _KIND_CLASS_DB.get(k, None) and _counted(_KIND_CLASS_DB[k], a, b)
                       or _built(a, b)
                       for (k, a), (_, b) in zip(runs_s, runs_n))
    kind_set = {_kind_of(c) for c in part_s + part_n}
    if len(kind_set) == 1 and next(iter(kind_set)) in _KIND_CLASS_DB:
        return _counted(_KIND_CLASS_DB[next(iter(kind_set))], part_s, part_n)
    if kind_set <= {"l", "u"}:
        return _counted("[A-Za-z]", part_s, part_n)
    if kind_set <= {"d", "l", "u"}:
        return _counted("[0-9A-Za-z]", part_s, part_n)
    return _built(part_s, part_n)


def _counted(klass, part_s, part_n):
    """RETURN: str, 'klass' with the lengths seen."""
    low, high = sorted((len(part_s), len(part_n)))
    if low == high == 1: return klass
    return klass + ("{%i}" % low if low == high else "{%i,%i}" % (low, high))


def pattern_of(word_s, word_n):
    """
    RETURN: str, a regular expression matching both words whole -- the
            shared prefix and suffix literal, the middle a class.
            None, where no pattern takes both (checked by compiling it).
    """
    pattern = _class_of(word_s, word_n, identifier_f=True)
    if pattern is None:
        prefix, middle_s, middle_n, suffix = _split(word_s, word_n)
        middle = _class_of(middle_s, middle_n, identifier_f=False) \
                 or _built(middle_s, middle_n)
        pattern = _escaped(prefix) + middle + _escaped(suffix)
    try:
        if re.fullmatch(pattern, word_s) and re.fullmatch(pattern, word_n):
            return pattern
    except re.error:
        pass
    return None


def _class_of(text_s, text_n, identifier_f):
    """RETURN: str, the first class of CLASS_LIST both texts match whole;
               'identifier' only where 'identifier_f'.
               None, where no class takes both."""
    for name, expression in CLASS_LIST:
        if name == "identifier" and not identifier_f: continue
        if re.fullmatch(expression, text_s) and re.fullmatch(expression, text_n):
            return expression
    return None


def _escaped(text):
    """RETURN: str, 'text' as a regular expression matching itself -- only
               the characters that mean something escaped, so a pattern
               stays readable ('re.escape' escapes '-' and '=' too)."""
    return "".join("\\" + c if c in ".^$*+?{}[]\\|()" else c for c in text)


def _split(word_s, word_n):
    """RETURN: (prefix, middle_s, middle_n, suffix) -- what both words
               share before and after the part that varies. Neither
               edge ends inside a run of digits."""
    i = 0
    while i < min(len(word_s), len(word_n)) and word_s[i] == word_n[i]: i += 1
    while i and word_s[i - 1].isdigit(): i -= 1
    j = 0
    while j < min(len(word_s), len(word_n)) - i \
          and word_s[-1 - j] == word_n[-1 - j]: j += 1
    while j and word_s[len(word_s) - j].isdigit(): j -= 1
    return (word_s[:i], word_s[i:len(word_s) - j],
            word_n[i:len(word_n) - j], word_s[len(word_s) - j:])


def _built(middle_s, middle_n):
    """RETURN: str, the class of every character seen in either middle --
               digits as '0-9', the rest as themselves -- with the
               lengths seen."""
    seen = set(middle_s + middle_n)
    body = "0-9" if any(c.isdigit() for c in seen) else ""
    body += "".join(_class_escaped(c) for c in sorted(seen) if not c.isdigit())
    low, high = sorted((len(middle_s), len(middle_n)))
    count = "{%i}" % low if low == high else "{%i,%i}" % (low, high)
    if not body: return ""
    return "[%s]%s" % (body, count)


def _class_escaped(c):
    """RETURN: str, 'c' as it may stand inside a character class."""
    return "\\" + c if c in "\\]^-[" else c


def _numeric_proposal(numeric_list, numeric_ratio):
    """RETURN: list[str], the numeric_ratio line and its origin line.
               None, where the proposed ratio does not exceed the one in
               force."""
    if not numeric_list: return None
    deviation, s, n, line_n = max(numeric_list)
    ratio = min(1.0, math.ceil(deviation * MARGIN * 1000) / 1000)
    if ratio <= numeric_ratio: return None
    return ["# numeric_ratio = %s    # OUTPUT %i: %s vs %s -- %s%% + 10%%"
            % (_short(ratio), line_n, s, n, _short(deviation * 100))]


def _word_pair_list(text_s, text_n):
    """RETURN: list[(kind, subject word, nominal word)] -- 'replace' for a
               word the diff substitutes, 'nothing' for a word standing
               on one side only (its partner is then ''). Where the diff
               replaces unequal counts, each side's words are joined."""
    word_s, word_n = text_s.split(), text_n.split()
    matcher = difflib.SequenceMatcher(None, word_s, word_n, autojunk=False)
    result = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace":
            if i2 - i1 == j2 - j1:
                result.extend(("replace", a, b)
                              for a, b in zip(word_s[i1:i2], word_n[j1:j2]))
            else:
                result.append(("replace", " ".join(word_s[i1:i2]),
                               " ".join(word_n[j1:j2])))
        elif tag == "delete":
            result.extend(("nothing", w, "") for w in word_s[i1:i2])
        elif tag == "insert":
            result.extend(("nothing", w, "") for w in word_n[j1:j2])
    return result


def _number_deviation_list(word_s, word_n):
    """RETURN: list[(deviation, subject number, nominal number)], where the
               two words differ in their numbers alone and every number
               pair deviates so little that, with the margin, the ratio
               stays at most 1 -- the numeric proposal takes such a pair; |s - n| / |n|, the tolerance being the
               NOMINAL's (E-87).
               None, where the words differ otherwise, or a number
               deviates further (or its nominal is 0): a pattern then
               takes the pair."""
    if _NUMBER_RE.sub("#", word_s) != _NUMBER_RE.sub("#", word_n): return None
    list_s = [m.group(0) for m in _NUMBER_RE.finditer(word_s)]
    list_n = [m.group(0) for m in _NUMBER_RE.finditer(word_n)]
    if len(list_s) != len(list_n): return None
    result = []
    for text_s, text_n in zip(list_s, list_n):
        s, n = float(text_s), float(text_n)
        if s == n: continue
        if n == 0 or abs(s - n) / abs(n) * MARGIN > 1.0: return None
        result.append((abs(s - n) / abs(n), text_s, text_n))
    return result


def _blank_only_f(text_s, text_n):
    """RETURN: bool, True where the texts differ in blanks alone."""
    return text_s.split() == text_n.split()


def _text_of(cell_list, side):
    """RETURN: str, the line as compare read it, its cells joined; a cell
               with no text on this side contributes nothing."""
    return "".join(getattr(cell, side, None) or "" for cell in cell_list)


def _kind(cell):
    return cell.tolerance_id.name


def _ok(cell):
    relation = getattr(cell, "relation_id", None)
    return relation is None or relation.name.startswith("OK_")


def _short(x):
    """RETURN: str, 'x' short and exact enough to read."""
    return "%.6g" % x


def _hocon_list(pattern_list):
    """RETURN: str, the patterns as a HOCON list of quoted strings --
               backslash and quote escaped, as a header writes them."""
    return "[%s]" % ", ".join(
        '"%s"' % p.replace("\\", "\\\\").replace('"', '\\"')
        for p in pattern_list)
