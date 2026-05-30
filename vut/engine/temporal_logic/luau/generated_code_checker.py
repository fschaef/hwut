"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

Type-checks the assembled transpiler output with 'luau-analyze' and traces every
diagnostic back to the original rule file.

The transpiler emits one Luau file: boilerplate interleaved with verbatim author
fragments. Rather than analyse each fragment in a synthetic context, the whole
program is checked once, in its real context. 'luau-analyze' reports diagnostics
against the GENERATED file; a Source2TargetLocationMapper (built during emission)
translates each back to the author's (file, line, column).

A diagnostic that lands on a fragment line is the author's to fix. One that lands
on boilerplate (no source interval) is a transpiler bug: it is reported as such,
NOT misattributed to nearby author code.

luau-analyze DIAGNOSTIC FORMAT (default report formatter, verified against the
Luau CLI source):

    <name>(<line>,<col>): <Type>: <message>

with <line> and <col> ONE-based. They are converted to the mapper's zero-based
convention on the way in.
______________________________________________________________________________
"""
import re
import subprocess
from dataclasses import dataclass


# <name>(<line>,<col>): <Type>: <message>   -- line/col are 1-based.
_DIAG_RE = re.compile(
    r"^(?P<name>.+?)\((?P<line>\d+),(?P<col>\d+)\):\s*"
    r"(?P<type>[A-Za-z]+):\s*(?P<message>.*)$")


@dataclass(frozen=True)
class Diagnostic:
    """One luau-analyze finding, traced back to original source.

    'kind' is the analyzer category ('TypeError', 'SyntaxError', ...).
    'message' is the analyzer text. 'source' is the original location, or None
    when the diagnostic fell on generated boilerplate. 'target_line' /
    'target_column' are the zero-based location in the generated file, kept for
    diagnosing the latter case.
    """
    kind:          str
    message:       str
    source:        object   # SourceLocation | None
    target_line:   int
    target_column: int

    @property
    def is_in_generated_code(self):
        """RETURN: True,  if the diagnostic has no original-source origin.
                  False, otherwise.
        """
        return self.source is None


class AnalyzerError(Exception):
    """INFRASTRUCTURE failure: luau-analyze could not be run.

    Raised when the binary is missing, times out, or its output cannot be
    parsed. Distinct from a clean run that reports type errors -- those are
    returned as Diagnostics, not raised.
    """
    pass


class GeneratedCodeChecker:
    """Runs luau-analyze on generated Luau and maps findings to source.

    'analyze_path' / 'analyze_text' run the checker over a file or a string.
    Both return a list of Diagnostics (empty == clean). The subprocess is the
    only external dependency and is isolated here.
    """
    def __init__(self, mapper, binary="luau-analyze"):
        """RETURN: None. Holds the mapper and the binary path.

        'mapper' is the Source2TargetLocationMapper built during emission. The
        type-checking mode ('--!strict' etc.) is selected by a directive in the
        emitted text, not here, so target line numbers stay aligned with the
        mapper.
        """
        self.mapper = mapper
        self.binary = binary

    def analyze_text(self, target_text, tmp_dir=None):
        """RETURN: list, the Diagnostics for 'target_text' (empty == clean).

        Raises AnalyzerError on infrastructure failure. Writes the text to a
        temporary file because luau-analyze checks files, then runs the binary
        and maps each diagnostic.

        'target_text' must be EXACTLY what the mapper described -- including any
        '--!strict' directive as its first emitted line. Nothing is injected
        here: injecting a line would shift every target line number by one and
        silently break trace-back. The directive belongs in the emitted text and
        must have been accounted for in the mapper (via 'advance(1)').
        """
        import tempfile
        import os
        directory = tmp_dir or tempfile.gettempdir()
        fd, path = tempfile.mkstemp(suffix=".luau", dir=directory)
        try:
            with os.fdopen(fd, "w") as handle:
                handle.write(target_text)
            return self._run_and_map(path)
        finally:
            os.remove(path)

    def analyze_path(self, target_path):
        """RETURN: list, the Diagnostics for the file at 'target_path'.

        Raises AnalyzerError on infrastructure failure. Use when the generated
        file already exists on disk exactly as the mapper described it (no
        injected directive lines), so target line numbers line up with the
        mapper.
        """
        return self._run_and_map(target_path)

    def _run_and_map(self, path):
        """RETURN: list, Diagnostics parsed from a luau-analyze run on 'path'."""
        try:
            completed = subprocess.run(
                [self.binary, path],
                capture_output=True, text=True, timeout=120)
        except FileNotFoundError as exc:
            raise AnalyzerError("luau-analyze binary not found: %s" % exc)
        except subprocess.TimeoutExpired as exc:
            raise AnalyzerError("luau-analyze timed out: %s" % exc)

        # Diagnostics go to stderr in the default formatter. A clean run emits
        # nothing there and exits zero.
        diagnostics = []
        for line in completed.stderr.splitlines():
            parsed = self._parse_line(line, path)
            if parsed is not None:
                diagnostics.append(parsed)

        if not diagnostics and completed.returncode not in (0, 1):
            # Non-zero exit with no parseable diagnostics: a real tool failure
            # rather than a type error (which exits 1 with diagnostics).
            raise AnalyzerError(
                "luau-analyze failed (exit %d): %s"
                % (completed.returncode, completed.stderr.strip()))
        return diagnostics

    def _parse_line(self, line, path):
        """RETURN: Diagnostic for 'line', or None if it is not a diagnostic.

        Lines for other files (luau-analyze can echo required-module errors)
        are ignored by matching only the analysed file's name.
        """
        match = _DIAG_RE.match(line.strip())
        if match is None:
            return None
        # luau-analyze may prefix paths differently ('./x', 'x'); compare on
        # the basename so an echoed path still matches the analysed file.
        import os
        if os.path.basename(match.group("name")) != os.path.basename(path):
            return None

        target_line = int(match.group("line")) - 1   # 1-based -> 0-based
        target_col  = int(match.group("col"))  - 1
        source      = self.mapper.source_line_of(target_line, target_col)
        return Diagnostic(
            kind=match.group("type"), message=match.group("message"),
            source=source, target_line=target_line, target_column=target_col)


def format_diagnostic(diag):
    """RETURN: str, a human-readable one-line rendering of 'diag'.

    Author-attributable findings point at the original file:line:col. Findings
    in generated code are clearly marked as a transpiler concern with the
    generated location, so they are never blamed on author source.
    """
    if diag.is_in_generated_code:
        return ("[generated code: likely transpiler bug] "
                "%s at generated line %d col %d: %s"
                % (diag.kind, diag.target_line, diag.target_column,
                   diag.message))
    loc = diag.source
    return ("%s:%d:%d: %s: %s"
            % (loc.file, loc.line, loc.column, diag.kind, diag.message))
