"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

RELOCATION  (pass 2, disc-4 SETTLED 3 / SETTLED 5)

A cross-file reference that is NOT seated concretely at resolve time is recorded
as a RELOCATION -- the shared-library term, adopted deliberately: a recorded
load-and-link instruction the linker seats, rather than a binding fixed at build
time. A relocation is COMPLETE information (it knows which file to load and how
to bind the name), never an absence; a program and a library both have EVERY
reference resolved -- concretely or by relocation.

LOADABILITY IS TOTALLY DYNAMIC: lazy by design, eager by default. seat() is the
primitive; eager link is seat() in a startup loop, lazy link is seat() on first
miss. A relocation is PERMANENT -- it is the recipe an unseat/reseat re-runs --
so it is frozen and kept for the unit's whole life, separate from its disposable
seated result.

A shippable form (a ParsedModule or ResolvedModule a loader returns pre-built)
carries a UnitHeader so the linker can VERIFY it: the form's declared identity
(id_hash) is compared against the expecting relocation's expected_hash, and the
form's built_from records the upstream hash it was built against (the stale-form
self-check basis). The hash is a declared identity token, COMPARED not
necessarily recomputed; recompute-from-content is optional verification.
______________________________________________________________________________
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class UnitHeader:
    """The identity a shippable cached form carries for load-and-link.

    'id_hash' is THIS form's declared identity token -- compared against an
    expecting relocation's 'expected_hash' at link (compared, not necessarily
    recomputed from content). 'built_from' is the hash of the upstream form this
    one was built against (a ParsedModule's source hash; a ResolvedModule's
    parsed hash); link compares it against the upstream actually present to catch
    a STALE cached form. A SourceModule carries NO header -- source is the
    ground, not a cached form built from anything.
    """
    id_hash:    str
    built_from: str


@dataclass(frozen=True)
class Relocation:
    """One cross-file reference recorded for load-and-link, frozen and permanent.

    'path' names the target file (a version may ride in its extension).
    'into_scope' is the import's 'into:' mount -- the dotted scope path the
    target's names land under, or None for the current scope (todo-7).
    'expected_hash' is the target id_hash this unit was built against; link
    compares it with the loaded form's UnitHeader.id_hash. 'site' is the source
    offset of the reference, carried for diagnostics so any of the six link
    errors is attributable to a concrete relocation.

    Frozen and kept for the unit's whole life: it is the recipe seat() re-runs on
    a lazy (re)load, so it is never consumed. The SEATED RESULT lives elsewhere
    (an evictable id(node)->Symbol entry), so unseat can drop the binding back to
    this recipe without mutating it.
    """
    path:          str
    into_scope:    "list[str] | None"
    expected_hash: str
    site:          int
