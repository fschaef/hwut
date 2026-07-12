"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

AST NODES -- the typed products of the rule-file grammar (three-file contract,
             file 2 of 3: grammar.py = data, ast_nodes.py = products,
             ast_map.py = the wiring).

Every product IS-A core Node (core/symbol/ast.py), so the semantic unit can
rely on one base without knowing this vocabulary. Names lean on the core leaf
kinds where the grammar already decides the classification:

    DeclarationLeaf  a site that INTRODUCES a name (signature, declaration,
                     namespace, import alias, loop/comprehension vars, the
                     spawn handle, an exit-label definition)
    ReferenceLeaf    a site that NAMES something declared elsewhere (name-ref,
                     an event, a dropto target)
    ConstantLeaf     a literal (number, string path, glob, true/false)

Construction discipline (the four-way siting rule): a product built from ONE
rule sites its constructor as a classmethod 'from_cst' on the node; a product
several rules share is built by a small function in ast_map.py; OR routing is
an OrMap; passthrough is PASS. Constructors receive the FINISHED CST node and
read role-tagged children BY ROLE (strict), inline operator slots (OPT/STAR
wrappers, which carry no taggable name) BY POSITION.

Pass 2.5 scope: SYNTAX WITH SHAPE. No resolution, no symbol table, no peeking:
these nodes transcribe structure into the vocabulary declare/elaborate walk.
______________________________________________________________________________
"""
from dataclasses import dataclass

from ..core.parser_generator.cst_nodes import NodeAbsent
from ..core.symbol.ast import (Node, NodeList, ConstantLeaf, ConstantKind,
                               ReferenceLeaf, DeclarationLeaf)


# == constant kinds (the application's concrete set, core leaves carry them) ==
@dataclass(frozen=True)
class Kind(ConstantKind):
    """RETURN: Kind, a named lexical class for a ConstantLeaf ('int', 'float',
              'bool', 'string', 'glob') -- carried, never re-derived from text.
    """
    name: str

    def __repr__(self):
        return self.name


K_INT    = Kind("int")
K_FLOAT  = Kind("float")
K_BOOL   = Kind("bool")
K_STRING = Kind("string")
K_GLOB   = Kind("glob")


# == expressions (D-2: ONE parse grammar; sort is a pass-2 property) ==========
@dataclass(frozen=True)
class BinOp(Node):
    """A binary operation: 'lhs op rhs', already grouped -- chain factories fold
    left, so a * b * c arrives as BinOp(*, BinOp(*, a, b), c); the grouping is
    the tree, not a downstream convention.
    """
    op: str
    lhs: Node
    rhs: Node


@dataclass(frozen=True)
class Not(Node):
    """The boolean negation of 'operand' (condition world, R-4)."""
    operand: Node


@dataclass(frozen=True)
class Neg(Node):
    """The arithmetic negation of 'operand' (algebraic world, R-4)."""
    operand: Node


@dataclass(frozen=True)
class Ternary(Node):
    """Bridge B2 (R-4): 'cond ? then : els' -- a value selected by a truth."""
    cond: Node
    then: Node
    els:  Node


@dataclass(frozen=True)
class DataAccess(Node):
    """A place (R-16): a named base, optional call arguments, chained index
    steps. 'args' is NodeAbsent when no parens were written (a bare name), a
    NodeList of arguments otherwise; 'steps' is a NodeList of index expressions
    (empty when unindexed). The lvalue restriction (SEMANTICS 9) and the
    binding-head rule (R-9, D-8) are pass-2 judgements over 'name'.
    """
    name:  ReferenceLeaf
    args:  object                       # NodeList | NodeAbsent
    steps: NodeList


# == collections (R-17) =======================================================
@dataclass(frozen=True)
class Comprehension(Node):
    """A collection built by generation (R-17): 'element' produced under one or
    more chained 'generators'.
    """
    element:    Node
    generators: NodeList


@dataclass(frozen=True)
class Generator(Node):
    """One 'with: vars from: source [if: cond]' arm of a comprehension; 'cond'
    is NodeAbsent when unguarded; 'variables' are DeclarationLeafs (loop-local,
    SEMANTICS 6).
    """
    variables: NodeList
    source:    Node
    cond:      object                   # Node | NodeAbsent


# == causality (R-1, R-5, R-6, R-15) ==========================================
@dataclass(frozen=True)
class Cause(Node):
    """The unified cause (D-3): a named trigger with optional arguments and
    optional guard. 'target' is a ReferenceLeaf or a Lifecycle; 'args' is
    NodeAbsent for a bare event (kind -- raw event vs cause-ref -- is pass-2,
    SEMANTICS 2/5); 'guard' is NodeAbsent when unguarded.
    """
    target: Node
    args:   object                      # NodeList | NodeAbsent
    guard:  object                      # Node | NodeAbsent


@dataclass(frozen=True)
class Lifecycle(Node):
    """A reserved lifecycle event (R-10): kind is '~ENTRY' or '~EXIT'."""
    kind: str


@dataclass(frozen=True)
class Causality(Node):
    """A cause with its one-or-more effects: the language's atom (R-1)."""
    cause:   Node
    effects: NodeList


