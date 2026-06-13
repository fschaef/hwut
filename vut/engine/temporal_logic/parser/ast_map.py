"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

RULE-FILE AST MAP  --  rule name -> constructor.

The engine builds the canonical CST (core.cst_nodes) by default; this map is the
partial overlay (D-5) naming, for each rule, the CONSTRUCTOR that turns its
finished CST node into the typed value. Construction lives where it belongs:

  - a rule producing ONE AST NODE maps to a classmethod ON that node's class
    (ast_nodes): Spawn.from_seq, HasRef.from_seq, ... -- one factory per class;
  - a rule producing a PLAIN VALUE (a name-dotted segment list, a signature
    tuple, an arg list, a kind dict, a ref-member pair) maps to a small
    function HERE -- there is no node class to host it;
  - a rule whose node KIND the input decides -- the merged named tails and the
    declaration family, where 'the parens decide' (D-26) or the kind keyword
    decides (D-21) -- maps to a DISPATCH function HERE that builds one of the
    candidate classes;
  - a PASS-THROUGH rule (an OR dispatch forwarding its single child) maps to
    _passthrough -- it builds nothing.

Every constructor receives the rule's finished CST node -- children already
transformed, bottom-up -- and reads its structure DIRECTLY: SEQ children by
stable slot, OR branches by triggered_index, repetitions off their STAR/PLUS
slot, optionals as OPT_Nodes whose presence is the 'present' flag ON the node
(never inferred from the parent's child count).

Single-terminal rules (<guard-luau>, <mutation>, <report-string>) have no
operator node: their factory receives the raw leaf (SpanResult / Token) itself.

validate_ast_map() is the load-time coverage guard (every grammar rule mapped);
the shape correspondence (a SEQ rule's node IS SEQ_Interface, ...) is asserted
by TEST/test-ast-signals.py.
______________________________________________________________________________
"""
from .core.cst_nodes import OR_Node, SEQ_Node, PLUS_Node, STAR_Node
from . import ast_nodes as ast


# ---------------------------------------------------------------------------
# Plain-value rule factories (no node class to host them).
# ---------------------------------------------------------------------------
def _name_dotted(node):
    """RETURN: list[str], the dotted name as its segment list ['A', 'B', 'C'].

    children = (head_tok, STAR(('.', tok))): each repetition item is the
    anonymous one-survivor SEQ around the next segment token ('.' is silent).
    The list shape (not a joined string) keeps the segmentation pass-2 walks.
    """
    head = node.children[0]
    return [head.text] + [s.children[0].text for s in node.children[1].items]


def _signature(node):
    """RETURN: (name, params), a reactor/aggregate signature.

    children = (name_dotted, opt_params): the optional round-bracket parameter
    list is an OPT_Node at a stable slot; absent and '()' both give []. One
    signature value per rule slot, so no parent ever type-spots params.
    """
    opt = node.children[1]
    params = opt.child if opt.present else []
    return (node.children[0], params)


def _head_and_rest(node):
    """RETURN: list, '(X, STAR((sep, X)))' collapsed to [X, X, ...].

    The shared shape of <list-arg> and <list-decl-arg>: a head value, then a
    repetition whose items are anonymous one-survivor SEQs (separator silent).
    <list-decl-arg> carries a third slot (the SYNTAX_DOC-sanctioned trailing
    ';', an OPT over a silent terminal) -- it contributes no value and is not
    read.
    """
    return [node.children[0]] + [s.children[0] for s in node.children[1].items]


def _parens(node):
    """RETURN: list, the values inside '( ... )' (empty for '()').

    The shared shape of <parens-arg> and <parens-decl>: parens silent, so the
    single child is the optional inner list -- an OPT_Node whose child is the
    already-reduced list when present.
    """
    opt = node.children[0]
    return opt.child if opt.present else []


def _ref_member(node):
    """RETURN: (list[str], bool), a <ref-member>: (segments, is_void).

    children = (name_dotted, opt_void): the optional ('.', VOID) is an
    OPT_Node at a stable slot; presence IS is_void ('.' silent, VOID captured
    but its text is constant). The pair is consumed by HasRef / DefaultRef,
    which rebase to their keyword offset.
    """
    return (node.children[0], node.children[1].present)


def _opt_by(opt_node):
    """RETURN: OpaqueCode | None, an optional ['by:', LVALUE] slot's binding.

    Present -> the anonymous one-survivor SEQ around the LVALUE span ('by:'
    silent), wrapped into an OpaqueCode node; absent -> None.
    """
    if not opt_node.present:
        return None
    return ast.OpaqueCode.from_span(opt_node.child.children[0])


# ---------------------------------------------------------------------------
# Kind factories and the declaration dispatch (D-21): the grammar shares ONE
# head across the kinds; each kind rule reduces to a dict tagged 'kind', and
# the declaration dispatcher builds the matching node class.
# ---------------------------------------------------------------------------
def _kind_reactor(node):
    """RETURN: dict, {'kind': <keyword>} for mode/state/mode_group/state_machine.

    The rule is the OR of the four captured kind keywords; the matched token's
    text IS the kind.
    """
    return {"kind": node.child.text}


def _kind_struct(node):
    """RETURN: dict, {'kind': 'struct'} -- the single captured 'struct' keyword."""
    return {"kind": "struct"}


def _kind_container(node):
    """RETURN: dict, a container kind: 'kind'/'cargs'/'by'.

    children = (container_tok, opt_angle, opt_by): the angle-bracket type
    parameters are a NESTED optional -- opt_angle present yields the anonymous
    SEQ ('<', opt_cargs, '>') with '<'/'>' captured (slots of their own);
    opt_by per _opt_by.
    """
    opt_angle = node.children[1]
    cargs = []
    if opt_angle.present:
        opt_cargs = opt_angle.child.children[1]
        cargs = opt_cargs.child if opt_cargs.present else []
    return {"kind": "container", "cargs": cargs, "by": _opt_by(node.children[2])}


def _kind_variable(node):
    """RETURN: dict, a variable kind: 'kind'/'type'/'args'/'by'.

    children = (type_or, args, opt_by): the type slot is the inline OR
    (built-in keyword | struct/class id) whose child is the token either way;
    'args' is the already-reduced mandatory initialiser list.
    """
    return {"kind": "variable", "type": node.children[0].child.text,
            "args": node.children[1], "by": _opt_by(node.children[2])}


def _declaration(node):
    """RETURN: ReactorDecl | StructDecl | ContainerDecl | VariableDef.

    children = (name_tok, opt_sig, kind_dict): the optional round-bracket head
    signature is an OPT_Node at a stable slot (its child is the already-
    reduced ArgDecl list when present); 'kind_dict' from <kind-decl> carries the
    kind tag and the kind-specific payload. The kind keyword decides the class
    (D-21); kind-vs-shape legality of the head signature is pass 2 (F-2) --
    every class records what was written.
    """
    name_tok, opt_sig, kind = node.children
    head_params = opt_sig.child if opt_sig.present else []
    name, begin = name_tok.text, name_tok.begin
    match kind["kind"]:
        case "struct":
            return ast.StructDecl(name=name, members=head_params, begin=begin)
        case "container":
            return ast.ContainerDecl(name=name, cargs=kind["cargs"],
                                     by=kind["by"], head_params=head_params,
                                     begin=begin)
        case "variable":
            return ast.VariableDef(name=name, type_name=kind["type"],
                                   args=kind["args"], by=kind["by"],
                                   head_params=head_params, begin=begin)
        case reactor_kind:
            return ast.ReactorDecl(kind=reactor_kind, name=name,
                                   params=head_params, begin=begin)


# ---------------------------------------------------------------------------
# Merged named tails (D-26): THE PARENS DECIDE. One grammar shape per side; the
# dispatcher reads the optional parens slot and builds reference or emission.
# ---------------------------------------------------------------------------
def _opt_guard(opt_node):
    """RETURN: OpaqueCode | Condition | None, an optional ['&', <guard>] slot's guard.

    Present -> the anonymous one-survivor SEQ around the guard ('&' silent);
    absent -> None.
    """
    if not opt_node.present:
        return None
    return opt_node.child.children[0]


def _cause_system(node):
    """RETURN: Cause, a system trigger 'ANY|END|BEGIN|CHANGE ["&" <guard>]'.

    children = (kw_or, opt_guard): the keyword OR's child is the captured
    token; the trigger name is its single-segment list, is_keyword True.
    """
    tok = node.children[0].child
    trigger = ast.Trigger(name=[tok.text], is_keyword=True, begin=tok.begin)
    return ast.Cause(trigger=trigger, guard=_opt_guard(node.children[1]),
                     begin=tok.begin)


def _cause_named(node):
    """RETURN: Cause | CauseRef, '<name-dotted> [parens] ["&" <guard>]'.

    children = (name, opt_parens, opt_guard). The parens decide (D-26): present
    -> a CauseRef carrying the args (and any trailing guard, recorded for the
    pass-2 F-7 decision); absent -> an inline named Trigger wrapped in a Cause.
    """
    name, opt_parens, opt_guard = node.children
    guard = _opt_guard(opt_guard)
    if opt_parens.present:
        return ast.CauseRef(name=name, args=opt_parens.child, guard=guard,
                            begin=node.begin)
    trigger = ast.Trigger(name=name, is_keyword=False, begin=node.begin)
    return ast.Cause(trigger=trigger, guard=guard, begin=node.begin)


def _effect_named(node):
    """RETURN: EventSpec | EffectRef, '<name-dotted> [parens]'.

    children = (name, opt_parens). The parens decide (D-26): present -> an
    event emission (EventSpec); absent -> an effect-bundle reference
    (EffectRef).
    """
    name, opt_parens = node.children
    if opt_parens.present:
        return ast.EventSpec(name=name, args=opt_parens.child, begin=node.begin)
    return ast.EffectRef(name=name, begin=node.begin)


# ---------------------------------------------------------------------------
# Condition terms: the bare boolean stands (D-26).
# ---------------------------------------------------------------------------
def _left_fold(node):
    """RETURN: BinOp | operand, a left-associative operator level (D-13).

    children = (head, STAR((op, operand))): the head operand, then the
    repetition -- each item an anonymous SEQ (captured operator token, next
    operand). An empty repetition forwards the bare head; otherwise the items
    fold left into nested BinOp nodes, the operator read verbatim from each
    token. Shared by every binary ladder rule (cond-or/-xor/-and, alg-shift/
    -add/-mul).
    """
    acc = node.children[0]
    for item in node.children[1].items:
        op_tok, operand = item.children
        acc = ast.BinOp(op=op_tok.text, left=acc, right=operand, begin=op_tok.begin)
    return acc


def _un_fold(node):
    """RETURN: UnOp | operand, an optional unary prefix (D-13).

    children = (opt_prefix, operand): the inline optional 'not' (cond-not) or
    '-' (alg-un) is an OPT_Node at a stable slot. Present -> a UnOp carrying the
    captured operator's verbatim text; absent -> the bare operand, forwarded.
    """
    opt, operand = node.children
    if opt.present:
        tok = opt.child
        return ast.UnOp(op=tok.text, operand=operand, begin=tok.begin)
    return operand


def _comparison(node):
    """RETURN: Comparison | BoolRef | operand, '<algebr> [op-cmp <algebr>]' (D-13).

    children = (left, opt_tail): with a comparison tail -> a Comparison (the
    num->bool crossing); without one, a bare boolean expression -- a lone
    <name-dotted> becomes a BoolRef ('== true' in meaning, F-5), anything else
    (a Literal, a nested expression) forwards unchanged.
    """
    left, opt_tail = node.children
    if opt_tail.present:
        op_tok, right = opt_tail.child.children
        return ast.Comparison(left=left, op=op_tok.text, right=right,
                              begin=node.begin)
    if isinstance(left, list):
        return ast.BoolRef(name=left, begin=node.begin)
    return left


def _alg_atom(node):
    """RETURN: object, one <alg-atom> branch value (D-13).

    A parenthesised algebra (0), the '?'-bridge (1) and a bare <name-dotted> (7)
    forward unchanged; an opaque expression span (6) becomes an OpaqueCode; the
    number/string/true/false literals (2..5) wrap into a Literal.
    """
    i = node.triggered_index
    if i in (0, 1, 7):
        return node.child
    if i == 6:
        return ast.OpaqueCode.from_span(node.child)
    return ast.Literal.from_token(node.child)


def _recip_rhs(node):
    """RETURN: tuple ('recip', operand, else_body), a recip tail carrier.

    children = (operand, PLUS(body)); 'recip:'/'else:'/':end' silent. A plain
    carrier consumed by _clockwork_name_step, which has the lvalue to build the
    Recip node.
    """
    return ("recip", node.children[0], list(node.children[1].items))


def _clockwork_name_step(node):
    """RETURN: EventSpec | Assign | Recip, a name-led clockwork step (D-13).

    children = (name, tail): the tail is the left-factored dispatch on the token
    after the shared <name-dotted>. A parens-arg list -> a paced EventSpec
    emission; the 'gets:' algebr (forwarded bare) -> an Assign; the 'recip:'
    carrier -> a Recip with the lvalue filled in.
    """
    name, or_node = node.children
    tail = or_node.child
    if isinstance(tail, tuple) and tail and tail[0] == "recip":
        return ast.Recip(lvalue=name, operand=tail[1], else_body=tail[2],
                         begin=node.begin)
    if isinstance(tail, list):
        return ast.EventSpec(name=name, args=tail, begin=node.begin)
    return ast.Assign(lvalue=name, rhs=tail, begin=node.begin)


# ---------------------------------------------------------------------------
# Pass-through: forward the single matched value (no dedicated node).
# ---------------------------------------------------------------------------
_PASS_THROUGH = (
    "top-level", "cause", "guard", "cond", "cond-atom", "cond-bracket",
    "algebr", "alg-paren", "op-cmp", "op-or", "op-xor", "op-and",
    "op-shift", "op-add", "op-mul", "assign-rhs",
    "effect", "kind-decl", "type-built-in",
    "elm-mode", "elm-mode-group", "elm-state-machine",
    "elm-clockwork", "step-clockwork",
)


def _passthrough(node):
    """RETURN: object, the rule's single surviving value, unwrapped."""
    if isinstance(node, OR_Node):
        return node.child
    if isinstance(node, SEQ_Node):
        return node.children[0] if node.children else None
    if isinstance(node, (PLUS_Node, STAR_Node)):
        return node.items[0] if node.items else None
    return node


# ---------------------------------------------------------------------------
# The map: rule name -> constructor.
# ---------------------------------------------------------------------------
AST_MAP = {
    # plain-value rules (hosted here)
    "name-dotted":           _name_dotted,
    "signature":             _signature,
    "list-arg":              _head_and_rest,
    "list-decl-arg":         _head_and_rest,
    "parens-arg":            _parens,
    "parens-decl":           _parens,
    "ref-member":            _ref_member,

    # kind family + declaration dispatch (D-21)
    "kind-reactor":          _kind_reactor,
    "kind-struct":           _kind_struct,
    "kind-container":        _kind_container,
    "kind-variable":         _kind_variable,
    "declaration":           _declaration,

    # merged named tails (D-26): the input decides the class
    "cause-system":          _cause_system,
    "cause-named":           _cause_named,
    "effect-named":          _effect_named,

    # expression band (D-13): the two ladders, comparison, atom, bridge
    "cond-or":               _left_fold,
    "cond-xor":              _left_fold,
    "cond-and":              _left_fold,
    "cond-not":              _un_fold,
    "comparison":            _comparison,
    "alg-shift":             _left_fold,
    "alg-add":               _left_fold,
    "alg-mul":               _left_fold,
    "alg-un":                _un_fold,
    "alg-atom":              _alg_atom,
    "bridge":                ast.Bridge.from_seq,

    # node rules (constructors on the classes)
    "namespace":             ast.Namespace.from_seq,
    "import":                ast.Import.from_seq,
    "causality":             ast.Causality.from_seq,
    "def-cause":             ast.CauseDef.from_seq,
    "def-effect":            ast.EffectDef.from_seq,
    "guard-luau":            ast.OpaqueCode.from_span,
    "guard-bracket":         ast.Condition.from_seq,
    "mutation":              ast.Mutation.from_span,
    "spawn":                 ast.Spawn.from_seq,
    "unspawn":               ast.Unspawn.from_seq,
    "arming-mode":           ast.ModeArming.from_seq,
    "report-string":         ast.ReportString.from_token,
    "arg":                   ast.Arg.from_or,
    "mode":                  ast.Mode.from_seq,
    "init":                  ast.InitBlock.from_seq,
    "deinit":                ast.DeinitBlock.from_seq,
    "state":                 ast.State.from_seq,
    "ref-has":               ast.HasRef.from_seq,
    "default":               ast.DefaultRef.from_seq,
    "mode-group":            ast.ModeGroup.from_seq,
    "state-machine":         ast.StateMachine.from_seq,
    "def-event":             ast.EventDef.from_seq,
    "def-clock":             ast.ClockDef.from_seq,
    "decl-arg":              ast.ArgDecl.from_seq,

    # clockwork band (D-11) + mutations (D-13)
    "clockwork":                 ast.Clockwork.from_seq,
    "clockwork-name-step":       _clockwork_name_step,
    "recip-rhs":                 _recip_rhs,
    "incr":                      ast.Incr.from_seq,
    "decr":                      ast.Decr.from_seq,
    "clockwork-instant":         ast.Instant.from_seq,
    "clockwork-wait":            ast.WaitLine.from_seq,
    "clockwork-select":          ast.SelectFrame.from_seq,
    "clockwork-if":              ast.IfFrame.from_seq,
    "clockwork-while":           ast.WhileFrame.from_seq,
}
AST_MAP.update({name: _passthrough for name in _PASS_THROUGH})


def validate_ast_map(grammar_dict):
    """RETURN: None. Raises ValueError if a grammar rule has no constructor.

    The load-time coverage guard, run alongside the LL(2) analysis. The shape
    correspondence (each node class derives from its rule's operator signal) is
    a standing test (TEST/test-ast-signals.py), not re-derived here.
    """
    missing = set(grammar_dict) - set(AST_MAP)
    if missing:
        raise ValueError("AST_MAP does not cover rules: %s"
                         % ", ".join(sorted(missing)))