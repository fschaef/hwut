"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

REGEX LEXER

Tokenizes the rule-file language under parser control. A single compiled regular
expression with named capture groups identifies token boundaries. The lexer is
PULL-driven: the parser calls 'next()' for each token. Every character of the
source is control-plane; '{' and '}' are ordinary tokens with no special
handling. The lexer knows nothing of any embedded or target language.

ERROR MODEL (see diagnostic.py):

    A MISMATCH (illegal character) is reported non-fatal and returned as a
    token so the parser may resync at the next 'end' or top-level keyword.

Source positions are absolute character offsets. A Token carries its
'[begin:end]' span; SourceMap converts an offset to a 1-based (line, column)
on demand, independent of how the text was tokenized.
______________________________________________________________________________
"""
import re
import bisect
from dataclasses  import dataclass

from ..diagnostic import Diagnostic, Phase, DiagnosticReporter
from ..parser_generator.combinators import _Combinator
from ..parser_generator.ll2_grammar_spec import T



# ---------------------------------------------------------------------------
# Lexer-spec generation.
#
# A token's IDENTITY is the Terminal object that produced it (terminals.py); the
# lexer is written against those objects, never against a hand-maintained id
# enum. _TOKEN_SPEC is GENERATED from two sources, the SINGLE source being the
# parser engine's terminal database:
#
#   1. terminals.TERMINAL_DB -- the T.regex / T.string / T.captured
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
    elif spelling.endswith(":"):
        return r'\b' + spelling
    elif _is_identifier(spelling):
        return r'\b' + spelling + r'\b'
    else:
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
        5. symbols (string keywords that are not identifiers, '=>', '{', '}')
           -> re.escape, LONGEST-FIRST.
        6. regex class terminals (T.regex) in DECLARATION order.
        7. mismatch framing ('.') -- fixed framing, last.

    The end-of-file framing terminal carries no scanner pattern (it is
    synthesized, not matched) and is omitted from the spec.
    """
    from ..parser_generator.ll2_grammar_spec import (TERMINAL_DB, t_fr_comment, t_fr_ws,
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
    # Comment skip: the LINE form only. The BLOCK form ('#' + non-newline
    # whitespace + '{', braces NESTING to the balancing '}') cannot be a
    # regex group -- nesting counts -- and is intercepted by Lexer.next()
    # BEFORE the scanner runs (see _BLOCK_OPEN / _block_comment_end).
    spec.append((t_fr_comment, r'#[^\n]*'))                           # tier 1
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

    for t in regexes:                                                # tier 6
        spec.append((t, t.pattern))

    spec.append((t_fr_mismatch, r'.'))                               # tier 7
    return spec



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
    from ..parser_generator.subspace import flatten
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
    exact lexeme. Line/column are not stored -- a SourceMap resolves 'begin' on
    demand. END_OF_FILE has 'begin == end' at text length.
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
    is independent of tokenization.
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


# Block-comment opener: '#', one or more NON-NEWLINE whitespace, '{'. A '#'
# not fitting this shape comments to end of line (the tier-1 spec pattern).
# Intercepted in Lexer.next() before the scanner: the block body needs BRACE
# COUNTING (nesting), which no regex group expresses.
_BLOCK_OPEN = re.compile(r'#[^\S\n]+\{')


def _block_comment_end(source, brace_pos):
    """RETURN: int, the index just past the '}' balancing the '{' at
              'brace_pos' if the block closes within 'source',
              -1, else (end of text reached with braces still open).

    Braces NEST by counting: every '{' deepens, every '}' shallows; the block
    ends where the depth returns to zero. Balanced rule-code inside the block
    -- including further '# {' openers, whose '{' counts like any other --
    is therefore commented out whole.
    """
    depth = 1
    i     = brace_pos + 1
    n     = len(source)
    while i < n:
        ch = source[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


class Lexer:
    """Pull-driven tokenizer for one rule-file text under parser control.

    The parser calls 'next()' to advance the token stream. 'error_f' is sticky:
    once any author-fixable error is reported it stays True for the rest of the
    run. Diagnostics accumulate in the injected reporter.
    """
    def __init__(self, source_text: str, reporter: DiagnosticReporter):
        """RETURN: None, always. Binds the source text and the diagnostic reporter.

        Reads nothing until 'next()' is called.
        """
        self.source   = source_text
        self.reporter = reporter
        self.cursor   = 0
        self.length   = len(source_text)
        self.error_f  = False

    def next(self) -> Token:
        """
        RETURN: Token, the next token; END_OF_FILE at text end.

        '{' and '}' are ordinary tokens. A MISMATCH is reported non-fatal and
        returned so the parser can resync. WS and comments are consumed
        silently; a BLOCK comment ('# {', braces nesting to the balancing
        '}') is intercepted here, before the scanner. An UNTERMINATED block
        comment is reported non-fatal at its opener and consumes to text end.
        """
        scanner = _scanner()
        from ..parser_generator.ll2_grammar_spec import t_fr_comment, t_fr_ws, \
            t_fr_mismatch, t_fr_eof
        skip = {t_fr_comment, t_fr_ws}
        while self.cursor < self.length:
            opener = _BLOCK_OPEN.match(self.source, self.cursor)
            if opener is not None:
                end = _block_comment_end(self.source, opener.end() - 1)
                if end < 0:
                    self._report(self.cursor,
                                 "unterminated block comment ('# {' without "
                                 "a balancing '}')", fatal=False)
                    self.cursor = self.length
                    break
                self.cursor = end
                continue

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
