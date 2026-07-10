"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

DECLARE -- the second transition of the module spine:

    ParsedModule --declare--> DeclaredModule

Declare PUBLISHES this module's export_db and touches nothing else. The two
phases stay separated (renewal lesson 7.4): declare populates the table,
elaborate consults it -- never entangled. In particular:

    - REFERENCES ARE NEVER TOUCHED. No resolution, no recipe, no peeking of
      peers happens here; a reference is opaque cargo until elaborate.
    - IMPORTS ARE RECORDED, NOT MOUNTED. An import declares its ALIAS in this
      module's scope (existence + kind); reading the imported unit's exports
      into scope is elaborate step 0 (F-1).

THE F-6 GATE (strict, ratified (a)): any parser diagnostic blocks declare.
declare_module refuses -- by raising, not by diagnosing -- when the reporter
carries anything from the parse phase, so declare only ever sees a clean tree
and no downstream unit inherits cascade artefacts.

THE EXPORT SURFACE (what is published, and what deliberately is not):

    published    Character / Aspect / Behavior   signature name, its kind
                 DefCause                        signature name, kind 'cause'
                 Declaration                     member name, kind 'declaration'
                 Import                          alias name, kind 'import'
                 Namespace                       recursed: items publish under
                                                 the extended scope; re-opening
                                                 the same path EXTENDS it
                                                 (never a collision)
    not          Causality                       anonymous: declares nothing
    published    definition INTERNALS            behaviours inside an aspect
                                                 body, has: members, signature
                                                 parameters -- these are
                                                 addressed through their OWNER,
                                                 not through dotted scope, so
                                                 they are no namespace member
                                                 and no export; elaborate owns
                                                 them

