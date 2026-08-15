"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Faults as values. Exploration completes and reports every fault at
         once; nothing raises across a component boundary.

A 'Position' is FILE-RELATIVE, always: the line and column an author finds
in an editor. No position anywhere in the system is region-relative.
______________________________________________________________________________
"""
from dataclasses import dataclass
from enum        import Enum, auto


class E_FaultKind(Enum):
    SYNTAX     = auto()   # the text does not parse
    REFUSED    = auto()   # a construct that does not exist here, by name
    VOCABULARY = auto()   # an unknown key, a misspelt key, a missing key
    TYPE       = auto()   # a value of the wrong shape
    DIRECTORY  = auto()   # TEST DIRECTORY ERROR: carriers in conflict


@dataclass(frozen=True, slots=True)
class Position:
    """One place in one file; 1-based, as an editor counts."""
    line:   int
    column: int

    def __str__(self):
        """RETURN: str, 'line:column'."""
        return "%d:%d" % (self.line, self.column)


@dataclass(frozen=True, slots=True)
class Fault:
    """One fault, where it stands, and what it is."""
    kind:     E_FaultKind
    file:     str
    position: Position | None
    message:  str

    def __str__(self):
        """RETURN: str, 'file:line:column: KIND: message'."""
        where = "%s:%s" % (self.file, self.position) if self.position \
                else self.file
        return "%s: %s: %s" % (where, self.kind.name, self.message)
