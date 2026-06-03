==============================================================================
REACTIVE RULE ENGINE  --  HWUT 2.0
SEMANTIC LAYER ARCHITECTURE
===============================================================================

The semantic layer consumes the parser's Abstract Syntax Tree and produces a
symbol table: a tree of scopes that records every named entity and the scope it
lives in. On that table it resolves every name a rule file references and
checks the constraints the parser deferred. The parser stays a pure recognizer;
all resolution, include mounting, and cross-name checking happen here, over the
finished AST.

A name-bearing AST node is one of two kinds. A DEFINITION introduces a name:
Mode, ModeGroup, StateMachine, EventDef, ClockDef, the member State and Mode
inside an aggregate, and the 'as' instance of a Spawn. A REFERENCE names an
entity defined elsewhere: a Trigger names an event, a ModeArming and a Spawn
name a type, an Unspawn names an instance, a HasRef and a default name a member.
The layer collects definitions into the table, then resolves references against
it.

-------------------------------------------------------------------------------
(A) THE SCOPE TREE
-------------------------------------------------------------------------------

A SCOPE is a named region that owns a set of local names. Scopes nest, so each
scope except one has a parent; the one without a parent is the ROOT, the
implicit file-scope region that contains a rule file's top-level items. Every
construct that brackets declarations opens a child scope: an 'open ... close'
namespace, a mode group, and a state machine each open one. A mode group and a
state machine therefore are scopes as well as definitions -- the aggregate is a
name in its parent scope, and its members are names in the child scope it opens.

A SYMBOL is one definition recorded in a scope. It holds the defined name, the
AST node that defined it, that node's source offset, and a KIND tag (mode, mode
group, state machine, event, instance, member). A scope owns a single map from
name to symbol. Mode, mode group, state machine, event, and instance names all
share that one map, so two definitions of the same name in one scope collide
regardless of their kinds. The KIND tag is read only when a reference is
resolved, never when a definition is recorded.

The scope tree mirrors the AST's nesting:

    ROOT (file scope)
      |
      |-- world ............... opened by 'open world.europe'
      |     |
      |     +-- europe
      |           |-- Traffic ..... a state_machine; also a scope
      |           |     |-- RED ......... member state (symbol in Traffic)
      |           |     +-- GREEN ....... member state (symbol in Traffic)
      |           +-- north ....... a Spawn 'as' instance (symbol in europe)
      |
      +-- SIREN ............... an event (symbol in ROOT)

'open world.europe' nests two levels in one statement; it materializes the
chain world -> europe and places the namespace's items in europe, the deepest
link. The path from the root to a symbol, with the symbol's name appended,
spells the symbol's FULLY-QUALIFIED NAME: 'world.europe.Traffic.RED' names the
member state RED with nothing left implicit. A name written without that full
path is a BARE or PARTIALLY-QUALIFIED reference, meaningful only against a
current scope.

-------------------------------------------------------------------------------
(B) BUILDING THE TABLE  --  STACKLESS WALK
-------------------------------------------------------------------------------

The builder turns a RuleFile into a scope tree by one walk over the AST. The
walk is STACKLESS: it carries its pending work on an explicit heap stack of
(scope, item) pairs, not on the Python call stack, so build depth is bounded by
memory, not by the interpreter's recursion limit. The seed is the root scope
paired with each top-level item.

Each popped pair is dispatched on item kind:

    Namespace        materialize the dotted chain from the current scope to the
                     target child scope; push (target, item) for each nested
                     item.
    ModeGroup        record the aggregate symbol in the current scope; open its
                     child scope; push (child, member) for each inline member
                     and each has-ref.
    StateMachine     as ModeGroup; the default ref is held for pass (C).
    Mode (top-level) record the symbol in the current scope; open its child
                     scope for nested members.
    State, Mode      (members) record the member symbol in the aggregate's
                     child scope.
    EventDef         record the event symbol in the current scope.
    ClockDef         record the event symbol in the current scope, kind event.
    Spawn            record the 'as' instance symbol in the current scope when
                     'as' is present.
    Include          record a pending mount (mount path, file name, offset) on
                     the current scope for pass (D).
    Causality, ...   reference-only items; collected for pass (C), define
                     nothing.

Recording a symbol whose name already maps in the target scope is a COLLISION:
the diagnostic names the entity, the scope, and both source offsets. Unbounded
namespace nesting builds the way the parser parses it -- the depth that
overflows a recursive walker passes here.

