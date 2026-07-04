"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

AST MAP -- the wiring from every grammar rule to its typed product (three-file
           contract, file 3 of 3: grammar.py = data, ast_nodes.py = products,
           ast_map.py = the wiring).

One entry per rule (flattened name, 'causality/cause'), written as PLAIN DATA
-- the entry's Python type IS its meaning:

    callable          SEQ rule: the factory. Called on the finished sequence
                      node, which is its own role-db -- role-tagged children
                      read BY ROLE (strict), inline operator slots (OPT/STAR/
                      OR wrappers, which carry no taggable name) BY POSITION.
    dict              OR rule: the route table. Branch address (role, index,
                      or tuple of either) -> leaf (factory, PASS, constant).

No wrapper ceremony at the authoring surface. The engine still receives ONE
uniform seam ('fn(node)' at Grammar._reduce): load_ast_map() types each entry
against its rule's compiled shape and NORMALISES it into the core family
(dict -> OrMap, callable -> SeqMap) before the engine ever holds the map --
the family remains core machinery, it just stops being authoring surface.

What is asserted WHERE:
    at load (load_ast_map)   coverage, both directions (A-2); entry kind
                             against rule shape (dict on OR, callable on SEQ).
    at first parse           a factory's PRODUCT shape -- a bare callable
                             claims nothing about its return, so the product
                             guard is the GOOD suite (ast_shape), where it
                             always was.

StarMap/PlusMap/OptMap serve INLINE slots inside factories (no rule tops on
STAR/PLUS/OPT in this grammar: every rule compiles to SEQ or OR).

CST SHAPE LAWS the factories are written against (probed, engine-verified):
    - Transformed RULE references reduce to their PRODUCT at the parent's
      slot; INLINE operators (tuple, OR(...), [...], STAR/PLUS) stay CST
      nodes (SEQ_Node/OR_Node/OPT_Node/STAR_Node/PLUS_Node).
    - An inline multi-element body ALWAYS wraps in a SEQ_Node, even when only
      one child survives silencing; a single-element optional '[x]' holds x's
      product directly.
    - Silent terminals leave no child; captured and regex terminals survive
      as Tokens at their slots.
