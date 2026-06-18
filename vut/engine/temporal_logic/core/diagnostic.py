"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

DIAGNOSTICS

Collects diagnostics across a transpilation run so the author sees every
fixable problem from a single pass, not one-error-at-a-time. Recording is
separated from aborting: 'report()' always appends; a caller decides at a phase
boundary whether collected fatal diagnostics should stop the run.
______________________________________________________________________________
"""
from dataclasses import dataclass
from enum        import Enum, auto


class Phase(Enum):
    """The transpiler phase a diagnostic originates from."""
    LEXER    = auto()
    PARSER   = auto()
    ANALYZER = auto()
    SEMANTIC = auto()


@dataclass(frozen=True)
class Diagnostic:
    """One diagnostic: phase, message, source position, and severity.

    'source_offset' is an absolute character offset into the rule-file text; a
    SourceMap converts it to a 1-based (line, column) at the render site.
    'fatal' True marks an error that must stop the run at the next phase
    boundary; False marks a recoverable problem the run continues past.
    'tag' is a core-neutral diagnostic-class label, used by a phase that
    classifies its errors (the semantic layer tags NAME / KIND / BINDING /
    CASCADE / GUARD / STRUCTURE / SWEEP). It defaults None so the lexer and
    parser, which do not classify, construct unchanged. Core never enumerates
    the tag values; each phase owns its own vocabulary and stringifies into
    this slot.
    """
    phase:         Phase
    message:       str
    source_offset: int
    fatal:         bool = True
    tag:           "str | None" = None


class DiagnosticReporter:
    """Accumulates Diagnostics; never aborts on its own.

    'report' appends. 'has_fatal' answers whether the run should stop.
    'abort_if_fatal' is the single explicit place a phase boundary may raise.
    A run with no reporter passed shares no global state -- each reporter is
    independent, so two files (or two tests) never bleed into each other.
    """
    def __init__(self):
        """RETURN: None. Starts with an empty diagnostic list."""
        self.errors = []

    def report(self, diagnostic: Diagnostic):
        """RETURN: None. Appends 'diagnostic'; does not raise.

        Recording is unconditional so collect-and-continue recovery in the
        lexer and parser can gather every fixable problem in one pass.
        """
        self.errors.append(diagnostic)

    def has_fatal(self) -> bool:
        """RETURN: True,  if any recorded diagnostic is fatal.
                  False, else.
        """
        return any(d.fatal for d in self.errors)

    def abort_if_fatal(self):
        """RETURN: None. Raises FatalDiagnostics if any fatal was recorded.

        Call at a phase boundary (after lexing, after parsing) to stop before
        the next phase consumes a half-built result. Within a phase, code keeps
        running so all fixable problems accumulate first.
        """
        if self.has_fatal():
            raise FatalDiagnostics(self.errors)


class FatalDiagnostics(Exception):
    """Raised at a phase boundary when fatal diagnostics were collected.

    Carries the full diagnostic list (fatal and non-fatal) so the caller can
    render the complete report, not merely the first fatal.
    """
    def __init__(self, diagnostics):
        super().__init__("%d diagnostic(s), fatal present" % len(diagnostics))
        self.diagnostics = diagnostics
