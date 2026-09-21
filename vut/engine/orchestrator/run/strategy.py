"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE STRATEGY -- when a directory's unit of work starts (O-15).

    CStrategy.run(unit_list, emit, budget) -> list[CDirDone]   the template
    CStrategy.may_start(index, running)    -> bool             the hook

The template walks the units in walk order. Before starting unit 'index'
it asks 'may_start(index, running)' -- 'running' is the set of indices
in flight -- and asks again each time a running unit ends. Units that
raise are the caller's business: 'run' is given a coroutine factory
that already guards them.

    CLinear     may_start = not running         one directory at a time
    CSuccessor  may_start = len(running) < 2    the next starts while the
                                                current still runs
    CParallel   may_start = True                all at once

The strategy decides WHEN a unit starts and nothing else: the budget
(O-12) bounds what stands at once, the unit (O-13) owns its directory.

TWO QUESTIONS, ONE OPTION (O-27). Beside 'when a directory starts'
stands 'which admissible node starts', and they are orthogonal -- the
measured gain lives in 'parallel' AND 'longest-first' together, so a
single enum holding both could not spell it. They are two enums,
'E_SchedulerTestRun_Strategy' and 'E_SchedulerTestRun_SelectionOrder',
and ONE command line option carries both as a comma list, because two
options would ask the user to hold a distinction the tool can resolve
for him:

    --strategy=parallel,longest-first
    --strategy=p,lf                     the same thing
______________________________________________________________________________
"""
import asyncio
from   enum import Enum


class CStrategy:
    """The template; a strategy overrides 'may_start'."""

    name = "strategy"

    def may_start(self, index, running):
        """
        RETURN: bool, True where the unit at 'index' (walk order) may
                start now, 'running' being the set of indices of units
                in flight.
        """
        raise NotImplementedError

    async def run(self, guarded_list):
        """
        RETURN: list[CDirDone], one per unit, in walk order.

        'guarded_list' holds one coroutine factory per unit; each
        answers a CDirDone and never raises.
        """
        done_list = [None] * len(guarded_list)
        running   = {}                          # index -> asyncio.Task
        index     = 0
        while index < len(guarded_list) or running:
            while index < len(guarded_list) \
                  and self.may_start(index, set(running)):
                running[index] = asyncio.ensure_future(
                                     guarded_list[index]())
                index += 1
            if not running: continue
            ended_set, _ = await asyncio.wait(
                               running.values(),
                               return_when=asyncio.FIRST_COMPLETED)
            for i in sorted(i for i, task in running.items()
                            if task in ended_set):
                done_list[i] = running.pop(i).result()
        return done_list


class CLinear(CStrategy):
    """One directory after another, in walk order."""
    name = "linear"

    def may_start(self, index, running):
        """RETURN: bool, True where nothing runs."""
        return not running


class CSuccessor(CStrategy):
    """The next directory starts while the current one still runs;
    the one after waits."""
    name = "successor"

    def may_start(self, index, running):
        """RETURN: bool, True where fewer than two units run."""
        return len(running) < 2


class CParallel(CStrategy):
    """Every directory at once; the budget alone bounds."""
    name = "parallel"

    def may_start(self, index, running):
        """RETURN: bool, always True."""
        return True


class E_SchedulerTestRun_Strategy(Enum):
    """WHEN a directory's unit of work starts."""
    LINEAR    = "linear"
    SUCCESSOR = "successor"
    PARALLEL  = "parallel"


class E_SchedulerTestRun_SelectionOrder(Enum):
    """WHICH of the admissible nodes starts, where more than one may."""
    LONGEST_FIRST  = "longest-first"
    PLAN_ORDER     = "plan-order"
    SHORTEST_FIRST = "shortest-first"
    NAME_SORTED    = "name-sorted"


STRATEGY_DB = {E_SchedulerTestRun_Strategy.LINEAR:    CLinear,
               E_SchedulerTestRun_Strategy.SUCCESSOR: CSuccessor,
               E_SchedulerTestRun_Strategy.PARALLEL:  CParallel}

class E_Criterion(Enum):
    """ONE COMPONENT of a lexicographic sort key. A selection order IS
    an ordered tuple of these, and adding a criterion is adding a
    member here plus one line in '_component_of' -- not editing the
    scheduler."""
    UNMEASURED_LAST  = "unmeasured-last"
    DURATION_DESC    = "duration-desc"
    DURATION_ASC     = "duration-asc"
    NAME_ASC         = "name-asc"
    PLAN_ORDER       = "plan-order"


