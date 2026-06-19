"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

SEMANTIC DIAGNOSTIC CLASSES

The seven classes a pass-2 error can carry, and one helper that builds a core
Diagnostic already tagged with its class and Phase.SEMANTIC. Core stays
ignorant of these names: the enum lives here, the helper stringifies the class
into the neutral 'tag' slot (README E, K).

Each class is raised by exactly one family of check, so the test suite carries
one choice per class (README J):

    NAME       undefined name; a shadowed pseudo-symbol; a descent that seats
               no symbol; a member-or-VOID tail naming no member.
    KIND       kind-vs-shape on a declaration head; a struct in a comparison;
               a cross-resolution (emission <-> bundle); a non-CLOCK clockwork
               trigger.
    BINDING    'e'/'sm'/'mg'/'m'/'cw' used where it is not in scope; a member
               on a memberless trigger.
    CASCADE    a cascade cycle; a system kind named as an emission.
    GUARD      a mutation inside a read-only guard or bracket condition.
    STRUCTURE  a shape the grammar admits but pass 2 refuses.
    SWEEP      a step kind forbidden in its sweep role.
______________________________________________________________________________
"""
from enum import Enum

from ..core.diagnostic import Diagnostic, Phase

class SemanticClass(Enum):
    """The diagnostic class a pass-2 error carries.

    The value is the bracket label rendered in messages and pinned by the test
    suite (README J); 'NAME' renders as '[NAME]'. Owned here, not in core.
    """
    NAME      = "NAME"
    KIND      = "KIND"
    BINDING   = "BINDING"
    CASCADE   = "CASCADE"
    GUARD     = "GUARD"
    STRUCTURE = "STRUCTURE"
    SWEEP     = "SWEEP"


def semantic_error(cls: SemanticClass, offset: int, message: str,
                   fatal: bool = True) -> Diagnostic:
    """RETURN: Diagnostic, a Phase.SEMANTIC diagnostic tagged with class 'cls'.

    'offset' is the absolute character offset the error points at -- for a
    drained (B) obligation this is the obligating REFERENCE's offset, not the
    scope close that found it unkept (README D). 'message' is the human text;
    the class is carried structurally in 'tag' (not only spelled in the text)
    so a test can assert the class without string-matching prose, and the
    rendered '[NAME] ...' prefix is produced once, here.
    """
    return Diagnostic(phase=Phase.SEMANTIC,
                      message="[%s] %s" % (cls.value, message),
                      source_offset=offset,
                      fatal=fatal,
                      tag=cls.value)
