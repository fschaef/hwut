===============================================================================
REACTIVE RULE ENGINE  --  HWUT 2.0
SEMANTIC LAYER (PASS 2) ARCHITECTURE
===============================================================================

A name inserts the meaning it refers to when it is mentioned; meanings are
combined by operators. Take the rule cond/and:

    cond/and :=  <cond/not> ( ('and' | 'nand') <cond/not> )*

It produces an AST node when text like 'e.armed and sm.ready' appears. The node
holds three things: a left operand ('e.armed'), an operator ('and'), and a right
operand ('sm.ready'). The two operands are themselves names -- bare segment
chains the parser copied down verbatim. They mean nothing yet.

The semantic layer mentions each name and inserts what it refers to: 'e.armed'
resolves to a member of the firing event's symbol, 'sm.ready' to a member of the
enclosing aggregate's symbol. Now the 'and' node combines two MEANINGS, not two
spellings -- two booleans whose kinds the check can verify. Restructuring the
tree into meaning is exactly this, node by node: resolve the operands, and the
operator that joined their spellings now joins their referents.

VOCABULARY  (house terms this layer assumes; the owning doc is cited)
  OPAQUE SPAN   The '{ ... }' embedded target-language text the control plane
                does NOT parse (parser-core README). Pass 2 sees only the names
                referenced inside it, never the code.
  ORACLE        The SpanOracle (world/span_oracle.py): the abstract boundary
                that measures an opaque span and, on demand, collects the
                Reference names inside it. The ONE external dependency; a source
                with no spans never calls it.
  PSEUDO-SYMBOL One of e / sm / mg / m (and cw): a binding the resolver seats
                ITSELF, never user-declared. They resolve FIRST; declaring any
                of their spellings is fatal [NAME] (F-1).
  STACKLESS     A house rule, not an algorithm property: every walk uses an
                explicit work-list, never interpreter recursion, so depth is
                bounded by memory not the stack (as the parser driver is).
  REGIME (A)/(B) The two name-ordering rules (D), NOT the section letters.
                (A) = strict define-before-use; (B) = declare-before-use with
                bounded-forward definition. Read "(A)-strict" / "(B)-forward".

        AST
     from parser
         |
         v
    .----------.   scope   .-----------.  refs   .--------------.
    | ScopeGen |---------->| Resolver  |-------->| Checks       |
    | +Modules |  symbols  | (A)/(B)   |  Symbol | F-2..F-13    |
    '----------'           '-----------'  map    '--------------'
         |                       ^                       |
    import mounts          pseudo-symbols                v
    (asymmetric graft)      e/sm/mg/m/cw            .-----------.
                                                    | Cascade   |
                                                    | DFS       |
                                                    '-----------'
                                                         |
                                                         v
                                                   ResolvedProgram
                                                     (frozen)

Four stages run in dependency order behind one hard gate each: ALL modules
PARSED, then the scope tree built, then references resolved and the F-checks
run, then the cascade proven acyclic. A stage that emits an error stops the
pipeline after reporting; later stages over broken input are suppressed. All
diagnostics accumulate WITHIN a stage; there is no numeric cap.

-------------------------------------------------------------------------------
RUNNING A RESOLUTION
-------------------------------------------------------------------------------

from vut.engine.temporal_logic.semantic.resolve       import resolve_program
from vut.engine.temporal_logic.parser.core.diagnostic import DiagnosticReporter

reporter = DiagnosticReporter()
program  = resolve_program(root_source, oracle, loader, reporter)

Arguments:

    root_source   the top-level rule-file text, one str. Imports reach further
                  modules through the loader.
    oracle        the same world.span_oracle.SpanOracle the parser uses. Pass 2
                  calls it a SECOND time, through OpaqueCode.get_references, to
                  collect the names referenced inside opaque spans (the guard
                  read-only check reads them). A program with no opaque
                  references never makes the second call.
    loader        resolves an import path to module source text. Each module is
                  fetched once.
    reporter      a DiagnosticReporter shared with pass 1. Phase.SEMANTIC
                  diagnostics carry a class tag; 'resolve_program' does not
                  raise on an author error.

Returns:

    program       a ResolvedProgram on success; None when any stage gated. On a
                  gated stage the reporter holds the located errors:

    if reporter.has_fatal():
        ...                         # infrastructure failure (e.g. loader down)
    for d in reporter.errors:
        ...                         # d.phase, d.tag, d.message, d.source_offset