@dataclass(frozen=True)
class Effect(Node):
    """One effect: 'marker' is '=>' (spawn) or '=x=>' (cancel); 'action' is a
    Spawn or a CommandBlock (disjoint by R-6).
    """
    marker: str
    action: Node


@dataclass(frozen=True)
class Spawn(Node):
    """A spawned call (R-15): optionally ROUTED ('to_channel' the named
    out-channel of the enclosing reactor, a DeclarationLeaf-free plain
    token leaf -- NodeAbsent when suffix-less: the send FANS to all
    out-channels plus self, pipe ruling), optionally recurring ('every'
    period, NodeAbsent when one-shot) and optionally named ('handle' a
    DeclarationLeaf, NodeAbsent when anonymous; entity-local per
    SEMANTICS 11).
    """
    call:       Node
    every:      object                  # Node | NodeAbsent
    handle:     object                  # DeclarationLeaf | NodeAbsent
    to_channel: object = NodeAbsent     # ReferenceLeaf | NodeAbsent


@dataclass(frozen=True)
class Wire(Node):
    """A wire statement of a work body (pipe ruling: WIRING IS WORK):
    'source ----> dest;' / 'source --[ channel ]--> dest;' -- creates a
    PIPE: the destination subscribes to the source's out-channel.
    'channel' is the written name, or '' for the plain arrow (elaborate
    resolves it to the source's single out-channel where the type is
    visible; flagged open beyond that). 'source'/'dest' are
    ReferenceLeaf heads over bare locals.
    """
    source:  ReferenceLeaf
    dest:    ReferenceLeaf
    channel: str = ""


@dataclass(frozen=True)
class DefCause(Node):
    """A named cause definition (R-5): 'cause:' signature cause-explicit ';'.
    'doc' carries the preceding docstring (D-18), NodeAbsent when none.
    """
    signature: Node
    cause:     Node
    doc:       object = NodeAbsent


# == definitions (R-7, R-10) ==================================================
@dataclass(frozen=True)
class Signature(Node):
    """A definition head: the DECLARED bare name (D-1) and its parameter list
    (NodeAbsent when unparameterised).
    """
    name:   DeclarationLeaf
    params: object                      # NodeList | NodeAbsent


@dataclass(frozen=True)
class Call(Node):
    """A reference with optional arguments: 'name(args)' or a bare 'name'
    ('args' NodeAbsent).
    """
    name: ReferenceLeaf
    args: object                        # NodeList | NodeAbsent


@dataclass(frozen=True)
class NamedArg(Node):
    """A keyword argument 'name = value' in a call's argument list (D-28:
    the same '=' marks a declaration default; position tells them apart)."""
    name:  str
    value: Node


@dataclass(frozen=True)
class DeclArg(Node):
    """One declared entry '[known:|had:] name [: type] [= default]' of a
    signature or panel (D-11, R-41.1): 'type_' NodeAbsent means float
    (LANGUAGE 2.1); 'default' NodeAbsent means the entry is REQUIRED at
    every call. 'marker' carries the relation as WRITTEN: 'known' (a view),
    'had' (the optional visibility marker), or '' (unmarked -- having is
    implicit, custody is the ground state, LANGUAGE 0.3).
    """
    name:    DeclarationLeaf
    type_:   object                     # Node | NodeAbsent
    default: object                     # Node | NodeAbsent
    marker:  str = ""                   # 'known' | 'had' | '' (R-41.1)


