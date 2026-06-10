"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

RULE-FILE ACTIONS  --  reduce builders, paired with the grammar in grammar.py.

The grammar itself (the GRAMMAR dict, the OR/PLUS/STAR combinators, the bare
tuple for sequence, and the bare list for optional) is defined in grammar.py, the
single source of truth for both the productions and their prose specification.
This module imports GRAMMAR from
there and supplies ACTIONS: the reduce builders that turn parse frames into AST
nodes.

ACTIONS maps each GRAMMAR rule name to a builder 'fn(frame) -> node', or None
for a pass-through rule (one that simply forwards its single matched value, as
the OR dispatch rules do). The parser engine zips GRAMMAR and ACTIONS by key.
______________________________________________________________________________
"""
from .grammar import GRAMMAR, t_kw_void, t_kw_container, t_re_id # noqa E401

# Keywords whose matched Token an action inspects (so the engine keeps them in
# the frame rather than dropping them as punctuation) are marked in the GRAMMAR
# dict itself, as '<captured:"X">' elements -- there is no separate set here.


# ---------------------------------------------------------------------------
# Reduce actions. Same keys as GRAMMAR. None == pass-through (forward the one
# matched value). Each fn takes a Frame and returns an ast node. Frame.values
# holds the matched child values with punctuation terminals dropped; Frame.begin
# is the construct's start offset. See parser_engine for the Frame contract.
# ---------------------------------------------------------------------------
from . import ast_nodes as ast
from .core.span_oracle import SpanResult


def _build_trigger(frame):
    """RETURN: Trigger, from the single matched token of <trigger>."""
    tok = frame.values[0]
    is_kw = tok.kind is not t_re_id
    return ast.Trigger(name=tok.text, is_keyword=is_kw, begin=tok.begin)


def _build_cause(frame):
    """RETURN: Cause | CauseRef, an inline trigger-cause or a cause reference.

    The <cause> rule is '<cause-ref> | (<trigger> ["&" <guard>])'. When the
    cause-ref branch matched, the frame carries the single already-built CauseRef
    and it is forwarded unchanged. Otherwise the frame is the trigger-cause:
    [Trigger] or [Trigger, Luau] when a guard followed '&'.
    """
    first = frame.values[0]
    if isinstance(first, ast.CauseRef):
        return first
    trigger = first
    guard   = frame.values[1] if len(frame.values) > 1 else None
    return ast.Cause(trigger=trigger, guard=guard, begin=trigger.begin)


def _build_cause_ref(frame):
    """RETURN: CauseRef, a reference to a defined cause: 'NAME(args)'.

    frame.values = [name_tok, [Arg, ...]] -- the identifier token and the
    arg-parens arg list (empty list for 'NAME()').
    """
    name_tok, args = frame.values[0], frame.values[1]
    return ast.CauseRef(name=name_tok.text, args=args, begin=name_tok.begin)


def _build_effect_ref(frame):
    """RETURN: EffectRef, a reference to a defined effect bundle: bare 'NAME'.

    frame.values = [name_tok] -- a single identifier (effect bundle names are not
    dotted, which is what keeps this distinguishable from an event-spec).
    """
    name_tok = frame.values[0]
    return ast.EffectRef(name=name_tok.text, begin=name_tok.begin)


def _build_cause_def(frame):
    """RETURN: CauseDef, a named parameterised cause definition.

    frame.values = [Signature, Cause]: the signature (name + params) before the
    'on:' signal, then the cause body after it ('cause:'/'on:' are silent
    keywords). The body is an inline Cause (a CauseRef in a definition body would
    be meaningless, and the grammar's <cause> there is parsed as one; pass-2
    rejects a ref body if one ever appears).
    """
    sig, body = frame.values[0], frame.values[1]
    name, params = sig
    return ast.CauseDef(name=name, params=params, body=body,
                        begin=frame.begin)


def _build_effect_def(frame):
    """RETURN: EffectDef, a named effect bundle definition.

    frame.values = [Signature, effect, effect, ...]: the signature (name +
    params) before the '=>' signals, then one-or-more effects from the PLUS over
    '=> <effect>' ('effect:' is a silent keyword, each '=>' a silent signal).
    """
    sig          = frame.values[0]
    name, params = sig
    effects      = list(frame.values[1:])
    return ast.EffectDef(name=name, params=params, effects=effects,
                         begin=frame.begin)


def _to_luau(span):
    """RETURN: Luau, the rule-language node wrapping an engine SpanResult.

    The engine yields a neutral core.span_oracle.SpanResult at an opaque-span
    position (it knows no language); the rule language turns it into its own
    ast.Luau here. SpanResult.mode is the Role this grammar attached to the
    opaque terminal, so it maps straight onto Luau.role. This single conversion
    is the seam between the language-agnostic engine and the Luau AST.
    """
    return ast.Luau(text=span.text, role=span.mode, begin=span.begin)


def _build_luau_guard(frame):
    """RETURN: Luau, the CONDITION span wrapped from the engine's span marker."""
    return _to_luau(frame.values[0])