Two error worlds are distinct. A loader exception (the source cannot be
fetched) is INFRASTRUCTURE: it sets has_fatal and stops the load stage at once.
An author mistake (a cycle, an undefined name) is a located diagnostic the
author fixes; it never sets the infrastructure flag.

-------------------------------------------------------------------------------
(A) MODULES: SOURCE -> PARSED -> RESOLVED
-------------------------------------------------------------------------------

Any file is a MODULE. The module manager moves each module through three
states:

   -- SOURCE (text located through the loader)
   -- PARSED (lexed and parsed once -- parsing needs no resolution, so the
      cache holds this)
   -- RESOLVED.

Resolution is a WHOLE-PROGRAM phase: when every reachable module is PARSED,
they are resolved and connected in one step, not interleaved per import.

The load walk that reaches modules is itself a graph walk, and an IMPORT CYCLE
(A imports B imports A) is found here, before any scope tree exists -- a looping
load can never reach ALL-PARSED. An import cycle is FATAL-STOP for the load
stage, reported as one ordered chain; the pipeline does not advance to the
scope build. (Contrast the cascade cycle below, which accumulates every chain
and continues -- the two cycle checks have OPPOSITE recovery policies because a
load cycle leaves no remainder to continue over.)

An import MOUNTS one parsed module's tree under a namespace path in the
mounter ('import: "<file>" into: <path>'). The graft is ASYMMETRIC by tree
shape: the mounted module sees nothing of its mounter (inside it, "above" is its
own textual order alone); the mounter sees everything mounted as defined AT the
import line's position. A fresh subtree is grafted per mount. The links a mount
materialises seal the moment the graft completes -- an import is a complete
statement, never an opening bracket -- and a mount may not land on or pass
through a sealed scope.

ORDER WITHIN THE SCOPE STAGE. The graft needs a built, sealed donor: a module
is fully built and SEALED before any mount grafts onto it, and the graft itself
seals on completion. So the scope stage runs build-all, then graft-all, and
only then does resolution read the sealed forest. Resolution never observes a
half-built or still-open foreign tree; "one step" names the resolution, not the
build that precedes it.

-------------------------------------------------------------------------------
(B) THE SCOPE TREE AND SYMBOLS
-------------------------------------------------------------------------------

The scope tree carries the TYPE plane only. Scopes are opened by exactly four
kinds: GROUND (the file root), NAMESPACE, MODE GROUP, and STATE MACHINE. Modes
and states are SYMBOLS in their containing scope and open no scope of their own.
A clockwork's body is a scope of its own only for its 'cw' members (G).

A SYMBOL records {name, kind, params, offset}. 'kind' is the declared kind
(event, clock, variable, struct, cause-def, effect-def, mode, state, mode-group,
state-machine, container). 'params' is the declared-member list: a struct's
members, an event's fields, an aggregate's signature parameters. Parameters are
instance data on the symbol, NOT scope symbols -- 'Traffic.threshold' finds no
scope entry, only an object has a threshold. The params list is consulted by
exactly the binding checks (E).

WORKED EXAMPLE. The struct declaration

    Traffic(threshold: int; lane: int) is: struct

records ONE Symbol in its scope:

    Symbol(name   = "Traffic",
           kind   = "struct",
           params = [ ("threshold", "int"), ("lane", "int") ],   # ordered
           offset = <decl offset>)

'params' is a flat ordered list of (member-name, member-type) pairs -- a member
is a pair, NOT a nested Symbol and NOT a scope entry. So a TYPE-descent tail
('myTraffic.threshold', C) walks THIS list by member-name and stops at the leaf;
a SCOPE-descent lookup of 'Traffic.threshold' finds nothing in the scope tree,
which is exactly why it fails (D-4). An aggregate's params are its signature
parameters in the same shape; an event's are its typed fields. (One cheap check
at record time: a parameter may not share a spelling with a mode/state of the
same aggregate -- data in one breath, a state in the next, is a confusion.)

The build is STACKLESS (the house rule, VOCABULARY) over RuleFile.items: a
linear forward sweep, a work-list never the interpreter stack. SEAL LAW: a
namespace path opens
ONCE ('open: a.b ... :close' materialises a -> b and the close seals the whole
chain, 'a' included); a closed scope is FINAL and is never reopened. A reference
reaches names in its own scope and outward through its still-OPEN enclosers up
to the unit root; nesting IS the dependency. Mounts reach OTHER units.

-------------------------------------------------------------------------------
(C) HEAD RESOLUTION AND THE TWO DESCENT REGIMES
-------------------------------------------------------------------------------

