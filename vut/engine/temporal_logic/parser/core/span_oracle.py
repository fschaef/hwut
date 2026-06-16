"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

SPAN ORACLE  --  the abstract boundary for OPAQUE SPANS in a grammar.

The engine is grammar-agnostic: it lexes control-plane tokens until it reaches
an opaque-span OPEN delimiter ('{'), then hands the span off to be measured by
something it does NOT understand. That "something" is a SpanOracle. The engine
knows only this interface; it knows nothing of Luau, of any embedded language,
or of what the span MEANS. A concrete oracle (e.g. the Luau layer's
LuauSpanOracle) derives from SpanOracle and supplies the language-specific
brace-finding and validation.

This inverts what used to be a layering violation: core formerly imported the
Luau component directly (find_matching_brace, Role, the Luau exceptions). Now
the dependency points the right way -- the Luau component imports this abstract
base from core and implements it; core depends on nothing below itself.

WHAT THE ENGINE -- AND, FOR REFERENCES, PASS 2 -- NEEDS FROM AN OPAQUE SPAN:

    find_close(source, open_offset, mode) -> int
        Given the whole source text, the index of the OPEN delimiter, and the
        span's 'mode' (an opaque, oracle-defined tag carried by the opaque
        terminal -- see SpanMode), return the index of the matching CLOSE
        delimiter. Raise SpanSyntaxError if the span content is malformed (an
        author error, surfaced as an ordinary parse error) or SpanOracleError on
        infrastructure failure (a tool crash the author cannot fix).

    collect_references(source, open_offset, close_offset, mode)
            -> tuple[Reference]
        The names referenced inside one already-measured span, as neutral
        (segments, begin) pairs -- the vocabulary the semantic pass resolves.
        Lazy by design: nothing calls this during parsing; the opaque-code AST
        node exposes it on demand (OpaqueCode.get_references).

    open_delimiter / close_delimiter
        The single characters that open and close a span ('{' and '}' for Luau).
        The lexer frames the open delimiter as a token; the oracle owns the rest.

'mode' is deliberately untyped here. To core it is an opaque handle the grammar
author attached to an opaque terminal (T.opaque(mode=...)); the oracle is the
only party that interprets it (the Luau oracle treats it as a Role selecting a
wrapper frame). A different embedded language would define its own modes.
______________________________________________________________________________
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class Reference:
    """One name referenced inside an opaque span: its segments and offset.

    The neutral pair pass 2 resolves: 'segments' is the dotted chain as a list
    (['e', 'temp'] for 'e.temp'); 'begin' is the ABSOLUTE source offset of the
    chain's head, like every node offset. WHAT counts as a reference -- which
    identifiers, in which syntactic positions -- is the concrete oracle's
    private knowledge; core carries only these pairs.
    """
    segments: "list[str]"
    begin:    int


@dataclass(frozen=True)
class SpanResult:
    """The neutral outcome of consuming one opaque span.

    What the engine yields at an opaque-terminal position: the raw span text
    (delimiters included), the span 'mode' the grammar attached, and the source
    'begin' offset. It carries NO language meaning -- the rule's reduce action
    turns it into a language node (the rule grammar wraps it as ast.Luau). This
    is what keeps the engine free of any embedded-language AST type.
    """
    text:  str
    mode:  object
    begin: int


class SpanMode:
    """Marker base for an opaque-span mode tag.

    A concrete oracle defines its own modes (the Luau layer's Role is one such
    set) and is the only party that interprets them. Core carries a mode on an
    opaque terminal and passes it back to the oracle unread; it requires only
    that a mode has a stable 'name' for diagnostics and identity. Subclassing
    this is optional -- any object with a '.name' string works -- but it
    documents intent and lets isinstance checks distinguish a mode from a stray
    value at the terminals factory boundary.
    """
    __slots__ = ()