DUPLICATES (SEMANTICS 18, REJECT): the same name declared twice in the same
scope is rejected via the reporter; the FIRST publication stays authoritative
so the walk remains total and later diagnostics keep their anchor.
______________________________________________________________________________
"""
from dataclasses import dataclass, field

from ..core.diagnostic import DiagnosticReporter, Diagnostic, Phase
from .module_states import ParsedModule, DeclaredModule
from ..core.symbol.ast import ConstantLeaf
from . import ast_nodes as A


@dataclass(frozen=True)
class Member:
    """RETURN: Member, one name of a definition's DECLARED surface: a
              signature parameter ('param', with the D-11 default flag) or a
              has: member ('member', never defaulted) -- the name and two
              booleans a caller-side check needs, nothing of any body.
    """
    name:        str
    category:    str                    # 'param' | 'member'
    has_default: bool = False


@dataclass(frozen=True)
class ExportEntry:
    """RETURN: ExportEntry, one published name: its KIND ('character',
              'aspect', 'behavior', 'cause', 'declaration', 'import',
              'namespace'), the SCOPE it lives in (namespace path, () at top
              level), whether the definition is ABSTRACT ('~' written on its
              line), and its declared MEMBER surface (parameters with default
              flags, has: names) in declaration order.

    The peek contract: a peer reads the DECLARED surface -- existence, kind,
    abstractness, member names -- and never anything of a body.
    """
    kind:     str
    scope:    tuple
    abstract: bool  = False
    members:  tuple = ()


class ExportDB:
    """RETURN: never a value itself -- the peekable table of every name this
              module declares: fully-qualified name (scope segments + own
              segments, one tuple) -> ExportEntry.

    Deterministic to iterate (sorted keys), so a printed dump is byte-stable
    for the GOOD suite. Publication reports a collision instead of raising:
    the caller (declare) owns the diagnostic; the table owns only the
    first-wins law.
    """

    def __init__(self):
        self._entries = {}

    def publish(self, scope, segments, kind, abstract=False, members=()):
        """RETURN: True, if the name was new and is now published.
                  False, if the fully-qualified name is already present --
                  the existing entry stays authoritative (first wins), the
                  caller diagnoses.
        """
        key = tuple(scope) + tuple(segments)
        if key in self._entries:
            return False
        self._entries[key] = ExportEntry(kind=kind, scope=tuple(scope),
                                         abstract=abstract,
                                         members=tuple(members))
        return True

    def peek(self, qualified):
        """RETURN: ExportEntry, the entry published under the fully-qualified
                  name 'qualified' (a tuple of segments) if present.
                  None, else.

        Existence + kind is ALL a peek reveals -- the cross-module contract
        the module spine documents.
        """
        return self._entries.get(tuple(qualified))

    def __len__(self):
        """RETURN: int, the number of published names."""
        return len(self._entries)

    def __iter__(self):
        """RETURN: iterator, over (qualified-name tuple, ExportEntry) pairs in
                  sorted key order -- deterministic for printing and diffing.
        """
        return iter(sorted(self._entries.items()))

    def __contains__(self, qualified):
        """RETURN: bool, True if the fully-qualified name is published."""
        return tuple(qualified) in self._entries


def declare_module(parsed: ParsedModule,
                   reporter: DiagnosticReporter) -> DeclaredModule:
    """RETURN: DeclaredModule, the given module with its export_db published --
              origin and file_node carried over by reference, references
              untouched.
              Raises ValueError if 'reporter' already carries any diagnostic
              (the strict F-6 gate: declare only ever sees a clean tree);
              duplicate declarations (SEMANTICS 18) are reported through
              'reporter' and do not interrupt the walk (first wins).

    The walk covers top-level items and recurses ONLY through namespaces
    (re-opening the same path extends the scope); everything inside a
    definition body is the owner's and is deliberately not published.
    """
    if reporter.errors:
        raise ValueError(
            "F-6 strict gate: %d parser diagnostic(s) block declare -- "
            "declare only ever sees a clean tree" % len(reporter.errors))
    db = ExportDB()
    _declare_items(parsed.file_node.items, scope=(), db=db, reporter=reporter)
    return DeclaredModule(origin=parsed.origin,
                          file_node=parsed.file_node,
                          export_db=db)


def _declare_items(items, scope, db, reporter):
    """RETURN: None, always. Publishes every declaring item of 'items' into
              'db' under 'scope', reporting SEMANTICS-18 duplicates through
              'reporter'; recurses through namespaces, skips anonymous
              causalities, and never descends into a definition body.
    """
    for item in items:
        if isinstance(item, A.Namespace):
            path = item.name.segments
            # Publish each namespace link once; re-opening is EXTENSION, not
            # collision -- publish() returning False on a 'namespace' kind
            # that is already a namespace is therefore NOT diagnosed.
            deep = tuple(scope)
            for segment in path:
                already = db.peek(deep + (segment,))
                if already is None:
                    db.publish(deep, (segment,), "namespace")
                elif already.kind != "namespace":
                    _duplicate(reporter, deep + (segment,), item)
                deep = deep + (segment,)
            _declare_items(item.items, scope=deep, db=db, reporter=reporter)
            continue
        if isinstance(item, ConstantLeaf) and str(item.kind) == "docstring":
            _reject_misplaced_doc(reporter, item)          # SEMANTICS 22
            continue
        if isinstance(item, A.Declaration) and not _is_absent(item.doc):
            _reject_doc_on_declaration(reporter, item)     # SEMANTICS 22, D-20
        name, kind = _declared_name(item)
        if name is None:
            continue                       # anonymous (causality): no export
        if not db.publish(scope, name.segments, kind,
                          abstract=getattr(item, "abstract", False),
                          members=_member_surface(item)):
            if isinstance(item, A.Work) and len(name.segments) == 2 \
                    and name.segments[1] != "-":
                continue    # a CONSTRUCTOR OVERLOAD (R-32): several
                            # '+class.ext' completions share one name; the
                            # first publication stands, the set is checked
                            # for arity disjointness by elaborate (SEM 26)
            _duplicate(reporter, tuple(scope) + tuple(name.segments), item)


def _declared_name(item):
    """RETURN: (DeclarationLeaf, str), the item's declared name and its export
              kind, for every publishing construct.
              (None, None), for a construct that declares nothing (causality).
    """
    if isinstance(item, A.Character):
        return item.signature.name, "character"
    if isinstance(item, A.Aspect):
        return item.signature.name, "aspect"
    if isinstance(item, A.Behavior):
        return item.signature.name, "behavior"
    if isinstance(item, A.DefCause):
        return item.signature.name, "cause"
    if isinstance(item, A.ClassDef):
        return item.signature.name, "class"
    if isinstance(item, A.Work):
        return item.signature.name, "work"
    if isinstance(item, A.ClockworkDef):
        return item.signature.name, "clockwork"
    if isinstance(item, A.Declaration):
        return item.name, "declaration"
    if isinstance(item, A.Import):
        return item.alias, "import"
    return None, None


def _member_surface(item):
    """RETURN: tuple, the item's declared Member surface in declaration order
              -- signature parameters (with the D-11 default flag), then has:
              members -- for every definition kind and named cause; empty for
              declarations, imports, and anything without a surface.
    """
    members = []
    signature = getattr(item, "signature", None)
    if signature is not None and not _is_absent(signature.params):
        for arg in signature.params:
            members.append(Member(name=arg.name.segments[0],
                                  category="param",
                                  has_default=not _is_absent(arg.default)))
    for decl in getattr(item, "has", ()):
        members.append(Member(name=decl.name.segments[0], category="member"))
    return tuple(members)


def _is_absent(value):
    """RETURN: bool, True exactly when 'value' is the typed absence
              (NodeAbsent) -- the one test the member harvest needs."""
    from ..core.parser_generator.cst_nodes import NodeAbsent
    return value is NodeAbsent


def _reject_misplaced_doc(reporter, leaf):
    """RETURN: None, always. The SEMANTICS-22 rejection: a docstring that
              precedes no definition is the MODULE docstring and lawful only
              as the file's very first item -- anywhere else it documents
              nothing.
    """
    reporter.report(Diagnostic(
        phase=Phase.SEMANTIC,
        message="misplaced docstring: a docstring precedes the definition "
                "it documents, or stands first in the file as the module "
                "docstring (SEMANTICS 22)",
        source_offset=leaf.begin,
        fatal=True,
        tag="STRUCTURE"))


def _reject_doc_on_declaration(reporter, item):
    """RETURN: None, always. The SEMANTICS-22 rejection of D-20's widened
              parse: a docstring may document a character, an aspect, a
              behaviour, or a named cause (LANGUAGE 1.2) -- never a
              declaration; the declaration itself remains published.
    """
    reporter.report(Diagnostic(
        phase=Phase.SEMANTIC,
        message="misplaced docstring: a docstring documents a character, "
                "an aspect, a behaviour, or a named cause -- not a "
                "declaration (SEMANTICS 22)",
        source_offset=item.doc.begin,
        fatal=True,
        tag="STRUCTURE"))


def _duplicate(reporter, qualified, item):
    """RETURN: None, always. Reports one SEMANTICS-18 rejection: the
              fully-qualified name is already declared in this scope; the
              first publication stays authoritative.

    fatal=True carries the REJECT severity: the walk continues (collect and
    continue), the run stops at the next phase boundary; tag 'NAME' places
    the diagnostic in the semantic layer's name class.
    """
    reporter.report(Diagnostic(
        phase=Phase.SEMANTIC,
        message="duplicate declaration of %r in this scope; the first "
                "declaration stays authoritative (SEMANTICS 18)"
                % ".".join(qualified),
        source_offset=_begin_of(item),
        fatal=True,
        tag="NAME"))


def _begin_of(item):
    """RETURN: int, the best source anchor the item offers -- its declared
              name's offset where one exists, 0 else (an item without a leaf
              cannot anchor better; the message still names the qualified
              name).
    """
    name, _ = _declared_name(item)
    if name is not None:
        return name.begin
    if isinstance(item, A.Namespace):
        return item.name.begin
    return 0
