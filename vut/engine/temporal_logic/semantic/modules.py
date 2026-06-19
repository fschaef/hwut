"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

MODULE LOADER  (pass 2, README A)

A file METAMORPHOSES through two per-file worlds and then folds into one
program-level world:

  SourceFile   (key, text, provenance)   -- located through the loader
        |  parse_source                  -- materialise: text -> structure
        v
  ParsedModule (key, ast,  provenance)   -- the parsed Module node
        |  resolve (whole-program, elsewhere)
        v
  ResolvedProgram                         -- many ParsedModules fold into one

The two per-file worlds are DISTINCT TYPES, not two states of one record: a
SourceFile has text and no AST; a ParsedModule has an AST and no text. The
transition 'parse_source' consumes one and produces the other. RESOLVED is NOT
a per-file world -- it is the whole-program fold (one ResolvedProgram for the
entire closure), so it lives one layer up (program.py), not here.

PROVENANCE rides through unchanged: which import pulled a file into the closure,
and from where. parse_source copies it from SourceFile to ParsedModule. An error
at any stage can reconstruct the import chain by walking importer links up to the
root (whose provenance has no importer).

The LOAD WALK is the first stackless walk of pass 2: from the root, fetch and
parse a module, read its imports, and descend, never recursing the interpreter.
Two outcomes stop it:

  -- an IMPORT CYCLE (A imports B imports A) is reported as one ordered chain
     and is FATAL-STOP: a looping load can never reach ALL-PARSED, and there is
     no remainder to continue over, so the pipeline does not advance to the
     scope build (contrast the cascade cycle, which accumulates and continues).

  -- a LOADER failure (the source cannot be fetched) is INFRASTRUCTURE, not an
     author error: it sets the reporter's fatal flag with a Phase.SEMANTIC
     diagnostic and stops the walk.