def _build_bracket_guard(frame):
    """RETURN: Condition, the root of a '[ ... ]' bracket guard.

    frame.values = [expr]: the single top boolean expression between '[' and ']'
    ('[' and ']' are silent). Wrapping it in a Condition keeps the two guard
    forms (Luau span vs. bracket condition) type-distinguishable on Cause.guard.
    """
    expr = frame.values[0]
    return ast.Condition(expr=expr, begin=frame.begin)


def _build_bool_level(frame, op):
    """RETURN: BoolOp | <operand>, an 'and'/'or' level, collapsed when trivial.

    frame.values = [operand, operand, ...]: the terms at this precedence level
    (the silent 'and'/'or' separators are dropped from the frame). A single
    operand is forwarded unchanged so a BoolOp always holds two-or-more; two-or-
    more become one BoolOp carrying 'op'.
    """
    operands = list(frame.values)
    if len(operands) == 1:
        return operands[0]
    return ast.BoolOp(op=op, operands=operands, begin=operands[0].begin)


def _build_or_cond(frame):
    """RETURN: BoolOp('or') | operand. The 'or' precedence level (lowest)."""
    return _build_bool_level(frame, "or")


def _build_and_cond(frame):
    """RETURN: BoolOp('and') | operand. The 'and' precedence level."""
    return _build_bool_level(frame, "and")


def _build_not_cond(frame):
    """RETURN: Not | <cond-atom>, an optionally-negated atom.

    frame.values = [atom] when 'not' was absent (forwarded unchanged), or
    [atom] with the silent 'not' having been recorded; the keyword 'not' is a
    captured token, so its presence is what distinguishes the two. The grammar
    keeps 'not' as a bare (silent) keyword, so a present 'not' shows as the only
    way the atom is wrapped: the builder wraps iff the frame carries the marker.
    """
    # 'not' is a silent keyword; when present the frame still has just the atom,
    # so negation presence is signalled by a captured marker appended ahead of
    # the atom. Distinguish by count: [atom] -> plain; [marker, atom] -> negated.
    if len(frame.values) == 2:
        atom = frame.values[1]
        return ast.Not(operand=atom, begin=frame.begin)
    return frame.values[0]


def _build_comparison(frame):
    """RETURN: Comparison, '<evt-member> <op> <operand>'.

    frame.values = [EventMember, op_token, operand]: the left event-member, the
    comparison operator token (its '.text' is the verbatim op), and the right
    operand (EventMember or Literal).
    """
    left, op_tok, right = frame.values[0], frame.values[1], frame.values[2]
    return ast.Comparison(left=left, op=op_tok.text, right=right,
                          begin=left.begin)


def _build_evt_member(frame):
    """RETURN: EventMember, a leading-dot event member '.name'.

    frame.values = [name_tok]: the identifier after the silent '.'. The event is
    implicit (the trigger's); only the member name is recorded.
    """
    name_tok = frame.values[0]
    return ast.EventMember(name=name_tok.text, begin=name_tok.begin)


def _build_cond_operand(frame):
    """RETURN: EventMember | Literal, the right side of a comparison.

    frame.values = [value]: either an already-built EventMember (the '.name'
    branch) or a number/string token wrapped here as a Literal.
    """
    value = frame.values[0]
    if isinstance(value, ast.EventMember):
        return value
    return ast.Literal(text=value.text, begin=value.begin)


