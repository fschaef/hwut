SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
===============================================================================
core/symbol  --  the general AST vocabulary: Node / NodeList / Leaf, the
                 leaf kinds, and the recipe slot the semantic unit writes.
===============================================================================

TOPOLOGY
-------------------------------------------------------------------------------

    Node (abstract base)
      |
      +-- NodeList                   uniform STAR/PLUS product
      +-- Leaf (base: 'begin' offset)
      |     +-- ConstantLeaf         object inline (text + ConstantKind)
      |     +-- ReferenceLeaf        object reached by key ('_access' slot)
      |     +-- DeclarationLeaf      introduces a name
      |     +-- AnonymousLeaf        object built in place
      |     +-- LeftFolding          left-grouping operator sequence
      |     +-- RightFolding         right-grouping operator sequence
      |
    Root                             ordered top-level items (walk entry)
    MutableBranch                    placeholder, not yet designed
    ConstantKind                     marker base for a ConstantLeaf's kind

THE PARTS  (all in ast.py)
-------------------------------------------------------------------------------

    Node            The abstract base of every AST product; a factory's
                    output IS-A Node, always. Carries nothing.
    NodeList        The uniform product of a STAR or PLUS rule: the item
                    products in match order. Iterable, indexable, sized,
                    falsey when empty. Empty for a STAR that matched
                    nothing; never empty for a PLUS.
    Leaf            A terminal's place in the tree: a description of HOW
                    the object it stands for is accessed. Fixes 'begin',
                    the absolute source offset.
    ConstantLeaf    The object is inline. 'text' is the verbatim lexeme;
                    'kind' is a ConstantKind carried from the terminal.
                    Interpretation to a machine value is the static
                    layer's job. Factory: from_text(text, kind, begin).
    ReferenceLeaf   The object is reached by key. 'segments' is the
                    dotted name as written, head first. '_access' is the
                    recipe slot: empty at construction, seated once by
                    resolve(access); the 'access' property answers the
                    seated recipe, None while unresolved.
    DeclarationLeaf Introduces a name. 'segments' as written. No recipe
                    slot: a declaration is resolved against, never
                    resolved.
    AnonymousLeaf   The object is built in place; 'value' is the
                    constructed description. Names nothing outside
                    itself.
    LeftFolding     A same-precedence operator sequence grouping left:
                    'head' plus 'star', the engine's STAR_Node mounted,
                    each item an (op_token, operand) pair in source
                    order. Associativity is the node's type identity.
    RightFolding    The dual: same shape, right grouping. Not produced by
                    the current ladders.
    Root            A mutable ordered list of top-level items; the
                    generic walk entry. The application derives its own
                    root type.
    ConstantKind    Marker base; the application defines the concrete
                    kind set. core carries a kind and never inspects it.

HOW TO RUN / TEST
-------------------------------------------------------------------------------

No TEST directory here. The vocabulary is exercised through
../parser_generator/TEST (the map family produces NodeList) and
../../language/TEST (typed products and recipes).

POINTERS
-------------------------------------------------------------------------------

    ../README.txt                        core overview
    ../parser_generator/README.txt       STAR_Node/NodeAbsent, the map
                                         family producing NodeList
    ../../language/README.txt            the application vocabulary
                                         derived from these bases
