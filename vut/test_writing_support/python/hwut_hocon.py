"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Parse the HOCON subset of the specification language into the
         ANNOTATED TREE: every key, every value and every block carries its
         file-relative position.

This module is SUPPORT FOR WRITING TESTS, not part of the engine: a test
author in any language meets this grammar, and every supported language is
given a parser that behaves the same way. It depends on nothing but the
standard library, and names no engine type.

THE SUBSET: nested objects, lists, numbers, booleans (true/false/yes/no),
the spellings of nothing, '#' and '//' comments, '=' or ':' before a value,
a brace directly after a key. A dot inside a key is a literal character,
never a path -- 'test-gen.c' is one key.

A STRING VALUE IS WRITTEN IN DOUBLE QUOTES. Real HOCON admits the unquoted
string and pays for it: an unquoted value runs to the end of the line, so a
comment marker ends a value, two entries cannot share a line without
ambiguity, and 'yes' is a boolean while 'yes please' is a string. The quotes
are no burden once one is used to them, and they say plainly where a value
begins and ends.

REFUSED BY NAME, each with a fault: 'include', substitutions '${...}',
'+=', and triple-quoted strings. The first two would let a specification
refer outside its file.

The parser accumulates faults and recovers at the next line; it never
raises. The annotated tree lives between this parser and the validator and
nowhere else.
______________________________________________________________________________
"""
import re

from dataclasses import dataclass, field
from enum        import Enum, auto


class E_ParseFault(Enum):
    SYNTAX  = auto()    # the text does not parse
    REFUSED = auto()    # a construct that does not exist here, by name


@dataclass(frozen=True, slots=True)
class Position:
    """One place in one file; 1-based, as an editor counts."""
    line:   int
    column: int

    def __str__(self):
        """RETURN: str, 'line:column'."""
        return "%d:%d" % (self.line, self.column)


@dataclass(frozen=True, slots=True)
class ParseFault:
    """One fault of the parse, where it stands and what it is. The engine
    converts it into its own fault record; this module knows nothing of
    that record."""
    kind:     E_ParseFault
    file:     str
    position: Position
    message:  str

    def __str__(self):
        """RETURN: str, 'file:line:column: KIND: message'."""
        return "%s:%s: %s: %s" % (self.file, self.position,
                                  self.kind.name, self.message)


@dataclass(frozen=True, slots=True)
class SourceLine:
    """One line as the parser reads it, tied to where it stands on disk.
    'column_offset' counts what was removed before 'text' begins."""
    text:          str
    line:          int
    column_offset: int

_BOOL_DB  = {"true": True, "yes": True, "false": False, "no": False}

#  The spellings of NOTHING. A key bound to one of these carries the NULL
#  value -- a ScalarNode whose value is 'None'. An empty value ('a =' and
#  the line's end) is the same thing. What null MEANS is each key's own
#  affair; the validator decides, not the parser.
_NULL_SET = ("null", "nil", "none", "nihil")

#  THE NUMBER, in every radix, with '_' admitted anywhere between digits
#  as a visual helper and carried by none of them into the value.
#
#      decimal   +7e212   -0.12   1_000   .5   6.02e23
#      hex       0xDEAD_BEEF
#      binary    0b0111_11_01
#      octal     0o3124
#      roman     0rIV
#
#  A sign may stand apart from its digits ('- 0.12'); the two are joined
#  where nothing but blanks lies between them.
_SIGN_SET = ("+", "-")

_DECIMAL_RE = re.compile(r"""[-+]?
    (?: [0-9](?:_?[0-9])*             (?: \. (?:[0-9](?:_?[0-9])*)? )?
      | \.[0-9](?:_?[0-9])* )
    (?: [eE][-+]?[0-9](?:_?[0-9])* )? $""", re.X)

_RADIX_DB = {"0x": 16, "0X": 16, "0b": 2, "0B": 2, "0o": 8, "0O": 8}
_RADIX_DIGIT_DB = {16: "0123456789abcdefABCDEF",
                    2: "01",
                    8: "01234567"}

_ROMAN_RE    = re.compile(r"M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})"
                          r"(IX|IV|V?I{0,3})$")
_ROMAN_VALUE_DB = {"I": 1, "V": 5, "X": 10, "L": 50,
                   "C": 100, "D": 500, "M": 1000}


#  Returned where a bare token is none of the above: an unquoted string.
_NOT_A_TOKEN = object()

#  A TOKEN -- a key, or a bare value -- runs to the first character that
#  binds, opens, closes or separates. Blanks end it too: a bare value is a
#  boolean, a number or a spelling of nothing, and a string carries quotes
#  (R-49). Matching the whole run in one step is what makes the scan
#  cheap.
_TOKEN_RE = re.compile(r'[^\s{}\[\]=,:"#]*')

#  A string with no backslash in it -- the common case -- is taken whole.
_QUOTED_PLAIN_RE = re.compile(r'([^"\\\n]*)"')

_ESCAPE_DB = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}




@dataclass(frozen=True, slots=True)
class ScalarNode:
    """One scalar value: str, int, float or bool."""
    value:    object
    position: Position


@dataclass(frozen=True, slots=True)
class ListNode:
    """One list of nodes."""
    item_list: tuple
    position:  Position


@dataclass(frozen=True, slots=True)
class Entry:
    """One key with its value inside an object."""
    key:          str
    key_position: Position
    node:         object


@dataclass(slots=True)
class ObjectNode:
    """One object: ordered entries, duplicate keys refused at parse."""
    position:   Position
    entry_list: list = field(default_factory=list)

    def get(self, key):
        """
        RETURN: Entry, the entry named 'key'.
                None,  no such entry.
        """
        for entry in self.entry_list:
            if entry.key == key: return entry
        return None

    def keys(self):
        """RETURN: list[str], the keys in written order."""
        return [entry.key for entry in self.entry_list]


class _Cursor:
    """Walks a list of SourceLines character by character; every position
    it reports is file-relative through the lines' offsets.

    The current line's text is held in a slot: every 'peek' would otherwise
    index the line list and the dataclass to reach the same string.
    """
    __slots__ = ("line_list", "line_n", "i_line", "i_col", "text")

    def __init__(self, line_list):
        """RETURN: _Cursor at the first character."""
        self.line_list = line_list
        self.line_n    = len(line_list)
        self.i_line    = 0
        self.i_col     = 0
        self.text      = line_list[0].text if line_list else ""

    def at_end(self):
        """RETURN: bool, no character remains."""
        return self.i_line >= self.line_n

    def peek(self, ahead=0):
        """
        RETURN: str,  the character 'ahead' places from here, on this line.
                '\\n', at this line's end.
                '',   beyond the last line.
        """
        if self.i_line >= self.line_n: return ""
        i = self.i_col + ahead
        text = self.text
        return text[i] if i < len(text) else "\n"

    def advance(self):
        """RETURN: None. Steps one character; line ends step to the next
        line."""
        if self.i_line >= self.line_n:       return
        if self.i_col < len(self.text):      self.i_col += 1
        else:                                self.skip_line()

    def skip(self, n):
        """RETURN: None. Steps 'n' characters WITHIN the current line; the
        caller has already seen that they are there."""
        self.i_col += n

    def skip_line(self):
        """RETURN: None. Steps to the beginning of the next line."""
        self.i_line += 1
        self.i_col   = 0
        self.text    = (self.line_list[self.i_line].text
                        if self.i_line < self.line_n else "")

    def position(self):
        """RETURN: Position, file-relative, of the character at the
        cursor."""
        if self.i_line >= self.line_n:
            if not self.line_list: return Position(1, 1)
            last = self.line_list[-1]
            return Position(last.line,
                            last.column_offset + len(last.text) + 1)
        line = self.line_list[self.i_line]
        return Position(line.line, line.column_offset + self.i_col + 1)


def parse(line_list, file):
    """
    RETURN: [0] ObjectNode, the document -- every entry of the outermost
                            level; possibly empty.
            [1] list[Fault], every fault found; empty on a clean parse.

    'line_list' are SourceLines; 'file' names the file for faults.
    """
    fault_list = []
    cursor     = _Cursor(line_list)
    document   = _parse_body(cursor, None, file, fault_list)
    return document, fault_list


def _parse_body(cursor, terminator, file, fault_list):
    """
    RETURN: ObjectNode, the entries up to 'terminator' ('}' or None for
            the end of the text).
    """
    result = ObjectNode(cursor.position())
    while True:
        _skip_blank(cursor)
        if cursor.at_end():
            if terminator is not None:
                fault_list.append(ParseFault(
                    E_ParseFault.SYNTAX, file, cursor.position(),
                    "unterminated object: '%s' missing" % terminator))
            return result

        match cursor.peek():
            case c if c == terminator:
                cursor.skip(1)
                return result
            case "}":
                fault_list.append(ParseFault(
                    E_ParseFault.SYNTAX, file, cursor.position(),
                    "unmatched '}'"))
                cursor.skip(1)
            case _:
                _parse_entry(cursor, result, file, fault_list)


def _parse_entry(cursor, object_node, file, fault_list):
    """RETURN: None. Parses one 'key = value' pair into 'object_node';
    faults recover at the next line."""
    key_position = cursor.position()
    key          = _parse_key(cursor, file, fault_list)
    if key is None:
        cursor.skip_line()
        return

    if key == "include":
        fault_list.append(ParseFault(
            E_ParseFault.REFUSED, file, key_position,
            "'include' does not exist here: a specification refers to "
            "nothing outside its file"))
        cursor.skip_line()
        return

    _skip_space(cursor)

    match cursor.peek():
        case "=" | ":":
            cursor.skip(1)
            _skip_space(cursor)
        case "{":
            pass                          # a brace binds without a sign
        case "+" if cursor.peek(1) == "=":
            fault_list.append(ParseFault(
                E_ParseFault.REFUSED, file, cursor.position(),
                "'+=' does not exist here"))
            cursor.skip_line()
            return
        case _:
            fault_list.append(ParseFault(
                E_ParseFault.SYNTAX, file, cursor.position(),
                "expected '=', ':' or '{' after key '%s'" % key))
            cursor.skip_line()
            return

    node = _parse_value(cursor, file, fault_list)
    if node is None:
        #  The value parser has recovered already (line skipped or cursor
        #  at the fault); a second skip here would eat the NEXT line.
        return

    if object_node.get(key) is not None:
        fault_list.append(ParseFault(
            E_ParseFault.SYNTAX, file, key_position,
            "duplicate key '%s'; the first stands, this one is refused"
            % key))
        return
    object_node.entry_list.append(Entry(key, key_position, node))


def _parse_key(cursor, file, fault_list):
    """
    RETURN: str,  the key.
            None, no key stands here (fault recorded).

    A key runs to the first character that binds, opens, closes or
    separates -- matched in one step rather than one character at a time.
    """
    if cursor.peek() == '"':
        return _parse_quoted(cursor, file, fault_list)

    text = _TOKEN_RE.match(cursor.text, cursor.i_col).group()
    if not text:
        fault_list.append(ParseFault(
            E_ParseFault.SYNTAX, file, cursor.position(),
            "expected a key, found '%s'" % cursor.peek().strip()))
        return None
    cursor.skip(len(text))
    return text


def _parse_value(cursor, file, fault_list, in_list_f=False):
    """
    RETURN: ScalarNode | ListNode | ObjectNode, the value here.
            None, nothing usable stands here (fault recorded).

    'in_list_f' says an empty value is a fault rather than null: inside a
    list there is no key it could belong to.
    """
    _skip_space(cursor)
    position = cursor.position()

    match cursor.peek():
        case "{":
            cursor.skip(1)
            return _parse_body(cursor, "}", file, fault_list)
        case "[":
            cursor.skip(1)
            return _parse_list(cursor, position, file, fault_list)
        case '"' if cursor.peek(1) == '"' and cursor.peek(2) == '"':
            fault_list.append(ParseFault(
                E_ParseFault.REFUSED, file, position,
                "triple-quoted strings do not exist here"))
            cursor.skip_line()
            return None
        case '"':
            value = _parse_quoted(cursor, file, fault_list)
            return None if value is None else ScalarNode(value, position)
        case "$" if cursor.peek(1) == "{":
            fault_list.append(ParseFault(
                E_ParseFault.REFUSED, file, position,
                "substitutions '${...}' do not exist here: a "
                "specification refers to nothing outside its file"))
            cursor.skip_line()
            return None
        case _:
            return _parse_bare(cursor, position, file, fault_list,
                               in_list_f)


def _parse_list(cursor, position, file, fault_list):
    """RETURN: ListNode, the items up to ']'."""
    item_list = []
    while True:
        _skip_blank(cursor)
        if cursor.at_end():
            fault_list.append(ParseFault(
                E_ParseFault.SYNTAX, file, cursor.position(),
                "unterminated list: ']' missing"))
            break
        match cursor.peek():
            case "]":
                cursor.skip(1)
                break
            case ",":
                cursor.skip(1)
            case _:
                item = _parse_value(cursor, file, fault_list,
                                    in_list_f=True)
                if item is not None: item_list.append(item)
    return ListNode(tuple(item_list), position)


def _parse_quoted(cursor, file, fault_list):
    """
    RETURN: str,  the string's content, escapes resolved.
            None, the string is unterminated at its line's end.

    The common case -- a string with no backslash in it -- is taken in one
    step: the closing quote is FOUND rather than walked to.
    """
    begin = cursor.position()
    text  = cursor.text
    i     = cursor.i_col + 1                       # past the opening quote

    match = _QUOTED_PLAIN_RE.match(text, i)
    if match is not None:
        cursor.i_col = match.end()
        return match.group(1)

    piece_list = []
    while True:
        if i >= len(text):
            fault_list.append(ParseFault(
                E_ParseFault.SYNTAX, file, begin, "unterminated string"))
            cursor.i_col = i
            return None
        c = text[i]
        match c:
            case '"':
                cursor.i_col = i + 1
                return "".join(piece_list)
            case "\\":
                i += 1
                escaped = text[i] if i < len(text) else ""
                piece_list.append(_ESCAPE_DB.get(escaped, escaped))
                i += 1
            case _:
                piece_list.append(c)
                i += 1


def _parse_bare(cursor, position, file, fault_list, in_list_f):
    """
    RETURN: ScalarNode, the bare token here: a boolean, a number, or one
            of the spellings of nothing.
            None, the token is none of those (fault recorded) -- a string
            value is written in double quotes.

    A bare token ends at a blank: a value with blanks in it is a string
    and carries quotes. The run is matched in one step.
    """
    raw = _TOKEN_RE.match(cursor.text, cursor.i_col).group()

    #  A SIGN STANDING APART from its digits: '- 0.12'. A bare token ends
    #  at a blank, so the sign arrives alone; where nothing but blanks
    #  lies between it and a number, the two are one number.
    if raw in _SIGN_SET:
        text  = cursor.text
        after = _TOKEN_RE.match(text, _blank_end(text,
                                                 cursor.i_col + 1)).group()
        if after and _number(after) is not _NOT_A_TOKEN:
            cursor.i_col = _blank_end(text, cursor.i_col + 1) + len(after)
            return ScalarNode(_number(raw + after), position)

    if raw.startswith("${"):
        fault_list.append(ParseFault(
            E_ParseFault.REFUSED, file, cursor.position(),
            "substitutions '${...}' do not exist here"))
        cursor.skip_line()
        return None
    i_comment = raw.find("//")
    if i_comment != -1: raw = raw[:i_comment]
    cursor.skip(len(raw))

    if not raw:
        if in_list_f:
            fault_list.append(ParseFault(
                E_ParseFault.SYNTAX, file, position,
                "expected a value, found '%s'" % cursor.peek().strip()))
            return None
        return ScalarNode(None, position)          # an empty value is null

    value = _interpret(raw)
    if value is _NOT_A_TOKEN:
        fault_list.append(ParseFault(
            E_ParseFault.SYNTAX, file, position,
            'a string is written in double quotes: "%s"' % raw))
        return None
    return ScalarNode(value, position)


def _interpret(raw):
    """
    RETURN: None, bool, int or float -- what the bare text says; 'None'
            for the spellings of nothing.
            '_NOT_A_TOKEN', the text is no bare token at all: it is an
            unquoted string, and this language has none.
    """
    match raw:
        case _ if raw in _NULL_SET:     return None
        case _ if raw in _BOOL_DB:      return _BOOL_DB[raw]
        case _:                         return _number(raw)


def _number(raw):
    """
    RETURN: int | float, the number the text spells, in whatever radix it
            spells it; '_' is a visual helper and enters no value.
            '_NOT_A_TOKEN', the text spells no number.
    """
    body = raw[1:] if raw[:1] in _SIGN_SET else raw
    sign = -1 if raw[:1] == "-" else 1

    match body[:2]:
        case "0r" | "0R":
            value = _roman(body[2:])
            #  A refusal is a refusal: it must not be signed.
            return value if value is _NOT_A_TOKEN else sign * value
        case prefix if prefix in _RADIX_DB:
            radix = _RADIX_DB[prefix]
            digit_set = _RADIX_DIGIT_DB[radix]
            digit_text = _without_helper(body[2:], digit_set)
            if digit_text is None: return _NOT_A_TOKEN
            return sign * int(digit_text, radix)

    if not _DECIMAL_RE.match(raw): return _NOT_A_TOKEN
    text = raw.replace("_", "")
    if "." in text or "e" in text or "E" in text: return float(text)
    return int(text)


def _without_helper(text, digit_set):
    """
    RETURN: str, the text with every '_' removed.
            None, the text carries no digit, or a character that is no
            digit of this radix, or an '_' that separates nothing.
    """
    if not text or text[0] == "_" or text[-1] == "_": return None
    if "__" in text:                                  return None
    stripped = text.replace("_", "")
    if not stripped:                                  return None
    if any(c not in digit_set for c in stripped):     return None
    return stripped


def _roman(text):
    """
    RETURN: int, the number the roman numeral spells.
            '_NOT_A_TOKEN', the text is no roman numeral -- 'IIII' and
            'VX' among them: the form is the strict one.
    """
    if not text or not _ROMAN_RE.match(text): return _NOT_A_TOKEN
    total    = 0
    previous = 0
    for character in reversed(text):
        value = _ROMAN_VALUE_DB[character]
        total = total - value if value < previous else total + value
        previous = max(previous, value)
    return total


def _blank_end(text, i):
    """RETURN: int, the index of the first character at or after 'i' that
    is no blank."""
    n = len(text)
    while i < n and (text[i] == " " or text[i] == "\t"): i += 1
    return i


def _skip_space(cursor):
    """RETURN: None. Skips blanks and comments on the current line.

    Written flat, against the line's own text: this is the most called
    function of the parser, and a call into 'peek' per character was the
    parse's largest single cost.
    """
    text = cursor.text
    n    = len(text)
    i    = cursor.i_col
    while i < n and (text[i] == " " or text[i] == "\t"): i += 1
    cursor.i_col = i
    if i < n and (text[i] == "#" or text.startswith("//", i)):
        cursor.skip_line()


def _skip_blank(cursor):
    """RETURN: None. Skips blanks, newlines, commas and comments.

    A line whose remainder is blank, or which turns out to be a comment,
    is left in one step rather than a character at a time.
    """
    while cursor.i_line < cursor.line_n:
        text = cursor.text
        n    = len(text)
        i    = cursor.i_col
        while i < n and (text[i] == " " or text[i] == "\t"
                         or text[i] == ","): i += 1
        if i >= n:
            cursor.skip_line()
            continue
        cursor.i_col = i
        c = text[i]
        if c == "#" or (c == "/" and text.startswith("//", i)):
            cursor.skip_line()
            continue
        return
