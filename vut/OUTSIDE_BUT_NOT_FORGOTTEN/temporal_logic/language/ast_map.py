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
import dataclasses

from . import units

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


def _body_items(opt_node):
    """RETURN: tuple, the class-shaped body items of an optional
              '{ <item>+ }' tail in source order -- empty when the tail is
              absent (braces silent: the PLUS is the single surviving
              child).
    """
    return () if not opt_node.present else tuple(_list(opt_node.child[0]))


def _split_body(items, *kinds):
    """RETURN: tuple of NodeLists, 'items' distributed over 'kinds' in
              source order within each -- one NodeList per kind tuple, the
              interleave law (R-41.3 (A)) making the split lossless.
    """
    return tuple(NodeList(tuple(it for it in items if isinstance(it, kind)))
                 for kind in kinds)


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


def make_documented(n):
    """RETURN: Node, the documented subject with its docstring seated (a
              definition product carrying the doc leaf, D-18), if the
              docstring precedes a definition.
              ConstantLeaf of kind 'docstring', else -- a candidate MODULE
              docstring; finalize_file seats the file's FIRST one, declare
              rejects any other placement (SEMANTICS 22).

    The doc leaf's text is the string BETWEEN the triple quotes, verbatim;
    its offset is the opening quote's. The subject is a <named-item> product
    (D-19, single-element optional: the product sits directly); a Declaration
    subject is parseable but unlawful (D-20) -- the doc rides its product and
    declare rejects the placement (SEMANTICS 22).
    """
    token = n[0]
    leaf = ConstantLeaf.from_text(text=token.text[3:-3], kind="docstring",
                                  begin=token.begin)
    subject_opt = n[1]
    if not subject_opt.present:
        return leaf
    return dataclasses.replace(subject_opt.child, doc=leaf)


