"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

REGEX LEXER & ORACLE HANDOFF

Tokenizes the HWUT 2.0 rule-file language under parser control. A single
compiled regular expression with named capture groups identifies token
boundaries. The lexer is PULL-driven: the parser calls 'next()' for each
control-plane token and, when it reaches a '{', calls 'read_luau_block(role)'
with the role its grammar context demands -- CONDITION for a guard, EXPRESSION
for an rvalue, STATEMENT_BLOCK for a '=>'/init/deinit body. The lexer never
guesses a role; only the parser knows the context.

ERROR MODEL (see diagnostic.py):

    A MISMATCH (illegal control-plane character) is reported non-fatal and
    returned as a token so the parser may resync at the next 'end' or
    top-level keyword.

    A malformed Luau fragment (FragmentSyntaxError from the oracle) is reported
    non-fatal, the sticky 'error_f' flag is raised, and lexing continues past
    the best closing-'}' candidate the oracle reached. The run yields a
    LUAU_BLOCK over that recovered span so the parser can proceed; the
    accumulated diagnostics are the detailed report.

    An OracleError (infrastructure: binary missing, crash, timeout) is NOT
    author-fixable. It is reported fatal and ends the stream.

Source positions are absolute character offsets. A Token carries its
'[begin:end]' span; SourceMap converts an offset to a 1-based (line, column)
on demand, independent of how the text was tokenized.
______________________________________________________________________________
"""
import re
import bisect
from enum         import Enum, auto
from dataclasses  import dataclass
from typing       import Optional

from ..luau.luau_fragment import (find_matching_brace, Role,
                                 FragmentSyntaxError, OracleError)

from .diagnostic import Diagnostic, Phase, DiagnosticReporter


class E_TokenId(Enum):
    """Enumeration of all valid rule-file tokens."""
    KW_ON       = auto()
    KW_MODE     = auto()
    KW_MGROUP   = auto()
    KW_SM       = auto()
    KW_STATE    = auto()
    KW_HAS      = auto()
    KW_AS       = auto()
    KW_END_BLK  = auto()
    KW_UNTIL    = auto()
    KW_EVENT    = auto()
    KW_CLOCK    = auto()
    KW_OPEN     = auto()
    KW_CLOSE    = auto()

    KW_ANY      = auto()
    KW_BEGIN    = auto()
    KW_END      = auto()
    KW_SWITCHED = auto()
    KW_DEFAULT  = auto()
    KW_INIT     = auto()
    KW_DEINIT   = auto()
    KW_VOID     = auto()

    ARROW       = auto()
    AND         = auto()
    EQUAL       = auto()
    COLON       = auto()
    COMMA       = auto()
    PLUSBANG    = auto()   # '+!'  spawn an aggregate
    MINUSBANG   = auto()   # '-!'  unspawn a named aggregate
    BANG        = auto()   # '!'   arm a single mode
    SEMI        = auto()
    DOT         = auto()
    LPAREN      = auto()
    RPAREN      = auto()
    LUAU_OPEN   = auto()   # a bare '{'; parser converts via read_luau_block()
    LUAU_BLOCK  = auto()   # synthesized: a whole '{ ... }' span after handoff

    NUMBER      = auto()
    STRING      = auto()
    ID          = auto()

    MISMATCH    = auto()   # illegal character; parser resyncs
    END_OF_FILE = auto()   # sentinel returned by next() at EOF


# Tokens skipped silently in the control plane. NOTE: '##' comments only.
# Inside a '{ ... }' span the bytes are opaque Luau and never seen here.
_TOKEN_SPEC = [
    ("COMMENT",          r'##[^\n]*'),
    ("WS",               r'\s+'),

    (E_TokenId.KW_ON,       r'\bon\b'),
    (E_TokenId.KW_MGROUP,   r'\bmode_group\b'),
    (E_TokenId.KW_MODE,     r'\bmode\b'),
    (E_TokenId.KW_SM,       r'\bstate_machine\b'),
    (E_TokenId.KW_STATE,    r'\bstate\b'),
    (E_TokenId.KW_HAS,      r'\bhas\b'),
    (E_TokenId.KW_AS,       r'\bas\b'),
    (E_TokenId.KW_END_BLK,  r'\bend\b'),
    (E_TokenId.KW_UNTIL,    r'\buntil\b'),
    (E_TokenId.KW_EVENT,    r'\bevent\b'),
    (E_TokenId.KW_CLOCK,    r'\bclock\b'),
    (E_TokenId.KW_OPEN,     r'\bopen\b'),
    (E_TokenId.KW_CLOSE,    r'\bclose\b'),

    (E_TokenId.KW_ANY,      r'\bANY\b'),
    (E_TokenId.KW_BEGIN,    r'\bBEGIN\b'),
    (E_TokenId.KW_END,      r'\bEND\b'),
    (E_TokenId.KW_SWITCHED, r'\bswitched\b'),
    (E_TokenId.KW_DEFAULT,  r'\bdefault\b'),
    (E_TokenId.KW_INIT,     r'\binit\b'),
    (E_TokenId.KW_DEINIT,   r'\bdeinit\b'),
    (E_TokenId.KW_VOID,     r'\bVOID\b'),

    (E_TokenId.ARROW,       r'=>'),
    (E_TokenId.AND,         r'&'),
    (E_TokenId.EQUAL,       r'='),
    (E_TokenId.COLON,       r':'),
    (E_TokenId.COMMA,       r','),
    (E_TokenId.PLUSBANG,    r'\+!'),
    (E_TokenId.MINUSBANG,   r'-!'),
    (E_TokenId.BANG,        r'!'),
    (E_TokenId.SEMI,        r';'),
    (E_TokenId.DOT,         r'\.'),
    (E_TokenId.LPAREN,      r'\('),
    (E_TokenId.RPAREN,      r'\)'),
    (E_TokenId.LUAU_OPEN,   r'\{'),

    (E_TokenId.NUMBER,      r'[+-]?\d+(?:\.\d+)?'),
    (E_TokenId.STRING,      r'"[^"]*"'),
    (E_TokenId.ID,          r'[a-zA-Z_]\w*'),

    (E_TokenId.MISMATCH,    r'.'),
]


def _group_name(kind):
    """RETURN: str, the regex group name for a spec entry's kind.

    Skip-kinds are plain strings ('COMMENT', 'WS'); token-kinds are E_TokenId
    members whose '.name' is used. Keeps the two namespaces from colliding.
    """
    return kind if isinstance(kind, str) else kind.name


_SCANNER = re.compile(
    '|'.join(f'(?P<{_group_name(k)}>{p})' for k, p in _TOKEN_SPEC)
)

_SKIP_GROUPS = {"COMMENT", "WS"}


@dataclass(frozen=True, slots=True)
class Token:
    """
    RETURN: Token, one lexical unit: its kind, its lexeme, and its source span.

    'begin'/'end' are absolute character offsets; 'source[begin:end]' is the
    exact lexeme. For a LUAU_BLOCK the span runs from the opening '{' through
    the closing '}' inclusive. Line/column are not stored -- a SourceMap
    resolves 'begin' on demand. END_OF_FILE has 'begin == end' at text length.
    """
    kind:  E_TokenId
    text:  str
    begin: int
    end:   int


class SourceMap:
    """
    RETURN: SourceMap, converter from an absolute offset to a 1-based
            (line, column).

    Built once per source text. 'line_starts[i]' is the offset of the first
    character of line 'i' (zero-based index). Resolution bisects that array and
    is independent of tokenization, so an offset inside or beyond an
    oracle-skipped Luau block resolves with no lexer bookkeeping.
    """
    def __init__(self, source_text: str):
        self.line_starts = [0]
        self.line_starts += [
            i + 1 for i, ch in enumerate(source_text) if ch == '\n'
        ]

    def line_column(self, offset: int):
        """
        RETURN: (line, column), the 1-based line and 1-based column of 'offset'.

        A position at a line's first character yields column 1.
        """
        line   = bisect.bisect_right(self.line_starts, offset)
        column = offset - self.line_starts[line - 1] + 1
        return line, column


class Lexer:
    """Pull-driven tokenizer for one rule-file text under parser control.

    The parser calls 'next()' to advance the control plane and
    'read_luau_block(role)' when it has reached a LUAU_OPEN and its grammar
    context fixes the Luau role. 'error_f' is sticky: once any author-fixable
    error is reported it stays True for the rest of the run. Diagnostics
    accumulate in the injected reporter.
    """
    def __init__(self, source_text: str, oracle, reporter: DiagnosticReporter):
        """RETURN: None. Binds the text, the Luau oracle, and the reporter.

        'oracle' is any object with 'parse(text) -> ParseResult'; it is handed
        to 'find_matching_brace' unchanged. Launches nothing and reads nothing
        until 'next()' is called.
        """
        self.source   = source_text
        self.oracle   = oracle
        self.reporter = reporter
        self.cursor   = 0
        self.length   = len(source_text)
        self.error_f  = False

    def next(self) -> Token:
        """
        RETURN: Token, the next control-plane token; END_OF_FILE at text end.

        A LUAU_OPEN ('{') is returned as-is; the parser must follow it with
        'read_luau_block(role)'. A MISMATCH is reported non-fatal and returned
        so the parser can resync. WS and '##' comments are consumed silently.
        """
        while self.cursor < self.length:
            match = _SCANNER.match(self.source, self.cursor)
            # MISMATCH ('.') matches any non-newline; WS ('\\s+') matches
            # newlines. A None match cannot occur while cursor < length.
            assert match is not None

            group = match.lastgroup
            begin = self.cursor
            end   = match.end()
            self.cursor = end

            if group in _SKIP_GROUPS:
                continue

            kind  = E_TokenId[group]
            value = match.group()

            if kind == E_TokenId.MISMATCH:
                self._report(begin, f"unexpected character {value!r}",
                             fatal=False)
                return Token(E_TokenId.MISMATCH, value, begin, end)

            return Token(kind, value, begin, end)

        return Token(E_TokenId.END_OF_FILE, "", self.length, self.length)

    def read_luau_block(self, open_token: Token, role: Role) -> Optional[Token]:
        """
        RETURN: Token,  a LUAU_BLOCK spanning '{ ... }' for the parser's role.
                None,   if the oracle infrastructure failed (stream ends).

        'open_token' is the LUAU_OPEN just returned by 'next()'. On a malformed
        fragment the error is reported, 'error_f' is raised, and a LUAU_BLOCK
        over the recovered span is still returned so the parser can continue.
        On OracleError the failure is reported fatal and None is returned.
        """
        begin = open_token.begin
        try:
            closing_idx = find_matching_brace(self.source, begin, role,
                                              self.oracle)
        except FragmentSyntaxError as exc:
            return self._recover_fragment(begin, exc)
        except OracleError as exc:
            self._report(begin, f"Luau oracle failure: {exc}", fatal=True)
            self.cursor = self.length
            return None

        end = closing_idx + 1
        self.cursor = end
        return Token(E_TokenId.LUAU_BLOCK, self.source[begin:end], begin, end)

    def _recover_fragment(self, begin: int, exc: FragmentSyntaxError) -> Token:
        """
        RETURN: Token, a LUAU_BLOCK over the recovered '{ ... }' span.

        Reports the malformed fragment non-fatal, raises 'error_f', and recovers
        to the nearest closing '}' at or after the opening brace so lexing can
        continue. If no '}' exists at all, recovers to end of text.
        """
        self.error_f = True
        self._report(begin, f"malformed Luau fragment: {exc}", fatal=False)

        candidate = self.source.find("}", begin + 1)
        end = (candidate + 1) if candidate != -1 else self.length
        self.cursor = end
        return Token(E_TokenId.LUAU_BLOCK, self.source[begin:end], begin, end)

    def _report(self, offset: int, message: str, fatal: bool):
        """RETURN: None. Appends a LEXER-phase Diagnostic and updates error_f.

        A non-fatal report raises the sticky 'error_f'. A fatal report is
        forwarded to the reporter, which owns abort policy.
        """
        if not fatal:
            self.error_f = True
        self.reporter.report(Diagnostic(
            phase         = Phase.LEXER,
            message       = message,
            source_offset = offset,
            fatal         = fatal,
        ))