class E_SpanMode(SpanMode, Enum):
    """The rule-language span positions an opaque terminal may occupy.

    A core-owned enum so the rule-file grammar names its opaque positions
    without importing any embedded language: EXPRESSION (an rvalue span),
    LVALUE (a 'by:'/'as:' access span), and STATEMENT_BLOCK (a mutation / init /
    deinit body). CONDITION is retained as a lexer-role label only -- the
    grammar no longer opens an opaque guard span (a guard is the bracket
    condition '[ <cond> ]'); the member stays for the span-handling tests that
    drive the oracle handoff under a CONDITION role. The concrete oracle
    interprets each member (the Luau oracle maps it to a wrapper frame); core
    carries it on the opaque terminal and hands it back unread.

    qualified_name() is the identity half an opaque terminal stamps into its
    _name() ('opaque:' + qualified_name()). It is oracle-neutral here -- the
    member spelling alone -- since one compiled grammar binds one oracle, so
    the member already distinguishes every opaque position within it.
    """
    CONDITION       = "condition"        # lexer role only; grammar opens no guard span
    EXPRESSION      = "expression"       # rvalue: '{ <luau-expr> }'
    LVALUE          = "lvalue"           # access: 'by: { <luau-lvalue> }'
    STATEMENT_BLOCK = "statement_block"  # '=> { }', init, deinit, BEGIN, END

    def qualified_name(self):
        """RETURN: str, the opaque terminal's identity half -- the member value."""
        return self.value




class SpanSyntaxError(Exception):
    """INPUT-SIDE failure: the opaque span's content is malformed.

    Raised by find_close when no candidate close delimiter yields a valid span.
    Carries the open-delimiter offset so the caller can locate the span in the
    source. Surfaces to the user as an ordinary rule-file syntax error -- the
    author can fix it by editing the span.
    """
    def __init__(self, message, open_offset):
        """RETURN: None. Stores the message and the open-delimiter offset."""
        super().__init__(message)
        self.open_offset = open_offset


class SpanOracleError(Exception):
    """INFRASTRUCTURE failure: the oracle itself misbehaved.

    Raised when the machinery that validates spans fails (a subprocess crashes,
    a binary is missing, a timeout). Distinct from SpanSyntaxError: the author
    cannot fix this by editing rules, so the engine treats it as fatal rather
    than as a recoverable parse error.
    """
    pass


class SpanOracle(ABC):
    """Abstract boundary the engine uses to measure an opaque span.

    A concrete oracle implements find_close and declares its delimiters. The
    engine constructs nothing here; an oracle instance is injected into the lexer
    (Lexer(source, oracle, reporter)). Keeping this abstract is what lets the
    engine stay free of any embedded language: swap the oracle, parse a grammar
    whose opaque spans are SQL, JSON, or anything else, with no engine change.
    """

    #: The single characters that delimit an opaque span. Subclasses override
    #: if their embedded language uses different brackets.
    open_delimiter  = "{"
    close_delimiter = "}"

    @abstractmethod
    def find_close(self, source, open_offset, mode):
        """RETURN: int, the index of the CLOSE delimiter matching the OPEN one.

        Raises SpanSyntaxError if the span content is malformed (no valid close
        found), SpanOracleError on infrastructure failure.

        'source' is the whole source text; 'open_offset' indexes the OPEN
        delimiter; 'mode' is the opaque mode tag the grammar attached to this
        span's terminal, interpreted only by the concrete oracle.
        """
        raise NotImplementedError

    @abstractmethod
    def collect_references(self, source, open_offset, close_offset, mode):
        """RETURN: tuple[Reference], the names referenced inside one span.

        Raises SpanSyntaxError if the span content is malformed,
        SpanOracleError on infrastructure failure.

        'source' is the text containing the span; 'open_offset' /
        'close_offset' index its OPEN and CLOSE delimiters; 'mode' is the
        span's mode tag. Reference begins are offsets INTO 'source'; a caller
        holding only the span text passes it as 'source' and rebases. WHAT
        counts as a reference is the concrete oracle's private knowledge.
        """
        raise NotImplementedError