"""
from ..core.parser_generator.ast_map_family import (
    SeqMap, OrMap, OptMap, StarMap, PASS)
from ..core.parser_generator.ll2_grammar_spec import SEQ_Spec
from ..core.parser_generator.cst_nodes import NodeAbsent
from ..core.symbol.ast import (NodeList, ConstantLeaf, ReferenceLeaf,
                               DeclarationLeaf)
from . import ast_nodes as A


# == small shared builders (four-way rule: cases 2 and 4) =====================

def _opt(opt_node, ctor=PASS):
    """RETURN: object, 'ctor' applied to the optional's child if it fired,
              NodeAbsent, else.

    The inline-slot twin of a rule-level OptMap: factories hand it the
    OPT_Node sitting at a positional slot. A multi-element body arrives as one
    SEQ_Node; a single-element body '[x]' as x's product directly.
    """
    return OptMap(present=ctor)(opt_node)


def _list(star_or_plus, item_ctor=PASS):
    """RETURN: NodeList, 'item_ctor' over the repetition's items in match
              order -- empty for a STAR that matched nothing.
    """
    return StarMap(item_ctor)(star_or_plus)


def _decl(ref_leaf):
    """RETURN: DeclarationLeaf, the declaring twin of 'ref_leaf' -- same
              segments, same source position.

    name-dotted always builds a ReferenceLeaf; the DECLARING sites (namespace,
    import alias) convert at the point the grammar says "this introduces".
    """
    return DeclarationLeaf(begin=ref_leaf.begin, segments=ref_leaf.segments)


def _decl_tok(token):
    """RETURN: DeclarationLeaf, the one-segment name 'token' introduces."""
    return DeclarationLeaf(begin=token.begin, segments=(token.text,))


def _ref_tok(token):
    """RETURN: ReferenceLeaf, the one-segment name 'token' references."""
    return ReferenceLeaf(begin=token.begin, segments=(token.text,))


def _const(token, kind):
    """RETURN: ConstantLeaf, the literal 'token' as lexical class 'kind'."""
    return ConstantLeaf.from_text(token.text, kind, token.begin)


def _is_list(opt_node):
    """RETURN: NodeList, the inherited references of an optional
              'is: a, b(x)' tail -- empty when the tail is absent.

    The fired body is SEQ(head-call, STAR of (',' call)); the comma is silent,
    so each STAR item is a one-child inline SEQ holding the call product.
    """
    if not opt_node.present:
        return NodeList(())
    body = opt_node.child
    return NodeList((body[0],) + tuple(it[0] for it in body[1].items))


def _has_list(opt_node):
    """RETURN: NodeList, the declarations of an optional 'has: { ... }' tail
              -- empty when the tail is absent.

    The fired body is SEQ(decl-block-product,) -- 'has:' silent -- and the
    decl-block product is already a NodeList.
    """
    return opt_node.child[0] if opt_node.present else NodeList(())


def _fold_chain(seq_node):
    """RETURN: Node, the left-folded product of a '(head, STAR (op operand))'
              chain rule -- the head's product unchanged when the STAR matched
              nothing (the tier is transparent), nested left-associated BinOp
              else.

    ONE builder for every expr tier (or/and/cmp/add/mul): each STAR item is an
    inline SEQ (op, operand); the op slot holds a Token -- directly for a
    captured keyword, or as the routed product of an op-cmp/op-add/op-mul rule
    reference, which reduces to its fired Token.
    """
    product = seq_node[0]
    for step in seq_node[1].items:
        product = A.BinOp(op=step[0].text, lhs=product, rhs=step[1])
    return product


def make_command_block(seq_node):
    """RETURN: CommandBlock, the imperative body of a '{ STAR(statement) }'
              rule -- braces silent, the STAR is the single surviving child.
              Shared by 'code' (the effect body) and 'code/block' (nested
              bodies): R-12, one brace form, one product.
    """
    return A.CommandBlock(statements=_list(seq_node[0]))


def make_module_root(star_node):
    """RETURN: ModuleRoot, the typed file product over the engine's
              STAR_Node('<file>') -- finalize_file's input (the file loop is
              the engine's, not a rule: transformers never see it).
    """
    return A.ModuleRoot(items=NodeList(tuple(star_node.items)))


# == per-rule factories =======================================================

def make_namespace(n):
    """RETURN: Namespace, from 'open: path { items }' -- the path DECLARES."""
    return A.Namespace(name=_decl(n["namespace"]), items=_list(n[1]))


def make_import(n):
    """RETURN: Import, from 'import: "path" as: alias' -- the alias
              DECLARES.
    """
    return A.Import(path=_const(n["path"], A.K_STRING),
                    alias=_decl(n["namespace"]))


def make_name_dotted(n):
    """RETURN: ReferenceLeaf, the dotted name as written, head first -- dots
              silent, so the children are exactly the name tokens: the head,
              then a STAR of one-token inline SEQs.
    """
    head = n[0]
    segs = (head.text,) + tuple(it[0].text for it in n[1].items)
    return ReferenceLeaf(begin=head.begin, segments=segs)


def make_character(n):
    """RETURN: Character, from '~? character: sig is:? has:?'."""
    return A.Character(abstract=n[0].present, signature=n["signature"],
                       is_=_is_list(n[2]), has=_has_list(n[3]))


def make_aspect(n):
    """RETURN: Aspect, from '~? aspect: sig is:? has:? { body }'."""
    return A.Aspect(abstract=n[0].present, signature=n["signature"],
                    is_=_is_list(n[2]), has=_has_list(n[3]), body=n["body"])


def make_behavior(n):
    """RETURN: Behavior, from '~? behavior: sig is:? has:? { causality* }'."""
    return A.Behavior(abstract=n[0].present, signature=n["signature"],
                      is_=_is_list(n[2]), has=_has_list(n[3]),
                      causalities=_list(n[4]))


def make_causality(n):
    """RETURN: Causality, from 'cause effects' (D-12): the chain rule already
              built the NodeList of effects, terminator included.
    """
    return A.Causality(cause=n["cause"], effects=n[1])


def make_cause(n):
    """RETURN: Cause, the unified cause (D-3): the head is an inline OR --
              branch 0 an inline SEQ (name-ref product, optional parens-arg),
              branch 1/2 a lifecycle token; the guard rides an OPT whose body
              is SEQ(condition,).
    """
    head = n[0]
    if head.triggered_index == 0:
        pair = head.child
        target, args = pair[0], _opt(pair[1])
    else:
        target, args = A.Lifecycle(kind=head.child.text), NodeAbsent
    return A.Cause(target=target, args=args,
                   guard=_opt(n[1], ctor=lambda body: body[0]))


def make_cause_explicit(n):
    """RETURN: Cause, from 'event [when: cond]' -- the same product as the
              unified cause (one noun per concept), with no argument surface.
    """
    return A.Cause(target=n[0], args=NodeAbsent,
                   guard=_opt(n[1], ctor=lambda body: body[0]))


def make_def_cause(n):
    """RETURN: DefCause, from 'cause: signature cause-explicit ;'."""
    return A.DefCause(signature=n[0], cause=n[1])


def make_effects(n):
    """RETURN: NodeList, this effect and every effect after it in the chain,
              in source order (D-12, right recursion: the FINAL effect decided
              the terminator during the parse).

    Branch 0 (block-final capable): SEQ(command-block, OPT[chain]) -- the
    block ends at '}'; a present optional holds the tail NodeList directly.
    Branch 1 (spawn): SEQ(spawn, OR(';' | chain)) -- the inner OR fires ';'
    (silent, NodeAbsent child) to end, or the tail NodeList to continue.
    """
    marker = n[0].text
    branch = n[1]
    if branch.triggered_index == 0:
        body = branch.child
        effect = A.Effect(marker=marker, action=body[0])
        tail = _opt(body[1])
        if tail is NodeAbsent:
            tail = NodeList(())
    else:
        body = branch.child
        effect = A.Effect(marker=marker, action=body[0])
        chain_or = body[1]
        tail = chain_or.child if chain_or.triggered_index == 1                else NodeList(())
    return NodeList((effect,) + tuple(tail))


def make_spawn(n):
    """RETURN: Spawn, from 'call [every: period [as: name]]' -- the recurrence
              tail is SEQ(period, OPT(as-name)); the as-body is SEQ(name-token,)
              and the handle DECLARES.
    """
    every, handle = NodeAbsent, NodeAbsent
    tail = n[1]
    if tail.present:
        every = tail.child[0]
        inner = tail.child[1]
        if inner.present:
            handle = _decl_tok(inner.child[0])
    return A.Spawn(call=n[0], every=every, handle=handle)


def make_ternary_top(n):
    """RETURN: Node, the expression TOP: the or-tier product alone, or a
              Ternary when the '? then : els' tail fired (bridge B2) -- the
              tail SEQ is (?-token, then, :-token, els).
    """
    tail = n[1]
    if not tail.present:
        return n[0]
    return A.Ternary(cond=n[0], then=tail.child[1], els=tail.child[3])


def make_not(n):
    """RETURN: Node, the operand's product, wrapped in Not when 'not' fired."""
    return A.Not(operand=n[1]) if n[0].present else n[1]