This module performs the load walk and hands back the parsed modules keyed by
import path. It does NOT build scopes (scope_tree.py) and does NOT graft mounts
-- the graft is a scope-stage step that needs sealed donor trees (README A,
ORDER WITHIN THE SCOPE STAGE), run after every module is built.
______________________________________________________________________________
"""
from dataclasses import dataclass, field
from enum        import Enum

from .diagnostics         import SemanticClass, semantic_error
from ..core.diagnostic    import Diagnostic, Phase
from ..parser.rule_parser import parse
from ..parser.ast_nodes   import Import


@dataclass(frozen=True)
class Provenance:
    """Where a file came from in the import closure.

    'importer_key' is the key of the file whose import: line pulled this one in,
    or None for the root (imported by nobody). 'import_offset' is the offset of
    that import: line in the importer (0 for the root). The full import chain is
    reconstructed on demand by following importer_key up the LoadTable until the
    root -- paid for only when an error actually fires, never stored as a list.
    """
    importer_key:  "str | None"
    import_offset: int = 0


@dataclass(frozen=True)
class SourceFile:
    """The SOURCE world: a located file, fetched but not yet parsed.

    'key' is the import path it was fetched under. 'text' is the raw source the
    loader returned. 'provenance' is the import that introduced it. Has NO ast --
    parsing has not happened. Consumed by parse_source into a ParsedModule.
    """
    key:        str
    text:       str
    provenance: Provenance


@dataclass(frozen=True)
class ParsedModule:
    """The PARSED world: a file materialised into structure.

    'key' is the import path. 'ast' is the parsed Module node. 'provenance' is
    copied through from the SourceFile. Has NO text -- it has metamorphosed into
    an AST. Import edges are derived on demand via 'imports' (not stored): the
    AST is the single source of truth.
    """
    key:        str
    ast:        object
    provenance: Provenance

    @property
    def imports(self) -> "list[tuple[str, list, int]]":
        """RETURN: list of (filename, mount-path, offset) for each top-level
                  Import in this module's AST, in source order.

        Derived from the AST each call. The load walk reads this a bounded number
        of times over a handful of modules; cache here only if a profile ever
        shows the re-walk. 'mount' is the dotted target path the scope stage grafts
        under.
        """
        out = []
        for item in self.ast.items:
            if isinstance(item, Import):
                out.append((item.filename, list(item.mount), item.begin))
        return out


@dataclass
class LoadTable:
    """The result of the load walk: every reachable ParsedModule, keyed by path.

    'modules' maps an import path to its ParsedModule. 'root_key' is the entry
    module's key. 'ok' is False when the walk stopped on an import cycle or a
    loader failure -- the caller does not advance to the scope build. When False
    the reporter carries the located diagnostic(s).
    """
    modules:  "dict[str, ParsedModule]" = field(default_factory=dict)
    root_key: str = ""
    ok:       bool = True


@dataclass
class _Frame:
    """One active load-walk frame: a module key, its remaining import edges, and
    the ordered key path from root to it (for the cycle chain)."""
    key:     str
    imports: object
    path:    "list[str]"


def load_import_closure(root_source, root_key, oracle, loader, reporter) -> "LoadTable":
    """RETURN: LoadTable, every module reachable from the root, each a ParsedModule;
              '.ok' False if an import cycle or a loader failure stopped the
              walk (the reporter then carries the diagnostic).

    The stackless load walk. The root is a SourceFile built from 'root_source'
    directly; every imported path is fetched through 'loader(path) -> source
    text'. Each SourceFile materialises once into a ParsedModule (the cache is
    'result.modules'); a path met again that is already on the ACTIVE path is an
    import cycle.

    Cycle detection tracks each module's load state: a module on the current
    active load path is ON_PATH, a fully loaded one is COMPLETE. Meeting a module
    already ON_PATH closes a cycle; the chain from that module down to the
    current edge is the ordered report. A loader exception is caught and turned
    into an infrastructure-fatal diagnostic; neither outcome advances the pipeline.
    """
    result = LoadTable(root_key=root_key)

    class E_Mark(Enum):
        ON_PATH  = 0
        COMPLETE = 1

    mark = {}                         # key -> ON_PATH | COMPLETE (absent = unvisited)

    root_src = SourceFile(key=root_key, text=root_source,
                          provenance=Provenance(importer_key=None, import_offset=0))
    root_mod = parse_source(result, reporter, root_src, oracle)
    if root_mod is None:
        result.ok = False
        return result

    mark[root_key] = E_Mark.ON_PATH
    work = [_Frame(root_key, iter(root_mod.imports), [root_key])]

    while work:
        frame = work[-1]
        if (edge := next(frame.imports, None)) is None:
            mark[frame.key] = E_Mark.COMPLETE   # all imports done -> fully loaded
            work.pop()
            continue

        dep_key, _mount, offset = edge

        match mark.get(dep_key):
            case E_Mark.ON_PATH:
                # dep_key is on the active path -> cycle. Report the ordered chain.
                chain = frame.path[frame.path.index(dep_key):] + [dep_key]
                reporter.report(semantic_error(
                    SemanticClass.STRUCTURE, offset,
                    "import cycle: " + " -> ".join(chain)))
                result.ok = False
                return result
            case E_Mark.COMPLETE:
                continue                      # already loaded; shared, not a cycle

        # Fetch (-> SourceFile) then parse (-> ParsedModule).
        prov = Provenance(importer_key=frame.key, import_offset=offset)
        if (src := _fetch(loader, reporter, dep_key, prov)) is None:   # loader failure -> infrastructure
            result.ok = False
            return result
        elif (dep_mod := parse_source(result, reporter, src, oracle)) is None:
            result.ok = False
            return result

        mark[dep_key] = E_Mark.ON_PATH
        work.append(_Frame(dep_key, iter(dep_mod.imports), frame.path + [dep_key]))

    return result


def parse_source(result, reporter, source_file, oracle):
    """RETURN: ParsedModule, the SourceFile materialised into structure and cached;
              None if the key was already present (a re-parse attempt, a bug).

    The SOURCE -> PARSED materialisation. Parses 'source_file.text' with the real
    parser, wraps the AST in a ParsedModule carrying the same provenance, and
    caches it under the key. Parser diagnostics flow into the shared reporter; a
    parse that recovered still yields a (partial) AST so the load walk can read
    whatever imports parsed.
    """
    if source_file.key in result.modules:
        return None                       # parse-once invariant

    ast_module = parse(source_file.text, oracle, reporter)

    parsed = ParsedModule(key        = source_file.key,
                          ast        = ast_module,
                          provenance = source_file.provenance)

    result.modules[source_file.key] = parsed

    return parsed


def _fetch(loader, reporter, key, provenance) -> "SourceFile | None":
    """RETURN: SourceFile, the located source for 'key'; None on loader failure.

    A loader exception is an INFRASTRUCTURE fault, not an author error: it is
    reported as a Phase.SEMANTIC fatal at the importing site (provenance.
    import_offset) and stops the walk. (The diagnostic is built directly, not
    through semantic_error, so it carries no author-facing class tag -- it is a
    machine fault, not one of the seven author classes.) A fetch failure means no
    SourceFile is ever born, which is why the offset rides on the edge/provenance
    rather than on a SourceFile.
    """
    try:
        text = loader(key)
    except Exception as exc:              # loader contract: raises on absence
        reporter.report(Diagnostic(
            phase=Phase.SEMANTIC,
            message="cannot load module '%s': %s" % (key, exc),
            source_offset=provenance.import_offset,
            fatal=True))
        return None
    return SourceFile(key=key, text=text, provenance=provenance)
