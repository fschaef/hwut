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
    #  A strategy whose answer can CHANGE when a slot comes free inside
    #  an open directory says so, and 'run' then wakes on the budget as
    #  well as on a unit's ending (intend 20). The others' answers
    #  depend on the set of open units alone.
    wakes_on_budget_f = False

    def bind(self, budget, unit_list):
        """
        RETURN: None. Hands the strategy the run's budget and its units
                in start order, once, before 'run'. A strategy that
                needs neither ignores the call.
        """
        self.budget    = budget
        self.unit_list = unit_list

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
            #  THE WAIT ENDS ON A UNIT'S ENDING -- or, where the
            #  strategy asks, on a slot given back to the budget: a
            #  BUNDLED answer moves when a directory's own work runs
            #  dry, and no unit ends then.
            wait_list = list(running.values())
            changed   = None
            if self.wakes_on_budget_f:
                changed = self.budget.changed()
                wait_list.append(changed)
            ended_set, _ = await asyncio.wait(
                               wait_list,
                               return_when=asyncio.FIRST_COMPLETED)
            if changed is not None:
                changed.cancel()
                ended_set.discard(changed)
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


class CBundled(CStrategy):
    """Open a further directory ONLY where the open ones cannot fill
    the budget (intend 20): with 'b' free slots and 'r' nodes the open
    units could start now, the next unit starts exactly when r < b.
    A rule, not a number: how many directories stand open is what the
    tree needs at that instant, and nothing else."""
    name = "bundled"
    wakes_on_budget_f = True

    def may_start(self, index, running):
        """
        RETURN: bool, True where nothing runs, where the budget is
                unbounded, or where the open units together could
                start fewer nodes than there are free slots.

        A unit whose Scheduler does not stand yet answers None to
        'ready_n' and is taken to fill the budget on its own: opening
        beside a unit that has not spoken would open the whole tree
        in one pass.
        """
        if not running: return True
        limit = self.budget.limit
        if limit is None: return True
        free_n  = limit - self.budget.held_n
        ready_n = 0
        for i in running:
            n = self.unit_list[i].ready_n()
            if n is None: return False
            ready_n += n
        return ready_n < free_n


class E_SchedulerTestRun_Strategy(Enum):
    """WHEN a directory's unit of work starts."""
    LINEAR    = "linear"
    SUCCESSOR = "successor"
    PARALLEL  = "parallel"
    BUNDLED   = "bundled"


class E_SchedulerTestRun_SelectionOrder(Enum):
    """WHICH of the admissible nodes starts, where more than one may."""
    LONGEST_FIRST  = "longest-first"
    PLAN_ORDER     = "plan-order"
    SHORTEST_FIRST = "shortest-first"
    NAME_SORTED    = "name-sorted"


STRATEGY_DB = {E_SchedulerTestRun_Strategy.LINEAR:    CLinear,
               E_SchedulerTestRun_Strategy.SUCCESSOR: CSuccessor,
               E_SchedulerTestRun_Strategy.PARALLEL:  CParallel,
               E_SchedulerTestRun_Strategy.BUNDLED:   CBundled}

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
    #  THE APPLICATION LEVEL (O-32): an application weighs the sum of
    #  its choices and its choices go TOGETHER. These three stand in
    #  front of the node criteria, so the slowest application comes
    #  first and, inside it, its slowest choice.
    APP_UNMEASURED_LAST = "app-unmeasured-last"
    APP_DURATION_DESC   = "app-duration-desc"
    APP_DURATION_ASC    = "app-duration-asc"
    APP_TOGETHER        = "app-together"


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
        (E_Criterion.APP_UNMEASURED_LAST, E_Criterion.APP_DURATION_DESC,
         E_Criterion.APP_TOGETHER,
         E_Criterion.UNMEASURED_LAST, E_Criterion.DURATION_DESC,
         E_Criterion.PLAN_ORDER),
    E_SchedulerTestRun_SelectionOrder.SHORTEST_FIRST:
        (E_Criterion.APP_UNMEASURED_LAST, E_Criterion.APP_DURATION_ASC,
         E_Criterion.APP_TOGETHER,
         E_Criterion.UNMEASURED_LAST, E_Criterion.DURATION_ASC,
         E_Criterion.PLAN_ORDER),
    E_SchedulerTestRun_SelectionOrder.NAME_SORTED:
        (E_Criterion.NAME_ASC, E_Criterion.PLAN_ORDER),
    E_SchedulerTestRun_SelectionOrder.PLAN_ORDER:
        (E_Criterion.PLAN_ORDER,)}


