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
    """A spawned call (R-15): optionally recurring ('every' period, NodeAbsent
    when one-shot) and optionally named ('handle' a DeclarationLeaf, NodeAbsent
    when anonymous; entity-local per SEMANTICS 11).
    """
    call:   Node
    every:  object                      # Node | NodeAbsent
    handle: object                      # DeclarationLeaf | NodeAbsent


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
    """A keyword argument 'name = value' in a call's argument list."""
    name:  str
    value: Node


@dataclass(frozen=True)
class DeclArg(Node):
    """One declared parameter 'name [: type] [= default]' of a signature (D-11,
    Python behaviour): 'type_' NodeAbsent means float (LANGUAGE 2.1);
    'default' NodeAbsent means the parameter is REQUIRED at every call.
    """
    name:    DeclarationLeaf
    type_:   object                     # Node | NodeAbsent
    default: object                     # Node | NodeAbsent


@dataclass(frozen=True)
class Character(Node):
    """A character definition (R-7): concurrent aspects via has:. 'abstract'
    per R-10 ('~'); 'is_' the NodeList of inherited references (empty when
    none); 'has' the NodeList of declarations (empty when none).
    """
    abstract:  bool
    signature: Signature
    is_:       NodeList
    has:       NodeList
    doc:       object = NodeAbsent      # preceding docstring (D-18)


@dataclass(frozen=True)
class SignalDecl(Node):
    """One entry of a panel's signals: section (D-23): the signal's name and
    its payload parameter list ('params' NodeAbsent when bare).
    """
    name:   DeclarationLeaf
    params: object                      # NodeList | NodeAbsent


@dataclass(frozen=True)
class Aspect(Node):
    """An aspect definition (R-7, R-25): governs its one active behaviour; the
    body is a NodeList of behaviours. 'signals' is the panel's declared fault
    set (D-23) -- recorded here; its checks land with the work construct.
    """
    abstract:  bool
    signature: Signature
    is_:       NodeList
    has:       NodeList
    body:      Node
    signals:   NodeList = ()            # panel signals: section (D-23)
    doc:       object = NodeAbsent      # preceding docstring (D-18)


@dataclass(frozen=True)
class Behavior(Node):
    """A behaviour definition (R-7): aggregates causalities."""
    abstract:    bool
    signature:   Signature
    is_:         NodeList
    has:         NodeList
    causalities: NodeList
    doc:         object = NodeAbsent    # preceding docstring (D-18)


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
    """One mutation statement (R-13 leaf): 'lvalue op rhs;'."""
    lvalue: DataAccess
    op:     str
    rhs:    Node


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
    """The bounded collection loop 'for: var in: source' (R-13, D-16): 'var'
    is a DeclarationLeaf, local to the loop (SEMANTICS 6).
    """
    var:    DeclarationLeaf
    source: Node
    block:  CommandBlock


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
    """'exit: label;' -- a bare drop-through label (R-14), outermost-body-only
    (SEMANTICS 7).
    """
    label: DeclarationLeaf


# == declarations and types (R-19) ============================================
@dataclass(frozen=True)
class Declaration(Node):
    """A 'name: type;' member declaration (has: block or top level; D-5: no
    parameter list). 'doc' exists only because D-19's factored head makes a
    preceding docstring PARSEABLE on a top-level declaration; the placement
    is unlawful (LANGUAGE 1.2) and declare rejects it (SEMANTICS 22, D-20).
    """
    name:  DeclarationLeaf
    type_: Node
    doc:   object = NodeAbsent          # D-20: parseable, rejected in declare


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
