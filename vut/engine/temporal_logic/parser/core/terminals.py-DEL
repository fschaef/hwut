"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

TERMINALS  --  the named-terminal authoring surface for the GRAMMAR in grammar.py.

A rule references a richer terminal -- a character class, a kept keyword, or an
opaque embedded span -- by a 't_...' object defined once in a preamble above GRAMMAR
and bound to a variable whose name documents it. The 'T' factory mints those
objects; every call RECORDS the terminal into a per-import database in
declaration order. The lexer-spec generator (lexer.py) later reads that database
plus the plain keywords extracted from GRAMMAR to mint '_TOKEN_SPEC' and the
token ids -- the author supplies no token id and no precedence number; ordering
is a deterministic function of each terminal's shape and its declaration order.

Three terminal shapes, three factories:

    T.regex(pattern)        a character-class terminal (id, number, string,
                            name_colon). No name argument -- the 't_...' variable
                            it is bound to carries the name; declaration order is
                            the author's only precedence lever over the classes.
    T.captured(spelling)    a keyword KEPT in the parse frame and handed to the
                            production's builder (ANY/END/BEGIN/VOID/container),
                            as opposed to a plain bare-string keyword that is
                            silent punctuation.
    T.opaque(mode)
                            an opaque span terminal carrying the span MODE under
                            which the oracle measures the span (a
                            core.span_oracle.SpanMode -- e.g. the Luau layer's
                            Role: CONDITION / EXPRESSION / LVALUE /
                            STATEMENT_BLOCK). The mode lives on the terminal
                            object, so a rule expresses "this position takes an
                            opaque span of this kind" by which 't_...' it names.

'R(name)' wraps a reference to another GRAMMAR rule (a non-terminal). It is part
of the same object authoring surface as T and the Alt/Opt/Plus/Star classes, but
it is NOT a terminal: it records nothing into the database; the engine resolves
the name against the rule map at compile time.

