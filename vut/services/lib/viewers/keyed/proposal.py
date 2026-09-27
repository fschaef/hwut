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

       The eq_pattern and nothing proposals are ONE line each, holding
       the patterns in force first: uncommenting it keeps what stood.

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


def proposal_line_list(pair_list, numeric_ratio=0.0, pattern_list=(),
                       nothing_list=(), whitespace_f=True):
    """
    RETURN: list[str], the proposal lines, every one a comment -- the
            head, then per proposal its key line and the lines naming
            where it came from.
            [], nothing differs in a way a tolerance could take.

    'pair_list' holds report.Pair records (line numbers, both cell
    lists) as the screen collected them; 'numeric_ratio', 'pattern_list',
    'nothing_list' and 'whitespace_f' are the tolerance in force.
    """
    numeric_list = []           # (deviation, subject, nominal, line_n_s)
    pattern_db   = {}           # pattern -> [(line_n_s, subject word, nominal word)]
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
            pattern = pattern_of(word_s, word_n)
            if pattern is None: continue
            pattern_db.setdefault(pattern, []).append(
                                         (pair.line_n_s, word_s, word_n))

    result = []
    numeric = _numeric_proposal(numeric_list, numeric_ratio)
    if numeric is not None: result.extend(numeric)
    new_list = [p for p in pattern_db if p not in pattern_list]
    if new_list:
        result.append("# eq_pattern = %s"
                      % _hocon_list(list(pattern_list) + new_list))
        for pattern in new_list:
            for line_n, word_s, word_n in pattern_db[pattern]:
                result.append("#     OUTPUT %i: '%s' vs '%s' -> \"%s\""
                              % (line_n, word_s, word_n, pattern))
    if blank_list:
        result.append("# whitespace = true")
        result.append("#     OUTPUT %s: blanks only"
                      % ", ".join(str(n) for n in blank_list))
    new_list = [p for p in nothing_db if p not in nothing_list]
    if new_list:
        result.append("# nothing = %s"
                      % _hocon_list(list(nothing_list) + new_list))
        for pattern in new_list:
            for line_n, word in nothing_db[pattern]:
                result.append("#     OUTPUT %i: '%s' on one side only"
                              % (line_n, word))
    return [HEAD] + result if result else []


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
    return ["# numeric_ratio = %s" % _short(ratio),
            "#     OUTPUT %i: %s vs %s -- %s%% + 10%%"
            % (line_n, s, n, _short(deviation * 100))]


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