def _build_mutation(frame):
    """RETURN: Mutation, wrapping the STATEMENT_BLOCK span."""
    body = _to_luau(frame.values[0])
    return ast.Mutation(body=body, begin=body.begin)


def _build_causality(frame):
    """RETURN: Causality, from a cause and one-or-more effects.

    frame.values = [Cause, effect, effect, ...]; the PLUS over '=> <effect>'
    contributes each effect as a separate value. begin is the 'on' offset.
    """
    cause   = frame.values[0]
    effects = list(frame.values[1:])
    return ast.Causality(cause=cause, effects=effects, begin=frame.begin)


def _build_event_spec(frame):
    """RETURN: EventSpec, name plus argument list.

    frame.values = [name_str, [Arg, ...]].
    """
    name, args = frame.values[0], frame.values[1]
    return ast.EventSpec(name=name, args=args, begin=frame.begin)


def _build_mode_arming(frame):
    """RETURN: ModeArming, name plus argument list (the '+' is punctuation)."""
    name, args = frame.values[0], frame.values[1]
    return ast.ModeArming(name=name, args=args, begin=frame.begin)


def _build_report_string(frame):
    """RETURN: ReportString, from the matched STRING token."""
    tok = frame.values[0]
    return ast.ReportString(text=tok.text, begin=tok.begin)


def _build_arg_parens(frame):
    """RETURN: list, the Args inside the parens (empty when '()').

    frame.values is [] for '()' or [[Arg, ...]] when an arg-list matched.
    """
    if not frame.values:
        return []
    return frame.values[0]


def _build_arg_list(frame):
    """RETURN: list, the Args of an arg-list in order."""
    return list(frame.values)


def _build_arg(frame):
    """RETURN: Arg, one argument -- a bare-rvalue positional or 'name = value'.

    <arg> is '("<rvalue>", OR, (t_re_id, "=", "<rvalue>"))': a positional whose
    value is any rvalue, OR a named 'id = rvalue'. The choice needs 2-token
    lookahead -- an identifier alone is a positional rvalue, but 'identifier ='
    opens the named branch -- so this rule is the canonical LL(2) construct (the
    two branches share the identifier in their FIRST sets). Two frame shapes:
      - [rvalue]            POSITIONAL: the value is the rvalue (a number/string/
                            identifier LITERAL, a ShallowMemberAccess MEMBER, or a
                            Luau LUAU span); name is None.
      - [id_tok, rvalue]    NAMED: 'name' is the identifier text ('=' is silent),
                            'rvalue' the value, classified by _arg_from_value.
    """
    if len(frame.values) == 2:
        id_tok, rvalue = frame.values
        return _arg_from_value(rvalue, name=id_tok.text, begin=frame.begin)
    rvalue = frame.values[0]
    return _arg_from_value(rvalue, name=None, begin=frame.begin)


def _arg_from_value(value, name, begin):
    """RETURN: Arg, classifying 'value' into its E_ArgKind.

    'value' is one of: a ShallowMemberAccess (MEMBER), a SpanResult opaque span
    wrapped here into a Luau node (LUAU), a bare-identifier/number/string string
    OR a value-bearing Token carried as text (LITERAL). A Token is reduced to its
    '.text'. 'name' is the keyword-argument name or None.
    """
    if isinstance(value, ast.ShallowMemberAccess):
        return ast.Arg(name=name, value=value, kind=ast.E_ArgKind.MEMBER, begin=begin)
    if isinstance(value, SpanResult):
        return ast.Arg(name=name, value=_to_luau(value),
                       kind=ast.E_ArgKind.LUAU, begin=begin)
    text = value if isinstance(value, str) else value.text
    return ast.Arg(name=name, value=text, kind=ast.E_ArgKind.LITERAL, begin=begin)


def _build_shallow_member_access(frame):
    """RETURN: ShallowMemberAccess, 'binding.member'.

    frame.values = [binding_tok, member_tok]; the '.' is silent. 'binding_tok'
    is the captured binding keyword (event/sm/mg/mode), 'member_tok' the bare
    member name after the dot.
    """
    binding_tok, member_tok = frame.values
    return ast.ShallowMemberAccess(binding=binding_tok.text,
                                   member=member_tok.text, begin=frame.begin)