def make_module_root(star_node):
    """RETURN: ModuleRoot, the typed file product over the engine's
              STAR_Node('<file>') -- finalize_file's input (the file loop is
              the engine's, not a rule: transformers never see it).
    """
    items = tuple(star_node.items)
    if items and isinstance(items[0], ConstantLeaf) \
            and str(items[0].kind) == "docstring":
        return A.ModuleRoot(items=NodeList(items[1:]), doc=items[0])
    return A.ModuleRoot(items=NodeList(items))


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
              silent, so the children are the optional SELF dot (reactor
              ruling: a leading '.' roots at this instance, recorded as an
              EMPTY first segment -- prints naturally as '.x'), the head
              token, then a STAR of one-token inline SEQs.
    """
    self_dot = n[0].present
    head = n[1]
    segs = (head.text,) + tuple(it[0].text for it in n[2].items)
    if self_dot:
        segs = ("",) + segs
    return ReferenceLeaf(begin=head.begin, segments=segs)


def _tail_sig(opt_parens):
    """RETURN: Signature, the HEADLESS signature of a kind tail (D-19) -- the
              tail's parameter list under a placeholder name, completed by
              the defining rule's factory (_complete_def), which seats the
              head name.
    """
    return A.Signature(name=NodeAbsent, params=_opt(opt_parens))


def _complete_def(node, name_token, abstract=False):
    """RETURN: Node, the tail product 'node' completed into the full
              definition (D-19) -- the head name seated in the signature,
              the abstract flag set.

    Tails parse without their head ('<name> :' lives in named-item /
    behavior-def); this reunion keeps the AST identical to the keyword-first
    era: one Signature, name and parameters together.
    """
    sig = dataclasses.replace(node.signature, name=_decl_tok(name_token))
    if abstract:
        return dataclasses.replace(node, signature=sig, abstract=True)
    return dataclasses.replace(node, signature=sig)


def make_reactor_tail(n):
    """RETURN: Reactor, HEADLESS and MODELESS, from '(channels)? is:?
              { item+ }' (reactor + pipe rulings) -- name seated by
              _complete_def, the mode ('single' | 'multi') seated by the
              kind branch; ins/outs the channel-panel name tuples (empty
              when absent); the body items split into member declarations,
              member works, and behavior members (a behavior: only
              causalities, grouped or ungrouped).
    """
    panel = _opt(n[0])
    ins, outs = ((), ()) if panel is NodeAbsent else panel
    members, works, behaviors = _split_body(
        tuple(_list(n[2])), A.Declaration, A.Work, A.Behavior)
    return A.Reactor(signature=A.Signature(name=NodeAbsent, params=NodeAbsent),
                     mode="", is_=_is_list(n[1]),
                     members=members, works=works, behaviors=behaviors,
                     ins=ins, outs=outs)


def make_reactor_panel(n):
    """RETURN: tuple, (ins, outs) -- each a tuple of DeclarationLeaf naming
              the reactor's channels (pipe ruling: plain names, no types,
              no markers; a channel is an object the reactor HAS). Consumed
              whole by make_reactor_tail; each section optional's body is
              SEQ(first-token, STAR-rest).
    """
    def names(seq):
        toks = (seq[0],) + tuple(it[0] for it in seq[1].items)
        return tuple(_decl_tok(t) for t in toks)
    def sec(k):
        v = _opt(n[k], ctor=names)
        return () if v is NodeAbsent else v
    return (sec(0), sec(1))


def make_panel(n):
    """RETURN: Panel, the flat direction-sectioned panel (R-41.1) -- each
              of in:/out:/signals: a NodeList, empty when absent; slots
              0..2 are the section optionals, each an OPT over
              SEQ(first, STAR-rest).
    """
    def entries(seq):
        # each STAR item is a one-child inline SEQ (the ',' is silent)
        return (seq[0],) + tuple(it[0] for it in seq[1].items)
    def sec(k):
        v = _opt(n[k], ctor=entries)
        return () if v is NodeAbsent else v
    return A.Panel(ins=sec(0), outs=sec(1), signals=sec(2))


def make_panel_entry(n):
    """RETURN: DeclArg, one panel entry '[known:|had:] name [: type]
              [= default]' (R-41.1) -- the decl-arg product with the
              relation marker seated as written ('' when unmarked: having
              implicit); the marker optional's child is the fired inline
              OR holding the captured keyword token.
    """
    marker = _opt(n[0])
    text = "" if marker is NodeAbsent else marker.child.text.rstrip(":")
    return dataclasses.replace(n[1], marker=text)


def make_signal_decl(n):
    """RETURN: SignalDecl, from 'name [(decl-args)]' of a signals: section
              (D-23) -- the name DECLARES; the single-element optional holds
              the parens-decl NodeList directly.
    """
    return A.SignalDecl(name=_decl_tok(n["name"]), params=_opt(n[1]))


def make_reactor_member(n):
    """RETURN: Behavior / Work / Declaration, the reactor body's name-led
              item (reactor ruling): after 'name :' the fired branch
              decides -- 'behavior' completes a behavior member (ONLY
              causalities, GROUPED by in-channel or bare -- pipe ruling;
              the braces silent, the PLUS the surviving child), 'work' a
              member work, a type an unmarked declaration.
    """
    branch = n[2]
    body = branch.child
    if branch.triggered_index == 0:
        sig = A.Signature(name=_decl_tok(n["name"]), params=NodeAbsent)
        items = tuple(_list(body[0]))
        groups      = tuple(i for i in items if isinstance(i, A.ChannelGroup))
        causalities = NodeList(tuple(i for i in items
                                     if not isinstance(i, A.ChannelGroup)))
        return A.Behavior(signature=sig, causalities=causalities,
                          groups=groups)
    if branch.triggered_index == 1:
        return _complete_def(body[0], n["name"])
    return A.Declaration(name=_decl_tok(n["name"]), type_=body[0])


def make_channel_group(n):
    """RETURN: ChannelGroup, from '(<channel> | .) : { causality+ }' (pipe
              ruling) -- 'channel' the in-channel name, '.' when the SELF
              channel fired (the head OR's dot branch is all-silent:
              triggered_index 1, child NodeAbsent); 'begin' the colon
              token's offset when the head is the dot (no head token to
              anchor on), the head token's else.
    """
    head = n[0]
    if head.triggered_index == 0:
        channel, begin = head.child.text, head.child.begin
    else:
        channel, begin = ".", n[1].begin
    return A.ChannelGroup(channel=channel, causalities=_list(n[2]),
                          begin=begin)


def make_cause_tail(n):
    """RETURN: DefCause, HEADLESS, from '(params)? cause-explicit ;' (D-19)
              -- name seated by _complete_def (a named cause is never
              abstract: the grammar admits no '~' on its branch).
    """
    return A.DefCause(signature=_tail_sig(n[0]), cause=n[1])


def make_marked_member(n):
    """RETURN: Declaration, from '(known:|had:) name : type ;' (R-41.3) --
              a marker-led item is a member declaration by construction;
              the fired marker OR holds the captured keyword token at
              slot 0.
    """
    return A.Declaration(name=_decl_tok(n["name"]), type_=n[3],
                         marker=n[0].child.text.rstrip(":"))


def make_plain_member(n):
    """RETURN: Work, the member work completed with its name, if the
              factored head's 'work' branch fired (R-41.3, D-20
              precedent: 'name :' consumed, the next token decided).
              Declaration (unmarked: having implicit), else.
    """
    branch = n[2]
    if branch.triggered_index == 0:
        return _complete_def(branch.child[0], n["name"])
    return A.Declaration(name=_decl_tok(n["name"]), type_=branch.child[0])



def make_named_item(n):
    """RETURN: Node, the product of the factored '<name> : <tail>' head
              (D-19, reactor ruling): a Reactor (mode seated from the
              kind word -- 'reactor' the state machine, 'reactor++' the
              mode group), a DefCause / ClassDef / Work / ClockworkDef
              completed from its kind tail, or a Declaration when the
              type branch fired -- definition and top-level declaration
              are ONE head. Kind words are silent; every branch holds the
              tail product only.
    """
    name_token, head = n["name"], n[2]
    branch = head.child
    if head.triggered_index == 7:                            # declaration
        return A.Declaration(name=_decl_tok(name_token), type_=branch[0])
    if head.triggered_index == 0:              # reactor++ (captured kind
        node = _complete_def(branch[1], name_token)   # word survives at 0)
        return dataclasses.replace(node, mode="multi")
    node = _complete_def(branch[0], name_token)
    if head.triggered_index == 1:                            # reactor
        return dataclasses.replace(node, mode="single")
    return node                          # cause/event/class/work/clockwork


def make_event_tail(n):
    """RETURN: EventDef, HEADLESS, from '(fields)? ;' (R-45/D-34) -- the
              payload NodeList rides the signature's params (name seated
              by _complete_def); an empty parens is the bare event.
    """
    params = n[0] if n[0] else NodeAbsent
    return A.EventDef(signature=A.Signature(name=NodeAbsent, params=params))


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
    elif head.triggered_index == 3:
        # R-44/D-33: the ~ANY catch-all cause -- matches any event on the
        # group's channel; e is Nothing under it.
        target, args = A.AnyPattern(begin=head.child.begin), NodeAbsent
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
    elif branch.triggered_index == 1:
        # R-46: the causality shrug -- 'action' NodeAbsent, chain-final.
        return NodeList((A.Effect(marker=marker, action=NodeAbsent),))
    else:
        body = branch.child
        effect = A.Effect(marker=marker, action=body[0])
        chain_or = body[1]
        tail = chain_or.child if chain_or.triggered_index == 1 \
               else NodeList(())
    return NodeList((effect,) + tuple(tail))


def make_upower(n):
    """RETURN: Fraction, the exponent one <upower> spells (R-50): the
              inner OR's branch 0 is the folded caret form, branch 1 a
              Unicode superscript run through units.super_int.
    """
    head = n[0]
    if head.triggered_index == 1:                         # superscript
        return units.Fraction(units.super_int(head.child.text))
    return head.child                                     # caret, folded


def make_upower_caret(n):
    """RETURN: Fraction, the '^' exponent -- '^<int>' (optionally signed)
              or '^(<p>/<q>)' (rationals parenthesise, R-50).
    """
    body = n[1]
    if body.triggered_index == 0:
        pair = body.child
        p = int(pair[1].text)
        return units.Fraction(-p if pair[0].present else p)
    inner = body.child          # silent parens drop: [sign?, p, '/', q]
    frac = units.Fraction(int(inner[1].text), int(inner[3].text))
    return -frac if inner[0].present else frac


def make_ufactor(n):
    """RETURN: (tuple, str), one <ufactor>'s vector and written name
              (R-50) -- the unit name's vector raised to its power (1
              when the power is absent); an UNKNOWN name folds as the
              zero vector and keeps its spelling for the semantic
              reject (elaborate rejects by the written form).
    """
    name = n["uname"].text
    p = n[1].child if n[1].present else units.Fraction(1)
    # the id pattern swallows a trailing DIGIT superscript into the name
    # ('m\u00b2' is ONE token; sign-led runs like 's\u207b\u00b2' split into
    # id + super token and arrive through n[1]) -- peel it here (R-50).
    core = name.rstrip("\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079")
    if core != name:
        p = p * units.Fraction(units.super_int(name[len(core):]))
        name = core
    base = units.lookup(name)
    if base is None:
        base = (units.Fraction(0),) * 7
        name = "?" + name                    # the reject marker
    return units.power(base, p), name


def make_uprod(n):
    """RETURN: (tuple, str), one <uprod> folded -- factors MULTIPLY
              (exponents add); the written form joins by '*'.
    """
    vec, name = n[0]
    names = [name]
    for link in n[1].rep_items():
        fvec, fname = link[1]
        vec = units.mul(vec, fvec)
        names.append(fname)
    return vec, "*".join(names)


def make_unit(n):
    """RETURN: (tuple, str), one <unit> folded -- quotients SUBTRACT
              (left-assoc: a/b/c == a/(b*c)); the written form joins
              by '/'.
    """
    vec, name = n[0]
    names = [name]
    for link in n[1].rep_items():
        qvec, qname = link[1]
        vec = units.div(vec, qvec)
        names.append(qname)
    return vec, "/".join(names)


def make_type_physical(n):
    """RETURN: PhysicalType, from 'physical [ <unit> ]' (R-50) -- the
              canonical vector plus the author's written spelling
              ('?'-marked names are unknown; elaborate rejects them).
    """
    vec, written = n[1]
    return A.PhysicalType(vector=vec, written=written,
                          begin=n[0].begin)


def make_physical_literal(n):
    """RETURN: PhysicalLiteral, from '<number> [ <unit> ]' -- or the bare
              number node itself when the bracket is absent (R-50: the
              dimensionless case stays a plain number).
    """
    opt = n[1]
    if not opt.present:
        return n[0]
    vec, written = opt.child[1]
    return A.PhysicalLiteral(number=n[0], vector=vec, written=written,
                             begin=opt.child[0].begin)


def make_spawn(n):
    """RETURN: Spawn, from 'call [to channel]' (pipe ruling; R-49: the
              recurrence tail died) -- the 'to' suffix routes the emission
              onto the named out-channel (a ReferenceLeaf; NodeAbsent =
              suffix-less, the send FANS).
    """
    to_channel = NodeAbsent
    routed = n[1]
    if routed.present:
        to_channel = _ref_tok(routed.child[0])
    return A.Spawn(call=n[0], to_channel=to_channel)


def make_wire(n):
    """RETURN: Wire, from 'source ----> dest;' / 'source --[ ch ]--> dest;'
              (pipe ruling: WIRING IS WORK) -- 'channel' the written name,
              '' for the plain arrow; the middle OR's open form carries
              [open-token, channel-token, close-token, arrow-token], the
              plain form the bare arrow token.
    """
    middle = n[1]
    if middle.triggered_index == 0:
        channel = middle.child[1].text
    else:
        channel = ""
    return A.Wire(source=_ref_tok(n["source"]), dest=_ref_tok(n["dest"]),
                  channel=channel)


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


def make_site_target(n):
    """RETURN: KnownSite over the lvalue, if the 'known:' site marker fired
              (R-41.2) -- the marker recorded, no check invented.
              The lvalue product unchanged, else.
    """
    return A.KnownSite(target=n[1]) if n[0].present else n[1]


def make_mutation(n):
    """RETURN: Mutation, from 'lvalue (, lvalue)* op rhs (; | else: handler)'
              (D-26) -- slot 1 holds the extra targets STAR, the tail OR
              fires ';' (index 0) or the handler branch (index 1).
    """
    tail = n[4]
    handler = tail.child[0] if tail.triggered_index == 1 else NodeAbsent
    return A.Mutation(lvalue=n[0], op=n[2].text, rhs=n[3],
                      extra_lvalues=_list(n[1]), handler=handler)


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


def make_for(n):
    """RETURN: For, from 'for: var (in: coll | from: source) block
              [else: handler]' (D-16, D-26; the give flavour retired by
              ruling) -- the var DECLARES, loop-local (SEMANTICS 6); the
              source OR's index marks the from:-arm.
    """
    head = n[1]
    pulls = (head.triggered_index == 1)
    return A.For(var=_decl_tok(n["var"]), source=head.child[0], block=n[2],
                 pulls=pulls, handler=_opt(n[3]))


def make_count(n):
    """RETURN: Count | CountWith, from the two counter arms (D-17): the '='
              RANGE arm ('type: var = lo .. hi [step: s] block'; '=' and
              '..' captured, so its branch slots run '='=0, lo=1, '..'=2,
              hi=3, step=4) or the 'with:' ENUMERATION arm ('type: var
              with: item from: source [start: i0] block'; 'with:'/'from:'
              silent, so its slots run item=0, source=1, start=2). Each
              optional body is SEQ(algebr,).
    """
    type_ = n[0].text.rstrip(":")
    counter = _decl_tok(n["var"])
    branch = n[2]
    body = branch.child
    if branch.triggered_index == 0:
        return A.Count(type_=type_, var=counter,
                       lo=body[1], hi=body[3],
                       step=_opt(body[4], ctor=lambda b: b[0]),
                       block=n[3])
    return A.CountWith(type_=type_, index=counter,
                       var=_decl_tok(body["item"]),
                       source=body[1],
                       start=_opt(body[2], ctor=lambda b: b[0]),
                       block=n[3])


def make_dropto(n):
    """RETURN: DropTo, from 'dropto: label ;' -- the label REFERENCES."""
    return A.DropTo(label=_ref_tok(n["label"]))


def make_exit_label(n):
    """RETURN: ExitLabel, from ':name: [=> { ... }]' (D-21, D-31) -- the
              label DECLARES; both bare colons survive as tokens beside it.
              With the arm-arrow tail: a CATCH REGION (B-1/R-39), the
              elseto: target; 'region' carries its block, else NodeAbsent.
    """
    tail = _opt(n[3])
    region = tail if tail is NodeAbsent else tail[1]
    return A.ExitLabel(label=_decl_tok(n["label"]), region=region)


def make_ctor_def(n):
    """RETURN: Work, from '+<class>.<ext> : work <work-tail>' (D-27, R-31)
              -- a CONSTRUCTION-WORK completion: the Work carries the
              qualified name (class, ext); the '+' marker's role agreement
              with the panel is SEMANTICS 25's check.
    """
    work = n[4]                     # the captured '+' survives at slot 0
    sig = A.Signature(name=DeclarationLeaf(
        begin=n["class"].begin,
        segments=(n["class"].text, n["ext"].text)), params=NodeAbsent)
    return dataclasses.replace(work, signature=sig)


def make_dtor_def(n):
    """RETURN: Work, from '-<class>[()] : work <work-tail>' (D-27, D-29) --
              THE disposal-work completion, named by the class under the
              reserved extension '-'; one per class (SEMANTICS 25); '()'
              sets the EXPLICIT flag (R-37, SEMANTICS 27).
    """
    explicit = n[2].present         # the '()' flag (D-29, SEMANTICS 27)
    work = n[4]                     # the captured '-' survives at slot 0
    sig = A.Signature(name=DeclarationLeaf(
        begin=n["class"].begin,
        segments=(n["class"].text, "-")), params=NodeAbsent)
    return dataclasses.replace(work, signature=sig, explicit=explicit)


def make_class_tail(n):
    """RETURN: ClassDef, HEADLESS, from 'is:? { item+ }?' (R-29, R-41.3)
              -- name seated by _complete_def; a class takes no '~' and no
              parameter list, so the signature carries the name only; the
              body items split into member declarations and member works
              (interleave (A): lossless).
    """
    members, works = _split_body(_body_items(n[1]),
                                 A.Declaration, A.Work)
    return A.ClassDef(signature=A.Signature(name=NodeAbsent, params=NodeAbsent),
                      is_=_is_list(n[0]), members=members, works=works)


def make_work_tail(n):
    """RETURN: Work, HEADLESS, from '[<panel>] [{ statement* }]' -- body
              NodeAbsent = a SPEC (12.1); panel AND body absent = a class
              body's SEMI-DECLARATION (D-27, empty panel stands in); name
              seated by _complete_def.
    """
    panel = _opt(n[0])
    body = _opt(n[1])
    return A.Work(signature=A.Signature(name=NodeAbsent, params=NodeAbsent),
                  panel=A.Panel(ins=(), outs=(), signals=()) if panel is NodeAbsent else panel,
                  body=body if body is NodeAbsent else _list(body[0]))


def make_clockwork_tail(n):
    """RETURN: ClockworkDef, HEADLESS, from '<panel> [{ statement* }]' with
              the tick-capable body (LANGUAGE 13) -- a clockwork's panel is
              MANDATORY (D-27's semi-declaration is a class-member-work
              form); name seated by _complete_def.
    """
    body = _opt(n[1])
    return A.ClockworkDef(signature=A.Signature(name=NodeAbsent, params=NodeAbsent),
                          panel=n["panel"],
                          body=body if body is NodeAbsent else _list(body[0]))


def make_give_stmt(n):
    """RETURN: Give, from 'give [port (, port)*];' (LANGUAGE 12.4, R-37,
              R-41.4) -- the ports REFERENCE the panel's out: entries;
              empty for the bare terminal (no out: declared).
    """
    tail = _opt(n[0])
    if tail is NodeAbsent:
        return A.Give(ports=NodeList(()))
    ports = (_ref_tok(tail[0]),) + tuple(_ref_tok(it[0])
                                         for it in tail[1].items)
    return A.Give(ports=NodeList(ports))


def make_destruct_stmt(n):
    """RETURN: Destruct, from 'destruct: <object> (; | else: handler)'
              (R-37) -- the tail OR fires ';' (index 0) or the handler
              branch (index 1).
    """
    tail = n[1]
    handler = tail.child[0] if tail.triggered_index == 1 else NodeAbsent
    return A.Destruct(object=n["object"], handler=handler)


def make_tick_stmt(n):
    """RETURN: Tick, the 'tick:' delivery statement (LANGUAGE 13.3)."""
    return A.Tick()


def make_signal_stmt(n):
    """RETURN: Signal, from 'signal [<variant> [(args)] [to <channel>]];'
              (R-41.7, R-43) -- the variant REFERENCES its declaration (a
              panel signal in work code, a raw event in behavior code); a
              bare 'signal;' yields the typed absences (the nothing-more
              egress); 'to <channel>' a ReferenceLeaf (NodeAbsent =
              suffix-less; the position law is semantic, SEMANTICS 23/31).
    """
    head = _opt(n[0])
    if head is NodeAbsent:
        return A.Signal(variant=NodeAbsent, args=NodeAbsent,
                        to_channel=NodeAbsent)
    to_channel = NodeAbsent
    routed = head[2]
    if routed.present:
        to_channel = _ref_tok(routed.child[0])
    return A.Signal(variant=_ref_tok(head[0]), args=_opt(head[1]),
                    to_channel=to_channel)


def make_handler(n):
    """RETURN: Handler, from '{ arm* }' (LANGUAGE 12.6)."""
    return A.Handler(arms=_list(n[0]))


def make_arm(n):
    """RETURN: Arm, from '(<variant> | ~ANY) [when: <cond>] => action'
              (R-44, D-33) -- the head is an inline OR: branch 0 the
              variant token, branch 1 the ~ANY keyword (variant
              NodeAbsent: the catch-all; e is Nothing under it); 'guard'
              the when: condition or NodeAbsent.
    """
    head = n[0]
    variant = _decl_tok(head.child) if head.triggered_index == 0 \
              else NodeAbsent
    return A.Arm(variant=variant,
                 guard=_opt(n[1], ctor=lambda body: body[0]),
                 action=n[3])


def _retired_make_arm_fields(n):
    """RETURN: tuple, RETIRED (R-44/D-33: the parens-binding arm head left
              the grammar) -- kept dead one pass for the diff reader,
              never routed.
    """
    inner = _opt(n[0])
    if inner is NodeAbsent:
        return ()
    return (_decl_tok(inner[0]),) + tuple(_decl_tok(t)
                                          for t in _list(inner[1]))


def make_arm_shrug(n):
    """RETURN: NodeAbsent, always -- the ';' arm action is the written
              shrug: acknowledged, deliberately nothing (LANGUAGE 12.6).
    """
    return NodeAbsent


def make_declaration(n):
    """RETURN: Declaration, from the TOP-LEVEL 'name : type ;' branch --
              the name DECLARES; the bare ':' (D-9, a regex terminal)
              survives at slot 1, the type product at 2; unmarked (the
              relation markers belong to class-shaped bodies, R-41.3).
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


