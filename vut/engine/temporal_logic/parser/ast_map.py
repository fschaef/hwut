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

Single-terminal rules (<mutation>, <report-string>) have no
operator node: their factory receives the raw leaf (SpanResult / Token) itself.

validate_ast_map() is the load-time coverage guard (every grammar rule mapped);
the shape correspondence (a SEQ rule's node IS SEQ_Interface, ...) is asserted
by TEST/test-ast-signals.py.
______________________________________________________________________________
"""
from vut.engine.temporal_logic.core.parser_generator.cst_nodes import OR_Node, SEQ_Node, PLUS_Node, STAR_Node
from . import ast_nodes as ast
from vut.engine.temporal_logic.core.parser_generator.ast_map_family import OrMap, OptMap, StarMap, PASS


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
    return (node.children[0], node.children[1].or_else([]))


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
    return node.children[0].or_else([])


def _ref_member(node):
    """RETURN: (list[str], bool), a <ref-member>: (segments, is_void).

    children = (name_dotted, opt_void): the optional ('.', VOID) is an
    OPT_Node at a stable slot; presence IS is_void ('.' silent, VOID captured
    but its text is constant). The pair is consumed by HasRef / DefaultRef,
    which rebase to their keyword offset.
    """
    return (node.children[0], node.children[1].present)


# An optional ['by:', LVALUE] binding read off a child OPT_Node: present -> the
# one-survivor SEQ around the LVALUE span ('by:' silent), wrapped into an
# OpaqueCode; absent -> None. An OptMap used as a helper (D-19) -- the same
# present/absent routing the family expresses, reused off a rule entry.
_opt_by = OptMap({True:  lambda seq: ast.OpaqueCode.from_span(seq.children[0]),
                  False: None})


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


def _kind_dict(node):
    """RETURN: dict, a dict-container kind: 'kind'/'dtype'/'by'.

    children = (type_dict, opt_by): the type slot is the already-reduced
    DictType; 'by' the optional storage accessor (an LVALUE opaque span) per
    _opt_by, hoisted to the declaration level so a nested 'dict<...>' type stays
    by:-free.
    """
    return {"kind": "dict", "dtype": node.children[0],
            "by": _opt_by(node.children[1])}


def _kind_list(node):
    """RETURN: dict, a list-container kind: 'kind'/'dtype'/'by'.

    children = (type_list, opt_by): the type slot is the already-reduced
    ListType; 'by' per _opt_by (declaration-level, as for _kind_dict).
    """
    return {"kind": "list", "dtype": node.children[0],
            "by": _opt_by(node.children[1])}



def _kind_variable(node):
    """RETURN: dict, a variable kind: 'kind'/'type'/'args'/'by'.

    children = (type_or, args, opt_by): the type slot is the inline OR
    (built-in keyword | struct/class id) whose child is the token either way;
    'args' is the already-reduced mandatory initialiser list.
    """
    return {"kind": "variable", "type": node.children[0].child.text,
            "args": node.children[1], "by": _opt_by(node.children[2])}


def _declaration(node):
    """RETURN: ReactorDecl | StructDecl | DictDecl | ListDecl | VariableDef.

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
        case "dict":
            return ast.DictDecl(name=name, dtype=kind["dtype"], by=kind["by"],
                                head_params=head_params, begin=begin)
        case "list":
            return ast.ListDecl(name=name, dtype=kind["dtype"], by=kind["by"],
                                head_params=head_params, begin=begin)
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
    """RETURN: Condition | None, an optional ['&', <guard>] slot's guard.

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



def _operand(node):
    """RETURN: list[str] | MethodCall, a base reference with postfixes (D-13, D-23).

    children = (receiver_tok, opt_call, STAR(<postfix>)): each postfix is ('.',
    member, opt_parens). A leading 'opt_call' present means the receiver is
    itself CALLED ('sqrt(x)', 'min(a,b)') -- a free-function call, built as a
    MethodCall with receiver=None and method=the receiver name. Bare members
    ('.field') extend the current name-segment list; a '.member(args)' postfix
    becomes a MethodCall whose receiver is everything accumulated so far, after
    which further postfixes chain on that call. With NO call and NO method
    postfix the result collapses to the segment list, so a bare reference stays
    list[str] and the BoolRef path is preserved. The math-function catalogue
    (which free names are valid) is a pass-2 concern; the grammar admits any
    'name(args)'.
    """
    recv = node.children[0]
    opt_call = node.children[1]
    if opt_call.present:
        value = ast.MethodCall(receiver=None, method=recv.text,
                               args=opt_call.child, begin=recv.begin)
        is_list = False
    else:
        value = [recv.text]          # accumulating name-segment list
        is_list = True               # True while 'value' is still a segment list
    for s in node.children[2].items:
        member_tok, opt_parens = s.children
        if opt_parens.present:
            args = opt_parens.child
            value = ast.MethodCall(receiver=value, method=member_tok.text,
                                   args=args, begin=recv.begin)
            is_list = False
        elif is_list:
            value.append(member_tok.text)
        else:
            # A bare member read on a call result ('d.first().name'): a postfix
            # carrying args=None to mark a field read rather than a call.
            value = ast.MethodCall(receiver=value, method=member_tok.text,
                                   args=None, begin=recv.begin)
    return value


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
    "top-level", "cause", "cond", "cond/atom", "cond/bracket",
    "algebr/paren", "cond/op-cmp", "cond/op-or", "cond/op-xor", "cond/op-and",
    "algebr/op-shift", "algebr/op-add", "algebr/op-mul", "step/assign-rhs",
    "effect", "declaration/decl", "type-built-in",
    "elm-mode", "elm-mode-group", "elm-state-machine",
    "elm-clockwork", "step",
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


def _raw(node):
    """RETURN: the CST node itself, unchanged -- for rules a parent reads
    structurally (e.g. <postfix>, whose children _operand walks directly)."""
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
    "declaration/reactor":   _kind_reactor,
    "declaration/struct":    _kind_struct,
    "declaration/dict":      _kind_dict,
    "declaration/list":      _kind_list,
    "declaration/variable":  _kind_variable,
    # type (D-13): a built-in scalar word (branch 0, forwarded as its token
    # text) or a named-type id (role "type", its text) resolve to the type word;
    # a nested dict<...> / list<...> (branches 1, 2) forward the already-reduced
    # type node. OrMap routes by branch index and by role -- the named-id branch
    # keyed by role so its position can shift without touching this entry.
    "type":                  OrMap({(0, "type"): lambda v: v.text,
                                    (1, 2): PASS}),
    "type-dict":             ast.DictType.from_seq,
    "type-list":             ast.ListType.from_seq,
    "declaration":           _declaration,

    # merged named tails (D-26): the input decides the class
    "cause-system":          _cause_system,
    "cause-named":           _cause_named,
    "effect-named":          _effect_named,

    # expression band (D-13): the two ladders, comparison, atom, bridge
    "cond/or":               _left_fold,
    "cond/xor":              _left_fold,
    "cond/and":              _left_fold,
    "cond/not":              _un_fold,
    "cond/comparison":       _comparison,
    "algebr":                ast.Expr.from_seq,
    "algebr/shift":          _left_fold,
    "algebr/add":            _left_fold,
    "algebr/mul":            _left_fold,
    "algebr/un":             _un_fold,
    # alg-atom (D-13): paren-algebra (0), bridge (1), operand (7) forward
    # unchanged; an opaque expr span (6) -> OpaqueCode; the literals (2..5) ->
    # Literal. OrMap collapses each group to one leaf -- the fan-out that was a
    # hand-written 'i in (...)' ladder.
    "algebr/atom":           OrMap({(0, 1, 7): PASS,
                                    6: ast.OpaqueCode.from_span,
                                    (2, 3, 4, 5): ast.Literal.from_token}),
    "algebr/operand":        _operand,
    "algebr/postfix":        _raw,
    "algebr/bridge":         ast.Bridge.from_seq,

    # node rules (constructors on the classes)
    "namespace":             ast.Namespace.from_seq,
    "import":                ast.Import.from_seq,
    "causality":             ast.Causality.from_seq,
    "do-sweep":              ast.DoSweep.from_seq,
    "code-block":            OrMap({0: ast.OpaqueCode.from_span, 1: PASS}),
    "def-cause":             ast.CauseDef.from_seq,
    "def-effect":            ast.EffectDef.from_seq,
    "guard":                 ast.Condition.from_seq,
    "mutation":              ast.Mutation.from_block,
    "step/spawn":            ast.Spawn.from_seq,
    "step/spawn/into":       _raw,
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
    "step/name-step":            _clockwork_name_step,
    "step/recip-rhs":            _recip_rhs,
    "step/incr":                 ast.Incr.from_seq,
    "step/decr":                 ast.Decr.from_seq,
    "step/instant":              ast.Instant.from_seq,
    "step/wait":                 ast.WaitLine.from_seq,
    "step/select":               ast.SelectFrame.from_seq,
    "step/if":                   ast.IfFrame.from_seq,
    "step/while":                ast.WhileFrame.from_seq,
}
AST_MAP.update({name: _passthrough for name in _PASS_THROUGH})


def validate_ast_map(grammar_dict):
    """RETURN: None. Raises ValueError if a grammar rule has no constructor.

    The load-time COVERAGE guard, run alongside the LL(2) analysis. Shape
    correspondence is a SECOND gate, validate_ast_map_shapes, run after compile
    (it needs the compiled rules to read each rule's shape).
    """
    missing = set(grammar_dict) - set(AST_MAP)
    if missing:
        raise ValueError("AST_MAP does not cover rules: %s"
                         % ", ".join(sorted(missing)))


class MapShapeError(Exception):
    """Raised when an AST_MAP entry's form does not fit its rule's shape (D-19).

    A router belongs only on its shape: an OrMap on an OR rule, an OptMap on an
    OPT rule, a StarMap on a STAR rule. A SEQ or PLUS rule takes a single plain
    factory (no router). A bare-terminal rule needs no factory (a Token is the
    value); a plain callable that transforms the Token is allowed, a router is
    not. Like the LL(2) and role gates, all violations are collected and raised
    together, each naming the rule, so one compile reports every mismatch. The
    gate inspects only the rule's OWN shape -- never what a factory produces,
    which is branch-dependent and opaque.
    """
    def __init__(self, violations):
        super().__init__("%d AST-map shape violation(s)" % len(violations))
        self.violations = violations


def validate_ast_map_shapes(grammar):
    """RETURN: None. Raises MapShapeError if any AST_MAP entry mismatches shape.

    'grammar' is the COMPILED Grammar (rule_shape needs the compiled patterns).
    A router (OrMap/OptMap/StarMap) carries a '.shape'; it must sit on a rule of
    that shape. A plain callable is accepted on any shape (SEQ/PLUS hand it the
    node; FORWARD/TERMINAL hand it the forwarded value / Token). An OrMap is
    additionally checked: its branch addresses must be valid for the OR (int in
    range, role actually tagged on a branch) and cover every branch.
    """
    from vut.engine.temporal_logic.core.parser_generator.ast_map_family import OrMap, OptMap, StarMap
    from vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec import (rule_shape, Tagged_Spec,
                                         SHAPE_OR, SHAPE_OPT, SHAPE_STAR)
    violations = []
    routers = (OrMap, OptMap, StarMap)
    for name, entry in AST_MAP.items():
        if name not in grammar.rules:
            continue
        shape = rule_shape(grammar.rules[name])
        if isinstance(entry, routers):
            if entry.shape != shape:
                violations.append(
                    "rule %r is %s but its entry is %s"
                    % (name, shape, type(entry).__name__))
                continue
            if isinstance(entry, OrMap):
                violations.extend(_check_or_addresses(name, entry, grammar))
        # a plain callable (or _passthrough) fits any shape -- no claim to check
    if violations:
        raise MapShapeError(sorted(set(violations)))


def _check_or_addresses(name, ormap, grammar):
    """RETURN: list[str], address violations of an OrMap against its OR rule.

    Every int address must index a real branch; every str address must be a role
    actually tagged on some branch; together the addresses must cover all
    branches (no branch left unrouted). Reads the rule's OR_Spec branches and
    their Tagged_Spec roles.
    """
    from vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec import Tagged_Spec, OR_Spec
    p = grammar.rules[name].pattern
    while isinstance(p, Tagged_Spec):
        p = p.body
    if not isinstance(p, OR_Spec):
        return ["rule %r OrMap but pattern is not an OR" % name]
    n = len(p.branches)
    roles = {b.role for b in p.branches if isinstance(b, Tagged_Spec)}
    out, covered = [], set()
    for addr in ormap.addresses():
        if isinstance(addr, int):
            if not (0 <= addr < n):
                out.append("rule %r: OrMap index %d out of range (0..%d)"
                           % (name, addr, n - 1))
            else:
                covered.add(addr)
        elif isinstance(addr, str):
            if addr not in roles:
                out.append("rule %r: OrMap role %r tags no branch" % (name, addr))
            else:
                for i, b in enumerate(p.branches):
                    if isinstance(b, Tagged_Spec) and b.role == addr:
                        covered.add(i)
        else:
            out.append("rule %r: OrMap address %r is neither int nor str"
                       % (name, addr))
    missing = set(range(n)) - covered
    if missing:
        out.append("rule %r: OrMap leaves branches unrouted: %s"
                   % (name, ", ".join(map(str, sorted(missing)))))
    return out