def _build_dotted_name(frame):
    """RETURN: list[str], the dotted name as its segment list ['A', 'B', 'C'].

    A bare name 'A' yields ['A']; 'A.B.C' yields ['A','B','C']. The list shape
    (not a joined 'A.B.C' string) keeps the segmentation that pass-2 needs --
    scope resolution walks segments -- without re-splitting a joined string, and
    removes the str/list ambiguity that forced _build_spawn to type-spot its
    trailing values.
    """
    return [tok.text for tok in frame.values]


def _build_arg_decl(frame):
    """RETURN: ArgDecl, one 'member: type'.

    frame.values = [name_colon_tok, type_tok]; the member name carries a glued
    trailing ':' (NAME_COLON), stripped here to recover the bare member name.
    """
    member_tok, type_tok = frame.values
    member = member_tok.text[:-1]          # strip the glued ':'
    return ast.ArgDecl(member=member, type=type_tok.text,
                       begin=member_tok.begin)


def _build_arg_decl_list(frame):
    """RETURN: list, the ArgDecls in order."""
    return list(frame.values)


def _build_decl_parens(frame):
    """RETURN: list, the ArgDecls inside the parens (empty when '()')."""
    if not frame.values:
        return []
    return frame.values[0]


def _build_init(frame):
    """RETURN: InitBlock, wrapping the STATEMENT_BLOCK body after 'init'."""
    body = frame.values[0]
    return ast.InitBlock(body=body, begin=body.begin)


def _build_deinit(frame):
    """RETURN: DeinitBlock, wrapping the STATEMENT_BLOCK body after 'deinit'."""
    body = frame.values[0]
    return ast.DeinitBlock(body=body, begin=body.begin)


def _build_default(frame):
    """RETURN: StateMachineModeRef, the 'default:' target.

    Rebinds the ref's begin to the construct start rather than the inner SM-name
    token. ('=' is retired; 'default:' is the connective.)
    """
    ref = frame.values[0]
    return ast.StateMachineModeRef(sm_name=ref.sm_name, mode_name=ref.mode_name,
                                   is_void=ref.is_void, begin=frame.begin)


def _build_sm_mode_ref(frame):
    """RETURN: StateMachineModeRef, 'SM.member' or 'SM.VOID'.

    frame.values = [sm_tok, member_tok]; member is the VOID keyword or an ID.
    """
    sm_tok, member_tok = frame.values
    is_void = member_tok.kind is t_kw_void
    return ast.StateMachineModeRef(sm_name=sm_tok.text, mode_name=member_tok.text,
                                   is_void=is_void, begin=sm_tok.begin)


def _split_members_and_untils(values):
    """
    RETURN: (members, untils), the leading member values and trailing Causes.

    A reactor/aggregate body is '<elm>+ ( until <cause> )+'. Every until cause
    reduces to a Cause; every member reduces to a Causality, InitBlock,
    DeinitBlock, StateMachineModeRef, State, Mode, or HasRef. The untils are
    exactly the trailing run of bare Cause nodes, so split at the first trailing
    Cause. A member's own nested untils live inside that member node, not here.
    """
    split = len(values)
    while split > 0 and isinstance(values[split - 1], ast.Cause):
        split -= 1
    return values[:split], values[split:]


def _members_slice(values):
    """
    RETURN: list, the member/until values after the <signature>.

    values[0] is the <signature> -- a (name, params) tuple, one slot -- so the
    members start at index 1 unconditionally (no params type-spotting needed).
    """
    return values[1:]


def _bases_and_members(values):
    """RETURN: (bases, members), splitting an aggregate body after the signature.

    values[1:] begins with zero-or-more 'is:' base names -- each a dotted-name
    list[str] from the STAR(('is:', <dotted-name>)) -- followed by the member
    nodes. Bases are the leading list values; members are the dataclass nodes
    after them. A base is a list and a member never is, so the boundary is the
    first non-list value.
    """
    rest = values[1:]
    bases = []
    i = 0
    while i < len(rest) and isinstance(rest[i], list):
        bases.append(rest[i])
        i += 1
    return bases, rest[i:]


def _name_and_params(frame):
    """RETURN: (name, params), unpacked from the <signature> at frame.values[0]."""
    return frame.values[0]