@dataclass(frozen=True)
class Reactor(Node):
    """A reactor definition (reactor ruling): a CLASS with behavior
    content -- and an event recipient. 'mode' is 'single' (the kind word
    'reactor': a STATE MACHINE, one behavior active) or 'multi'
    ('reactor++': a MODE GROUP, several active at once). 'members'/'works'
    are the class-shaped body items; 'behaviors' the behavior members.
    State lives HERE: behaviors own no members -- their code reaches the
    reactor through the bare-dot self binding ('.x'). 'ins'/'outs' name
    the reactor's CHANNELS (pipe ruling: publish/subscribe objects the
    reactor HAS, created and destructed with it) -- tuples of
    DeclarationLeaf, empty when the panel or a section is absent.
    """
    signature: Signature
    mode:      str
    is_:       NodeList
    members:   NodeList
    works:     NodeList
    behaviors: NodeList
    ins:       tuple = ()
    outs:      tuple = ()
    doc:       object = NodeAbsent      # preceding docstring (D-18)


@dataclass(frozen=True)
class ClassDef(Node):
    """A class definition (R-29, LANGUAGE 11; R-41.3): a named composite kind
    of persistent object -- is: inheritance, and ONE body brace whose items
    are member declarations ('[known:|had:] name : type;', having implicit)
    and member works, interleaving freely. Role by panel (R-30/R-41.1): a
    member work whose out: names the class is its construction work; one
    whose in: names it is its disposal work.
    """
    signature: Signature
    is_:       NodeList
    members:   NodeList
    works:     NodeList
    doc:       object = NodeAbsent


@dataclass(frozen=True)
class Panel(Node):
    """The flat, direction-sectioned panel (R-41.1, LANGUAGE 12.2/13.2):
    'ins'/'outs' the in:/out: entries (DeclArg, each carrying its relation
    marker -- unmarked = had, custody the ground state), 'signals' the
    SignalDecl fault set; each a NodeList, empty when absent.
    """
    ins:     NodeList
    outs:    NodeList
    signals: NodeList


@dataclass(frozen=True)
class Work(Node):
    """A work definition (LANGUAGE 12): panel + body statements. 'body' is
    NodeAbsent for a SPEC (panel without machine, 12.1); 'explicit' marks a
    '-class()' disposal (R-37, SEMANTICS 27).
    """
    signature: Signature
    panel:     Panel
    body:      object                   # NodeList | NodeAbsent (spec)
    explicit:  bool = False
    doc:       object = NodeAbsent


@dataclass(frozen=True)
class ClockworkDef(Node):
    """A clockwork definition (LANGUAGE 13): a work whose body may tick:."""
    signature: Signature
    panel:     Panel
    body:      object                   # NodeList | NodeAbsent
    doc:       object = NodeAbsent


@dataclass(frozen=True)
class NothingLeaf(Node):
    """The 'Nothing' atom (R-38, LANGUAGE 0.5): non-existence as a value --
    assignable to KNOWN holders only; never had."""
    begin: int


@dataclass(frozen=True)
class RelContainer(Node):
    """A relation-prefixed container type (R-38, LANGUAGE 10): 'have list' /
    'know dict' -- 'rel' the relation word, 'inner' the container type."""
    rel:   str
    inner: Node


@dataclass(frozen=True)
class Give(Node):
    """The 'give: [port (, port)*]' success terminal (LANGUAGE 12.4, R-37,
    R-41.4): 'ports' the named leaving out-ports as written (ReferenceLeafs,
    empty when bare) -- elaborate checks the list against the panel's out:
    section; the out-bundle leaves in declaration order (12.5)."""
    ports: NodeList = ()


@dataclass(frozen=True)
class Destruct(Node):
    """A 'destruct: <object>() ...' statement (R-37, SEMANTICS 27): ends a
    having explicitly by calling the object's disposal work; 'handler' the
    else:-block or NodeAbsent."""
    object:  Node
    handler: object = NodeAbsent


@dataclass(frozen=True)
class Tick(Node):
    """The 'tick:' delivery statement (LANGUAGE 13.3)."""


@dataclass(frozen=True)
class ExitSignal(Node):
    """An 'exit: [<variant>[(payload)]];' fault egress (LANGUAGE 12.4,
    R-41.7): 'variant' NodeAbsent is the BARE egress -- the nothing-more
    exhaustion signal of a clockwork (catcher-mandatory; the built-in
    variant's name in the puller's match domain stays 'finished',
    rename flagged)."""
    variant: object                     # ReferenceLeaf | NodeAbsent
    args:    object                     # NodeList | NodeAbsent


@dataclass(frozen=True)
class Handler(Node):
    """An 'else: { arms }' handler block (LANGUAGE 12.6)."""
    arms: NodeList


