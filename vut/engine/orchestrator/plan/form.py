"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE TEST PLAN -- the formal data structure that determination
         emits and the scheduler obeys. Nouns only; no policy.

A plan states CONSTRAINTS and ADMISSIONS, never a total order:

    nodes            the work: TEST, BUILD, SESSION
    ordering links   'x -> y': x runs to completion before y starts;
                     no verdict enters (R-33)
    supports links   'w ==> t': w broken, t FAILS -- the verdict-carrying
                     link (build ==> test, session ==> test)
    exclusion sets   members may not stand at once; a member names an
                     application or one choice (target form, R-34)

The scheduler decides at run time what to dispatch out of the remaining
satisfied work. A [MISDEP] node is never dispatched and is reported as
FAILURE. Every construction law below is enforced at the door; a plan
that violates one never comes into being.
______________________________________________________________________________
"""
from dataclasses import dataclass, field
from enum        import Enum, auto


class E_NodeKind(Enum):
    TEST    = auto()   # one (file, choice) call
    BUILD   = auto()   # one build action, from test_run's multi-builder
    SESSION = auto()   # one interactive application call (R-46)


class E_Provenance(Enum):
    NAMED   = auto()   # the wish named it
    IMPLIED = auto()   # implication closure over 'dependency' added it


class E_LinkKind(Enum):
    ORDERING = auto()  # test -> test: run-to-completion order, no verdict
    SUPPORTS = auto()  # work ==> test: supporter broken, supported FAILS


@dataclass(frozen=True, slots=True)
class CPlanNode:
    """One node of the plan. 'kind' says which fields carry meaning:

        TEST     file, choice ('None' for the choice-less application),
                 misdep_f, provenance, implied_by
        BUILD    action -- the build action's name
        SESSION  file -- the interactive application

    'payload' is the constructor's own object (a CTestCase, a build
    action record); the form never reads it and the printer never
    prints it. Construction goes through 'test()', 'build()' and
    'session()' alone.
    """
    kind:       E_NodeKind
    file:       str | None   = None
    choice:     str | None   = None
    action:     str | None   = None
    misdep_f:   bool         = False
    provenance: E_Provenance = E_Provenance.NAMED
    implied_by: str | None   = None
    payload:    object       = field(default=None, compare=False)

    @classmethod
    def test(cls, file, choice, misdep_f=False,
             provenance=E_Provenance.NAMED, implied_by=None, payload=None):
        """
        RETURN: CPlanNode, a TEST node for the call (file, choice) --
                'choice' is 'None' for the choice-less application.

        Raises AssertionError where 'implied_by' contradicts
        'provenance': an IMPLIED node names who required it; a NAMED
        node names nobody.
        """
        assert (provenance is E_Provenance.IMPLIED) == (implied_by is not None), \
               "TEST node '%s': provenance %s with implied_by %r" \
               % (file, provenance.name, implied_by)
        return cls(kind=E_NodeKind.TEST, file=file, choice=choice,
                   misdep_f=misdep_f, provenance=provenance,
                   implied_by=implied_by, payload=payload)

    @classmethod
    def build(cls, action, payload=None):
        """
        RETURN: CPlanNode, a BUILD node for the named build action.
        """
        return cls(kind=E_NodeKind.BUILD, action=action, payload=payload)

    @classmethod
    def session(cls, file, payload=None):
        """
        RETURN: CPlanNode, a SESSION node for the interactive
                application 'file'.
        """
        return cls(kind=E_NodeKind.SESSION, file=file, payload=payload)

    def name(self):
        """
        RETURN: str, the node's identity, unique per plan:

            TEST     'file' or 'file choice' -- the target form (R-34)
            BUILD    'build[action]'
            SESSION  'session[file]'
        """
        if self.kind is E_NodeKind.TEST:
            if self.choice is None: return self.file
            return "%s %s" % (self.file, self.choice)
        elif self.kind is E_NodeKind.BUILD:
            return "build[%s]" % self.action
        else:
            return "session[%s]" % self.file


@dataclass(frozen=True, slots=True)
class CPlanLink:
    """One link, source and target naming nodes of the plan.

    ORDERING: 'source' runs to completion before 'target' starts; the
    verdict of 'source' does not enter (R-33). SUPPORTS: 'source' is
    the BUILD or SESSION node whose failure FAILS the TEST node
    'target'."""
    kind:   E_LinkKind
    source: str
    target: str


@dataclass(frozen=True, slots=True)
class CExclusionSet:
    """Members that may not stand at once. A member is a target (R-34):
    'file' -- every choice of the file -- or 'file choice'."""
    member_tuple: tuple

    def covers(self, node):
        """
        RETURN: bool, True where 'node' is a TEST node named by one of
                the members -- by its call, or by its file alone.
        """
        return any(_member_covers(member, node)
                   for member in self.member_tuple)


class CTestPlan:
    """The plan: nodes, links, exclusion sets -- read-only after
    construction. Iteration yields nodes in construction order, which
    is the printer's order.

    Derived at construction, one tuple per name, deterministic:

        before_db     TEST name -> names that run to completion first
        supports_db   BUILD/SESSION name -> TEST names it supports
        supporter_db  TEST name -> BUILD/SESSION names supporting it
    """

    def __init__(self, node_list, link_list=(), exclusion_list=()):
        """
        RETURN: CTestPlan over the given nodes, links and exclusion
                sets.

        Raises AssertionError, naming the offender, where a law is
        violated: (i) node names collide; (ii) a link endpoint names no
        node; (iii) an ORDERING link's endpoints are not both TEST;
        (iv) a SUPPORTS link's source is not BUILD or SESSION or its
        target is not TEST; (v) a SESSION supports a choice of another
        file; (vi) the ORDERING links carry a cycle -- resolved before
        the plan exists (R-35), asserted here; (vii) an ORDERING link
        leaves a [MISDEP] node for a non-[MISDEP] node -- the R-35
        closure violated; (viii) an exclusion member covers no TEST
        node of the plan.
        """
        self.node_tuple      = tuple(node_list)
        self.link_tuple      = tuple(link_list)
        self.exclusion_tuple = tuple(exclusion_list)

        self.node_db = {}
        for node in self.node_tuple:
            name = node.name()
            assert name not in self.node_db, \
                   "two nodes named '%s'" % name
            self.node_db[name] = node

        before_db    = {}
        supports_db  = {}
        supporter_db = {}
        for link in self.link_tuple:
            source = self.node_db.get(link.source)
            target = self.node_db.get(link.target)
            assert source is not None, \
                   "link source '%s' names no node" % link.source
            assert target is not None, \
                   "link target '%s' names no node" % link.target
            if link.kind is E_LinkKind.ORDERING:
                assert source.kind is E_NodeKind.TEST \
                       and target.kind is E_NodeKind.TEST, \
                       "ordering link '%s -> %s': both ends must be " \
                       "TEST nodes" % (link.source, link.target)
                assert (not source.misdep_f) or target.misdep_f, \
                       "'%s' [MISDEP] -> '%s' without [MISDEP]: the " \
                       "R-35 closure is violated" \
                       % (link.source, link.target)
                before_db.setdefault(link.target, []).append(link.source)
            else:
                assert source.kind in (E_NodeKind.BUILD,
                                       E_NodeKind.SESSION), \
                       "supports link '%s ==> %s': source must be a " \
                       "BUILD or SESSION node" % (link.source, link.target)
                assert target.kind is E_NodeKind.TEST, \
                       "supports link '%s ==> %s': target must be a " \
                       "TEST node" % (link.source, link.target)
                assert source.kind is not E_NodeKind.SESSION \
                       or source.file == target.file, \
                       "'%s' supports '%s': a session serves the " \
                       "choices of its own file alone" \
                       % (link.source, link.target)
                supports_db.setdefault(link.source, []).append(link.target)
                supporter_db.setdefault(link.target, []).append(link.source)

        self.before_db    = {k: tuple(v) for k, v in before_db.items()}
        self.supports_db  = {k: tuple(v) for k, v in supports_db.items()}
        self.supporter_db = {k: tuple(v) for k, v in supporter_db.items()}

        cycle = _find_ordering_cycle(self.node_db, self.before_db)
        assert cycle is None, \
               "ordering links carry a cycle: %s -- resolved before " \
               "the plan exists (R-35)" % " -> ".join(cycle)

        for exclusion in self.exclusion_tuple:
            for member in exclusion.member_tuple:
                assert any(_member_covers(member, node)
                           for node in self.node_tuple), \
                       "exclusion member '%s' covers no TEST node of " \
                       "the plan" % member

    def __iter__(self):
        """YIELD: [0] CPlanNode  one node, in construction order."""
        yield from self.node_tuple

    def __len__(self):
        """RETURN: int, the number of nodes."""
        return len(self.node_tuple)

    def node(self, name):
        """
        RETURN: CPlanNode, the node of that name if present /
                None, else.
        """
        return self.node_db.get(name)

    def exclusion_sets_of(self, name):
        """
        RETURN: tuple of CExclusionSet, every exclusion set covering
                the node of that name -- empty where none does or the
                name names no node.
        """
        node = self.node_db.get(name)
        if node is None: return ()
        return tuple(x for x in self.exclusion_tuple if x.covers(node))


def _member_covers(member, node):
    """
    RETURN: bool, True where the target 'member' names the TEST node
            'node' -- by its call ('file choice'), or by its file alone
            (every choice of the file, R-34).
    """
    if node.kind is not E_NodeKind.TEST: return False
    return member == node.name() or member == node.file


def _find_ordering_cycle(node_db, before_db):
    """
    RETURN: list of str, the names of one cycle -- first name repeated
            last, in LINK direction ('x -> y': x before y) -- if the
            ordering links carry one / None, else.

    Iterative depth-first walk over 'before' edges; three colours; the
    found cycle is reversed into link direction.
    """
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {name: WHITE for name in node_db}
    for start in node_db:
        if colour[start] != WHITE: continue
        stack = [(start, iter(before_db.get(start, ())))]
        colour[start] = GREY
        path = [start]
        while stack:
            name, edge_iter = stack[-1]
            advanced = False
            for source in edge_iter:
                if colour[source] == GREY:
                    cycle = path[path.index(source):] + [source]
                    cycle.reverse()
                    return cycle
                if colour[source] == WHITE:
                    colour[source] = GREY
                    stack.append((source,
                                  iter(before_db.get(source, ()))))
                    path.append(source)
                    advanced = True
                    break
            if not advanced:
                colour[name] = BLACK
                stack.pop()
                path.pop()
    return None
