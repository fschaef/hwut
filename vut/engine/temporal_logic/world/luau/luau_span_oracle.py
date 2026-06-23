"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

Finds the matching '}' of an opaque Luau span in a rule file.

The rule-file parser scans control-plane text until it meets an opening '{'.
From that point the content is opaque Luau. This module locates the matching
'}', WITHOUT the rule-file parser ever lexing Luau itself. It does NOT analyse
the span: name resolution and type checking happen later, once, on the
assembled transpiler output (see the luau-analyze checker).

MECHANISM:

    A candidate closing '}' is the next '}' in plain text, nesting ignored. The
    span from the opening '{' up to and including the candidate is wrapped in a
    role-specific frame and handed to a Luau parser oracle ('luau-ast'). The
    wrapper turns the opening '{' into the start of a construct whose only legal
    terminator is the matching '}'. A premature candidate therefore leaves the
    wrapper unterminated and the oracle reports a parse error; the loop advances
    to the next candidate. The FIRST candidate that parses is the true closer --
    no nesting count, no string/comment lexer, no remainder check. Strings,
    long-bracket strings, comments, and backtick interpolation holes that
    contain '}' are skipped for free, because cutting inside one of them yields
    an unterminated construct that fails to parse.

LAYERS:

    LuauOracle              parse(text) -> ParseResult; the only thing that
                            touches the luau-ast subprocess. Writes to a temp
                            file and detects failure from stderr output.
    find_matching_brace     candidate loop + wrapper; pure logic, oracle
                            injected.