def make_un(n):
    """RETURN: Node, the atom's product, wrapped in Neg when '-' fired."""
    return A.Neg(operand=n[1]) if n[0].present else n[1]


def make_data_access(n):
    """RETURN: Node, from 'base step*': the plain ReferenceLeaf itself when
              argument-free and unindexed (a bare name is not a place-wrapper),
              a DataAccess place else.
    """
    name, args = n[0]
    steps = _list(n[1])
    if args is NodeAbsent and not steps:
        return name
    return A.DataAccess(name=name, args=args, steps=steps)


def make_base(n):
    """RETURN: tuple, (name ReferenceLeaf, args NodeList | NodeAbsent) -- the
              base's two parts, an internal hand-off consumed by
              make_data_access, never an AST product.
    """
    return (n[0], _opt(n[1]))


def make_comprehension(n):
    """RETURN: Comprehension, from '[ element generator+ ]' -- brackets
              captured, so element sits at slot 1, the generators at 2.
    """
    return A.Comprehension(element=n[1], generators=_list(n[2]))


def make_generator(n):
    """RETURN: Generator, from 'with: vars from: source [if: cond]' -- the
              keywords are silent; the if-body is SEQ(condition,).
    """
    return A.Generator(variables=n[0], source=n[1],
                       cond=_opt(n[2], ctor=lambda body: body[0]))