-------------------------------------------------------------------------------
(C) RESOLVING A REFERENCE  --  INNERMOST-OUT LEXICAL SEARCH
-------------------------------------------------------------------------------

A reference is resolved against the scope at its site. A bare name is sought in
the site's own scope first; on a miss the search steps to the parent scope, and
again outward, stopping at the root of the reference's own unit. The first scope
whose map holds the name supplies the symbol; reaching the root without a hit is
an UNRESOLVED diagnostic.

A dotted reference 'Traffic.RED' resolves its HEAD segment 'Traffic' by that
same innermost-out search, then DESCENDS strictly: 'RED' is sought only in the
scope 'Traffic' opened, never by a further outward search. A miss on the head is
an unresolved diagnostic at the head; a miss on a tail segment is an unresolved
diagnostic at that segment. The tail never leaks into the lexical search.

Resolution carries the resolved symbol's KIND. A reference site expects a kind:
a Trigger expects an event, a ModeArming and a Spawn target expect a type, a
HasRef and a default expect a member, an Unspawn expects an instance. A name
that resolves to a symbol of another kind is a KIND-MISMATCH diagnostic distinct
from unresolved -- the name exists, but not as the site requires.

-------------------------------------------------------------------------------
(D) INCLUDE MOUNTING  --  PARSE-ONCE, BUILD-PER-MOUNT
-------------------------------------------------------------------------------

An Include records a request to mount another file's names at a chosen path. A
pending mount is resolved in three steps. First the file name resolves to a
file; its source is lexed and parsed to an AST, and that parse is CACHED by
resolved file path, so a file named by several includes is parsed once. Second
the cached AST is built into a FRESH scope tree by pass (B); each mount gets its
own tree, so every mounted symbol has one parent, one path, and one
fully-qualified name. Third that fresh tree's root is grafted as a child scope
at the mount path, the path materialized from the mounting scope exactly as a
namespace chain is.

The grafted root keeps no parent link across the graft. DESCENT crosses the
graft: from the mounting side, a dotted reference walks into the mounted subtree
and resolves its members. The outward LEXICAL SEARCH does not cross it: a
reference inside the mounted unit steps outward only to that unit's own root and
stops, never reaching the mounting scope. Visibility is asymmetric -- the
mounter sees every name under the mount path; the mounted unit sees only itself.

A mount whose resolution re-enters a file already being mounted on the current
chain is an INCLUDE CYCLE. The diagnostic prints the chain in order: the file
mounted first, the file it mounted, onward to the mount that re-enters the
in-progress file, each named with its mount-site offset.

-------------------------------------------------------------------------------
(E) THE CONSTRAINT CHECKS
-------------------------------------------------------------------------------

With the table built and references resolvable, the layer checks the
constraints the parser deferred:

    1. At most one init and one deinit per reactor or aggregate.
    2. State machine: at most one default; every member state's until-run ends
       with 'until switched'; the default target resolves to a member of that
       state machine or to VOID.
    3. Every mode-arming target and every spawn target resolves to a type;
       every has-ref and default target resolves to a member; every unspawn
       target resolves to an instance. VOID is the implicit member every
       aggregate owns; a reference to VOID resolves without a defining symbol.
    4. Each include resolves, parses once, builds a fresh tree, and mounts it;
       cycles are diagnosed (D).

The unspawn check is STATIC: the target must resolve to an instance symbol
introduced by some reachable Spawn 'as'. Whether that instance is live at the
unspawn's moment is a run-time question this layer does not answer.

-------------------------------------------------------------------------------
(F) THE TEST SUITE
-------------------------------------------------------------------------------

Each test is an HWUT driver: '--hwut-info' lists its choices, and running a
choice prints to stdout, compared byte-for-byte against a GOOD recording. The
printed output is the result under test -- the resolved fully-qualified name,
the scope tree, or the exact diagnostic text. A test prints what the resolver
produced; the recording is the oracle. No test prints a self-graded verdict.

    build-scope-tree    Feeds definition shapes; prints the scope tree with
                        each symbol's name, kind, and fully-qualified name.
    resolve-reference   Feeds a reference at a known site; prints the resolved
                        symbol's fully-qualified name and kind, or the
                        unresolved / kind-mismatch diagnostic.
    include-mount       Feeds a mounter and one or more included files; prints
                        the grafted tree and the asymmetric-visibility probes;
                        a cyclic set prints the ordered cycle chain.
    check-constraints   Feeds a rule file exercising one deferred constraint;
                        prints the diagnostic the check emits, or its silence.
