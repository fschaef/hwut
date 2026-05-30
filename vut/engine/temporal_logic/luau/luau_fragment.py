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


class Role(Enum):
    """Syntactic role of an opaque Luau span. Selects the wrapper frame."""
    CONDITION       = "condition"        # guard:  '& { <expr> }'
    EXPRESSION      = "expression"       # rvalue: '{ <luau-expr> }'
    STATEMENT_BLOCK = "statement_block"  # '=> { }', init, deinit, BEGIN, END


@dataclass
class ParseResult:
    """RETURN of the oracle: ok on a clean parse, not-ok with a diagnostic.

    'ok' is True iff the text parsed without any error node. 'error' carries the
    oracle's first diagnostic line when 'ok' is False.
    """
    ok:    bool
    error: str = None


class FragmentSyntaxError(Exception):
    """INPUT-SIDE failure: the Luau inside the span is malformed.

    Raised when no candidate '}' produces a parseable wrapped fragment. Carries
    the open '{' offset so the caller can locate the span in the original
    source. Surfaces as an ordinary rule-file syntax error.
    """
    def __init__(self, message, open_offset):
        super().__init__(message)
        self.open_offset = open_offset


class OracleError(Exception):
    """INFRASTRUCTURE failure: the oracle process misbehaved.

    Raised when the subprocess crashes, fails to start, or returns output that
    is not decodable. Distinct from FragmentSyntaxError: the author cannot fix
    this by editing rules.
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

    CONDITION / EXPRESSION are framed as a parenthesised rvalue. STATEMENT_BLOCK
    is framed as a function body.
    """
    if role in (Role.CONDITION, Role.EXPRESSION):
        return _Wrapper(prefix="local __guard__ = (", suffix=")")
    else:
        return _Wrapper(prefix="function __frag__()\n", suffix="\nend")


# ---------------------------------------------------------------------------
# The oracle boundary.
# ---------------------------------------------------------------------------

class LuauOracle:
    """Parses Luau text via the 'luau-ast [file]' subprocess.

    The ONLY component that touches the external binary. Substitutable in tests
    by any object with a 'parse(text) -> ParseResult' method.

    'luau-ast' accepts a single file argument and no flags. Parse success is
    detected by an empty stderr: a clean parse produces no output; a failed
    parse prints error lines to stderr.
    """
    def __init__(self, binary="luau-ast"):
        """RETURN: None. Remembers the binary path; launches nothing yet."""
        self.binary = binary

    def parse(self, text):
        """RETURN: ParseResult, ok on a clean parse, not-ok with a diagnostic.

        Raises OracleError on infrastructure failure (binary missing, timeout).
        A genuine Luau syntax error is NOT an OracleError: it returns a not-ok
        ParseResult, since malformed input is expected during candidate search.

        Writes 'text' to a temporary file, runs 'luau-ast <path>', checks stderr
        for error output, then removes the file.
        """
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix=".luau")
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write(text)
            try:
                completed = subprocess.run(
                    [self.binary, path],
                    capture_output=True, text=True, timeout=30)
            except FileNotFoundError as exc:
                raise OracleError("luau-ast binary not found: %s" % exc)
            except subprocess.TimeoutExpired as exc:
                raise OracleError("luau-ast timed out: %s" % exc)
        finally:
            os.remove(path)

        stderr = completed.stderr.strip()
        if stderr:
            return ParseResult(ok=False, error=_first_line(stderr))
        return ParseResult(ok=True)


def _first_line(text):
    """RETURN: str, the first non-empty stripped line of 'text', or ''."""
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


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