#  A SELECTION ORDER IS A TUPLE OF CRITERIA, applied lexicographically.
#  PLAN_ORDER ENDS EVERY ONE OF THEM, so the choice is DETERMINISTIC:
#  two candidates of equal weight go in the order the plan states them,
#  and a run is never at the mercy of a dict.
#  UNMEASURED LAST (ruled, O-30). A node nobody has measured goes
#  AFTER every measured one under either duration order. The reason is
#  the VIEWER: the flow must visibly honour its priority from the first
#  line, so the reader sees the slowest known test first and is never
#  left asking why an unknown jumped the queue. That a late unknown may
#  become the tail is a cost paid once, on the first run, and never
#  again -- after it, the node is measured.
#
#  NAME_SORTED READS NO TRACE. Its key is the name and the plan, both
#  of which the tree states; so its order holds on every machine and
#  on every day, which is what '--deterministic' promises.
CRITERIA_DB = {
    E_SchedulerTestRun_SelectionOrder.LONGEST_FIRST:
        (E_Criterion.UNMEASURED_LAST, E_Criterion.DURATION_DESC,
         E_Criterion.PLAN_ORDER),
    E_SchedulerTestRun_SelectionOrder.SHORTEST_FIRST:
        (E_Criterion.UNMEASURED_LAST, E_Criterion.DURATION_ASC,
         E_Criterion.PLAN_ORDER),
    E_SchedulerTestRun_SelectionOrder.NAME_SORTED:
        (E_Criterion.NAME_ASC, E_Criterion.PLAN_ORDER),
    E_SchedulerTestRun_SelectionOrder.PLAN_ORDER:
        (E_Criterion.PLAN_ORDER,)}


def _component_of(criterion, index, name, weight):
    """
    RETURN: a comparable, THIS CRITERION'S contribution to the sort
            key of a candidate standing at 'index' in plan order and
            weighing 'weight' milliseconds -- None where nothing has
            measured it.

    SMALLER WINS, always: the selection takes the minimum key, so
    every criterion states itself as 'less is earlier' and no caller
    has to remember which way round a particular one runs.
    """
    if criterion is E_Criterion.PLAN_ORDER:       return index
    if criterion is E_Criterion.NAME_ASC:         return name
    if criterion is E_Criterion.UNMEASURED_LAST:  return weight is None
    if weight is None:                            return 0
    if criterion is E_Criterion.DURATION_DESC:    return -weight
    return weight


def sort_key_of(selection_order, weight_of):
    """
    RETURN: callable, (index, name) -> tuple, the lexicographic sort
            key of one candidate under this selection order. The
            caller takes the MINIMUM, or sorts ascending; both say the
            same thing.

    'weight_of'  name -> milliseconds last measured, or None where
                 nothing measured it. A NODE weighs its own run; a
                 DIRECTORY weighs the sum of its cases. ONE VOCABULARY,
                 BOTH LEVELS (O-28) -- 'longest first' means the same
                 sentence about a directory as about a test.
    """
    criteria = CRITERIA_DB.get(
                   selection_order,
                   CRITERIA_DB[
                       E_SchedulerTestRun_SelectionOrder.PLAN_ORDER])
    def key_of(pair):
        index, name = pair
        weight      = weight_of(name)
        return tuple(_component_of(criterion, index, name, weight)
                     for criterion in criteria)
    return key_of


#  DIRECTORIES ARE BUNDLED, AND CONSIDERED TOGETHER (O-28, O-29).
#  RULED: 'we bundle directories; slow directories first; in each
#  directory, slow test runs first'. PARALLEL was the wrong reading of
#  'together' -- it opens every directory at once, and the flow stops
#  reading as bundled. The RIGHT member is BUNDLED: open a further
#  directory only when the open ones cannot fill the budget -- a rule,
#  not a number. It is not built: 'CStrategy.run' wakes only when a
#  DIRECTORY ends, and BUNDLED must also wake when a SLOT frees.
#  Until it is, SUCCESSOR is the default: at most two directories open,
#  which is 'bundled' in the strongest existing sense and 'together' in
#  the weakest. MEASURED: 16.2 s at 16 jobs against 13.0 s ideal.
DEFAULT_STRATEGY = E_SchedulerTestRun_Strategy.SUCCESSOR
DEFAULT_SELECTION_ORDER = E_SchedulerTestRun_SelectionOrder.LONGEST_FIRST

