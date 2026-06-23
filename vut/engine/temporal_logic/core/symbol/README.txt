SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
===============================================================================
core/symbol  --  GENERAL AST VOCABULARY FOR THE SEMANTIC UNIT
===============================================================================

WHAT THIS LAYER DOES
    Supplies the AST shapes the semantic unit walks without knowing the rule
    language. A specific grammar (parser/) derives its named nodes and
    terminals from these; the semantic unit then treats any such tree the same
    way.

WORKED EXAMPLE
    Written in a rule file:        NS.Other.Idle
    Parser builds:                 ReferenceLeaf(segments=('NS','Other','Idle'),
                                                 begin=...)
    Semantic pass resolves:        leaf.resolve(<seated access>)
    Later read:                    leaf.access  -> the seated access

    The SAME ReferenceLeaf is produced two ways:
        bracket grammar   eager, held in a node      (parser builds it)
        opaque Luau       lazy, OpaqueCode yields it  (oracle finds it)
    One leaf type, one resolution mechanism, two birth sites.

TOPOLOGY
    ast.py
        Root ............. ordered top-level items; walkable generically
                            (parser ModuleRoot derives it)
        Leaf (abstract) ... a terminal's description of HOW its object is reached
          ConstantLeaf .... object inline             (const-fold license)
          ReferenceLeaf ... reach by key/navigation   (carries resolution slot)
          DeclarationLeaf . introduces a name         (registered; resolved against)
          AnonymousLeaf ... object built in place
          OpaqueLeaf ...... embedded-language content (oracle, on demand;
                            referenced BY TEXT for now -- open to offset+extent,
                            url, ...)

LEAF NATURE
    An AST describes; it is not the object. A leaf is a description of access:

        ConstantLeaf    value in hand            no lookup
        ReferenceLeaf   segments + slot          symbol-table resolve
        AnonymousLeaf   value built here         no lookup

    The slot lives on ReferenceLeaf alone -- only by-key access resolves.
    Slot: one compare=False, repr=False field, written once via
    object.__setattr__; identity and print stay pure.

DEPENDENCY DIRECTION
    parser_generator  <--  symbol  <--  parser/ (app), semantic/ (vocabulary)
       (engine)            (here)
    The engine has NO edge here. The application and the semantic unit derive
    DOWN into here. Arrows follow the pipeline.

NOT HERE
    Leaf KINDS specific to one language (parser/ derivations).
    The symbol table's resolved-access payload types (filled by the
    application; declared where the table is built).
