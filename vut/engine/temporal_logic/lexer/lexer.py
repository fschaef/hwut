"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

REGEX LEXER & OPAQUE-SPAN ORACLE HANDOFF

Tokenizes the rule-file language under parser control. A single compiled regular
expression with named capture groups identifies token boundaries. The lexer is
PULL-driven: the parser calls 'next()' for each control-plane token and, when it
reaches an opaque-span open '{', calls 'read_span(mode)' with the span mode its
grammar context demands. The mode is opaque to the lexer and engine -- it is
defined by the injected oracle (the Luau layer's Role: a guard CONDITION, an
rvalue EXPRESSION, an lvalue access, a STATEMENT_BLOCK body). The lexer never
guesses a mode; only the parser knows the context, and only the oracle knows
what a mode means.

ERROR MODEL (see diagnostic.py):

    A MISMATCH (illegal control-plane character) is reported non-fatal and
    returned as a token so the parser may resync at the next 'end' or
    top-level keyword.

    A malformed opaque span (SpanSyntaxError from the oracle) is reported
    non-fatal, the sticky 'error_f' flag is raised, and lexing continues past
    the best closing-'}' candidate the oracle reached. The run yields a
    SPAN_BLOCK over that recovered span so the parser can proceed; the
    accumulated diagnostics are the detailed report.

    A SpanOracleError (infrastructure: binary missing, crash, timeout) is NOT
    author-fixable. It is reported fatal and ends the stream.

The lexer depends only on core.span_oracle (the abstract SpanSyntaxError /
SpanOracleError) and a duck-typed oracle with find_close(); it knows nothing of
Luau or any embedded language.

