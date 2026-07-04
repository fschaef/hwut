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
operator node: their factory receives the raw leaf (OpaqueTerminal / Token) itself.

validate_ast_map() is the load-time coverage guard (every grammar rule mapped);
the shape correspondence (a SEQ rule's node IS SEQ_Interface, ...) is asserted
by TEST/test-ast-signals.py.
______________________________________________________________________________
"""
from ..core.parser_generator.cst_nodes      import OR_Node, SEQ_Node, PLUS_Node, STAR_Node
from ..core.parser_generator.ast_map_family import OrMap, OptMap, PASS
from . import ast_nodes as ast


# ---------------------------------------------------------------------------
# Plain-value rule factories (no node class to host them).
# ---------------------------------------------------------------------------
def _name_dotted(node):
    """RETURN: Name, the dotted name as the <name-dotted> rule's product (A-11).

    children = (head_tok, STAR(('.', tok))): each repetition item is the
    anonymous one-survivor SEQ around the next segment token ('.' silent). The
    segments stay SEGMENTED (not joined) so pass-2 walks them without re-
    splitting; they live as the Name's field, never returned as a bare list (a
    name rule yields a NAME, not the name's debris). The reference-vs-declaration
    VIEW is the consumer's, applied via _ref / _decl.
    """
    head = node.children[0]
    segments = tuple([head.text] + [s.children[0].text for s in node.children[1].items])
    return ast.Name(segments=segments, begin=head.begin)


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


# An optional ['by:', LVALUE] binding read off a child OPT_Node: PRESENT -> the
# one-survivor SEQ around the LVALUE span ('by:' silent), wrapped into an
# OpaqueLeaf; ABSENT -> None (fixed, A-13). An OptMap helper (D-19) reused off a
# rule entry.
_opt_by = OptMap(lambda seq: ast.OpaqueLeaf.from_span(seq.children[0]))


# ---------------------------------------------------------------------------
# Kind factories (D-21, A-11): the grammar shares ONE head across the kinds;
# each kind rule yields a TYPED KIND-NODE (its product), and Declaration.from_seq
# carries it opaque -- the fan-out on the kind-node's TYPE is the semantic layer's
# (declare), not here. No 'kind' string, no dict, no match-on-string discriminator.
# ---------------------------------------------------------------------------
def _kind_reactor(node):
    """RETURN: ReactorKind, the matched reactor keyword as its product.

    The rule is the OR of the five captured kind keywords; the matched token's
    text is the keyword.
    """
    return ast.ReactorKind(keyword=node.child.text)


def _kind_dict(node):
    """RETURN: DictKind, a dict-container kind product.

    children = (type_dict, opt_by): the type slot the already-reduced DictType;
    'by' the optional storage accessor (an LVALUE opaque span) per _opt_by,
    hoisted to declaration level so a nested 'dict<...>' type stays by:-free.
    """
    return ast.DictKind(dtype=node.children[0], by=_opt_by(node.children[1]))


def _kind_list(node):
    """RETURN: ListKind, a list-container kind product.

    children = (type_list, opt_by): the type slot the already-reduced ListType;
    'by' per _opt_by (declaration-level, as for _kind_dict).
    """
    return ast.ListKind(dtype=node.children[0], by=_opt_by(node.children[1]))


def _kind_variable(node):
    """RETURN: VariableKind, a variable kind product.

    children = (type_or, args, opt_by): the type slot the inline OR (built-in
    keyword | struct/class id) whose child is the token either way; 'args' the
    already-reduced mandatory initialiser list.
    """
    return ast.VariableKind(type_name=node.children[0].child.text,
                            args=node.children[1], by=_opt_by(node.children[2]))


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
    trigger = ast.Trigger(name=ast._ref([tok.text], tok.begin), is_keyword=True, begin=tok.begin)
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
        return ast.CauseRef(name=ast._ref(name, node.begin), args=opt_parens.child, guard=guard,
                            begin=node.begin)
    trigger = ast.Trigger(name=ast._ref(name, node.begin), is_keyword=False, begin=node.begin)
    return ast.Cause(trigger=trigger, guard=guard, begin=node.begin)


def _effect_named(node):
    """RETURN: EventSpec | EffectRef, '<name-dotted> [parens]'.

    children = (name, opt_parens). The parens decide (D-26): present -> an
    event emission (EventSpec); absent -> an effect-bundle reference
    (EffectRef).
    """
    name, opt_parens = node.children
    if opt_parens.present:
        return ast.EventSpec(name=ast._ref(name, node.begin), args=opt_parens.child, begin=node.begin)
    return ast.EffectRef(name=ast._ref(name, node.begin), begin=node.begin)


# ---------------------------------------------------------------------------
# Condition terms: the bare boolean stands (D-26).
# ---------------------------------------------------------------------------
def _left_fold(node):
    """RETURN: LeftFolding | operand, a left-associative operator level (D-13).

    children = (head, STAR((op, operand))): the head operand, then the
    repetition. An empty repetition forwards the bare head (a level with no
    operator collapses to its operand); otherwise the head and the STAR_Node are
    MOUNTED into a LeftFolding -- the star is not unrolled, it is carried whole,
    and LeftFolding's type states the left grouping. Shared by every binary
    ladder rule (cond-or/-xor/-and, alg-shift/-add/-mul).
    """
    head, star = node.children
    if not star.items:
        return head
    return ast.LeftFolding(head=head, star=star, begin=node.begin)


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
    operand reference (now a ReferenceLeaf from _operand) becomes a BoolRef
    ('== true' in meaning, F-5), anything else (a ConstantLeaf, a nested
    expression) forwards unchanged.
    """
    left, opt_tail = node.children
    if opt_tail.present:
        op_tok, right = opt_tail.child.children
        return ast.Comparison(left=left, op=op_tok.text, right=right,
                              begin=node.begin)
    if isinstance(left, ast.ReferenceLeaf):
        return ast.BoolRef(name=left, begin=node.begin)
    return left



def _const(kind):
    """RETURN: callable, a tok -> ConstantLeaf builder that bakes in 'kind'.

    The returned function takes the matched token and produces a ConstantLeaf of
    the given E_ConstantKind, reading the verbatim text and source offset. Used
    to route each literal terminal (by role/arm) to its kind without a per-kind
    function; the kind rides from the terminal that matched.
    """
    return lambda tok: ast.ConstantLeaf.from_text(tok.text, kind, tok.begin)


def _operand(node):
    """RETURN: ReferenceLeaf | MethodCall, a base reference with postfixes (D-13, D-23).

    children = (receiver_tok, opt_call, STAR(<postfix>)): each postfix is ('.',
    member, opt_parens). A leading 'opt_call' present means the receiver is
    itself CALLED ('sqrt(x)', 'min(a,b)') -- a free-function call, built as a
    MethodCall with receiver=None and method=the receiver name. Bare members
    ('.field') extend the current name-segment list; a '.member(args)' postfix
    becomes a MethodCall whose receiver is everything accumulated so far, after
    which further postfixes chain on that call. With NO call and NO method
    postfix the accumulated segment list is a bare reference -- an operand is a
    PURE READ context (never an introduction), so it reduces to a ReferenceLeaf
    at the operand's begin (= recv.begin; the operand rule has no leading marker,
    so this is also node.begin). Consumers thus always receive a NODE -- no
    isinstance(list) sniff. The math-function catalogue (which free names are
    valid) is a pass-2 concern; the grammar admits any 'name(args)'.
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
    if is_list:
        # Bare reference: wrap the segments into a ReferenceLeaf at the operand's
        # begin. The operand never declares, so the leaf is always a reference.
        return ast._ref(value, recv.begin)
    return value


def _assign_rhs(node):
    """RETURN: AssignRhs, a 'gets: <algebr>' right-hand side product (A-11).

    children = (expr,): 'gets:' silent. Wrapping the bare expression in a typed
    product makes the <name-step> arm distinguishable by TYPE, retiring the
    isinstance(list) sum-sniff in _clockwork_name_step.
    """
    return ast.AssignRhs(expr=node.children[0])


def _clockwork_name_step(node):
    """RETURN: EventSpec | Assign | Recip, a name-led clockwork step (D-13).

    children = (name, tail): the tail is the left-factored dispatch on the token
    after the shared <name-dotted>, now distinguished purely BY TYPE (A-11) --
    an AssignRhs -> an Assign; a Recip partial -> a Recip with the lvalue filled
    in; otherwise the parens-arg list -> a paced EventSpec emission.
    """
    name, or_node = node.children
    tail = or_node.child
    if isinstance(tail, ast.Recip):
        return ast.Recip(lvalue=ast._ref(name, node.begin), operand=tail.operand,
                         else_body=tail.else_body, begin=node.begin)
    if isinstance(tail, ast.AssignRhs):
        return ast.Assign(lvalue=ast._ref(name, node.begin), rhs=tail.expr, begin=node.begin)
    return ast.EventSpec(name=ast._ref(name, node.begin), args=tail, begin=node.begin)


# ---------------------------------------------------------------------------
# Pass-through: forward the single matched value (no dedicated node).
# ---------------------------------------------------------------------------
_PASS_THROUGH = (
    "top-level", "cause", "cond", "cond/atom", "cond/bracket",
    "algebr/paren", "cond/op-cmp", "cond/op-or", "cond/op-xor", "cond/op-and",
    "algebr/op-shift", "algebr/op-add", "algebr/op-mul",
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
    "signature":             ast.Signature.from_seq,
    "list-arg":              _head_and_rest,
    "list-decl-arg":         _head_and_rest,
    "parens-arg":            _parens,
    "parens-decl":           _parens,
    "ref-member":            ast.RefMember.from_seq,

    # kind family + declaration dispatch (D-21)
    "declaration/reactor":   _kind_reactor,
    "declaration/struct":    lambda node: ast.StructKind(),
    "declaration/dict":      _kind_dict,
    "declaration/list":      _kind_list,
    "declaration/variable":  _kind_variable,
    # type (D-13): a built-in scalar word (branch 0, forwarded as its token
    # text) or a named-type id (role "type", its text) resolve to the type word;
    # a nested dict<...> / list<...> (branches 1, 2) forward the already-reduced
    # type node. OrMap routes by branch index and by role -- the named-id branch
    # keyed by role so its position can shift without touching this entry.
    "type":                  OrMap({("built_in", "type"): lambda v: v.text,
                                    ("dict", "list"):     PASS}),
    "type-dict":             ast.DictType.from_seq,
    "type-list":             ast.ListType.from_seq,
    "declaration":           ast.Declaration.from_seq,

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
    # alg-atom (D-13): paren-algebra (0), bridge (1), <number> (2), operand (7)
    # forward unchanged; an opaque expr span (6) -> OpaqueLeaf; string (3) and
    # true/false (4,5) -> ConstantLeaf. <number> (2) is its own rule that already
    # built a ConstantLeaf, so it just passes through here.
    "algebr/atom":           OrMap({("paren", "bridge", "number", "operand"): PASS,
                                    "opaque": ast.OpaqueLeaf.from_span,
                                    "string": _const(ast.E_ConstantKind.STRING),
                                    ("true", "false"): _const(ast.E_ConstantKind.BOOL)}),
    "number":                OrMap({"float": _const(ast.E_ConstantKind.FLOAT),
                                    "int":   _const(ast.E_ConstantKind.INT)}),
    "algebr/operand":        _operand,
    "algebr/postfix":        _raw,
    "algebr/bridge":         ast.Bridge.from_seq,

    # node rules (constructors on the classes)
    "namespace":             ast.Namespace.from_seq,
    "import":                ast.Import.from_seq,
    "causality":             ast.Causality.from_seq,
    "do-sweep":              ast.DoSweep.from_seq,
    "code-block":            OrMap({"opaque": ast.OpaqueLeaf.from_span, "one-sweep": PASS}),
    "def-cause":             ast.CauseDef.from_seq,
    "def-effect":            ast.EffectDef.from_seq,
    "guard":                 ast.Condition.from_seq,
    "mutation":              ast.Mutation.from_block,
    "step/spawn":            ast.Spawn.from_seq,
    "step/spawn/into":       _raw,
    "unspawn":               ast.Unspawn.from_seq,
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
    "step/recip-rhs":            ast.Recip.from_seq,
    "step/assign-rhs":           _assign_rhs,
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
    OPT rule. A SEQ/STAR/PLUS rule takes a single plain factory (no router). A
    bare-terminal rule needs no factory (a Token is the value); a plain callable
    that transforms the Token is allowed, a router is
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
    A router (OrMap/OptMap) carries a '.shape'; it must sit on a rule of that
    shape. A plain callable is accepted on any shape (SEQ/STAR/PLUS hand it the
    node; FORWARD/TERMINAL hand it the forwarded value / Token). An OrMap is
    additionally checked: its branch addresses must be valid for the OR (int in
    range, role actually tagged on a branch) and cover every branch.
    """
    from ..core.parser_generator.ast_map_family import OrMap, OptMap
    from ..core.parser_generator.ll2_grammar_spec import (rule_shape)
    violations = []
    routers = (OrMap, OptMap)
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
    from ..core.parser_generator.ll2_grammar_spec import Tagged_Spec, OR_Spec
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