def _component_of(criterion, index, name, weight, app):
    """
    RETURN: a comparable, THIS CRITERION'S contribution to the sort
            key of a candidate standing at 'index' in plan order and
            weighing 'weight' milliseconds -- None where nothing has
            measured it. 'app' is the candidate's APPLICATION as
            (weight, first index): the sum of its choices, or None
            where none is measured, and where the application first
            stands in the plan.

    SMALLER WINS, always: the selection takes the minimum key, so
    every criterion states itself as 'less is earlier' and no caller
    has to remember which way round a particular one runs.
    """
    if criterion is E_Criterion.PLAN_ORDER:       return index
    if criterion is E_Criterion.NAME_ASC:         return name
    if criterion is E_Criterion.UNMEASURED_LAST:  return weight is None
    if criterion is E_Criterion.APP_TOGETHER:     return app[1]
    if criterion is E_Criterion.APP_UNMEASURED_LAST:
        return app[0] is None
    if criterion is E_Criterion.APP_DURATION_DESC:
        return 0 if app[0] is None else -app[0]
    if criterion is E_Criterion.APP_DURATION_ASC:
        return 0 if app[0] is None else app[0]
    if weight is None:                            return 0
    if criterion is E_Criterion.DURATION_DESC:    return -weight
    return weight


def applications_of(plan, duration_db):
    """
    RETURN: dict, node name -> (weight, first index) of the node's
            APPLICATION (O-32): the sum of the measured durations of
            every node spelt 'app choice' with the same 'app', None
            where none is measured, and the plan index where the
            application first stands. A node whose name bears no
            choice is its own application.

    'plan' yields nodes answering 'name()'; 'duration_db' is name ->
    milliseconds, as 'traces.duration_db_of' spells it.
    """
    first_db, sum_db = {}, {}
    name_list = [node.name() for node in plan]
    for index, name in enumerate(name_list):
        app = name.split(" ", 1)[0]
        first_db.setdefault(app, index)
        weight = duration_db.get(name)
        if weight is not None:
            sum_db[app] = sum_db.get(app, 0) + weight
    return {name: (sum_db.get(name.split(" ", 1)[0]),
                   first_db[name.split(" ", 1)[0]])
            for name in name_list}


def sort_key_of(selection_order, weight_of, app_of=None):
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
    'app_of'     (index, name) -> (weight, first index) of the
                 candidate's APPLICATION (O-32): the sum of its
                 measured choices, or None where none is, and where it
                 first stands in the plan. None where a candidate is
                 its own application -- a directory -- and the level
                 collapses onto the candidate itself.
    """
    criteria = CRITERIA_DB.get(
                   selection_order,
                   CRITERIA_DB[
                       E_SchedulerTestRun_SelectionOrder.PLAN_ORDER])
    def key_of(pair):
        index, name = pair
        weight      = weight_of(name)
        app         = (weight, index) if app_of is None else app_of(pair)
        return tuple(_component_of(criterion, index, name, weight, app)
                     for criterion in criteria)
    return key_of


#  DIRECTORIES ARE BUNDLED, AND CONSIDERED TOGETHER (O-28, O-29).
#  RULED: 'we bundle directories; slow directories first; in each
#  directory, slow test runs first'. PARALLEL was the wrong reading of
#  'together' -- it opens every directory at once, and the flow stops
#  reading as bundled. The RIGHT member is BUNDLED: open a further
#  directory only when the open ones cannot fill the budget -- a rule,
#  not a number. BUILT (intend 20): 'CBundled' asks the open units
#  what they could start and wakes on the budget as well as on a unit's
#  ending. NOT YET THE DEFAULT: moving the default moves every
#  flow-subject nominal, and the move is a ruling of its own. Until
#  then SUCCESSOR stands: at most two directories open, which is
#  'bundled' in the strongest earlier sense. MEASURED (O-29): 16.2 s
#  at 16 jobs against 13.0 s ideal.
DEFAULT_STRATEGY = E_SchedulerTestRun_Strategy.SUCCESSOR
DEFAULT_SELECTION_ORDER = E_SchedulerTestRun_SelectionOrder.LONGEST_FIRST

#  THE SHORTHANDS SHARE ONE NAMESPACE, because the option's values are a
#  SET and no token says which enum it belongs to. So 'plan-order' is
#  'po' and never 'p' -- 'p' is 'parallel', and a token that could mean
#  either is a token that means nothing.
SHORTHAND_DB = {"l":  E_SchedulerTestRun_Strategy.LINEAR,
                "s":  E_SchedulerTestRun_Strategy.SUCCESSOR,
                "p":  E_SchedulerTestRun_Strategy.PARALLEL,
                "b":  E_SchedulerTestRun_Strategy.BUNDLED,
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