Source positions are absolute character offsets. A Token carries its
'[begin:end]' span; SourceMap converts an offset to a 1-based (line, column)
on demand, independent of how the text was tokenized.
______________________________________________________________________________
"""
import re
import bisect
from dataclasses  import dataclass
from typing       import Optional

from vut.engine.temporal_logic.world.span_oracle import SpanSyntaxError, SpanOracleError

from vut.engine.temporal_logic.core.diagnostic import Diagnostic, Phase, DiagnosticReporter


# ---------------------------------------------------------------------------
# Lexer-spec generation.
#
# A token's IDENTITY is the Terminal object that produced it (terminals.py); the
# lexer is written against those objects, never against a hand-maintained id
# enum. _TOKEN_SPEC is GENERATED from two sources, the SINGLE source being the
# parser engine's terminal database:
#
#   1. terminals.TERMINAL_DB -- the T.regex / T.string / T.captured / T.opaque
#      terminals (declared in grammar.py's preamble or minted from bare-string
#      keywords at grammar-compile time) plus the framing terminals.
#   2. the bare-string keywords walked out of every GRAMMAR rule body, each
#      routed through T.string so it becomes a Terminal like any other.
#
# The author supplies no token id and no precedence number. Ordering is a
# deterministic function of each terminal's SHAPE (the seven tiers below) and,
# within a tier, of length (longest-first where overlap matters) and declaration
# order. A token's debug name is Terminal._name(); a friendly map for tracing is
# token_debug_names().
#
# Generation runs lazily on first use (see _scanner / token_spec): it imports
# syntax and terminals INSIDE the builder, after the import graph has settled, so
# lexer.py carries no module-level dependency on the authoring layer and the
# graph stays acyclic (grammar_spec -> lexer -> diagnostic only).
# ---------------------------------------------------------------------------


def _is_identifier(spelling):
    """RETURN: True, if 'spelling' is a pure identifier; False, else."""
    return spelling.isidentifier()


def _keyword_pattern(spelling):
    """
    RETURN: str, the lexer regex for a string keyword 'spelling'.

    A leading-colon terminator (':end') becomes ':word\\b'. A trailing-colon
    keyword ('mode:') becomes '\\bword'. A pure identifier keyword ('ANY')
    becomes '\\bword\\b'. A symbol ('=>') becomes re.escape(spelling). Each '\\b'
    sits only on the side that abuts an identifier character.
    """
    if spelling.startswith(":"):
        return r':' + spelling[1:] + r'\b'
    if spelling.endswith(":"):
        return r'\b' + spelling
    if _is_identifier(spelling):
        return r'\b' + spelling + r'\b'
    return re.escape(spelling)


def _walk_string_keywords(element, out):
    """RETURN: None. Routes every bare-string KEYWORD leaf under 'element' through T.string.

    A bare string in GRAMMAR is sugar for a silent string keyword; walking the
    rule bodies and calling T.string on each makes it a real Terminal recorded in
    the database (reused if several rules share the spelling). 'out' is a dict
    used as an ordered set of the resulting terminals (first-appearance order),
    the deterministic tiebreak for equal-length spellings within a tier.

    A '<name>' string is NOT a keyword: it is a reference to the GRAMMAR rule
    'name' (the same spelling the leaf compiler resolves to a Rule_Spec).
    It is skipped here, so a rule reference never leaks a phantom '<name>' token
    into the lexer spec.
    """
    from vut.engine.temporal_logic.core.parser_generator.combinators import _Combinator
    from vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec import Terminal_Spec as Terminal, Ref, T
    if isinstance(element, _Combinator):
        for child in element.children:
            _walk_string_keywords(child, out)
    elif isinstance(element, tuple):
        for child in element:
            _walk_string_keywords(child, out)
    elif isinstance(element, str):
        if len(element) > 2 and element[0] == "<" and element[-1] == ">":
            return                     # a rule reference, not a keyword
        out[T.string(element)] = None
    # Terminal and Ref contribute no string keyword.


def _generate_token_spec():
    """
    RETURN: list, the generated _TOKEN_SPEC: (Terminal, pattern) entries, ordered
            by the seven tiers.

    Built from terminals.TERMINAL_DB (every Terminal, including framing and the
    string keywords minted while walking GRAMMAR). The tiers, in emission order:

        1. skip groups (comment, whitespace framing) -- fixed framing.
        2. leading-colon string keywords  (':end')  -> ':word\\b'.
        3. trailing-colon string keywords ('mode:') -> '\\bword', LONGEST-FIRST.
        4. bare keywords -- captured (ANY) and bare-identifier strings -> '\\bword\\b'.
        5. symbols (string keywords that are not identifiers, '=>') -> re.escape,
           LONGEST-FIRST; the opaque-span open framing token ('{') sits here.
        6. regex class terminals (T.regex) in DECLARATION order.
        7. mismatch framing ('.') -- fixed framing, last.

    The end-of-file and span-block framing terminals carry no scanner pattern
    (they are synthesized, not matched) and are omitted from the spec.
    """
    from vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec import (TERMINAL_DB, T,
                            t_fr_span_open, t_fr_comment, t_fr_ws,
                            t_fr_mismatch)

    if _GRAMMAR is None:
        raise RuntimeError(
            "lexer: no grammar registered; the parser facade must call "
            "register_grammar(GRAMMAR) before lexing")

    # Route every bare-string keyword through T.string so it is in the DB.
    string_terms = {}
    for body in _GRAMMAR.values():
        _walk_string_keywords(body, string_terms)
    decl_index = {t: i for i, t in enumerate(TERMINAL_DB)}

    def order(t):
        return decl_index[t]

    leading, trailing, bare, symbols, regexes = [], [], [], [], []
    for t in TERMINAL_DB:
        if t.shape == "regex":
            regexes.append(t)
        elif t.shape == "captured":
            bare.append(t)
        elif t.shape == "string":
            s = t.spelling
            if s.startswith(":"):
                leading.append(t)
            elif s.endswith(":"):
                trailing.append(t)
            elif _is_identifier(s):
                bare.append(t)
            else:
                symbols.append(t)
        # framing handled explicitly below

    spec = []
    spec.append((t_fr_comment, r'##[^\n]*'))                          # tier 1
    spec.append((t_fr_ws,      r'\s+'))

    for t in sorted(leading, key=order):                             # tier 2
        spec.append((t, _keyword_pattern(t.spelling)))

    trailing.sort(key=lambda t: (-len(t.spelling), order(t)))        # tier 3
    for t in trailing:
        spec.append((t, _keyword_pattern(t.spelling)))

    bare.sort(key=order)                                             # tier 4
    for t in bare:
        spelling = t.spelling
        spec.append((t, _keyword_pattern(spelling)))

    symbols.sort(key=lambda t: (-len(t.spelling), order(t)))         # tier 5
    for t in symbols:
        spec.append((t, re.escape(t.spelling)))
    spec.append((t_fr_span_open, re.escape("{")))                    # opaque-span open

    for t in regexes:                                                # tier 6
        spec.append((t, t.pattern))

    spec.append((t_fr_mismatch, r'.'))                               # tier 7
    return spec


def _span_block_term():
    """RETURN: Terminal, the framing terminal for a synthesized '{ ... }' span."""
    from vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec import t_fr_span_block
    return t_fr_span_block


def token_debug_names():
    """RETURN: dict, Terminal -> friendly name, for parser debug tracing only.

    Token identity is the Terminal object; this map renders it readable when
    tracing the parse. Framing tokens show their friendly tag; others show
    _name(). Token ids are never shown to the user -- only used for debugging.
    """
    return {t: t._name() for t, _ in token_spec()}


# The grammar whose string-keywords seed the token spec. The lexer is otherwise
# grammar-agnostic; the outer facade injects the specific grammar here once via
# register_grammar() before the first lex, inverting what was a direct import of
# the specific GRAMMAR (which would couple this core module to one language).
_GRAMMAR = None


def register_grammar(grammar_dict):
    """RETURN: None. Registers the GRAMMAR whose string keywords seed the token spec.

    Called once by the outer parser facade before lexing. Resets the lazily-built
    token-spec/scanner caches so a re-registration (e.g. a different grammar in a
    test) regenerates them. The lexer reads no specific grammar by import; this is
    the single injection point that keeps core independent of the rule language.
    """
    global _GRAMMAR, _TOKEN_SPEC, _SCANNER, _GROUP_OF
    # Flatten a possibly-nested grammar (subspaces, D-21) so the token-spec walk
    # below sees every rule body, including those inside subspace dicts. A flat
    # grammar passes through unchanged.
    from vut.engine.temporal_logic.core.parser_generator.subspace import flatten
    flat, _ = flatten(grammar_dict)
    _GRAMMAR    = flat
    _TOKEN_SPEC = None
    _SCANNER    = None
    _GROUP_OF   = None


# Generated lazily and cached. _TOKEN_SPEC / _SCANNER / _GROUP_OF stay None until
# first use, at which point syntax and terminals are importable. _GROUP_OF maps a
# synthetic regex group name (g0, g1, ...) back to the Terminal it matched, since
# a Terminal._name() is not a valid regex group identifier.
_TOKEN_SPEC = None
_SCANNER    = None
_GROUP_OF   = None


def token_spec():
    """RETURN: list, the generated _TOKEN_SPEC (built and cached on first call)."""
    global _TOKEN_SPEC
    if _TOKEN_SPEC is None:
        _TOKEN_SPEC = _generate_token_spec()
    return _TOKEN_SPEC


def _scanner():
    """RETURN: re.Pattern, the compiled scanner over the generated _TOKEN_SPEC.

    Each spec entry gets a synthetic group name 'gN'; _GROUP_OF maps it back to
    the Terminal, so a match's lastgroup yields the Terminal directly.
    """
    global _SCANNER, _GROUP_OF
    if _SCANNER is None:
        spec = token_spec()
        _GROUP_OF = {}
        parts = []
        for i, (term, pat) in enumerate(spec):
            g = "g%d" % i
            _GROUP_OF[g] = term
            parts.append("(?P<%s>%s)" % (g, pat))
        _SCANNER = re.compile("|".join(parts))
    return _SCANNER


@dataclass(frozen=True, slots=True)
class Token:
    """
    RETURN: Token, one lexical unit: its kind, its lexeme, and its source span.

    'begin'/'end' are absolute character offsets; 'source[begin:end]' is the
    exact lexeme. For a SPAN_BLOCK the span runs from the opening '{' through
    the closing '}' inclusive. Line/column are not stored -- a SourceMap
    resolves 'begin' on demand. END_OF_FILE has 'begin == end' at text length.
    """
    kind:  "Terminal"
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
    oracle-skipped opaque span resolves with no lexer bookkeeping.
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
    'read_span(mode)' when it has reached a SPAN_OPEN and its grammar
    context fixes the span mode. 'error_f' is sticky: once any author-fixable
    error is reported it stays True for the rest of the run. Diagnostics
    accumulate in the injected reporter.
    """
    def __init__(self, source_text: str, oracle, reporter: DiagnosticReporter):
        """RETURN: None. Binds the text, the span oracle, and the reporter.

        'oracle' is any object with 'parse(text) -> ParseResult'; it is handed
        to the oracle's find_close() unchanged. Launches nothing and reads nothing
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

        A SPAN_OPEN ('{') is returned as-is; the parser must follow it with
        'read_span(mode)'. A MISMATCH is reported non-fatal and returned
        so the parser can resync. WS and '##' comments are consumed silently.
        """
        scanner = _scanner()
        from vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec import t_fr_span_open, t_fr_comment, t_fr_ws, \
            t_fr_mismatch, t_fr_eof
        skip = {t_fr_comment, t_fr_ws}
        while self.cursor < self.length:
            match = scanner.match(self.source, self.cursor)
            # mismatch ('.') matches any non-newline; whitespace ('\\s+') matches
            # newlines. A None match cannot occur while cursor < length.
            assert match is not None

            term  = _GROUP_OF[match.lastgroup]
            begin = self.cursor
            end   = match.end()
            self.cursor = end

            if term in skip:
                continue

            value = match.group()

            if term is t_fr_mismatch:
                self._report(begin, f"unexpected character {value!r}",
                             fatal=False)
                return Token(t_fr_mismatch, value, begin, end)

            return Token(term, value, begin, end)

        return Token(t_fr_eof, "", self.length, self.length)

    def read_span(self, open_token: Token, mode) -> Optional[Token]:
        """
        RETURN: Token,  a SPAN_BLOCK spanning '{ ... }' for the parser's mode.
                None,   if the oracle infrastructure failed (stream ends).

        'open_token' is the SPAN_OPEN just returned by 'next()'. 'mode' is the
        opaque span mode the parser supplies from the grammar (passed through to
        the oracle unread). On a malformed span the error is reported, 'error_f'
        is raised, and a SPAN_BLOCK over the recovered span is still returned so
        the parser can continue. On SpanOracleError the failure is reported fatal
        and None is returned.
        """
        begin = open_token.begin
        try:
            closing_idx = self.oracle.find_close(self.source, begin, mode)
        except SpanSyntaxError as exc:
            return self._recover_span(begin, exc)
        except SpanOracleError as exc:
            self._report(begin, f"span oracle failure: {exc}", fatal=True)
            self.cursor = self.length
            return None

        end = closing_idx + 1
        self.cursor = end
        return Token(_span_block_term(), self.source[begin:end], begin, end)

    def _recover_span(self, begin: int, exc: SpanSyntaxError) -> Token:
        """
        RETURN: Token, a SPAN_BLOCK over the recovered '{ ... }' span.

        Reports the malformed span non-fatal, raises 'error_f', and recovers to
        the nearest closing '}' at or after the opening brace so lexing can
        continue. If no '}' exists at all, recovers to end of text.
        """
        self.error_f = True
        self._report(begin, f"malformed opaque span: {exc}", fatal=False)

        candidate = self.source.find("}", begin + 1)
        end = (candidate + 1) if candidate != -1 else self.length
        self.cursor = end
        return Token(_span_block_term(), self.source[begin:end], begin, end)

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