def _build_signature(frame):
    """RETURN: (name, params), a reactor/aggregate signature.

    frame.values = [dotted_name] or [dotted_name, [ArgDecl, ...]]; the
    round-bracket parameter list is optional ('()' or absent both give []).
    The single value a <signature> contributes to its parent frame, so a
    reactor/aggregate rule carries one signature slot, not a name plus a
    type-spotted optional params slot.
    """
    name   = frame.values[0]
    params = frame.values[1] if len(frame.values) > 1 else []
    return (name, params)


def _build_mode(frame):
    """RETURN: Mode, assembled from interleaved members and the until causes.

    Members are sorted by kind: Causality -> causalities, InitBlock -> init,
    DeinitBlock -> deinit. Duplicate init/deinit keeps the last (a validator
    concern, not a parse error).
    """
    name, params = _name_and_params(frame)
    members, untils = _split_members_and_untils(_members_slice(frame.values))
    init = deinit = None
    causalities = []
    for m in members:
        match m:
            case ast.InitBlock():   init = m.body
            case ast.DeinitBlock(): deinit = m.body
            case ast.Causality():   causalities.append(m)
    return ast.Mode(name=name, params=params, init=init, deinit=deinit,
                    causalities=causalities, untils=untils, begin=frame.begin)


def _build_state(frame):
    """RETURN: State, a state-machine member with its trailing until causes.

    Same shape as a mode: members ('<mode-elm>+') sorted by kind, then the
    trailing run of 'until' Causes (now optional -- possibly empty). The state's
    block is terminated structurally by the next state-machine element or 'end',
    not by a closer keyword.
    """
    name, params = _name_and_params(frame)
    members, untils = _split_members_and_untils(_members_slice(frame.values))
    init = deinit = None
    causalities = []
    for m in members:
        match m:
            case ast.InitBlock():   init = m.body
            case ast.DeinitBlock(): deinit = m.body
            case ast.Causality():   causalities.append(m)
    return ast.State(name=name, params=params, init=init, deinit=deinit,
                     causalities=causalities, untils=untils, begin=frame.begin)


def _build_member_ref(frame):
    """RETURN: HasRef, a bare or qualified member reference.

    frame.values = [name_tok] for a bare name, or [agg_tok, member_tok] for the
    qualified 'AGG.member' / 'AGG.VOID' form.
    """
    if len(frame.values) == 1:
        member_tok = frame.values[0]
        is_void = member_tok.kind is t_kw_void
        return ast.HasRef(aggregate=None, member=member_tok.text,
                          is_void=is_void, begin=member_tok.begin)
    agg_tok, member_tok = frame.values
    is_void = member_tok.kind is t_kw_void
    return ast.HasRef(aggregate=agg_tok.text, member=member_tok.text,
                      is_void=is_void, begin=agg_tok.begin)


def _build_has_ref(frame):
    """RETURN: HasRef, the 'has:' member, rebased to the 'has' keyword offset."""
    ref = frame.values[0]
    return ast.HasRef(aggregate=ref.aggregate, member=ref.member,
                      is_void=ref.is_void, begin=frame.begin)


def _build_declaration(frame):
    """RETURN: ForwardDecl, a '<name> [signature] is: <kind>' scope-level decl.

    frame.values = [name_tok, (signature?), kind_dict]; 'is:' is silent and the
    round-bracket signature is optional. 'signature' is the <decl-parens> list
    of ArgDecls when present, else []. 'kind_dict' comes from <type-ref>: keys
    'kind', 'cargs', 'luau_handle'. 'begin' is the name offset. Signature vs
    type-params, and the mandatory-on-spawnable-kinds rule: see SYNTAX_DOC in grammar.py.
    """
    name_tok  = frame.values[0]
    kind      = frame.values[-1]
    middle    = frame.values[1:-1]
    signature = middle[0] if (middle and isinstance(middle[0], list)) else []
    return ast.ForwardDecl(kind=kind["kind"], name=name_tok.text,
                           signature=signature,
                           cargs=kind["cargs"], luau_handle=kind["luau_handle"],
                           begin=name_tok.begin)