def make_var_list(n):
    """RETURN: NodeList, the DECLARED comprehension variables in order -- the
              head token, then a STAR of one-token inline SEQs (commas
              silent).
    """
    return NodeList((_decl_tok(n[0]),)
                    + tuple(_decl_tok(it[0]) for it in n[1].items))


def make_mutation(n):
    """RETURN: Mutation, from 'lvalue op rhs ;' -- the op-mut rule reduces to
              its fired operator Token.
    """
    return A.Mutation(lvalue=n[0], op=n[1].text, rhs=n[2])


def make_if(n):
    """RETURN: If, from 'if: c b (elif: c b)* [else: b]': the if-arm first,
              elif-arms in source order; the else-body is SEQ(block,),
              NodeAbsent when missing.
    """
    arms = [A.IfArm(cond=n[0], block=n[1])]
    for step in n[2].items:
        arms.append(A.IfArm(cond=step[0], block=step[1]))
    return A.If(arms=NodeList(tuple(arms)),
                els=_opt(n[3], ctor=lambda body: body[0]))


def make_match(n):
    """RETURN: Match, from 'match: scrutinee { case+ }'."""
    return A.Match(scrutinee=n[0], cases=_list(n[1]))


def make_case(n):
    """RETURN: Case, from 'case: pattern block'."""
    return A.Case(pattern=n[0], block=n[1])


def make_range(n):
    """RETURN: Range, from 'lo to: hi' (inclusive, SEMANTICS 8)."""
    return A.Range(lo=n[0], hi=n[1])


def make_foreach(n):
    """RETURN: Foreach, from 'foreach: var in: source block' -- the var
              DECLARES, loop-local (SEMANTICS 6).
    """
    return A.Foreach(var=_decl_tok(n["var"]), source=n[1], block=n[2])


def make_count(n):
    """RETURN: Count, from 'type: var = lo .. hi [step: s] block' -- the
              count-type rule reduces to its fired Token ('int:'/'float:');
              '=' and '..' are captured, so the slots run ct=0, var=1, '='=2,
              lo=3, '..'=4, hi=5, step=6, block=7; the step-body is
              SEQ(algebr,).
    """
    return A.Count(type_=n[0].text.rstrip(":"), var=_decl_tok(n["var"]),
                   lo=n[3], hi=n[5],
                   step=_opt(n[6], ctor=lambda body: body[0]),
                   block=n[7])


def make_dropto(n):
    """RETURN: DropTo, from 'dropto: label ;' -- the label REFERENCES."""
    return A.DropTo(label=_ref_tok(n["label"]))


def make_exit_label(n):
    """RETURN: ExitLabel, from 'exit: label ;' -- the label DECLARES."""
    return A.ExitLabel(label=_decl_tok(n["label"]))


def make_clockwork(n):
    """RETURN: Clockwork, from 'clockwork: cause { clockwork-statement+ }'."""
    return A.Clockwork(tick=n["tick"], statements=_list(n[1]))