@dataclass(frozen=True)
class Arm(Node):
    """One handler arm: variant pattern (name + field list) or the bare
    default ('variant' is NodeAbsent), and its action. 'action' is a code
    block NodeList, an ExitSignal, or NodeAbsent (the ';' shrug).
    """
    variant: object                     # DeclarationLeaf-ish | NodeAbsent
    fields:  NodeList
    action:  object


@dataclass(frozen=True)
class SignalDecl(Node):
    """One entry of a panel's signals: section (D-23): the signal's name and
    its payload parameter list ('params' NodeAbsent when bare).
    """
    name:   DeclarationLeaf
    params: object                      # NodeList | NodeAbsent


@dataclass(frozen=True)
class Behavior(Node):
    """A behavior member of a reactor (reactor ruling): ONLY causalities
    -- no members, no works, no parameters, no instances; it exists
    nowhere but inside a reactor body. Its code's self is the REACTOR.
    'causalities' are the UNGROUPED ones (lawful exactly when at most
    one in-channel stands in the panel -- the group law, elaborate);
    'groups' the channel groups (pipe ruling), source order kept within
    each tuple."""
    signature:   Signature
    causalities: NodeList
    groups:      tuple = ()
    doc:         object = NodeAbsent    # preceding docstring (D-18)


@dataclass(frozen=True)
class ChannelGroup(Node):
    """One receive-routing group of a behavior body (pipe ruling):
    '<channel>: { causality+ }' -- 'channel' the in-channel name, or '.'
    for the SELF channel (the bare-dot binding as group head); the
    grouped causalities fire only for events delivered on that channel.
    """
    channel:     str
    causalities: NodeList
    begin:       int = 0


# == command block (R-6, R-13, R-14) ==========================================
@dataclass(frozen=True)
class CommandBlock(Node):
    """A brace-delimited imperative body: statements in order, emission-free
    (R-6). Serves both the effect's block and every nested block (R-12: one
    brace form).
    """
    statements: NodeList


@dataclass(frozen=True)
class Mutation(Node):
    """One mutation statement (R-13 leaf, D-26): 'lvalues op rhs' closed by
    ';' or by an aware handler. 'extra_lvalues' are the assignment form's
    further targets (multi-output work call; empty otherwise, pass-2);
    'handler' the else:-block or NodeAbsent. A target may arrive wrapped in
    KnownSite (R-41.2: the site marker).
    """
    lvalue: Node
    op:     str
    rhs:    Node
    extra_lvalues: NodeList = ()
    handler: object = NodeAbsent


@dataclass(frozen=True)
class KnownSite(Node):
    """A 'known:'-marked binding target (R-41.2, site marking): the target
    receives a VIEW -- one word, two positions (panel entry and site). '='
    stays relation-neutral; marker and panel carry the relation. The
    site-vs-panel agreement law is flagged open: the marker is recorded,
    no check invented."""
    target: Node


@dataclass(frozen=True)
class If(Node):
    """The if/elif/else brancher (R-13): 'arms' is a NodeList of IfArm in
    source order (the if: first, each elif: after); 'els' is the else: block or
    NodeAbsent.
    """
    arms: NodeList
    els:  object                        # CommandBlock | NodeAbsent


@dataclass(frozen=True)
class IfArm(Node):
    """One condition-guarded arm of an If."""
    cond:  Node
    block: CommandBlock


@dataclass(frozen=True)
class Match(Node):
    """The match/case statement (R-13): an algebraic scrutinee against literal,
    range, glob, or wildcard patterns; exhaustiveness deliberately unchecked
    (SEMANTICS 8).
    """
    scrutinee: Node
    cases:     NodeList


@dataclass(frozen=True)
class Case(Node):
    """One 'case: pattern { ... }' arm of a Match."""
    pattern: Node
    block:   CommandBlock


@dataclass(frozen=True)
class Range(Node):
    """A 'lo to: hi' match pattern (inclusive)."""
    lo: Node
    hi: Node


@dataclass(frozen=True)
class Wildcard(Node):
    """The 'case: _' default pattern."""


@dataclass(frozen=True)
class For(Node):
    """The bounded collection loop (R-13, D-16, D-26): 'for: var in: source'
    over a collection, or 'for: var from: source' consuming a wound
    clockwork (LANGUAGE 13.5; the give flavour retired by ruling).
    'pulls' marks the from:-arm; 'handler' the trailing else:-block or
    NodeAbsent.
    """
    var:    DeclarationLeaf
    source: Node
    block:  CommandBlock
    pulls:  bool = False
    handler: object = NodeAbsent