______________________________________________________________________________
"""
import subprocess
from enum         import Enum
from dataclasses  import dataclass

from vut.engine.temporal_logic.world.span_oracle import (
        SpanOracle, SpanMode, SpanSyntaxError, SpanOracleError, SpanReference)


class Role(SpanMode, Enum):
    """Syntactic role of an opaque Luau span. Selects the wrapper frame.

    A Role is the Luau layer's concrete SpanMode: the engine carries it on an
    opaque terminal and hands it back to this oracle unread; only this module
    interprets it (to pick a wrapper). qualified_name() gives the engine a stable
    identity 'luau:<ROLE>' for the opaque terminal -- the sub-language ('luau')
    plus the role -- so two opaque positions of different roles are distinct
    terminals and the debug name reads 'opaque:luau:CONDITION'.
    """
    CONDITION       = "condition"        # guard:  '& { <expr> }'
    EXPRESSION      = "expression"       # rvalue: '{ <luau-expr> }'  (r-value)
    LVALUE          = "lvalue"           # access: 'as: { <luau-lvalue> }'
    STATEMENT_BLOCK = "statement_block"  # '=> { }', init, deinit, BEGIN, END

    def qualified_name(self):
        """RETURN: str, the engine-facing identity 'luau:<ROLE NAME>'."""
        return "luau:" + self.name


@dataclass
class ParseResult:
    """RETURN of the oracle: ok on a clean parse, not-ok with a diagnostic.

    'ok' is True iff the text parsed without any error node. 'error' carries the
    oracle's first diagnostic line when 'ok' is False.
    """
    ok:    bool
    error: str = None


class FragmentSyntaxError(SpanSyntaxError):
    """INPUT-SIDE failure: the Luau inside the span is malformed.

    Raised when no candidate '}' produces a parseable wrapped fragment. A Luau-
    flavoured SpanSyntaxError, so the engine's generic 'except SpanSyntaxError'
    handles it; it carries the open '{' offset for source location.
    """
    pass


class OracleError(SpanOracleError):
    """INFRASTRUCTURE failure: the oracle process misbehaved.

    Raised when the subprocess crashes, fails to start, or returns output that
    is not decodable. A Luau-flavoured SpanOracleError -- not author-fixable, so
    the engine treats it as fatal.
    """
    pass


# ---------------------------------------------------------------------------
# The wrapper: turns an opaque '{ ... }' span into parseable Luau.
# ---------------------------------------------------------------------------
#
# Each role maps to a (prefix, suffix). The wrapped text is 'prefix + inner +
# suffix', where 'inner' is the span content BETWEEN the braces. The wrapper
# makes a premature cut unparseable: CONDITION/EXPRESSION leave an open '(';
# STATEMENT_BLOCK leaves an unterminated 'function ... end'.

@dataclass(frozen=True)
class _Wrapper:
    prefix: str
    suffix: str


def _wrapper_for(role):
    """RETURN: _Wrapper, the frame for 'role'.

    CONDITION / EXPRESSION are framed as a parenthesised rvalue. LVALUE is
    framed as the left-hand side of an assignment, so only an assignable path
    parses (an expression like 'a + b' fails -- it is not an lvalue, which is
    exactly the distinction the access-spec must enforce). STATEMENT_BLOCK is
    framed as a function body.
    """
    if role in (Role.CONDITION, Role.EXPRESSION):
        return _Wrapper(prefix="local __guard__ = (", suffix=")")
    elif role is Role.LVALUE:
        return _Wrapper(prefix="", suffix=" = nil")
    else:
        return _Wrapper(prefix="function __frag__()\n", suffix="\nend")


# ---------------------------------------------------------------------------
# The oracle boundary.
# ---------------------------------------------------------------------------
class LuauOracle(SpanOracle):
    """Parses Luau text via the 'luau-ast [file]' subprocess; a SpanOracle.

    The ONLY component that touches the external binary. As the engine's injected
    SpanOracle it implements find_close (the brace search); its parse() is the
    substitutable seam -- any object with 'parse(text) -> ParseResult' stands in
    for the binary in tests.

    'luau-ast' accepts a single file argument and no flags. Parse success is
    detected by an empty stderr: a clean parse produces no output; a failed
    parse prints error lines to stderr.
    """
    open_delimiter  = "{"
    close_delimiter = "}"

    def __init__(self, binary="luau-ast"):
        """RETURN: None. Remembers the binary path; launches nothing yet."""
        self.binary = binary

    def find_close(self, source, open_offset, mode):
        """RETURN: int, the index of the '}' closing the '{' at 'open_offset'.

        The SpanOracle entry the engine calls. 'mode' is a Role; it selects the
        wrapper frame. Delegates to find_matching_brace with this oracle as the
        parse backend. Raises FragmentSyntaxError (a SpanSyntaxError) on malformed
        Luau, OracleError (a SpanOracleError) on infrastructure failure.
        """
        return find_matching_brace(source, open_offset, mode, self)

    def _run(self, text):
        """RETURN: CompletedProcess, one 'luau-ast <tmpfile>' run over 'text'.

        Raises OracleError on infrastructure failure (binary missing,
        timeout). The single place the subprocess is touched; parse() and
        parse_ast() interpret its stderr/stdout differently.
        """
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix=".luau")
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write(text)
            try:
                return subprocess.run(
                    [self.binary, path],
                    capture_output=True, text=True, timeout=30)
            except FileNotFoundError as exc:
                raise OracleError("luau-ast binary not found: %s" % exc)
            except subprocess.TimeoutExpired as exc:
                raise OracleError("luau-ast timed out: %s" % exc)
        finally:
            os.remove(path)

    def parse(self, text):
        """RETURN: ParseResult, ok on a clean parse, not-ok with a diagnostic.

        Raises OracleError on infrastructure failure. A genuine Luau syntax
        error is NOT an OracleError: it returns a not-ok ParseResult, since
        malformed input is expected during candidate search. Parse success is
        an empty stderr.
        """
        completed = self._run(text)
        stderr = completed.stderr.strip()
        if stderr:
            return ParseResult(ok=False, error=_first_line(stderr))
        return ParseResult(ok=True)

    def parse_ast(self, text):
        """RETURN: dict, the JSON AST 'luau-ast' prints for 'text'.

        Raises FragmentSyntaxError if the text does not parse (stderr output),
        OracleError on infrastructure failure or undecodable stdout. The
        substitutable seam for collect_references -- a test stands in any
        object whose parse_ast returns equivalent JSON.
        """
        import json
        completed = self._run(text)
        stderr = completed.stderr.strip()
        if stderr:
            raise FragmentSyntaxError(_first_line(stderr), 0)
        try:
            return json.loads(completed.stdout)
        except ValueError as exc:
            raise OracleError("luau-ast stdout is not JSON: %s" % exc)

    def collect_references(self, source, open_offset, close_offset, mode):
        """RETURN: tuple[SpanReference], names referenced inside one measured span,
        in source order; begins are offsets into 'source'.

        Raises FragmentSyntaxError on malformed span content, OracleError on
        infrastructure failure.

        The span content is wrapped in the SAME role frame find_close used and
        parsed through parse_ast; the JSON AST is walked for GLOBAL-rooted
        name chains. Luau resolves locals at parse time, so a name declared
        INSIDE the fragment is an AstExprLocal and never surfaces -- globals
        are exactly the references to the world outside the span. The
        pseudo-symbols 'e'/'sm'/'mg'/'m' surface this way BY DESIGN: the
        wrapper deliberately binds nothing, so 'e.temp' is a global chain the
        semantic pass receives as SpanReference(['e','temp']). (The GENERATED
        guard frame, by contrast, binds them as locals at run time -- one
        spelling, both planes; an emitter obligation, see DISCUSSIONS D-10.)

        A chain is the maximal '.'-spine over one global head: 'a.b.c' yields
        ONE SpanReference(['a','b','c']) at the head's offset. A computed index
        breaks the chain ('a[k].b' yields ['a'], plus whatever 'k' references).
        """
        wrapper = _wrapper_for(mode)
        inner   = source[open_offset + 1:close_offset]
        wrapped = wrapper.prefix + inner + wrapper.suffix
        tree    = self.parse_ast(wrapped)

        lo = len(wrapper.prefix)
        hi = lo + len(inner)
        line_starts = _line_start_offsets(wrapped)

        out = []
        for segments, line, col in _walk_global_chains(tree):
            w_off = line_starts[line] + col
            if not (lo <= w_off < hi):
                continue                       # wrapper artifact, not span text
            out.append(SpanReference(segments=segments,
                                 begin=open_offset + 1 + (w_off - lo)))
        out.sort(key=lambda r: (r.begin, r.segments))
        return tuple(out)


def _first_line(text):
    """RETURN: str, the first non-empty stripped line of 'text', or ''."""
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def _line_start_offsets(text):
    """RETURN: list[int], offset of each line start in 'text' (line 0 at 0)."""
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def _loc_head(node):
    """RETURN: (line, col), the 0-based start of a node's 'location'.

    luau-ast locations read 'l1,c1 - l2,c2'; the head pair is the start.
    """
    head = node["location"].split("-")[0].strip()
    line_s, col_s = head.split(",")
    return int(line_s), int(col_s)


def _walk_global_chains(tree):
    """YIELD: [0] list[str]  one reference's segments, head first
           [1] int        0-based line of the chain head
           [2] int        0-based column of the chain head

    Walks the luau-ast JSON on an EXPLICIT stack (no recursion; fragments may
    nest arbitrarily). An 'AstExprIndexName' spine is collapsed to one chain
    when its base is an 'AstExprGlobal'; the consumed spine is not re-entered.
    A spine over any other base (a call, a local, a computed index) emits no
    chain -- the base is walked on its own, so its own globals still surface.
    A bare 'AstExprGlobal' yields a one-segment chain.
    """
    stack = [tree]
    while stack:
        node = stack.pop()
        if isinstance(node, list):
            stack.extend(node)
            continue
        if not isinstance(node, dict):
            continue
        node_type = node.get("type")
        if node_type == "AstExprGlobal":
            line, col = _loc_head(node)
            yield [node["global"]], line, col
            continue
        if node_type == "AstExprIndexName":
            indices, cur = [], node
            while isinstance(cur, dict) and cur.get("type") == "AstExprIndexName":
                indices.append(cur["index"])
                cur = cur.get("expr")
            if isinstance(cur, dict) and cur.get("type") == "AstExprGlobal":
                line, col = _loc_head(cur)
                yield [cur["global"]] + list(reversed(indices)), line, col
                continue                       # spine consumed whole
            stack.append(cur)                  # non-global base: walk it alone
            continue
        for value in node.values():
            if isinstance(value, (dict, list)):
                stack.append(value)


# ---------------------------------------------------------------------------
# The public entry point.
# ---------------------------------------------------------------------------

def find_matching_brace(source, open_offset, role, oracle):
    """RETURN: int, the index in 'source' of the '}' matching the opening '{'.

    Raises FragmentSyntaxError if the span is malformed Luau (no candidate '}'
    parses). Raises OracleError on oracle infrastructure failure.

    'source' is the whole rule-file text. 'open_offset' is the index of the
    opening '{'. 'role' selects the wrapper. 'oracle' is any object with
    'parse(text) -> ParseResult'.

    Enumerates candidate '}' positions left to right. For each, wraps the span
    content and asks the oracle to parse. The first clean parse identifies the
    true closer.
    """
    if source[open_offset] != "{":
        raise ValueError("open_offset does not point at '{'")

    wrapper   = _wrapper_for(role)
    last_diag = "no closing '}' found"

    search_from = open_offset + 1
    while True:
        candidate = source.find("}", search_from)
        if candidate == -1:
            raise FragmentSyntaxError(last_diag, open_offset)

        inner   = source[open_offset + 1:candidate]
        wrapped = wrapper.prefix + inner + wrapper.suffix
        result  = oracle.parse(wrapped)

        if result.ok:
            return candidate

        last_diag   = result.error or last_diag
        search_from = candidate + 1