def make_emit_step(n):
    """RETURN: EmitStep, from '=> (call | ~NONE)': EmitNone on the ~NONE
              branch, the call's product else.
    """
    fired = n[1]
    target = A.EmitNone() if fired.triggered_index == 1 else fired.child
    return A.EmitStep(target=target)


def make_groove(n):
    """RETURN: Groove, from 'groove: { clock-arm+ }'."""
    return A.Groove(arms=_list(n[0]))


def make_clock_arm_select(child):
    """RETURN: ClockArm, from the fired '(clock-cause { body })' branch --
              braces silent, so the branch SEQ is (cause, STAR).
    """
    return A.ClockArm(cause=child[0], body=_list(child[1]))


def make_clock_arm_beat(child):
    """RETURN: BeatArm, from the fired '(beat: n { body })' branch -- the
              beat count read off the tagged integer token.
    """
    return A.BeatArm(beat=int(child["beat"].text), body=_list(child[1]))


def make_clock_else(child):
    """RETURN: ElseArm, from the fired '~ELSE [when: cond]' branch -- the
              else-token survives at slot 0; the when-body is SEQ(cond,).
    """
    return A.ElseArm(guard=_opt(child[1], ctor=lambda body: body[0]))


def make_decl_block(n):
    """RETURN: NodeList, the declarations of a '{ declaration+ }' block --
              braces silent, the PLUS is the single surviving child.
    """
    return _list(n[0])


def make_declaration(n):
    """RETURN: Declaration, from 'name : type ;' -- the name DECLARES; the
              bare ':' (D-9, a regex terminal) survives at slot 1, the type
              product at 2.
    """
    return A.Declaration(name=_decl_tok(n["name"]), type_=n[2])


def make_struct(n):
    """RETURN: StructType, from 'struct { field+ }' -- 'struct' captured at
              slot 0, the fields at 1.
    """
    return A.StructType(fields=_list(n[1]))


def make_field(n):
    """RETURN: DeclarationLeaf, one 'name ;' struct slot -- the name
              DECLARES.
    """
    return _decl_tok(n["name"])


def make_signature(n):
    """RETURN: Signature, from 'name [(decl-args)]' -- the name DECLARES
              (D-1: a bare id under the current scope); the single-element
              optional holds the parens-decl NodeList directly.
    """
    return A.Signature(name=_decl_tok(n["name"]), params=_opt(n[1]))


def make_call(n):
    """RETURN: Call, from 'name-ref [(args)]' -- the single-element optional
              holds the parens-arg NodeList directly.
    """
    return A.Call(name=n[0], args=_opt(n[1]))


def make_parens(n):
    """RETURN: NodeList, a parenthesised list's items -- EMPTY for '()':
              parens silent, so the one child is the optional listing, itself
              holding the listing's NodeList directly. Shared by parens-arg
              and parens-decl.
    """
    inner = n[0]
    return inner.child if inner.present else NodeList(())


def make_listing(n):
    """RETURN: NodeList, the items of an 'x (, x)*' listing -- commas silent,
              so each STAR item is a one-child inline SEQ holding the item's
              product. Shared by list-arg and list-decl.
    """
    return NodeList((n[0],) + tuple(it[0] for it in n[1].items))


def make_named_arg(child):
    """RETURN: NamedArg, from the fired 'name = value' branch -- '='
              captured at slot 1.
    """
    return A.NamedArg(name=child["arg-name"].text, value=child[2])


def make_decl_arg(n):
    """RETURN: DeclArg, from 'name [: type] [= default]' (D-11) -- the name
              DECLARES; each optional body is a two-slot SEQ (captured ':' or
              '=' at 0, the value at 1); NodeAbsent type means float,
              NodeAbsent default means the parameter is REQUIRED.
    """
    return A.DeclArg(name=_decl_tok(n["arg-name"]),
                     type_=_opt(n[1], ctor=lambda body: body[1]),
                     default=_opt(n[2], ctor=lambda body: body[1]))