def _build_fwd_kind(frame):
    """RETURN: dict, the kind of a forward declaration: keys 'kind', 'cargs',
            'luau_handle'.

    A lone ID token is a static kind ('kind' = its text, no cargs, no handle).
    The 'container' form (KW_CONTAINER captured) gives frame.values =
    ['container', [Arg,...], maybe Luau]: 'cargs' the angle-bracket type-params
    (ordinary <arg>s), 'luau_handle' the optional 'as:' LVALUE span. See
    SYNTAX_DOC in grammar.py, <type-ref>.
    """
    head = frame.values[0]
    if getattr(head, "kind", None) is t_kw_container:
        cargs    = next((v for v in frame.values[1:] if isinstance(v, list)), [])
        span     = next((v for v in frame.values[1:] if isinstance(v, SpanResult)),
                        None)
        luau_handle = _to_luau(span) if span is not None else None
        return {"kind": "container", "cargs": cargs, "luau_handle": luau_handle}
    # static kind: a bare ID token whose text names the kind
    return {"kind": head.text, "cargs": [], "luau_handle": None}


def _build_state_machine(frame):
    """RETURN: StateMachine, assembled from its member elements.

    Members are sorted by kind: State -> states, HasRef -> has_refs,
    StateMachineModeRef -> default, InitBlock/DeinitBlock -> init/deinit.
    Duplicate default/init/deinit keeps the last (a validator concern). The
    closing 'end' is silent, so every sliced value is a member.
    """
    name, params = _name_and_params(frame)
    bases, members = _bases_and_members(frame.values)
    init = deinit = default = None
    states, has_refs = [], []
    for m in members:
        match m:
            case ast.InitBlock():           init = m.body
            case ast.DeinitBlock():         deinit = m.body
            case ast.StateMachineModeRef(): default = m
            case ast.State():               states.append(m)
            case ast.HasRef():              has_refs.append(m)
    return ast.StateMachine(name=name, params=params, bases=bases, states=states,
                            has_refs=has_refs, default=default, init=init,
                            deinit=deinit, begin=frame.begin)


def _build_mode_group(frame):
    """RETURN: ModeGroup, assembled from its member elements.

    Members are sorted by kind: Mode -> modes, HasRef -> has_refs,
    InitBlock/DeinitBlock -> init/deinit. A mode group has no 'default'. The
    closing 'end' is silent, so every sliced value is a member.
    """
    name, params = _name_and_params(frame)
    bases, members = _bases_and_members(frame.values)
    init = deinit = None
    modes, has_refs = [], []
    for m in members:
        match m:
            case ast.InitBlock():   init = m.body
            case ast.DeinitBlock(): deinit = m.body
            case ast.Mode():        modes.append(m)
            case ast.HasRef():      has_refs.append(m)
    return ast.ModeGroup(name=name, params=params, bases=bases, modes=modes,
                         has_refs=has_refs, init=init, deinit=deinit,
                         begin=frame.begin)


def _build_spawn(frame):
    """RETURN: Spawn, an aggregate spawn '+! name (args) [ in: C [ as: {lv} ] ]'.

    frame.values are POSITIONAL (the '+!', 'in:', 'as:' punctuation is silent):

        [0] name          list[str]   the dotted aggregate name (always present)
        [1] args          list[Arg]   the arg list (always present: parens are
                                       mandatory, '()' giving [])
        [2] in_container  list[str]   the 'in:' container dotted-name  -- optional
        [3] luau_handle   Luau        the 'as:' lvalue span            -- optional

    Positional, not type-spotted: since <dotted-name> now reduces to a list (the
    same Python type as the arg list), the old 'the str is the container, the
    list is the args' discrimination is no longer possible -- and was fragile
    regardless. The grammar reaches 'as:' only inside 'in:', so a luau_handle
    cannot appear without an in_container; the trailing shapes are therefore
    exactly [], [C], or [C, lv], and a trailing Luau (when present) is always the
    last value.
    """
    values       = frame.values
    name         = values[0]
    args         = values[1]
    rest         = values[2:]
    span         = rest[-1] if rest and isinstance(rest[-1], SpanResult) else None
    luau_handle  = _to_luau(span) if span is not None else None
    in_container = None
    for v in rest:
        if not isinstance(v, SpanResult):
            in_container = v
            break
    return ast.Spawn(name=name, args=args, has_parens=True,
                     in_container=in_container, luau_handle=luau_handle,
                     begin=frame.begin)