This module depends on nothing in the parser engine and nothing in any embedded
language: the authoring layer stays engine-free AND language-free. An opaque
span carries a 'mode' (core.span_oracle.SpanMode) defined by whatever oracle
measures the span; terminals knows only that a mode exposes qualified_name() and
name. Dependency direction: grammar.py -> {terminals, combinators} -> grammar_spec.
______________________________________________________________________________
"""


# Every T.…() call registers its terminal here, in declaration order. The lexer
# reads this to generate _TOKEN_SPEC; declaration order is the regex-class
# precedence lever (e.g. t_re_name_colon before t_re_id). _BY_NAME indexes the
# same terminals by _name() so the implicit string path can reuse an already
# created terminal and so a duplicate definition is caught.
TERMINAL_DB = []
_BY_NAME    = {}


def _register(term):
    """
    RETURN: Terminal, 'term' if newly registered, or the existing terminal of
            the same _name() (reuse).

    A terminal's _name() is its identity. The first terminal of a given _name()
    is recorded in TERMINAL_DB (declaration order) and indexed. A later call that
    produces the SAME _name() is the same terminal: it is NOT recorded twice; the
    already-recorded one is returned, so an implicit string keyword shared by
    several rules is one token. Two terminals that are NOT identical can never
    share a _name() (the scheme encodes every distinguishing field), so a _name()
    clash is, by construction, a re-definition of the same terminal.
    """
    name = term._name()
    existing = _BY_NAME.get(name)
    if existing is not None:
        return existing
    _BY_NAME[name] = term
    TERMINAL_DB.append(term)
    return term


class Terminal:
    """A named terminal authored in grammar.py and recorded in TERMINAL_DB.

    'shape' is one of 'regex' / 'string' / 'captured' / 'opaque' / 'framing' --
    the discriminant the lexer generator and the engine's leaf compiler switch
    on. The other fields are populated per shape: 'pattern' for a regex class;
    'spelling' for a string keyword, a captured keyword, or a framing token's
    friendly tag; 'mode' (a span mode -- see core.span_oracle.SpanMode) for an
    opaque span, naming the oracle sub-language and the role within it. A field
    not relevant to the shape is None.

    A terminal's IDENTITY is _name() -- factory plus every distinguishing field.
    The engine compares terminals by object identity (one Terminal per _name(),
    guaranteed by _register), never by a hand-written id name.
    """
    __slots__ = ("shape", "pattern", "spelling", "mode")

    def __init__(self, shape, pattern=None, spelling=None, mode=None):
        self.shape    = shape
        self.pattern  = pattern
        self.spelling = spelling
        self.mode     = mode

    def _name(self):
        """RETURN: str, the terminal's identity -- factory plus its fields.

        Used as the token id for debug tracing and as the distinctness key. Two
        terminals are the same iff their _name() is equal; the scheme therefore
        includes every field that distinguishes one terminal from another. An
        opaque span's identity is 'opaque:' + the mode's own qualified name (the
        oracle sub-language plus the role), so core never hard-codes a language.
        """
        if self.shape == "regex":
            return "regex:" + self.pattern
        if self.shape == "string":
            return "string:" + self.spelling
        if self.shape == "captured":
            return "captured:" + self.spelling
        if self.shape == "opaque":
            return "opaque:" + self.mode.qualified_name()
        if self.shape == "framing":
            return "framing:" + self.spelling
        raise ValueError("unknown terminal shape %r" % (self.shape,))

    def __repr__(self):
        return "Terminal(%s)" % (self._name(),)


class _T:
    """The terminal factory namespace exposed to grammar.py as 'T'.

    Each method builds a Terminal and registers it (recording declaration order
    on first sight, reusing on a repeat _name()). The factory only records; it
    generates no lexer spec and mints no token id -- that is the lexer
    generator's job (lexer.py), driven off TERMINAL_DB and each terminal's
    _name().
    """
    @staticmethod
    def regex(pattern):
        """RETURN: Terminal, a character-class terminal matching 'pattern'.

        No name argument: the 't_re_...' variable the result is bound to carries
        the name, and the line's position in the preamble fixes the class
        precedence the generator emits (earlier line wins).
        """
        return _register(Terminal("regex", pattern=pattern))

    @staticmethod
    def string(spelling):
        """RETURN: Terminal, a silent string keyword spelled exactly as written.

        A plain keyword / symbol ('on:', '=>', '(', ':end'). Dropped from the
        parse frame as punctuation (silent). This is the factory behind a bare
        string in GRAMMAR: the engine routes a plain-string leaf through here, so
        every keyword is a terminal like any other and several rules sharing the
        same spelling share one terminal (reuse by _name()).
        """
        return _register(Terminal("string", spelling=spelling))

    @staticmethod
    def captured(spelling):
        """RETURN: Terminal, a keyword terminal kept in the frame for the builder.

        Unlike a silent string keyword, a captured keyword's matched token is
        passed to the production's reduce builder, which inspects which one
        matched (the OR discriminants ANY / END / BEGIN / VOID / container).
        """
        return _register(Terminal("captured", spelling=spelling))

    @staticmethod
    def opaque(mode):
        """RETURN: Terminal, an opaque span terminal carrying its span mode.

        'mode' is a span mode (core.span_oracle.SpanMode) defined by whatever
        oracle measures the span -- e.g. the Luau layer's Role. It rides on the
        terminal object, so a rule expresses "this position takes an opaque span
        of THIS kind" by which 't_opq_...' it names; the engine passes the mode
        back to the oracle unread. The mode must expose qualified_name() (used as
        the terminal's identity) and name (used in diagnostics); SpanMode is the
        documented base, but any object with those is accepted, keeping core free
        of any one embedded language.
        """
        if not (hasattr(mode, "qualified_name") and hasattr(mode, "name")):
            raise ValueError("opaque terminal needs a span mode "
                             "(qualified_name()/name), got %r" % (mode,))
        return _register(Terminal("opaque", mode=mode))

    @staticmethod
    def framing(tag):
        """RETURN: Terminal, a framing token with no grammar spelling.

        A token that is lexer/engine machinery rather than a written terminal:
        the opaque-span brace handoff (open and the synthesized block), the skip
        groups, and the end-of-file and mismatch sentinels. 'tag' is its friendly
        name; framing tokens reference through the same scheme as every other
        token and differ only in carrying this readable tag.
        """
        return _register(Terminal("framing", spelling=tag))


T = _T()


# Framing terminals: lexer/engine machinery with no place in GRAMMAR. Declared
# here (not in grammar.py) because both the grammar-authoring side and the engine
# import them, and terminals.py sits below both with no cycle. They are tokens
# like any other -- referenced by identity, named by the same scheme -- and are
# special only in their friendly tags and in being created here rather than from
# a rule.
t_fr_span_open  = T.framing("span-open")    # a bare '{'; handed to the oracle
t_fr_span_block = T.framing("span-block")   # the synthesized '{ ... }' span
t_fr_comment    = T.framing("comment")      # '## ...' skip group
t_fr_ws         = T.framing("whitespace")   # whitespace skip group
t_fr_mismatch   = T.framing("mismatch")     # illegal char; parser resyncs
t_fr_eof        = T.framing("end-of-file")  # sentinel returned past the end


class Ref:
    """A reference to another GRAMMAR rule (a non-terminal), authored as R(name).

    Holds the referenced rule's name; the engine interns one Rule_Spec per
    name and binds this reference to it at compile time. Not a terminal: it
    records nothing into TERMINAL_DB.
    """
    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "R(%r)" % (self.name,)


def R(name):
    """RETURN: Ref, a reference to the GRAMMAR rule called 'name'."""
    return Ref(name)


def terminal_by_name(name):
    """RETURN: Terminal, the registered terminal whose _name() equals 'name'.

    Reverse of Terminal._name(): used to reconstruct a token's identity from a
    stored debug name (e.g. a monkey-fuzz fixture). Raises KeyError if no such
    terminal has been registered.
    """
    return _BY_NAME[name]
