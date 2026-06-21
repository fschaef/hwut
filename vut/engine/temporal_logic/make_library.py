"""
make_library -- a SET of SourceModules to a packed, rootless library.

    sources ->  semanticize (each)  ->  (require NO entry point)  ->  pack  ->  Library
                   ^^^^^^^^^^^^^^^                                     ^^^^
                   common core, N times                               NO link

Plural and rootless: many sources, no entry point, a bag of SemanticModules.
Distinct from make_executable by two facts -- it FORBIDS an entry point, and
it DOES NOT link. References stay KNOWN (each Access keeps its recipe); they are
implemented only when some later make_executable folds this library in.

A Library re-enters a later build as a set of SemanticModules (a SemanticModule
IS-A DeclaredModule, so each member is peekable for its export_db).
"""

from __future__ import annotations
from common import semanticize, SemanticModule, SourceModule


# ---------------------------------------------------------------------------
# TYPE STATE (placeholder).
# ---------------------------------------------------------------------------
Library = "Library"      # a packed set of SemanticModules, no entry point, unlinked


def forbid_entry_point(semantics: "set[SemanticModule]") -> None:
    """
    RETURN: None on success; raises a diagnostic if any member carries an
            entry point

    A library is rootless by construction -- it is consumed, never launched.
    The postcondition that separates make_library from make_executable.
    """
    raise NotImplementedError


def pack(semantics: "set[SemanticModule]") -> Library:
    """
    RETURN: a Library, the set of SemanticModules bundled for serialisation
            and later re-entry

    No fold, no link: the members are stored AS SemanticModules (access known,
    not implemented), so re-entry into a future build is free. This is the disk
    artifact a later make_executable loads and links against.
    """
    raise NotImplementedError


def make_library(sources: "set[SourceModule]") -> Library:
    """
    RETURN: a Library, every source carried to the SemanticModule state and
            packed together with no entry point

    raises a diagnostic if any source carries an entry point.

    Multi-source build. Runs the common core once per source, forbids an entry
    point across the set, and packs the resulting SemanticModules. Does NOT
    link -- linking is deferred to whoever finally builds an executable.
    """
    semantics = { semanticize(s) for s in sources }    # common core, MANY modules
    forbid_entry_point(semantics)                       # POST: rootless
    return pack(semantics)