def _build_unspawn(frame):
    """RETURN: Unspawn, an aggregate removal '-! name'.

    frame.values = [name]. The '-!' is punctuation. The name is a dotted-name
    reference to a spawned aggregate; validity is a pass-2 concern.
    """
    return ast.Unspawn(name=frame.values[0], begin=frame.begin)


def _build_event_def(frame):
    """RETURN: EventDef, name plus parameter declarations.

    frame.values = [name_tok, [ArgDecl, ...]].
    """
    name_tok, params = frame.values
    return ast.EventDef(name=name_tok.text, params=params, begin=frame.begin)


def _build_clock_def(frame):
    """RETURN: ClockDef, event name plus period literal.

    frame.values = [name_tok, period_tok].
    """
    name_tok, period_tok = frame.values
    return ast.ClockDef(name=name_tok.text, period=period_tok.text,
                        begin=frame.begin)


def _build_namespace(frame):
    """RETURN: Namespace, the opened dotted path plus its nested items.

    frame.values = [dotted_name, item, item, ...]. The 'open' and 'close' are
    silent punctuation; each <top-level> item in the body contributes one value.
    """
    name  = frame.values[0]
    items = list(frame.values[1:])
    return ast.Namespace(name=name, items=items, begin=frame.begin)


def _build_include(frame):
    """RETURN: Include, the mounted file name and its target path.

    frame.values = [string_tok, dotted_name]. 'include:' and 'into:' are silent.
    Surrounding quotes are stripped from the filename lexeme.
    """
    string_tok = frame.values[0]
    mount       = frame.values[1]
    filename    = string_tok.text
    if len(filename) >= 2 and filename[0] in "\"'" and filename[-1] == filename[0]:
        filename = filename[1:-1]
    return ast.Include(filename=filename, mount=mount, begin=frame.begin)


ACTIONS = {
    "top-level":         None,
    "namespace":         _build_namespace,
    "include":           _build_include,
    "causality":         _build_causality,
    "cause":             _build_cause,
    "cause-ref":         _build_cause_ref,
    "cause-def":         _build_cause_def,
    "effect-def":        _build_effect_def,
    "effect-ref":        _build_effect_ref,
    "trigger":           _build_trigger,
    "guard":             None,
    "luau-guard":        _build_luau_guard,
    "bracket-guard":     _build_bracket_guard,
    "or-cond":           _build_or_cond,
    "and-cond":          _build_and_cond,
    "not-cond":          _build_not_cond,
    "cond-atom":         None,
    "paren-cond":        None,
    "comparison":        _build_comparison,
    "evt-member":        _build_evt_member,
    "cmp-op":            None,
    "cond-operand":      _build_cond_operand,
    "effect":            None,
    "mutation":          _build_mutation,
    "spawn":             _build_spawn,
    "unspawn":           _build_unspawn,
    "event-spec":        _build_event_spec,
    "mode-arming":       _build_mode_arming,
    "report-string":     _build_report_string,
    "arg-parens":        _build_arg_parens,
    "arg-list":          _build_arg_list,
    "arg":               _build_arg,
    "rvalue":            None,
    "shallow-member-access": _build_shallow_member_access,
    "binding":           None,
    "mode":              _build_mode,
    "mode-elm":          None,
    "init":              _build_init,
    "deinit":            _build_deinit,
    "state":             _build_state,
    "has-ref":           _build_has_ref,
    "declaration":      _build_declaration,
    "type-ref":          _build_fwd_kind,
    "member-ref":        _build_member_ref,
    "mode-group":        _build_mode_group,
    "mode-group-elm":    None,
    "state-machine":     _build_state_machine,
    "state-machine-elm": None,
    "default":           _build_default,
    "sm-mode-ref":       _build_sm_mode_ref,
    "event-def":         _build_event_def,
    "clock-def":         _build_clock_def,
    "decl-parens":       _build_decl_parens,
    "arg-decl-list":     _build_arg_decl_list,
    "arg-decl":          _build_arg_decl,
    "dotted-name":       _build_dotted_name,
    "signature":         _build_signature,
}


