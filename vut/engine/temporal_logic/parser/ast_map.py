"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

RULE-FILE AST MAP  --  rule name -> constructor.

The engine builds the canonical CST (core.cst_nodes) by default; this map is the
partial overlay (D-5) naming, for each rule, the CONSTRUCTOR that turns its
finished CST node into the typed value. Construction lives where it belongs:

  - a rule producing an AST NODE maps to a classmethod ON that node's class
    (ast_nodes): Comparison.from_seq, Trigger.from_or, ... -- one factory per
    class where one suffices, a named factory (HasRef.from_member_ref /
    from_has_kw) where one class serves several rules;
  - a rule producing a PLAIN VALUE (a dotted-name segment list, a signature
    tuple, an arg list, the type-ref kind dict) maps to a small function HERE --
    there is no node class to host it;
  - a PASS-THROUGH rule (an OR dispatch forwarding its single child) maps to
    _passthrough -- it builds nothing.

Every constructor receives the rule's finished CST node -- children already
transformed, bottom-up -- and reads its structure DIRECTLY: SEQ children by
stable slot, OR branches by triggered_index, repetitions off their STAR/PLUS
slot, optionals as OR_Nodes whose presence is a state on the node. The old dense
-frame idiom (and with it the count-sniffing, the trailing-run splits, and the
type-spotting boundary scans) is gone: the CST slots carry the structure those
reconstructed.

Single-terminal rules (<luau-guard>, <mutation>, <report-string>) have no
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
def _dotted_name(node):
    """RETURN: list[str], the dotted name as its segment list ['A', 'B', 'C'].

    children = (head_tok, STAR(('.', tok))): each repetition item is the
    anonymous one-survivor SEQ around the next segment token ('.' is silent).
    The list shape (not a joined string) keeps the segmentation pass-2 walks.
    """
    head = node.children[0]
    return [head.text] + [s.children[0].text for s in node.children[1].items]


def _signature(node):
    """RETURN: (name, params), a reactor/aggregate signature.

    children = (dotted_name, opt_params): the optional round-bracket parameter
    list is an OR_Node at a stable slot; absent and '()' both give []. One
    signature value per rule slot, so no parent ever type-spots params.
    """
    opt = node.children[1]
    params = opt.child if opt.triggered_index == 0 else []
    return (node.children[0], params)


def _head_and_rest(node):
    """RETURN: list, '(X, STAR((sep, X)))' collapsed to [X, X, ...].

    The shared shape of <arg-list> and <arg-decl-list>: a head value, then a
    repetition whose items are anonymous one-survivor SEQs (separator silent).
    """
    return [node.children[0]] + [s.children[0] for s in node.children[1].items]


def _parens(node):
    """RETURN: list, the values inside '( ... )' (empty for '()').

    The shared shape of <arg-parens> and <decl-parens>: parens silent, so the
    single child is the optional inner list -- an OR_Node whose present child is
    the already-reduced list.
    """
    opt = node.children[0]
    return opt.child if opt.triggered_index == 0 else []


def _fwd_kind(node):
    """RETURN: dict, a forward declaration's kind: 'kind'/'cargs'/'luau_handle'.

    <type-ref> is an OR: branches 0 (bare ID) and 1 (the 'mode' keyword) are a
    static kind named by the token text. Branch 2 is the container form -- the
    anonymous SEQ (container_tok, '<', opt_cargs, '>', opt_as): the angle-bracket
    type-params and the 'as:' LVALUE handle are stable optional slots ('<'/'>'
    are captured, so they occupy slots of their own).
    """
    if node.triggered_index in (0, 1):
        tok = node.child
        return {"kind": tok.text, "cargs": [], "luau_handle": None}
    seq      = node.child
    opt_args = seq.children[2]
    opt_as   = seq.children[4]
    cargs    = opt_args.child if opt_args.triggered_index == 0 else []
    if opt_as.triggered_index == 0:
        span        = opt_as.child.children[0]
        luau_handle = ast.Luau.from_span(span)
    else:
        luau_handle = None
    return {"kind": "container", "cargs": cargs, "luau_handle": luau_handle}


# ---------------------------------------------------------------------------
# Pass-through: forward the single matched value (no dedicated node).
# ---------------------------------------------------------------------------
_PASS_THROUGH = (
    "top-level", "guard", "cond-atom", "paren-cond", "cmp-op", "effect",
    "rvalue", "binding", "mode-elm", "mode-group-elm", "state-machine-elm",
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
    "dotted-name":           _dotted_name,
    "signature":             _signature,
    "arg-list":              _head_and_rest,
    "arg-decl-list":         _head_and_rest,
    "arg-parens":            _parens,
    "decl-parens":           _parens,
    "type-ref":              _fwd_kind,

    # node rules (constructors on the classes)
    "namespace":             ast.Namespace.from_seq,
    "include":               ast.Include.from_seq,
    "causality":             ast.Causality.from_seq,
    "cause":                 ast.Cause.from_or,
    "cause-ref":             ast.CauseRef.from_seq,
    "cause-def":             ast.CauseDef.from_seq,
    "effect-def":            ast.EffectDef.from_seq,
    "effect-ref":            ast.EffectRef.from_seq,
    "trigger":               ast.Trigger.from_or,
    "luau-guard":            ast.Luau.from_span,
    "bracket-guard":         ast.Condition.from_seq,
    "or-cond":               ast.BoolOp.from_or_cond,
    "and-cond":              ast.BoolOp.from_and_cond,
    "not-cond":              ast.Not.from_seq,
    "comparison":            ast.Comparison.from_seq,
    "evt-member":            ast.EventMember.from_seq,
    "cond-operand":          ast.Literal.from_or,
    "mutation":              ast.Mutation.from_span,
    "spawn":                 ast.Spawn.from_seq,
    "unspawn":               ast.Unspawn.from_seq,
    "event-spec":            ast.EventSpec.from_seq,
    "mode-arming":           ast.ModeArming.from_seq,
    "report-string":         ast.ReportString.from_token,
    "arg":                   ast.Arg.from_or,
    "shallow-member-access": ast.ShallowMemberAccess.from_seq,
    "mode":                  ast.Mode.from_seq,
    "init":                  ast.InitBlock.from_seq,
    "deinit":                ast.DeinitBlock.from_seq,
    "state":                 ast.State.from_seq,
    "has-ref":               ast.HasRef.from_has_kw,
    "member-ref":            ast.HasRef.from_member_ref,
    "declaration":           ast.ForwardDecl.from_seq,
    "mode-group":            ast.ModeGroup.from_seq,
    "state-machine":         ast.StateMachine.from_seq,
    "default":               ast.StateMachineModeRef.from_default,
    "sm-mode-ref":           ast.StateMachineModeRef.from_sm_mode_ref,
    "event-def":             ast.EventDef.from_seq,
    "clock-def":             ast.ClockDef.from_seq,
    "arg-decl":              ast.ArgDecl.from_seq,
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