@dataclass(frozen=True)
class Count(Node):
    """The bounded counting loop, range arm (R-13): a TYPED counter ('type_'
    is 'int' or 'float'), inclusive bounds, optional 'step'
    (NodeAbsent -> +1).
    """
    type_: str
    var:   DeclarationLeaf
    lo:    Node
    hi:    Node
    step:  object                       # Node | NodeAbsent
    block: CommandBlock


@dataclass(frozen=True)
class CountWith(Node):
    """The counting loop's ENUMERATION arm (D-17): 'index' counts in the
    counter's type from 'start' (NodeAbsent -> 0), 'var' walks the iterable
    source; both are DeclarationLeafs, loop-local (SEMANTICS 6).
    """
    type_:  str
    index:  DeclarationLeaf
    var:    DeclarationLeaf
    source: Node
    start:  object                      # Node | NodeAbsent
    block:  CommandBlock


@dataclass(frozen=True)
class Break(Node):
    """'break:;' -- leave the enclosing loop (R-14; no-loop is SEMANTICS 3)."""


@dataclass(frozen=True)
class Continue(Node):
    """'continue:;' -- next iteration of the enclosing loop (R-14)."""


@dataclass(frozen=True)
class DropTo(Node):
    """'dropto: label;' -- the forward-only jump to an exit-label (R-14);
    forward-only-ness and existence are SEMANTICS 7.
    """
    label: ReferenceLeaf


@dataclass(frozen=True)
class ExitLabel(Node):
    """':label:' -- the DEAD ADDRESS (R-24, B-1/R-39): dropto:'s target,
    drop-throughable like a kernel-driver goto label; outermost-body-only
    (SEMANTICS 7). 'region' NodeAbsent -- or the CATCH REGION's block
    (':label: => { ... }'): the elseto: target that catches routed
    signals; normal flow SKIPS the region.
    """
    label:  DeclarationLeaf
    region: object = NodeAbsent


# == declarations and types (R-19) ============================================
@dataclass(frozen=True)
class Declaration(Node):
    """A '[known:|had:] name: type;' member declaration (class-shaped body
    or top level; D-5: no parameter list). 'marker' carries the relation as
    WRITTEN (R-41.3): 'known' (a view member), 'had' (optional visibility
    marker), or '' (unmarked -- having implicit). 'doc' exists only because
    D-19's factored head makes a preceding docstring PARSEABLE on a
    top-level declaration; the placement is unlawful (LANGUAGE 1.2) and
    declare rejects it (SEMANTICS 22, D-20).
    """
    name:   DeclarationLeaf
    type_:  Node
    marker: str = ""                    # 'known' | 'had' | '' (R-41.3)
    doc:    object = NodeAbsent         # D-20: parseable, rejected in declare


@dataclass(frozen=True)
class BuiltinType(Node):
    """A built-in scalar type: 'int', 'float', 'string', or 'bool'."""
    kind: str


@dataclass(frozen=True)
class NamedType(Node):
    """A user-named type: resolution is the semantic unit's (pass 2+)."""
    name: ReferenceLeaf


@dataclass(frozen=True)
class ListType(Node):
    """The plain 'list' aggregate (R-19): variable-typed, no parameters."""


@dataclass(frozen=True)
class DictType(Node):
    """The plain 'dict' aggregate (R-19): variable-typed, no parameters."""


@dataclass(frozen=True)
class StructType(Node):
    """A 'struct { x; y; }' aggregate (R-19): named untyped slots."""
    fields: NodeList


# == namespaces and imports (R-18) ============================================
@dataclass(frozen=True)
class Namespace(Node):
    """An 'open: path { ... }' scope (R-18): 'name' DECLARES the (dotted) mount
    path; 'items' are the enclosed top-level constructs.
    """
    name:  DeclarationLeaf
    items: NodeList


@dataclass(frozen=True)
class Import(Node):
    """An 'import: "path" as: alias' mount (R-18): recorded by the parser,
    mounted by elaborate step 0 (F-1). 'alias' DECLARES the mount name.
    """
    path:  ConstantLeaf
    alias: DeclarationLeaf


# == the file =================================================================
@dataclass(frozen=True)
class ModuleRoot(Node):
    """The typed root of one rule-file: the top-level products in source order.
    What finalize_file yields and ParsedModule.file_node holds. 'doc' is the
    MODULE docstring -- the file's first item when written (D-18,
    SEMANTICS 22) -- NodeAbsent when none.
    """
    items: NodeList
    doc:   object = NodeAbsent
