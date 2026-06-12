"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

FAKE LUAU ORACLE  --  test substitute for the luau-ast subprocess

The real LuauOracle shells out to 'luau-ast'. That binary is absent in unit
tests, so this in-process stub stands in. It honours the same contract:

    parse(text) -> ParseResult        ok on a clean parse, not-ok otherwise

'find_matching_brace' wraps each candidate span in a role frame and asks the
oracle whether the WRAPPED text parses; the first candidate that parses is the
true closer. This fake judges "parses" by a balance check sufficient for the
wrapper frames in use ('local __guard__ = ( ... )' and 'function __frag__() ...
end'): brackets '() [] {}' must be balanced and not close below zero, and
quotes must be paired, OUTSIDE of Lua strings and comments. Cutting inside a
string, comment, or nested table therefore leaves an imbalance and fails,
exactly as the real oracle would reject the premature cut.

This is deliberately not a Luau parser. It is the smallest judge that makes the
candidate-search behaviour deterministic and subprocess-free in tests.
______________________________________________________________________________
"""
from vut.engine.temporal_logic.parser.core.span_oracle import (
        Reference, SpanSyntaxError)
from vut.engine.temporal_logic.luau.luau_fragment import ParseResult, LuauOracle


class FakeLuauOracle(LuauOracle):
    """In-process stand-in for LuauOracle, for tests.

    Inherits find_close (the candidate-'}'-search over find_matching_brace) from
    LuauOracle unchanged, and overrides only parse() with a subprocess-free
    balance judge -- so tests exercise the REAL brace search against a fake parse
    backend. Optionally records every wrapped text it was asked to parse, so a
    test can show how many candidates the search tried before it settled.
    """
    def __init__(self, record: bool = False):
        """RETURN: None. 'record' True keeps a log of parsed texts in 'seen'."""
        super().__init__()
        self.record = record
        self.seen   = []

    def parse(self, text: str) -> ParseResult:
        """
        RETURN: ParseResult, ok if 'text' is bracket/quote balanced, else not-ok.

        Approximates luau-ast acceptance for the wrapper frames: scans 'text'
        tracking Lua strings (' " and long-bracket [[ ]]) and comments (-- and
        --[[ ]]) so brackets and quotes inside them are ignored, then requires
        every opener to have a matching closer with no early underflow.
        """
        if self.record:
            self.seen.append(text)
        ok, detail = _balanced(text)
        return ParseResult(ok=True) if ok else ParseResult(ok=False, error=detail)

    def collect_references(self, source, open_offset, close_offset, mode):
        """RETURN: tuple[Reference], the dotted identifier chains in the span
                                   body the fake counts as references.

        Raises SpanSyntaxError when the body is not balance-clean (the same
        judge parse() applies).

        Approximation, in the module-docstring spirit (smallest deterministic
        judge, not a Luau parser): a reference is a maximal chain
        ident('.'ident)* -- no whitespace inside the chain -- outside strings
        and comments, whose head is not a reserved word and which is not
        preceded by '.' or ':' (a method name is no chain head). Definition
        sites and table keys are NOT excluded.
        """
        body = source[open_offset + 1: close_offset]
        ok, detail = _balanced(body)
        if not ok:
            raise SpanSyntaxError(detail, open_offset)
        result = []
        i, n = 0, len(body)
        while i < n:
            j, detail = _skip_noncode(body, i)
            if j > i:
                i = j
                continue
            ch = body[i]
            if ch.isalpha() or ch == "_":
                begin = i
                segments = []
                while True:
                    k = i
                    while k < n and (body[k].isalnum() or body[k] == "_"):
                        k += 1
                    segments.append(body[i:k])
                    i = k
                    if i < n and body[i] == "." and i + 1 < n \
                            and (body[i + 1].isalpha() or body[i + 1] == "_"):
                        i += 1
                        continue
                    break
                if segments[0] not in _RESERVED \
                        and (begin == 0 or body[begin - 1] not in ".:"):
                    result.append(Reference(segments=segments,
                                            begin=open_offset + 1 + begin))
                continue
            i += 1
        return tuple(result)


# Reserved words a chain head cannot be (Lua 5.1 set plus Luau 'continue').
_RESERVED = frozenset((
    "and", "break", "continue", "do", "else", "elseif", "end", "false", "for",
    "function", "goto", "if", "in", "local", "nil", "not", "or", "repeat",
    "return", "then", "true", "until", "while",
))


def _skip_noncode(text, i):
    """RETURN: (j, detail), j > i  index past the comment/string starting at i,
                            j == i  when no such construct starts here;
               detail names the defect when the construct never closes (j = end).
    """
    n = len(text)
    ch = text[i]
    if ch == "-" and i + 1 < n and text[i + 1] == "-":
        if text.startswith("--[[", i):
            end = text.find("]]", i + 4)
            if end == -1:
                return n, "unterminated block comment"
            return end + 2, None
        nl = text.find("\n", i)
        return (n if nl == -1 else nl), None
    if ch == "[" and i + 1 < n and text[i + 1] == "[":
        end = text.find("]]", i + 2)
        if end == -1:
            return n, "unterminated long string"
        return end + 2, None
    if ch in ("'", '"'):
        j = i + 1
        while j < n:
            if text[j] == "\\":
                j += 2
                continue
            if text[j] == ch:
                return j + 1, None
            j += 1
        return n, "unterminated string"
    return i, None


def _balanced(text: str):
    """
    RETURN: (ok, detail), ok True iff brackets/quotes balance outside strings.

    'detail' names the first imbalance found when ok is False. Handles Lua
    single/double quoted strings with backslash escapes, long-bracket strings
    '[[ ... ]]', line comments '-- ...', and block comments '--[[ ... ]]'.
    """
    depth = {"(": 0, "[": 0, "{": 0}
    close_to_open = {")": "(", "]": "[", "}": "{"}
    i, n = 0, len(text)

    while i < n:
        # comments and strings (shared with collect_references) -------------
        j, detail = _skip_noncode(text, i)
        if detail is not None:
            return False, detail
        if j > i:
            i = j
            continue
        ch = text[i]

        # brackets ----------------------------------------------------------
        if ch in depth:
            depth[ch] += 1
        elif ch in close_to_open:
            opener = close_to_open[ch]
            if depth[opener] == 0:
                return False, f"unbalanced '{ch}'"
            depth[opener] -= 1

        i += 1

    for opener, count in depth.items():
        if count != 0:
            return False, f"unclosed '{opener}'"
    return True, ""