Every reference outside an opaque span is a <name-dotted>: a dotted chain of
segments. The HEAD (first segment) resolves innermost-out through the open
enclosers. The four PSEUDO-SYMBOLS e / sm / mg / m (and cw, G) resolve FIRST;
declaring any of their spellings as a user symbol is fatal [NAME], so a binding
is never ambiguous.

The resolved head's class selects the TAIL descent, and the two regimes are
never unified:

    SCOPE descent   a namespace or aggregate head walks the scope tree (honours
                    mounts and the seal law).
    TYPE descent    a variable, struct, or pseudo-symbol head walks the params
                    member lists on the Symbol.

A chain may switch ONCE, scope -> type; a type segment never reopens scope
descent. A segment the legal descent cannot seat -- including a tail that tries
to switch BACK, type -> scope -- is an undefined name, fatal [NAME]. Depth
legality is resolution's; the parser admits any depth.

    head resolves                  one-way switch
    innermost-out                  (scope -> type)
         |                               |
         v          loop on a            v          loop on a
    .---------.     namespace/      .---------.     struct
    | SCOPE   |<--. aggregate seg   | TYPE    |<--. member seg
    | descent |---'                 | descent |---'
    '---------'-------------------->'---------'------> member leaf
         ^                                              (chain end)
         '-- type -> scope back-switch : FATAL [NAME] (no way back)

-------------------------------------------------------------------------------
(D) THE (A)/(B) REFERENCE RULE
-------------------------------------------------------------------------------

Two ordering regimes gate "is this name in scope yet". Every declarable kind
belongs to exactly one regime:

    (A) STRICT define-before-use -- fully defined above the reference:
            event        clock        variable
            struct       cause-def
        These leaves reference nothing, so loose ordering buys them nothing.
        Member cycles among (A) types are impossible BY CONSTRUCTION -- the
        ordering rule IS the check, no cycle detector.

    (B) DECLARE-before-use, bounded-forward definition -- declared above by
        name and kind (and signature where spawnable), body may follow in the
        same scope:
            mode                  aggregate member ('has:')
            arming target         spawn target           'is:' base
        An unmet (B) obligation DRAINS at the scope close, the diagnostic
        carrying the obligating REFERENCE's offset.

The (B) drain is the layer's quietest correctness boundary. A forward reference
whose body never arrives must surface AS AN ERROR at the close, not pass
silently -- a tolerated unknown name in a validation tool is a false PASS. The
drain queue is keyed by scope; the diagnostic points at the REFERENCE that made
the promise, not at the close that found it unkept.

-------------------------------------------------------------------------------
(E) THE CONSISTENCY CHECKS
-------------------------------------------------------------------------------

Each check owns one diagnostic class. The seven classes, and where each is
raised (the test suite carries one choice per class, J):

    NAME       undefined name; shadowed pseudo-symbol; bad descent (C); a
               member-or-VOID tail that names no member.
    KIND       kind-vs-shape on a declaration head; struct in a comparison;
               cross-resolution (emission <-> bundle); non-CLOCK clockwork
               trigger.
    BINDING    'e'/'sm'/'mg'/'m'/'cw' used where it is not in scope; a member
               on a memberless trigger.
    CASCADE    a cascade cycle; a system kind named as an emission.
    GUARD      a mutation inside a read-only guard or bracket condition.
    STRUCTURE  a shape the grammar admits but pass 2 refuses (e.g. a cause
               reference carrying '&', disc-3).
    SWEEP      a step kind forbidden in its sweep role (the one-sweep table, G).