#  THE SHORTHANDS SHARE ONE NAMESPACE, because the option's values are a
#  SET and no token says which enum it belongs to. So 'plan-order' is
#  'po' and never 'p' -- 'p' is 'parallel', and a token that could mean
#  either is a token that means nothing.
SHORTHAND_DB = {"l":  E_SchedulerTestRun_Strategy.LINEAR,
                "s":  E_SchedulerTestRun_Strategy.SUCCESSOR,
                "p":  E_SchedulerTestRun_Strategy.PARALLEL,
                "lf": E_SchedulerTestRun_SelectionOrder.LONGEST_FIRST,
                "po": E_SchedulerTestRun_SelectionOrder.PLAN_ORDER,
                "sf": E_SchedulerTestRun_SelectionOrder.SHORTEST_FIRST,
                "ns": E_SchedulerTestRun_SelectionOrder.NAME_SORTED}

#  '--deterministic' IS A SPEC, NOT A THIRD ENUM (O-30): it expands to
#  'linear,name-sorted' before 'words_of' ever sees it. RULED: content
#  in GOOD must be deterministic and depend SOLELY on the behaviour
#  under investigation; a test that records hwut's own flow says
#  '--deterministic' and the order it records is then a fact about the
#  tree and nothing else.
DETERMINISTIC_SPEC = "linear,name-sorted"

WORD_DB = dict(SHORTHAND_DB)
WORD_DB.update({member.value: member
                for enum in (E_SchedulerTestRun_Strategy,
                             E_SchedulerTestRun_SelectionOrder)
                for member in enum})


def strategy_of(strategy):
    """
    RETURN: CStrategy, an instance of the class this enum member names.

    Raises KeyError where the member is not a strategy.
    """
    return STRATEGY_DB[strategy]()


def words_of(spec):
    """
    RETURN: [0] E_SchedulerTestRun_Strategy, what '--strategy=' named,
                or DEFAULT_STRATEGY where it named no strategy.
            [1] E_SchedulerTestRun_SelectionOrder, likewise, or
                DEFAULT_SELECTION_ORDER.
            [2] None, where every token read.
                str, the REFUSAL otherwise: an unreadable token, or two
                tokens of one enum. The caller writes it and stops.

    ONE OPTION, TWO ENUMS, and the tokens may stand in either order:
    'p,lf' and 'longest-first,parallel' say the same thing. Each token
    is looked up in ONE shared namespace (see SHORTHAND_DB), so the
    user never states which question he is answering -- the word
    answers it.

    AN ENUM NAMED TWICE IS REFUSED, not last-wins:
    '--strategy=linear,parallel' is a contradiction the user can only
    have written by mistake, and a silent winner hides it.
    """
    chosen_db = {}
    for token in (word.strip() for word in spec.split(",")):
        if not token:
            return DEFAULT_STRATEGY, DEFAULT_SELECTION_ORDER, \
                   "'--strategy=%s': an empty word stands between the " \
                   "commas" % spec
        member = WORD_DB.get(token)
        if member is None:
            return DEFAULT_STRATEGY, DEFAULT_SELECTION_ORDER, \
                   "'--strategy=%s': '%s' names neither a strategy nor " \
                   "a selection order%s" \
                   % (spec, token, _did_you_mean(token))
        enum = type(member)
        if enum in chosen_db and chosen_db[enum] is not member:
            return DEFAULT_STRATEGY, DEFAULT_SELECTION_ORDER, \
                   "'--strategy=%s': '%s' and '%s' cannot both stand" \
                   % (spec, chosen_db[enum].value, member.value)
        chosen_db[enum] = member
    return (chosen_db.get(E_SchedulerTestRun_Strategy, DEFAULT_STRATEGY),
            chosen_db.get(E_SchedulerTestRun_SelectionOrder,
                          DEFAULT_SELECTION_ORDER),
            None)


def _did_you_mean(token):
    """
    RETURN: str, ' -- did you mean ...?' naming the vocabulary, always.
            The set is six words long; listing it beats guessing at it.
    """
    return " -- one of %s (short: %s)" \
           % (", ".join(member.value for enum in
                        (E_SchedulerTestRun_Strategy,
                         E_SchedulerTestRun_SelectionOrder)
                        for member in enum),
              ", ".join(sorted(SHORTHAND_DB)))
