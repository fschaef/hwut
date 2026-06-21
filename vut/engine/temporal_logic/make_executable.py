"""
make_executable -- ONE SourceModule to a runnable Luau application.

    source ->  semanticize  ->  (require entry point)  ->  link  ->  Executable
                  ^^^^^^^^                                  ^^^^
                  common core                              implements references

Single-rooted: one source, one entry point, one runnable artifact. Distinct
from make_library by two facts -- it REQUIRES an entry point, and it LINKS
(turns every KNOWN access into an IMPLEMENTED one).

Forward-referenced, not yet built:
    link unit            link(Set[SemanticModule]) -> LinkedModule
    emitter unit         emit(Executable)          -> luau application text
"""

from __future__ import annotations
from common import semanticize, SemanticModule, SourceModule


# ---------------------------------------------------------------------------
# TYPE STATES (placeholders -- real classes live in the link / emitter units).
# ---------------------------------------------------------------------------
LinkedModule = "LinkedModule"    # references IMPLEMENTED across the assembled set
Executable   = "Executable"      # a LinkedModule bound to an entry point


def link(modules: "set[SemanticModule]") -> LinkedModule:
    """
    RETURN: a LinkedModule, the assembled set with every Access implemented
            from its recipe and the cross-module cascade graph proven acyclic

    The fold. Worklist per module, iterate to fixpoint; each recipe into a
    foreign module is reached through its shared ModuleRef. Cross-module
    cascade-cycle is decidable only here (over the whole set). An open Access,
    a stalled worklist, or a cycle is a diagnostic. Entry-point-agnostic:
    link neither requires nor forbids one. The link unit, shared in spirit
    with make_library but CALLED only here.
    """
    raise NotImplementedError


def require_entry_point(semantic: SemanticModule) -> None:
    """
    RETURN: None on success; raises a diagnostic if no entry point is present

    An executable needs a root to run (a reachable BEGIN/END frame). The
    precondition that separates make_executable from make_library.
    """
    raise NotImplementedError


def make_executable(source: SourceModule) -> Executable:
    """
    RETURN: an Executable, the source linked into a single runnable artifact
            bound to its entry point

    raises a diagnostic if the source declares no entry point, or if link
    finds an open reference / cascade cycle.

    Single-source build. Runs the common core once, requires an entry point,
    then folds this module with its dependency set into a LinkedModule and
    binds the entry point. emit(Executable) is the next, separate unit.
    """
    semantic = semanticize(source)             # common core, ONE module
    require_entry_point(semantic)              # PRE: a root to run
    linked = link(_with_dependencies(semantic))
    return _bind_entry_point(linked, semantic)


# ---------------------------------------------------------------------------
# helpers (stubs) -- the dependency set the fold needs, and the entry binding.
# ---------------------------------------------------------------------------
def _with_dependencies(semantic: SemanticModule) -> "set[SemanticModule]":
    """
    RETURN: a set of SemanticModule, `semantic` together with every module it
            depends on, each carried to the SemanticModule state

    The fold's input. A dependency from disk arrives already a SemanticModule
    (library member); a dependency built this run is semanticized alongside.
    """
    raise NotImplementedError


def _bind_entry_point(linked: LinkedModule, semantic: SemanticModule) -> Executable:
    """
    RETURN: an Executable, `linked` paired with the entry point found in
            `semantic`

    The seam to the emitter: an Executable is what emit() consumes.
    """
    raise NotImplementedError
