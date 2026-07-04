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
from vut.engine.temporal_logic.world.luau.luau_span_oracle import ParseResult, LuauOracle


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
        ch = text[i]

        # -- comments (line or block) ---------------------------------------
        if ch == "-" and i + 1 < n and text[i + 1] == "-":
            if text.startswith("--[[", i):
                end = text.find("]]", i + 4)
                if end == -1:
                    return False, "unterminated block comment"
                i = end + 2
                continue
            nl = text.find("\n", i)
            i = n if nl == -1 else nl
            continue

        # long-bracket string [[ ... ]] ------------------------------------
        if ch == "[" and i + 1 < n and text[i + 1] == "[":
            end = text.find("]]", i + 2)
            if end == -1:
                return False, "unterminated long string"
            i = end + 2
            continue

        # quoted strings ----------------------------------------------------
        if ch in ("'", '"'):
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == ch:
                    break
                j += 1
            else:
                return False, "unterminated string"
            i = j + 1
            continue

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