# == the map ==================================================================
# One entry per flattened rule. Passthroughs are EXPLICIT (PASS routes, _FWD),
# so the coverage gate reads intent, never absence.

def _fwd(n):
    """RETURN: object, the single child's product, unchanged -- the entry for
              a one-child rule whose product IS the child's product (sort
              views, plain forwarders): an explicit passthrough the coverage
              gate reads as intent, never absence.
    """
    return n[0]


def _lifecycle(token):
    """RETURN: Lifecycle, the reserved event the fired '~ENTRY'/'~EXIT'
              token names.
    """
    return A.Lifecycle(kind=token.text)


AST_MAP = {
    # -- the file (D-7) ----------------------------------------------------
    "file":          lambda n: make_module_root(n[0]),

    # -- top level -------------------------------------------------------
    "top-level":     {("character", "aspect", "behavior", "causality",
                       "cause-def", "declaration", "namespace",
                       "import"): PASS},
    "namespace":     make_namespace,
    "import":        make_import,
    "name-dotted":   make_name_dotted,
    "character":     make_character,
    "aspect":        make_aspect,
    "aspect-body":   {("behaviors", "clockwork"): PASS},
    "behavior-list": lambda n: _list(n[0]),
    "behavior":      make_behavior,

    # -- causality -------------------------------------------------------
    "causality":                make_causality,
    "causality/cause":          make_cause,
    "causality/cause-explicit": make_cause_explicit,
    "causality/event":          {"event": PASS,
                                 (1, 2): _lifecycle},
    "causality/def-cause":      make_def_cause,
    "causality/effects":        make_effects,
    "causality/effect-marker":  {(0, 1): PASS},
    "causality/spawn":          make_spawn,

    # -- expressions (D-2: one grammar, sorts are pass-2 views) -----------
    "expr":        make_ternary_top,
    "expr/or":     _fold_chain,
    "expr/and":    _fold_chain,
    "expr/not":    make_not,
    "expr/cmp":    _fold_chain,
    "expr/op-cmp": {(0, 1, 2, 3, 4, 5): PASS},
    "expr/add":    _fold_chain,
    "expr/mul":    _fold_chain,
    "expr/un":     make_un,
    "expr/atom":   {("group", "literal", "operand"): PASS,
                    (2, 3): (lambda t: _const(t, A.K_BOOL))},
    "expr/group":  lambda n: n[0],
    "expr/op-add": {(0, 1): PASS},
    "expr/op-mul": {(0, 1): PASS},

    "condition":   _fwd,
    "algebr":      _fwd,
    "numeric":     _fwd,
    "number":      {0: (lambda t: _const(t, A.K_FLOAT)),
                    1: (lambda t: _const(t, A.K_INT))},

    # -- data access / collections ----------------------------------------
    "data-access":              make_data_access,
    "data-access/base":         make_base,
    "data-access/step":         lambda n: n[1],
    "collection":               _fwd,
    "collection/comprehension": make_comprehension,
    "collection/generator":     make_generator,
    "collection/var-list":      make_var_list,
    "collection/source":        {("access", "comprehension"): PASS},
    "collection/element":       {(0, 1): PASS},

    # -- command block -----------------------------------------------------
    "code":            make_command_block,
    "code/statement":  {("mutation", "if", "match", "foreach", "count",
                         "break", "continue", "dropto"): PASS,
                        8: PASS},
    "code/block":      make_command_block,
    "code/mutation":   make_mutation,
    "code/lvalue":     _fwd,
    "code/rhs":        {(0, 1): PASS},
    "code/op-mut":     {(0, 1, 2, 3, 4): PASS},
    "code/if":         make_if,
    "code/match":      make_match,
    "code/case":       make_case,
    "code/pattern":    {("literal", "range"): PASS,
                        "glob": (lambda t: _const(t, A.K_GLOB)),
                        3: (lambda t: A.Wildcard())},
    "code/range":       make_range,
    "code/foreach":     make_foreach,
    "code/coll-source": {("access", "comprehension"): PASS},
    "code/count":       make_count,
    "code/count-type":  {(0, 1): PASS},
    "code/break":       lambda n: A.Break(),
    "code/continue":    lambda n: A.Continue(),
    "code/dropto":      make_dropto,
    "code/exit-label":  make_exit_label,

    # -- clockwork ----------------------------------------------------------
    "clockwork":            make_clockwork,
    "clockwork/clockwork-statement":
                            {("statement", "emit", "groove"): PASS},
    "clockwork/emit-step":  make_emit_step,
    "clockwork/groove":     make_groove,
    "clockwork/clock-arm":  {0: make_clock_arm_select,
                             1: make_clock_arm_beat},
    "clockwork/clock-cause": {0: PASS,
                              1: make_clock_else,
                              2: (lambda c: A.TickDefault(cond=c[0]))},

    # -- declarations / types -----------------------------------------------
    "decl-block":    make_decl_block,
    "declaration":   make_declaration,
    "type":          {("type-builtin", "list", "dict", "struct"): PASS,
                      "type": (lambda t: A.NamedType(name=_ref_tok(t)))},
    "type-built-in": {(0, 1, 2, 3): (lambda t: A.BuiltinType(kind=t.text))},
    "type-list":     lambda n: A.ListType(),
    "type-dict":     lambda n: A.DictType(),
    "type-struct":   make_struct,
    "field":         make_field,

    # -- reference / definition ----------------------------------------------
    "signature":     make_signature,
    "call":          make_call,
    "name-ref":      _fwd,
    "parens-arg":    make_parens,
    "list-arg":      make_listing,
    "arg":           {0: PASS, 1: make_named_arg},
    "parens-decl":   make_parens,
    "list-decl":     make_listing,
    "decl-arg":      make_decl_arg,
}


