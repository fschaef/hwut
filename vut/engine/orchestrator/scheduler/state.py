"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE STATE OF A PLAN UNDER EXECUTION -- who has ended, who may
         start now. A state machine and nothing else: it runs nothing,
         waits for nothing, and knows no clock.

The scheduler asks 'ready()' and is told which nodes MAY start; which
of them it starts, and in which order, is the scheduler's own judgement
(P-3). It reports back with 'started()' and 'ended()'.

    PENDING     not started; may or may not be ready
    RUNNING     started, not ended
    ENDED_GOOD  ended, the work stood
    ENDED_BAD   ended, the work did not stand -- a test's verdict is
                negative, a build broke, a session did not launch
    UNSUPPORTED terminal without running: a supporter ended BAD (P-5)
    MISDEP      terminal without running: the dependencies cannot be
                met (P-6) -- reported as FAILURE

A TERMINAL state satisfies an ordering link, whatever it says: the link
is ordering, not success (R-33), and a node that will never run must not
hold its dependants for ever.
______________________________________________________________________________
"""
from enum import Enum, auto

from ..plan.form import E_NodeKind


class E_NodeState(Enum):
    PENDING     = auto()
    RUNNING     = auto()
    ENDED_GOOD  = auto()
    ENDED_BAD   = auto()
    UNSUPPORTED = auto()
    MISDEP      = auto()


TERMINAL_SET = (E_NodeState.ENDED_GOOD, E_NodeState.ENDED_BAD,
                E_NodeState.UNSUPPORTED, E_NodeState.MISDEP)

FAILURE_SET  = (E_NodeState.ENDED_BAD, E_NodeState.UNSUPPORTED,
                E_NodeState.MISDEP)


class CPlanState:
    """The states of one plan's nodes, and the readiness rules over
    them. Construction settles the [MISDEP] nodes at once: they are
    terminal before anything runs."""

    def __init__(self, plan):
        """
        RETURN: CPlanState over 'plan', every node PENDING except the
                [MISDEP] ones, which stand terminal as MISDEP.
        """
        self.plan     = plan
        self.state_db = {}
        for node in plan:
            self.state_db[node.name()] = (E_NodeState.MISDEP
                                          if node.misdep_f
                                          else E_NodeState.PENDING)

    # -- reading -------------------------------------------------------
    def state(self, name):
        """
        RETURN: E_NodeState, the state of that node / None, where the
                name names no node of the plan.
        """
        return self.state_db.get(name)

    def running(self):
        """
        RETURN: tuple of str, the names now RUNNING, in plan order.
        """
        return tuple(node.name() for node in self.plan
                     if self.state_db[node.name()] is E_NodeState.RUNNING)

    def done_f(self):
        """
        RETURN: bool, True where every node stands terminal -- nothing
                is running and nothing can still start.
        """
        return all(state in TERMINAL_SET
                   for state in self.state_db.values())

    def stuck_f(self):
        """
        RETURN: bool, True where nothing runs, nothing is ready, and
                nodes remain PENDING -- a state the construction laws
                of a plan make unreachable; asked so a scheduler need
                never spin.
        """
        return (not self.running()) and (not self.ready()) \
               and not self.done_f()

    def ready(self):
        """
        RETURN: tuple of str, every PENDING node that MAY start now, in
                plan order: its ordering sources stand terminal, its
                supporters ended GOOD, and no member of an exclusion set
                covering it is RUNNING.

        Which of them starts, and in which order, is the scheduler's
        own decision; this answer states admission, never choice.
        """
        return tuple(node.name() for node in self.plan
                     if self._ready_f(node))

    def failure_db(self):
        """
        RETURN: dict, name -> E_NodeState, every node whose state is a
                failure: ENDED_BAD, UNSUPPORTED or MISDEP. Empty where
                the run stood entirely.
        """
        return {name: state for name, state in self.state_db.items()
                if state in FAILURE_SET}

    # -- writing -------------------------------------------------------
    def started(self, name):
        """
        RETURN: None. Marks the node RUNNING.

        Raises AssertionError where the node is not PENDING, or is not
        ready -- a scheduler starting what may not start is a defect
        named here, not a riddle downstream.
        """
        node = self.plan.node(name)
        assert node is not None, "'%s' names no node of the plan" % name
        assert self.state_db[name] is E_NodeState.PENDING, \
               "'%s' is %s, not PENDING" \
               % (name, self.state_db[name].name)
        assert self._ready_f(node), \
               "'%s' is not ready to start" % name
        self.state_db[name] = E_NodeState.RUNNING

    def ended(self, name, good_f):
        """
        RETURN: tuple of str, the names driven terminal by this ending
                besides the node itself -- the TEST nodes left
                UNSUPPORTED where a BUILD or SESSION node ended BAD
                (P-5); empty else.

        Raises AssertionError where the node is not RUNNING.
        """
        assert self.state_db.get(name) is E_NodeState.RUNNING, \
               "'%s' is %s, not RUNNING" \
               % (name, self.state_db.get(name)
                        and self.state_db[name].name)
        self.state_db[name] = (E_NodeState.ENDED_GOOD if good_f
                               else E_NodeState.ENDED_BAD)
        if good_f: return ()

        node = self.plan.node(name)
        if node.kind is E_NodeKind.TEST: return ()

        unsupported = []
        for target in self.plan.supports_db.get(name, ()):
            if self.state_db[target] is E_NodeState.PENDING:
                self.state_db[target] = E_NodeState.UNSUPPORTED
                unsupported.append(target)
        return tuple(unsupported)

    def session_spent_f(self, name):
        """
        RETURN: bool, True where the SESSION node stands terminal and
                every TEST node it supports stands terminal too -- the
                session has nothing left to serve and may be closed.

        False for a node that is not a SESSION node.
        """
        node = self.plan.node(name)
        if node is None or node.kind is not E_NodeKind.SESSION:
            return False
        if self.state_db[name] not in TERMINAL_SET: return False
        return all(self.state_db[target] in TERMINAL_SET
                   for target in self.plan.supports_db.get(name, ()))

    # -- the rules -----------------------------------------------------
    def _ready_f(self, node):
        """
        RETURN: bool, True where the PENDING node may start now.
        """
        name = node.name()
        if self.state_db[name] is not E_NodeState.PENDING: return False

        for source in self.plan.before_db.get(name, ()):
            if self.state_db[source] not in TERMINAL_SET: return False

        for supporter in self.plan.supporter_db.get(name, ()):
            if self.state_db[supporter] is not E_NodeState.ENDED_GOOD:
                return False

        for exclusion in self.plan.exclusion_sets_of(name):
            for other in self.plan:
                if other.name() == name:              continue
                if not exclusion.covers(other):       continue
                if self.state_db[other.name()] is E_NodeState.RUNNING:
                    return False
        return True