class _NotIn:
    """RETURN: never constructed by callers directly -- the operator shim of
              the 'not in' branch (D-15): 'not' is silent, so the fired
              branch carries only the 'in' token; this shim presents the
              chain folder the two-word operator text at the token's
              position.
    """

    text = "not in"

    def __init__(self, in_token):
        self.begin = in_token.begin


def make_not_in(child):
    """RETURN: _NotIn, the operator value of a fired 'not in' branch -- the
              branch body is SEQ(not-token, in-token), both captured (D-15).
    """
    return _NotIn(child[0])


def make_named_arg(child):
    """RETURN: NamedArg, from the fired 'name = value' branch -- '='
              captured at slot 1.
    """
    return A.NamedArg(name=child["arg-name"].text, value=child[2])


def make_type_have(n):
    """RETURN: RelContainer, from 'have (list|dict)' (R-38, LANGUAGE 10):
              the container HAS its elements -- collective debt; the inner
              OR's product passes through.
    """
    return A.RelContainer(rel="have", inner=n[0].child)


def make_type_know(n):
    """RETURN: RelContainer, from 'know (list|dict)' (R-38): the container
              KNOWS its elements -- views, no debt.
    """
    return A.RelContainer(rel="know", inner=n[0].child)


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
    "top-level":     {("named", "ctor", "dtor", "causality", "namespace",
                       "import", "documented"): PASS},
    "namespace":     make_namespace,
    "import":        make_import,
    "name-dotted":   make_name_dotted,
    "named-item":    make_named_item,
    "event-tail":    make_event_tail,
    "reactor-tail":   make_reactor_tail,
    "reactor-panel":  make_reactor_panel,
    "reactor-item":   {("marked", "member"): PASS},
    "reactor-member": make_reactor_member,
    "behavior-item":  {("group", "causality"): PASS},
    "channel-group":  make_channel_group,
    "panel":         make_panel,
    "panel-entry":   make_panel_entry,
    "signal-decl":   make_signal_decl,
    "class-tail":    make_class_tail,
    "class-item":    {("marked", "plain"): PASS},
    "marked-member": make_marked_member,
    "plain-member":  make_plain_member,
    "ctor-def":      make_ctor_def,
    "dtor-def":      make_dtor_def,
    "work-tail":     make_work_tail,
    "clockwork-tail": make_clockwork_tail,
    "code/give-stmt":   make_give_stmt,
    "code/destruct-stmt": make_destruct_stmt,
    "code/tick-stmt":   make_tick_stmt,
    "code/signal-stmt": make_signal_stmt,
    "handler":       make_handler,
    "arm":           make_arm,
    "arm-action":    {("block", "signal", "shrug"): PASS},
    "arm-shrug":     make_arm_shrug,
    "type-physical":       make_type_physical,
    "unit":                make_unit,
    "uprod":               make_uprod,
    "ufactor":             make_ufactor,
    "upower":              make_upower,
    "upower-caret":        make_upower_caret,
    "expr/physical-literal": make_physical_literal,
    "causality/shrug": make_arm_shrug,   # R-46: same written shrug
    "cause-tail":    make_cause_tail,

    # -- causality -------------------------------------------------------
    "causality":                make_causality,
    "causality/cause":          make_cause,
    "causality/cause-explicit": make_cause_explicit,
    "causality/event":          {"event": PASS,
                                 (1, 2): _lifecycle},
    "causality/effects":        make_effects,
    "causality/effect-marker":  {(0, 1, 2): PASS},   # R-46: =!=> joins
    "causality/spawn":          make_spawn,

    # -- expressions (D-2: one grammar, sorts are pass-2 views) -----------
    "expr":        make_ternary_top,
    "expr/or":     _fold_chain,
    "expr/and":    _fold_chain,
    "expr/not":    make_not,
    "expr/cmp":    _fold_chain,
    "expr/op-cmp": {(0, 1, 2, 3, 4, 5, 6): PASS,
                    7: make_not_in},
    "expr/add":    _fold_chain,
    "expr/mul":    _fold_chain,
    "expr/un":     make_un,
    "expr/atom":   {("group", "literal", "operand", "physical"): PASS,
                    "literal-string": (lambda t: _const(t, A.K_STRING)),
                    (3, 4): (lambda t: _const(t, A.K_BOOL)),
                    5: (lambda t: A.NothingLeaf(begin=t.begin))},
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
    "code/statement":  {("wire", "mutation", "if", "match", "for", "count",
                         "break", "continue", "dropto",
                         "give", "signal", "tick", "destruct"): PASS,
                        9: PASS},
    "code/wire":       make_wire,
    "code/block":      make_command_block,
    "code/mutation":   make_mutation,
    "code/site-target": make_site_target,
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
    "documented":       make_documented,
    "code/for":         make_for,
    "code/coll-source": {("access", "comprehension"): PASS},
    "code/count":       make_count,
    "code/count-type":  {(0, 1): PASS},
    "code/break":       lambda n: A.Break(),
    "code/continue":    lambda n: A.Continue(),
    "code/dropto":      make_dropto,
    "code/exit-label":  make_exit_label,

    # -- declarations / types -----------------------------------------------
    "declaration":   make_declaration,
    "type":          {("type-builtin", "list", "dict", "struct",
                       "have", "know", "physical"): PASS,
                      "type": (lambda t: A.NamedType(name=_ref_tok(t)))},
    "type-have":     make_type_have,
    "type-know":     make_type_know,
    "type-built-in": {(0, 1, 2, 3): (lambda t: A.BuiltinType(kind=t.text))},
    "type-list":     lambda n: A.ListType(),
    "type-dict":     lambda n: A.DictType(),
    "type-struct":   make_struct,
    "field":         make_field,

    # -- reference / definition ----------------------------------------------
    "call":          make_call,
    "name-ref":      _fwd,
    "parens-arg":    make_parens,
    "list-arg":      make_listing,
    "arg":           {0: PASS, 1: make_named_arg},
    "parens-decl":   make_parens,
    "parens-payload": make_parens,
    "list-payload":  make_listing,
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