The checks, by the construct they guard:

  KIND-VS-SHAPE on the shared declaration head: a signature is mandatory for
  mode-group / state-machine / struct, forbidden for mode / state / container /
  variable.

  PSEUDO-SYMBOL BINDINGS, checked against the params list (D):
    e   the firing trigger's event -- legal only where a named trigger (or a
        cause definition's 'for:') pins it; under ANY / BEGIN / CHANGE any
        'e.member' is fatal [BINDING] (memberless), under END only the system
        members 'run_time_sec' / 'event_n' are legal.
    sm / mg   the enclosing aggregate -- in scope only inside its own definition
        body, exactly one by kind.
    m   the enclosing mode/state instance -- unbound at top level.

  VARIABLES AND STRUCTS: variable initialisers are argument lists (a built-in
  takes one positional value; a struct binds against its member signature, every
  member receiving a value), evaluated in declaration order at bootstrap. Structs
  are (A)-strict; an undefined struct type is fatal [NAME].

  CONDITIONS: a bracket-condition leaf must resolve to a built-in scalar; a
  struct-valued comparison side is fatal [KIND]. A bare boolean reference (no
  comparison tail) must resolve to bool ('== true').

  CALLS: a free function 'name(args)' and a method '.name(args)' are checked
  against a per-receiver-type method catalogue (receiver type, arity, argument
  kinds, result type). An unknown method or wrong arity/kind is a pass-2 error.

  NAMED TAILS: cause-named parens -> cause reference, bare -> inline trigger;
  effect-named parens -> event emission, bare -> effect-bundle reference. A
  cross-resolution (emission name resolving to an effect bundle, or the reverse)
  is fatal [KIND].

  REF-MEMBER TAILS ('has:', 'default:'): the final segment is member-or-VOID
  against the resolved aggregate; 'default:' additionally requires a member state
  of the enclosing machine.

  'is:' BASES: each base resolves by (B) and its reactor CATEGORY is checked (a
  state-machine base resolves to a state-machine, a mode-group to a mode-group;
  cross-category fatal). Merge / override / linearisation semantics are not
  assigned here.

  GUARD READ-ONLY LAW: an 'on: BEGIN' / 'on: END' guard, and a bracket
  condition, may not mutate. The check reads OpaqueCode.get_references against a
  mutating-builtin denylist; this is where the lazy reference collection (the
  second oracle call, RUNNING A RESOLUTION) is spent.

-------------------------------------------------------------------------------
(F) THE CASCADE GRAPH
-------------------------------------------------------------------------------

Nodes are event kinds; an edge X -> Y exists iff an X-triggered rule emits Y
(an EventSpec). Arming and spawning create no edges. Liveness is
over-approximated: every reactor's rules contribute their edges unconditionally.
A rule on ANY contributes its emission edges inbound from every node; 'until:'
causes contribute none. System-produced kinds (clock events, BEGIN, END, CHANGE)
carry outgoing edges but no rule-authored inbound edge; naming one as an emission
is a semantic error. CHANGE is delivered at the step boundary (the time axis),
so it adds no inbound cascade edge.

ANY cascade CYCLE is fatal [CASCADE] -- a cycle means an event kind re-fires
within one no-time cascade. Detection is a stackless coloured DFS, linear in
nodes plus edges; every back-edge is reported with its full event chain,
ACCUMULATE-AND-CONTINUE (unlike the import cycle, which stops the load stage).

-------------------------------------------------------------------------------
(G) CLOCKWORK CHECKS
-------------------------------------------------------------------------------

A clockwork's 'on:' target is a <cause> whose trigger must resolve to kind CLOCK
[KIND]. Its signature parameters are its instance members, read through 'cw' --
in scope only inside the clockwork's own body (the 'sm'/'mg' counterpart);
referencing 'cw' outside is fatal [BINDING], declaring 'cw' is fatal [NAME]. A
clockwork carries no 'is:' bases.

The imperative-construct fence is STRUCTURAL -- the grammar admits the
constructs only inside a clockwork body -- so pass 2 only ASSERTS it held. A
paced bare emission enters the cascade at a tick boundary; an 'instant:'
injection may land within a running no-time cascade; the clockwork itself is
never a cascade node. A 'wait:' / 'select:' branch binds 'e' for its guard and
co-temporal '=>' tail only; in an if:/elif:/while: control condition 'e' is not
in scope, so 'e.member' there is fatal [BINDING].

A 'do:' sweep reference carries the advisory role hint '<do-sweep(one-sweep)>'.
Pass 2 reads the role and looks it up in a FORBIDDEN-CONSTRUCT TABLE (role -> the
step kinds fatal in that role). The 'one-sweep' row (a body with no heartbeat)
forbids 'while:', a paced bare event, and 'wait:' / 'select:'; each forbidden
occurrence is a pass-2 error [SWEEP] against the step.

-------------------------------------------------------------------------------
(H) ResolvedProgram
-------------------------------------------------------------------------------

The emitter's ENTIRE input is one frozen dataclass:

    ast           the untouched RuleFile (nodes frozen; resolution is a sidecar).
    scope_tree    the scope tree with its symbols.
    resolutions   reference -> Symbol, keyed on node IDENTITY (id(node)), NOT on
                  the node as a dict key. The AST nodes are frozen dataclasses
                  with value equality: two textually identical references
                  ('e.temp' in two rules) compare EQUAL and would collide as
                  keys, yet they may resolve to different symbols. The frozen ast
                  in this same artefact keeps every node alive, so its id is
                  stable for the program's lifetime.
    mounts        the import grafts.
    cascade       the event-kind graph (cycle-free by the time this exists).
    queried       the event kinds the rules consume -- the set the emitter
                  generates tracer registration from (no hand-written watch).
    source_map    the diagnostics seed.

