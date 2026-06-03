"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

RULE-FILE GRAMMAR  --  declarative, mirrors SYNTAX section (A.1)

GRAMMAR maps each non-terminal name (in the SYNTAX file's '<...>' spelling) to
a pattern built from these elements:

    "literal"        a terminal, spelled exactly as in a rule file ('on', '=>',
                     '&'); resolved to its E_TokenId by the preprocessor.
    "<non-terminal>" a reference to another GRAMMAR rule.
    "#CLASS"         a character-class terminal that has no fixed spelling:
                     "#ID", "#NUMBER", "#STRING"; resolved to E_TokenId too.
    "{luau:ROLE}"    an opaque Luau span parsed under Role.ROLE.
    (OP, ...)        a combinator: SEQ, ALT, OPT, PLUS, STAR (this module).

ACTIONS maps the same names to a reduce function 'fn(frame) -> node', or None
for a pass-through rule (one that simply forwards its single matched value, as
the ALT dispatch rules do). The grammar block stays pure structure; the actions
live beside it under the same keys. The preprocessor zips the two.

The block reads line-for-line against SYNTAX (A.1). Keeping it perceivable in
one place is the point: this is the grammar, as data.
______________________________________________________________________________
"""
# Parse operators as plain identifiers (no enum). A grammar element is either a
# string (terminal literal, '#CLASS', '<non-terminal>', '{luau:ROLE}') or a
# tuple whose head is one of these. Distinct sentinel objects keep tuples
# self-describing in tracebacks.
class _Op:
    """A named grammar combinator marker. Identity-compared; prints its name."""
    def __init__(self, name): self.name = name
    def __repr__(self):       return self.name

SEQ  = _Op("SEQ")    # (SEQ, a, b, ...)   match a then b ...
ALT  = _Op("ALT")    # (ALT, a, b, ...)   match one branch, by FIRST set
OPT  = _Op("OPT")    # (OPT, x)           x zero or one time
PLUS = _Op("PLUS")   # (PLUS, x)          x one or more times
STAR = _Op("STAR")   # (STAR, x)          x zero or more times

# Character-class terminals (no fixed spelling) and the Luau-span marker prefix.
TOK_ID     = "#ID"
TOK_NUMBER = "#NUMBER"
TOK_STRING = "#STRING"

# Keywords whose matched Token an action inspects, so the engine must NOT drop
# them as punctuation: the trigger keywords (their identity is the trigger) and
# VOID (distinguishes a void state-machine mode-ref). Every other keyword and
# symbol is structural punctuation and is dropped from a frame's values.
CAPTURED_LITERALS = {"ANY", "BEGIN", "END", "VOID"}


GRAMMAR = {
    # <rule-file> is driven by the engine loop, not a rule; it repeats the
    # top-level alternation until end-of-file.
    "<top-level>":
        (ALT, "<namespace>", "<include>", "<causality>", "<mode>",
                 "<mode-group>", "<state-machine>", "<singleton-def>",
                 "<event-def>", "<clock-def>"),

    # <include>: 'include' <string> 'as' <dotted-name>
    # Mounts another file's namespace at <dotted-name> in THIS file. The
    # including file decides placement (Python-style); the included file is
    # placement-agnostic and lexically self-contained. The parser only RECORDS
    # the mount (filename + target path); resolving and mounting the file's
    # symbol table is a semantic-pass concern. FIRST(<include>) = {include},
    # disjoint from the other top-level starters.
    "<include>":
        (SEQ, "include", TOK_STRING, "as", "<dotted-name>"),

    # <namespace>: 'open' <dotted-name> <top-level>+ 'close'
    # Brackets the declarations it contains into a named scope. The dotted name
    # nests several levels at once ('open world.europe.berlin' rather than three
    # separate 'open's). The body is a recursive run of <top-level> items, so a
    # namespace may contain any declaration, including a nested 'open'/'close'.
    # FIRST(<namespace>) = {open}, disjoint from the other top-level starters,
    # and 'close' is never a <top-level> starter, so the run terminates
    # unambiguously at its matching 'close' (LL(1)).
    "<namespace>":
        (SEQ, "open", "<dotted-name>", (PLUS, "<top-level>"), "close"),

    # <causality>: 'on' <cause> ( '=>' <effect> )+
    # No closing token: each effect is introduced by '=>', so the effect loop
    # ends the moment the lookahead is not '=>'. The follower (a top-level
    # keyword, a mode/state element keyword, 'until', 'end', or EOF) is never
    # '=>', so the list is unambiguously self-delimiting (LL(1)).
    "<causality>":
        (SEQ, "on", "<cause>",
                 (PLUS, (SEQ, "=>", "<effect>"))),

    # <cause>: <trigger> [ '&' <guard> ]
    "<cause>":
        (SEQ, "<trigger>", (OPT, (SEQ, "&", "<guard>"))),

    # <trigger>: <event-name> | 'ANY' | 'END' | 'BEGIN'
    # 'switched' is NOT a general trigger; it appears only as the mandatory
    # 'until switched' closer of a <state> (see <state>).
    "<trigger>":
        (ALT, TOK_ID, "ANY", "END", "BEGIN"),

    # <guard>: '{' <luau-condition> '}'
    "<guard>":
        "{luau:CONDITION}",

    # <effect>: mutation | '+!' <spawn> | '-!' <unspawn> | '!' <mode-arming>
    #         | <report-string> | <event-spec>
    # Arming verbs: '!' arms a single mode, '+!' spawns an aggregate, '-!'
    # unspawns a named aggregate. All three are distinct single tokens, and
    # <event-spec> starts with an identifier, so the alternation is LL(1).
    "<effect>":
        (ALT, "<mutation>", "<spawn>", "<unspawn>", "<mode-arming>",
                 "<report-string>", "<event-spec>"),

    "<mutation>":
        "{luau:STATEMENT_BLOCK}",

    # <spawn>: '+!' <name> [ '(' [ <arg-list> ] ')' ] [ 'in' {luau:EXPRESSION} ]
    # Three forms, decided by shape (LL(1): '(' , 'in', and the effect-follower
    # are pairwise-distinct lookaheads):
    #   bare <name>            -> singleton re-init (no parens, no container)
    #   <name> '(' ... ')'     -> default-container spawn
    #   ... 'in' {luau-lvalue} -> container spawn (lvalue is opaque Luau)
    # Whether the parentheses are legal (singleton => forbidden) is a pass-2
    # check, not a grammar one; the grammar accepts both shapes.
    "<spawn>":
        (SEQ, "+!", "<dotted-name>", (OPT, "<arg-parens>"),
                 (OPT, (SEQ, "in", "{luau:EXPRESSION}"))),

    # <singleton-def>: 'singleton' ':' <name> [ '(' [ <arg-list> ] ')' ]
    # A top-level declaration fixing one instance of an aggregate type, named
    # and argument-bound here; spawned thereafter only by '+! <name>'.
    # FIRST = {singleton}, disjoint from the other top-level starters.
    "<singleton-def>":
        (SEQ, "singleton", ":", "<dotted-name>", (OPT, "<arg-parens>")),

    # <unspawn>: '-!' <name>
    # Ends an instance's existence. The operand is any reference-by-name (bare
    # or dotted); that it resolves to an existing instance is a pass-2 check --
    # the grammar accepts any <dotted-name>.
    "<unspawn>":
        (SEQ, "-!", "<dotted-name>"),

    # <event-spec>: <event-name> '(' [ <arg-list> ] ')'
    "<event-spec>":
        (SEQ, "<dotted-name>", "<arg-parens>"),

    # <mode-arming>: '!' <mode-name> '(' [ <arg-list> ] ')'
    "<mode-arming>":
        (SEQ, "!", "<dotted-name>", "<arg-parens>"),

    "<report-string>":
        TOK_STRING,

    # '(' [ <arg-list> ] ')'
    "<arg-parens>":
        (SEQ, "(", (OPT, "<arg-list>"), ")"),

    # <arg-list>: <arg> (',' <arg>)*
    "<arg-list>":
        (SEQ, "<arg>", (STAR, (SEQ, ",", "<arg>"))),

    # <arg>: [<member> '='] <rvalue>
    "<arg>":
        (SEQ, (OPT, (SEQ, TOK_ID, "=")), "<rvalue>"),

    # <rvalue>: <number> | <istring> | '{' <luau-expr> '}'
    "<rvalue>":
        (ALT, TOK_NUMBER, TOK_STRING, "{luau:EXPRESSION}"),

    # <mode>: 'mode' <name> [ '(' <arg-decl-list> ')' ] ':'
    #             <mode-elm>+ ( 'until' <cause> )+
    "<mode>":
        (SEQ, "mode", "<dotted-name>", (OPT, "<decl-parens>"), ":",
                 (PLUS, "<mode-elm>"),
                 (PLUS, (SEQ, "until", "<cause>"))),

    # <mode-elm>: <causality> | 'init' '{...}' | 'deinit' '{...}'
    "<mode-elm>":
        (ALT, "<causality>", "<init>", "<deinit>"),

    "<init>":
        (SEQ, "init", "{luau:STATEMENT_BLOCK}"),

    "<deinit>":
        (SEQ, "deinit", "{luau:STATEMENT_BLOCK}"),

    # <state>: 'state' <name> [ '(' <arg-decl-list> ')' ] ':'
    #              <mode-elm>+ <state-untils>
    # SYNTAX A.1 writes the closer as '( until <cause> )* until switched'. Both
    # alternatives start with 'until', so a flat repetition is not LL(1) and
    # would also greedily swallow the enclosing state-machine's own 'until'
    # closer. <state-untils> left-factors on 'until' and recurses on the right:
    # after 'until', one lookahead token chooses 'switched' (the terminator,
    # ending the run) or a <cause> (an explicit until, followed by more). This
    # is LL(1) and stops exactly at 'until switched', leaving the machine's
    # closing untils for the machine.
    "<state>":
        (SEQ, "state", "<dotted-name>", (OPT, "<decl-parens>"), ":",
                 (PLUS, "<mode-elm>"),
                 "<state-untils>"),

    # <state-untils>: 'until' ( 'switched' | <cause> <state-untils> )
    "<state-untils>":
        (SEQ, "until", (ALT, "switched", (SEQ, "<cause>", "<state-untils>"))),

    # <has-ref>: 'has' ':' <member-ref>   (pull in a member defined elsewhere)
    "<has-ref>":
        (SEQ, "has", ":", "<member-ref>"),

    # <member-ref>: <reactor-name> | <aggregate-name> '.' <reactor-name>
    #             | <aggregate-name> '.' 'VOID'   (a bare or qualified name)
    "<member-ref>":
        (SEQ, TOK_ID, (OPT, (SEQ, ".", (ALT, "VOID", TOK_ID)))),

    # <mode-group>: 'mode_group' <name> [ '(' <arg-decl-list> ')' ] ':'
    #                   <mode-group-elm>+ 'end'
    # Closed by 'end', not by its own 'until' causes. A member mode's own
    # ( 'until' <cause> )+ run is therefore followed by 'end' or the next
    # member keyword -- never by another 'until' that could belong to the group
    # -- so the inline-member boundary is decidable with one token (LL(1)).
    "<mode-group>":
        (SEQ, "mode_group", "<dotted-name>", (OPT, "<decl-parens>"), ":",
                 (PLUS, "<mode-group-elm>"),
                 "end"),

    # <mode-group-elm>: <mode> | <has-ref> | 'init' '{}' | 'deinit' '{}'
    "<mode-group-elm>":
        (ALT, "<mode>", "<has-ref>", "<init>", "<deinit>"),

    # <state-machine>: 'state_machine' <name> [ '(' <arg-decl-list> ')' ] ':'
    #                      <state-machine-elm>+ 'end'
    # Closed by 'end', not by 'until' causes. Each member state is self-
    # terminated by 'until switched', and the machine by 'end'.
    "<state-machine>":
        (SEQ, "state_machine", "<dotted-name>", (OPT, "<decl-parens>"),
                 ":",
                 (PLUS, "<state-machine-elm>"),
                 "end"),

    # <state-machine-elm>: <state> | <has-ref> | 'default' '=' <ref>
    #                    | 'init' '{}' | 'deinit' '{}'
    "<state-machine-elm>":
        (ALT, "<state>", "<has-ref>", "<default>", "<init>", "<deinit>"),

    "<default>":
        (SEQ, "default", "=", "<sm-mode-ref>"),

    # <sm-mode-ref>: <name> '.' <mode-name> | <name> '.' 'VOID'
    "<sm-mode-ref>":
        (SEQ, TOK_ID, ".", (ALT, "VOID", TOK_ID)),

    # <event-def>: 'event' <event-name> '(' <arg-decl-list> ')'
    "<event-def>":
        (SEQ, "event", TOK_ID, "<decl-parens>"),

    # <clock-def>: 'clock' <event-name> <number>
    "<clock-def>":
        (SEQ, "clock", TOK_ID, TOK_NUMBER),

    # '(' <arg-decl-list> ')'
    "<decl-parens>":
        (SEQ, "(", (OPT, "<arg-decl-list>"), ")"),

    # <arg-decl-list>: <arg-decl> (';' <arg-decl>)*
    "<arg-decl-list>":
        (SEQ, "<arg-decl>", (STAR, (SEQ, ";", "<arg-decl>"))),

    # <arg-decl>: <member> ':' <type>
    "<arg-decl>":
        (SEQ, TOK_ID, ":", TOK_ID),

    # <mode-name>: <name> '.' <identifier> | <identifier>   (dotted name)
    "<dotted-name>":
        (SEQ, TOK_ID, (STAR, (SEQ, ".", TOK_ID))),
}


# ---------------------------------------------------------------------------
# Reduce actions. Same keys as GRAMMAR. None == pass-through (forward the one
# matched value). Each fn takes a Frame and returns an ast node. Frame.values
# holds the matched child values with punctuation terminals dropped; Frame.begin
# is the construct's start offset. See parser_engine for the Frame contract.
# ---------------------------------------------------------------------------
from . import ast_nodes as ast
from ..luau.luau_fragment import Role


def _build_trigger(frame):
    """RETURN: Trigger, from the single matched token of <trigger>."""
    tok = frame.values[0]
    is_kw = tok.kind.name != "ID"
    return ast.Trigger(name=tok.text, is_keyword=is_kw, begin=tok.begin)


def _build_cause(frame):
    """RETURN: Cause, a trigger with optional guard.

    frame.values = [Trigger] or [Trigger, Luau] when a guard followed '&'.
    """
    trigger = frame.values[0]
    guard   = frame.values[1] if len(frame.values) > 1 else None
    return ast.Cause(trigger=trigger, guard=guard, begin=trigger.begin)


def _build_guard(frame):
    """RETURN: Luau, the CONDITION span value forwarded from the luau marker."""
    return frame.values[0]


def _build_mutation(frame):
    """RETURN: Mutation, wrapping the STATEMENT_BLOCK span."""
    body = frame.values[0]
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
    """RETURN: Arg, one '[member =] rvalue'.

    frame.values = [rvalue] or [member_tok, rvalue]. 'rvalue' is a Token
    (number/string literal) or a Luau node.
    """
    if len(frame.values) == 2:
        member_tok, rvalue = frame.values
        member = member_tok.text
    else:
        member = None
        rvalue = frame.values[0]
    is_luau = isinstance(rvalue, ast.Luau)
    value   = rvalue if is_luau else rvalue.text
    return ast.Arg(member=member, value=value, is_luau=is_luau, begin=frame.begin)


def _build_dotted_name(frame):
    """RETURN: str, the dotted name joined from its ID tokens."""
    return ".".join(tok.text for tok in frame.values)


def _build_arg_decl(frame):
    """RETURN: ArgDecl, one 'member : type'."""
    member_tok, type_tok = frame.values
    return ast.ArgDecl(member=member_tok.text, type=type_tok.text,
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
    """RETURN: StateMachineModeRef, the 'default =' target.

    Rebinds the ref's begin to the 'default' keyword offset so it matches the
    construct start rather than the inner SM-name token.
    """
    ref = frame.values[0]
    return ast.StateMachineModeRef(sm_name=ref.sm_name, mode_name=ref.mode_name,
                                   is_void=ref.is_void, begin=frame.begin)


def _build_sm_mode_ref(frame):
    """RETURN: StateMachineModeRef, 'SM.member' or 'SM.VOID'.

    frame.values = [sm_tok, member_tok]; member is the VOID keyword or an ID.
    """
    sm_tok, member_tok = frame.values
    is_void = member_tok.kind.name == "KW_VOID"
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
    RETURN: list, the member/until values after the name and optional params.

    values[0] is the dotted name. values[1] is the params list iff a
    decl-parens matched (a list); otherwise members start at index 1.
    """
    if len(values) > 1 and isinstance(values[1], list):
        return values[2:]
    return values[1:]


def _name_and_params(frame):
    """RETURN: (name, params), the dotted name and its parameter list (or [])."""
    name   = frame.values[0]
    params = frame.values[1] if (len(frame.values) > 1
                                 and isinstance(frame.values[1], list)) else []
    return name, params


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
        if isinstance(m, ast.InitBlock):
            init = m.body
        elif isinstance(m, ast.DeinitBlock):
            deinit = m.body
        elif isinstance(m, ast.Causality):
            causalities.append(m)
    return ast.Mode(name=name, params=params, init=init, deinit=deinit,
                    causalities=causalities, untils=untils, begin=frame.begin)


def _build_state_untils(frame):
    """
    RETURN: list, the explicit 'until' <cause> nodes of a state, in order.

    <state-untils> is 'until' ( 'switched' | <cause> <state-untils> ). The
    'switched' terminator is silent, so a frame either holds [] (just
    'until switched') or [Cause, [more causes...]] from the recursive tail.
    Flattens the head Cause and the tail list into one list.
    """
    if not frame.values:
        return []
    head = frame.values[0]
    tail = frame.values[1] if len(frame.values) > 1 else []
    return [head] + tail


def _build_state(frame):
    """RETURN: State, a state-machine member closed by 'until switched'.

    Same member sorting as a mode. The trailing value is the <state-untils>
    list: the optional preceding explicit 'until' causes (possibly empty); the
    mandatory 'until switched' closer is punctuation and carries no field.
    """
    name, params = _name_and_params(frame)
    rest = _members_slice(frame.values)
    untils = rest[-1] if rest and isinstance(rest[-1], list) else []
    members = rest[:-1] if rest and isinstance(rest[-1], list) else rest
    init = deinit = None
    causalities = []
    for m in members:
        if isinstance(m, ast.InitBlock):
            init = m.body
        elif isinstance(m, ast.DeinitBlock):
            deinit = m.body
        elif isinstance(m, ast.Causality):
            causalities.append(m)
    return ast.State(name=name, params=params, init=init, deinit=deinit,
                     causalities=causalities, untils=untils, begin=frame.begin)


def _build_member_ref(frame):
    """RETURN: HasRef, a bare or qualified member reference.

    frame.values = [name_tok] for a bare name, or [agg_tok, member_tok] for the
    qualified 'AGG.member' / 'AGG.VOID' form.
    """
    if len(frame.values) == 1:
        member_tok = frame.values[0]
        is_void = member_tok.kind.name == "KW_VOID"
        return ast.HasRef(aggregate=None, member=member_tok.text,
                          is_void=is_void, begin=member_tok.begin)
    agg_tok, member_tok = frame.values
    is_void = member_tok.kind.name == "KW_VOID"
    return ast.HasRef(aggregate=agg_tok.text, member=member_tok.text,
                      is_void=is_void, begin=agg_tok.begin)


def _build_has_ref(frame):
    """RETURN: HasRef, the 'has:' member, rebased to the 'has' keyword offset."""
    ref = frame.values[0]
    return ast.HasRef(aggregate=ref.aggregate, member=ref.member,
                      is_void=ref.is_void, begin=frame.begin)


def _build_state_machine(frame):
    """RETURN: StateMachine, assembled from its member elements.

    Members are sorted by kind: State -> states, HasRef -> has_refs,
    StateMachineModeRef -> default, InitBlock/DeinitBlock -> init/deinit.
    Duplicate default/init/deinit keeps the last (a validator concern). The
    closing 'end' is silent, so every sliced value is a member.
    """
    name, params = _name_and_params(frame)
    members = _members_slice(frame.values)
    init = deinit = default = None
    states, has_refs = [], []
    for m in members:
        if isinstance(m, ast.InitBlock):
            init = m.body
        elif isinstance(m, ast.DeinitBlock):
            deinit = m.body
        elif isinstance(m, ast.StateMachineModeRef):
            default = m
        elif isinstance(m, ast.State):
            states.append(m)
        elif isinstance(m, ast.HasRef):
            has_refs.append(m)
    return ast.StateMachine(name=name, params=params, states=states,
                            has_refs=has_refs, default=default, init=init,
                            deinit=deinit, begin=frame.begin)


def _build_mode_group(frame):
    """RETURN: ModeGroup, assembled from its member elements.

    Members are sorted by kind: Mode -> modes, HasRef -> has_refs,
    InitBlock/DeinitBlock -> init/deinit. A mode group has no 'default'. The
    closing 'end' is silent, so every sliced value is a member.
    """
    name, params = _name_and_params(frame)
    members = _members_slice(frame.values)
    init = deinit = None
    modes, has_refs = [], []
    for m in members:
        if isinstance(m, ast.InitBlock):
            init = m.body
        elif isinstance(m, ast.DeinitBlock):
            deinit = m.body
        elif isinstance(m, ast.Mode):
            modes.append(m)
        elif isinstance(m, ast.HasRef):
            has_refs.append(m)
    return ast.ModeGroup(name=name, params=params, modes=modes,
                         has_refs=has_refs, init=init, deinit=deinit,
                         begin=frame.begin)


def _build_spawn(frame):
    """RETURN: Spawn, an aggregate spawn '+! name [ (args) ] [ in {lvalue} ]'.

    frame.values is the dotted name, then 0..2 trailing values with silent
    punctuation ('+!', 'in') dropped: an arg list (a Python list) when the
    parentheses matched, and a Luau node when the 'in' container matched. The
    two are told apart by type, so either may be absent independently.
    """
    name       = frame.values[0]
    rest       = frame.values[1:]
    args       = next((v for v in rest if isinstance(v, list)), [])
    has_parens = any(isinstance(v, list) for v in rest)
    container  = next((v for v in rest if isinstance(v, ast.Luau)), None)
    return ast.Spawn(name=name, args=args, has_parens=has_parens,
                     container=container, begin=frame.begin)


def _build_singleton(frame):
    """RETURN: Singleton, a declaration 'singleton : name [ (args) ]'.

    frame.values = [name] or [name, [Arg, ...]] when the parentheses matched.
    The 'singleton' keyword and ':' are punctuation.
    """
    name = frame.values[0]
    args = frame.values[1] if (len(frame.values) > 1
                               and isinstance(frame.values[1], list)) else []
    return ast.Singleton(name=name, args=args, begin=frame.begin)


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

    frame.values = [string_tok, dotted_name]. 'include' and 'as' are silent.
    Surrounding quotes are stripped from the filename lexeme.
    """
    string_tok = frame.values[0]
    mount       = frame.values[1]
    filename    = string_tok.text
    if len(filename) >= 2 and filename[0] in "\"'" and filename[-1] == filename[0]:
        filename = filename[1:-1]
    return ast.Include(filename=filename, mount=mount, begin=frame.begin)


ACTIONS = {
    "<top-level>":         None,
    "<namespace>":         _build_namespace,
    "<include>":           _build_include,
    "<causality>":         _build_causality,
    "<cause>":             _build_cause,
    "<trigger>":           _build_trigger,
    "<guard>":             _build_guard,
    "<effect>":            None,
    "<mutation>":          _build_mutation,
    "<spawn>":             _build_spawn,
    "<singleton-def>":     _build_singleton,
    "<unspawn>":           _build_unspawn,
    "<event-spec>":        _build_event_spec,
    "<mode-arming>":       _build_mode_arming,
    "<report-string>":     _build_report_string,
    "<arg-parens>":        _build_arg_parens,
    "<arg-list>":          _build_arg_list,
    "<arg>":               _build_arg,
    "<rvalue>":            None,
    "<mode>":              _build_mode,
    "<mode-elm>":          None,
    "<init>":              _build_init,
    "<deinit>":            _build_deinit,
    "<state>":             _build_state,
    "<state-untils>":      _build_state_untils,
    "<has-ref>":           _build_has_ref,
    "<member-ref>":        _build_member_ref,
    "<mode-group>":        _build_mode_group,
    "<mode-group-elm>":    None,
    "<state-machine>":     _build_state_machine,
    "<state-machine-elm>": None,
    "<default>":           _build_default,
    "<sm-mode-ref>":       _build_sm_mode_ref,
    "<event-def>":         _build_event_def,
    "<clock-def>":         _build_clock_def,
    "<decl-parens>":       _build_decl_parens,
    "<arg-decl-list>":     _build_arg_decl_list,
    "<arg-decl>":          _build_arg_decl,
    "<dotted-name>":       _build_dotted_name,
}