# == the load gate (run by the facade, before the first parse) ================

def load_ast_map(grammar):
    """RETURN: dict, the engine-ready transformer map -- every AST_MAP entry
              typed against its rule's compiled TOP shape and normalised into
              the core family (dict -> OrMap, callable -> SeqMap).
              Raises LookupError naming every unmapped/unknown rule, and
              TypeError naming every kind mismatch, else.

    Three checks, one pass, at load -- never mid-walk in the semantic unit:
        coverage   rules == mapped, both directions (A-2): a rule without an
                   entry would leak a CST node into the typed tree.
        kind       a dict belongs on an OR rule (it is the route table); a
                   callable belongs on a SEQ rule (it is the factory).
        normalise  the engine's transformer seam is ONE case, 'fn(node)';
                   the raw data becomes callable core-family values here, so
                   the engine grows no second case and the author writes none.
    """
    rules   = set(grammar.rules)
    mapped  = set(AST_MAP)
    missing = sorted(rules - mapped)
    unknown = sorted(mapped - rules)
    if missing or unknown:
        raise LookupError(
            "AST_MAP coverage: %d rule(s) unmapped %r; %d entr(y/ies) name "
            "no rule %r" % (len(missing), missing, len(unknown), unknown))
    out, bad = {}, []
    for name, entry in AST_MAP.items():
        is_seq = isinstance(grammar.rules[name].pattern, SEQ_Spec)
        if isinstance(entry, dict):
            if is_seq:
                bad.append("%s: rule is SEQ_Spec, entry is a dict (route "
                           "table belongs on an OR rule)" % name)
            else:
                out[name] = OrMap(entry)
        elif callable(entry):
            if not is_seq:
                bad.append("%s: rule is OR_Spec, entry is a callable "
                           "(factory belongs on a SEQ rule)" % name)
            else:
                out[name] = SeqMap(entry)
        else:
            bad.append("%s: entry is %r -- neither dict nor callable"
                       % (name, type(entry).__name__))
    if bad:
        raise TypeError("AST_MAP kinds: " + "; ".join(bad))
    return out