Resolution is a SIDECAR: the ast is never rewritten to carry resolved symbols.
The resolutions map is the one place a reference's meaning lives.

-------------------------------------------------------------------------------
(I) FILES
-------------------------------------------------------------------------------

    resolve.py        resolve_program() -- the public seam; the stage driver and
                      the gates.
    modules.py        the module manager: SOURCE / PARSED / RESOLVED states, the
                      parse-once cache, import mounting, the import-cycle chain.
    scope_tree.py     Scope (GROUND / namespace / mode-group / state-machine),
                      Symbol{name, kind, params, offset}, the stackless build,
                      the seal law.
    resolver.py       head innermost-out, the two descent regimes, the
                      pseudo-symbols, the (A)/(B) reference rule.
    checks.py         the F-set (E), the method catalogue, the guard read-only
                      law, the one-sweep forbidden table.
    cascade.py        the EventSpec edge graph and the coloured-DFS cycle check.
    program.py        the frozen ResolvedProgram dataclass.

FOUR STACKLESS WALKS, never one shared walker -- each carries its own re-entry
policy and unifying them silently corrupts output:
    load DFS         (modules.py)    import-cycle, fatal-stop
    scope build      (scope_tree.py) linear forward sweep, seal at close
    head resolution  (resolver.py)   upward chain, bounded by the unit root
    cascade DFS      (cascade.py)    coloured, accumulate-and-continue

IMPORTS DOWN, from two layers, and nothing of its own consumers:

    parser core/    the diagnostic spine (Phase, DiagnosticReporter) and the
                    parsed AST (RuleFile and its frozen nodes).
    world/          the neutral span vocabulary (SpanOracle, Reference) -- the
                    oracle this layer calls a second time (D-1), and the
                    Reference pairs it returns. The world is the language
                    authority; this layer names no target language.

The emitter consumes ResolvedProgram (world/emission.py, Emitter) -- the world
sits beside this layer at the language boundary, not below the parser. This
layer imports the parser and the world; it is imported by neither.

-------------------------------------------------------------------------------
(J) THE TEST SUITE (TEST/)
-------------------------------------------------------------------------------

Each test is an HWUT driver: '--hwut-info' lists choices; a choice's stdout is
compared byte-for-byte against its GOOD/ recording. One choice per diagnostic
class (NAME, KIND, BINDING, CASCADE, GUARD, STRUCTURE, SWEEP) plus positive
coverage; multi-file import fixtures exercise the mount graft, asymmetric
visibility, and the import-cycle chain.

THREE SPINE FIXTURES prove the resolution core before any F-check is written:
    -- a (B) forward reference whose body NEVER arrives: must error at the scope
       close, the diagnostic carrying the reference's offset.
    -- a (B) forward reference whose body arrives LATE but valid: must pass.
    -- two textually identical references resolving to DIFFERENT symbols: both
       present in 'resolutions', each correct (the id-keying proof, H).

-------------------------------------------------------------------------------
(K) AUTHOR FLAGS  (obligations not yet met in the code below)
-------------------------------------------------------------------------------

    Phase.SEMANTIC is an obligation on core diagnostic.py; the live Phase enum
    is LEXER / PARSER / ANALYZER. It is added beside them. The class tag is a
    core-neutral 'tag' slot on Diagnostic (string, defaulting None so existing
    lexer/parser call sites are untouched); this layer owns the enum of class
    names and stringifies into that slot -- core never learns the semantic
    vocabulary.

    The mutating-builtin denylist (the guard read-only law, E) and the method
    catalogue (E, CALLS) are both per-builtin fact TABLES the checker reads.
    Whether they are one table or two is an open item (DISCUSSIONS/todo-1).

    The whole pass-2 block is DESIGNED, not yet built (RATIONALE + this file
    are the design; the modules above are the target). Open design items live
    under DISCUSSIONS/: the method catalogue table (todo-1), the one-sweep
    table wiring (todo-2), the clockwork checks (todo-3), the 'as:' lvalue
    binding (disc-2), a cause reference carrying an extra guard (disc-3, fatal
    [STRUCTURE] until decided), and 'is:' merge/override/linearisation (disc-1,
    deferred to the runtime object model).
