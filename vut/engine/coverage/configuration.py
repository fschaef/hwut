"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE COVERAGE CONTRACT -- what is gathered, and how much of it.

Held VERBATIM by 'TestConfiguration' (aggregation, not restatement): a
field is declared by the component that enforces it, once.

A coverage run is ITS OWN ANIMAL (RATIONALE D-4): caps may be disabled
for it, it produces no cadence, and it never takes the interactive road.
Those consequences are enforced where the run is wired; this struct only
states what was asked for.
______________________________________________________________________________
"""
from dataclasses import dataclass, field
from typing      import Sequence


@dataclass(frozen=True)
class CoverageConfig:
    """WHAT IS GATHERED, and nothing about what is shown.

    'include' / 'omit' are GLOB lists over source files. They exist to
    keep the GATHERING cheap and for no other purpose: what is
    displayed, recorded or further processed is a LATER STAGE'S filter
    (RATIONALE D-3). An empty 'include' means 'whatever the tool would
    take by itself'; 'omit' subtracts from that.

    'counts' asks for per-range HIT COUNTS. Off by default: counts are
    what prevent the interval collapse, and the question HWUT asks is
    'did this test reach this code', not 'how often' (D-5).

    THE LANGUAGE AND THE TOOL ARE NOT HERE (D-26): both come from the
    'language-setup' entry the test's language selects, in
    'hwut-root.conf'. What stands here is what THIS RUN GATHERS."""
    include:       Sequence[str] = field(default_factory=tuple)
    omit:          Sequence[str] = field(default_factory=tuple)
    counts:        bool          = False


class CoverageRefused(ValueError):
    """A coverage run that cannot be served, named at the door.

    Raised where the language resolves to no candidate, where no
    candidate is available on this machine, or where a configuration
    asks for two things that cannot both hold ('record_timing' beside
    'record_coverage'; 'interactive' beside 'record_coverage').

    REFUSE RATHER THAN GUESS: every alternative here has a tempting
    default, and every one of those fails silently, in the green
    direction.
    """
    pass
