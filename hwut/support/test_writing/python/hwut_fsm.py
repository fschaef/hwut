"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: A STATE MACHINE AS A TEST'S MODEL OF THE SYSTEM UNDER TEST -- the
         states it may be in, the events that move it, the states it must
         never reach. A test, or a pype script between the application and
         the comparison, FIRES the events it observes; every event the model
         does not allow, and every forbidden state entered, is PRINTED as a
         line -- so it lands in the GOOD file and the comparison judges it.

    from hwut.test_writing_support.python.hwut_fsm import Machine

    m = Machine.from_string('''
        initial: idle
        forbidden: crashed
        idle    ---( request )---> waiting ---( grant )---> busy
        busy    ---( release )---> idle
        :       ---( fault )--->   crashed
    ''')
    m.fire("request", where=1)  # True
    m.fire("release", where=2)  # BREACH line 2: 'release' in 'waiting' -- allowed: grant
    m.report()                  # what was visited, what never was

NOT PYPE'S MODES. A pype script's modes are the READER's state: what it
expects to parse next. A Machine is the SYSTEM's: which transitions it may
make. A script parses with its modes and fires the events into a Machine.

DFA (the default): one current state; two transitions for one (state,
event) are refused where the model is read. DFA=False: the machine holds a
SET of states, as an event may lead to several; it moves every state that
has the event, and an event none of them has is the breach.

AN EVENT THE MODEL DOES NOT ALLOW IS SAID AND IGNORED: the machine stays
where it was, so one surprise reads as one line, not a cascade. A
FORBIDDEN STATE IS ENTERED -- it is what the system did -- and said.

THE LAW MAY CHANGE WHILE THE MACHINE RUNS (a phase): 'disallow'/'allow'
an event, in every state or one; 'forbid'/'permit' a state; 'disallowed()'
and 'forbidding()' for a block. A refused event says since when; the
model's questions answer under the masks unless 'masked=False'.

EVERY PRINTED REPORT IS SORTED and carries no time: what a test prints from
a Machine is the same on every run that observes the same events.
______________________________________________________________________________
"""
import re
from collections import deque


class FsmError(ValueError):
    """A model that cannot be meant -- named with its line where read from
    text. Raised where the model is read, never while events are fired."""


#  THE TEXT OF A MODEL (see 'Machine.from_string'):
#      initial: A            forbidden: X, Y           final: A, B
#      state A               (a state with no transition yet)
#      A ---( ev )---> B ---( ev2 )---> C              a chain
#      :  ---( ev )---> D                              ':' -- the state that
#                                                      began the line above
_ARROW_RE = re.compile(r"-+\s*\(\s*([^()]*?)\s*\)\s*-*>")
_NAME_RE  = re.compile(r"^(?:state\s+)?([A-Za-z_][\w.\-]*)$")
_KEY_RE   = re.compile(r"^(initial|forbidden|final)\s*:\s*(.*)$")


def _name_of(text, number):
    """
    RETURN: str, the state named by 'text' -- 'A' or 'state A' -- if
            success; raises FsmError naming line 'number', else.
    """
    found = _NAME_RE.match(text.strip())
    if found is None:
        raise FsmError("line %d: '%s' names no state -- a state is a word "
                       "('A', 'state A')" % (number, text.strip()))
    return found.group(1)


def _where_text(where):
    """
    RETURN: str, ' line 3' for the int 3, ' <text>' for a text, '' for
            None -- the place a breach line names.
    """
    if where is None:        return ""
    if isinstance(where, int): return " line %d" % where
    return " %s" % where


def _since_text(where):
    """
    RETURN: str, ' since line 9' for the int 9, ' since <text>' for a text,
            '' for None -- when a mask or a forbidden state began.
    """
    return "" if where is None else " since%s" % _where_text(where)


class Machine:
    """A state machine, its current state(s), and what was seen of it."""

    def __init__(self, transitions, initial, forbidden=(), final=(),
                 DFA=True, name="fsm", write=print, states=()):
        """
        RETURN: Machine, standing in 'initial', if success;
                raises FsmError, else -- a DFA with two transitions for
                one (state, event); an initial, forbidden or final state
                no transition names.

        'transitions' is an iterable of (state, event, state) triples;
        'states' names states no transition touches (yet). 'write' takes
        one line; every breach and report goes through it.
        """
        self.name      = name
        self.dfa_f     = bool(DFA)
        self.write     = write
        self._edge_db  = {}                 # (state, event) -> set(state)
        state_set = {initial} | set(states)
        for source, event, target in transitions:
            target_set = self._edge_db.setdefault((source, event), set())
            if self.dfa_f and target_set and target not in target_set:
                raise FsmError("'%s' --(%s)--> '%s' and '%s': a DFA moves "
                               "one way per event -- or 'DFA=False'"
                               % (source, event, sorted(target_set)[0], target))
            target_set.add(target)
            state_set.update((source, target))
        self.initial   = initial
        self.model_forbidden = frozenset(forbidden)
        self.final     = frozenset(final)
        for label, chosen in (("forbidden", self.model_forbidden),
                              ("final", self.final)):
            unknown = sorted(chosen - state_set)
            if unknown:
                raise FsmError("%s state(s) %s: named nowhere else in the "
                               "model" % (label, ", ".join("'%s'" % s
                                                           for s in unknown)))
        self.state_tuple = tuple(sorted(state_set | self.model_forbidden))
        self.event_tuple = tuple(sorted({e for _, e in self._edge_db}))
        self.reset()

    # ------------------------------------------------------------- reading
    @classmethod
    def from_string(cls, text, DFA=True, name="fsm", write=print):
        """
        RETURN: Machine, the model the text states, if success;
                raises FsmError naming the line, else.

        One statement per line; '#' starts a comment:
            initial: A              where the machine starts; default:
                                    the first state the text names
            forbidden: X, Y         states the system must never enter
            final: A, B             states it may end in ('report' says
                                    where it ended otherwise)
            state A                 a state, transitions or not
            A ---( ev )---> B ---( ev2 )---> C
                                    transitions, chained; an arrow is
                                    dashes, '( event )', dashes, '>'
            :  ---( ev )---> D      ':' is the state that began the line
                                    above
        """
        triple_list, declared = [], {}
        line_of = {}                        # (state, event) -> first line
        first, previous_head = None, None
        for number, raw in enumerate(text.splitlines(), start=1):
            line = raw.split("#", 1)[0].strip()
            if not line: continue
            key = _KEY_RE.match(line)
            if key is not None:
                word, rest = key.group(1), key.group(2)
                name_list = [_name_of(part, number)
                             for part in rest.split(",") if part.strip()]
                if word == "initial" and len(name_list) != 1:
                    raise FsmError("line %d: 'initial:' names one state"
                                   % number)
                declared.setdefault(word, []).extend(name_list)
                continue
            part_list = _ARROW_RE.split(line)
            #  [state, event, state, event, state ...]: odd places are events
            if len(part_list) == 1:
                head = _name_of(line, number)
                first = first or head
                triple_list.append((head, None, None))
                previous_head = head
                continue
            if any(not part_list[i].strip()
                   for i in range(1, len(part_list), 2)):
                raise FsmError("line %d: an arrow names no event -- "
                               "'---( event )--->'" % number)
            head_text = part_list[0].strip()
            if head_text == ":":
                if previous_head is None:
                    raise FsmError("line %d: ':' stands for the state of the "
                                   "line above, and none stands there" % number)
                head = previous_head
            else:
                head = _name_of(head_text, number)
            first, previous_head = first or head, head
            source = head
            for i in range(1, len(part_list), 2):
                target = _name_of(part_list[i + 1], number)
                event  = part_list[i].strip()
                #  THE DFA'S CONFLICT NAMED WHERE IT STANDS: both lines.
                if DFA and (source, event) in line_of \
                   and line_of[(source, event)][0] != target:
                    raise FsmError("line %d: '%s' --(%s)--> '%s', and line "
                                   "%d: --> '%s' -- a DFA moves one way per "
                                   "event, or 'DFA=False'"
                                   % (number, source, event, target,
                                      line_of[(source, event)][1],
                                      line_of[(source, event)][0]))
                line_of.setdefault((source, event), (target, number))
                triple_list.append((source, event, target))
                source = target
        if first is None and "initial" not in declared:
            raise FsmError("the model names no state")
        initial = (declared.get("initial") or [first])[0]
        return cls([t for t in triple_list if t[1] is not None], initial,
                   declared.get("forbidden", ()), declared.get("final", ()),
                   DFA=DFA, name=name, write=write,
                   states={t[0] for t in triple_list if t[1] is None})

    def to_string(self):
        """
        RETURN: str, the model in the text 'from_string' reads, one
                transition per line, sorted -- what a book page or a GOOD
                file can show of it.
        """
        line_list = ["initial: %s" % self.initial]
        if self.model_forbidden:
            line_list.append("forbidden: %s"
                             % ", ".join(sorted(self.model_forbidden)))
        if self.final:
            line_list.append("final: %s" % ", ".join(sorted(self.final)))
        named = {self.initial}
        for (source, event), target_set in sorted(self._edge_db.items()):
            for target in sorted(target_set):
                line_list.append("%s ---( %s )---> %s" % (source, event, target))
                named.update((source, target))
        line_list.extend("state %s" % s for s in self.state_tuple
                         if s not in named and s not in self.model_forbidden)
        return "\n".join(line_list)

    # ------------------------------------------------------------- running
    def reset(self):
        """RETURN: None. The machine stands in its initial state again, under
        the model as written: what was seen is forgotten, and so is every
        mask and every state forbidden or permitted since."""
        self._mask_db     = {}              # (state | None, event) -> since
        self._forbid_db   = {s: None for s in self.model_forbidden}  # -> since
        self._permit_db   = {}              # model-forbidden state -> since
        self._current     = frozenset((self.initial,))
        self._visit_db    = {self.initial: 1}
        self._taken_db    = {}              # (state, event, state) -> count
        self._trace_list  = []
        self.breach_n     = 0

    def fire(self, event, where=None):
        """
        RETURN: True,  'event' moved the machine (and entered no forbidden
                       state);
                False, it was not allowed where the machine stands -- a
                       BREACH line is written and the machine stays -- or
                       it entered a forbidden state, which is written too.

        'where' is the place the breach line names: an int is a line
        number ('line 3'), a text stands as written.
        """
        moved, masked = set(), []
        for state in sorted(self._current):
            if self._masked_f(state, event):
                if (state, event) in self._edge_db: masked.append(state)
                continue
            for target in sorted(self._edge_db.get((state, event), ())):
                moved.add(target)
                key = (state, event, target)
                self._taken_db[key] = self._taken_db.get(key, 0) + 1
                self._trace_list.append((where, state, event, target))
        if not moved:
            self.breach_n += 1
            hint = ("allowed: %s" % ", ".join(self.allowed())
                    if self.allowed() else "no event leaves it")
            if event not in self.event_tuple:
                hint = "an event the model never names"
            elif masked:
                hint = "disallowed%s" % _since_text(
                           self._mask_db.get((masked[0], event),
                                             self._mask_db.get((None, event))))
            self.write("BREACH%s: '%s' in %s -- %s"
                       % (_where_text(where), event, self._here(), hint))
            return False
        self._current = frozenset(moved)
        for state in moved:
            self._visit_db[state] = self._visit_db.get(state, 0) + 1
        entered = sorted(moved & self.forbidden)
        for state in entered:
            self.breach_n += 1
            self.write("BREACH%s: '%s' entered by '%s' -- %s"
                       % (_where_text(where), state, event,
                          "a forbidden state" if state in self.model_forbidden
                          and self._forbid_db[state] is None else
                          "forbidden%s" % _since_text(self._forbid_db[state])))
        return not entered

    # --------------------------------------------------- the law, changing
    @property
    def forbidden(self):
        """RETURN: frozenset of str, the states forbidden NOW -- the model's,
        less those permitted, with those forbidden since."""
        return frozenset(self._forbid_db)

    def _masked_f(self, state, event):
        """RETURN: bool, True if 'event' is disallowed in 'state' now -- in
        every state, or in that one."""
        return (None, event) in self._mask_db or (state, event) in self._mask_db

    def _known(self, event=None, state=None):
        """
        RETURN: None, if 'event' and 'state' are named by the model;
                raises FsmError naming what is not, else -- a mask over a
                word the model never names would guard nothing.
        """
        if event is not None and event not in self.event_tuple:
            raise FsmError("'%s': an event the model never names -- events: %s"
                           % (event, ", ".join(self.event_tuple)))
        if state is not None and state not in self.state_tuple:
            raise FsmError("'%s': a state the model never names -- states: %s"
                           % (state, ", ".join(self.state_tuple)))

    def disallow(self, event, state=None, where=None):
        """
        RETURN: None. From now on 'event' is a breach -- in 'state' alone,
                or in every state where None -- until 'allow' lifts it; the
                breach line says 'disallowed since <where>'.
                Raises FsmError where the model names no such event or state.
        """
        self._known(event, state)
        self._mask_db.setdefault((state, event), where)

    def allow(self, event, state=None, where=None):
        """
        RETURN: None. The mask 'disallow(event, state)' set is lifted; a
                mask set for another scope ('state' None or a state) stays.
                Raises FsmError where the model names no such event or state.
        """
        self._known(event, state)
        self._mask_db.pop((state, event), None)

    def forbid(self, state, where=None):
        """
        RETURN: None. From now on entering 'state' is a breach, until
                'permit'. Where the machine STANDS in it, one BREACH line is
                written at once: the test forbade the present.
                Raises FsmError where the model names no such state.
        """
        self._known(state=state)
        if state in self._forbid_db: return
        self._forbid_db[state] = where
        self._permit_db.pop(state, None)
        if state in self._current:
            self.breach_n += 1
            self.write("BREACH%s: stands in '%s' -- forbidden%s"
                       % (_where_text(where), state, _since_text(where)))

    def permit(self, state, where=None):
        """
        RETURN: None. 'state' is no longer forbidden -- a state of the
                model's own 'forbidden:' too, until 'forbid' again.
                Raises FsmError where the model names no such state.
        """
        self._known(state=state)
        if self._forbid_db.pop(state, "absent") != "absent" \
           and state in self.model_forbidden:
            self._permit_db[state] = where

    def disallowed(self, event, state=None, where=None):
        """
        RETURN: a context manager: 'event' disallowed (see 'disallow') for
                the block, allowed again on leaving it -- whatever way.
        """
        return _Phase(lambda: self.disallow(event, state, where),
                      lambda: self.allow(event, state))

    def forbidding(self, state, where=None):
        """
        RETURN: a context manager: 'state' forbidden (see 'forbid') for the
                block, permitted again on leaving it -- whatever way.
        """
        return _Phase(lambda: self.forbid(state, where),
                      lambda: self.permit(state))

    def _here(self):
        """RETURN: str, where the machine stands: "'idle'", or
        "{'a', 'b'}" for a set."""
        if len(self._current) == 1: return "'%s'" % next(iter(self._current))
        return "{%s}" % ", ".join("'%s'" % s for s in sorted(self._current))

    # ------------------------------------------------------------ questions
    @property
    def state(self):
        """
        RETURN: str, the one state the machine stands in, if success;
                raises FsmError, else -- a set of states stands (DFA=False):
                ask 'current()'.
        """
        if len(self._current) != 1:
            raise FsmError("the machine stands in %s: ask 'current()'"
                           % self._here())
        return next(iter(self._current))

    def current(self):
        """RETURN: frozenset of str, every state the machine stands in."""
        return self._current

    def in_state(self, state):
        """RETURN: bool, True if the machine stands in 'state'."""
        return state in self._current

    def can(self, event):
        """RETURN: bool, True if 'event' would move the machine now."""
        return any((s, event) in self._edge_db and not self._masked_f(s, event)
                   for s in self._current)

    def allowed(self):
        """RETURN: tuple of str, the events that would move the machine
        now, sorted."""
        return tuple(sorted({e for (s, e) in self._edge_db
                             if s in self._current
                             and not self._masked_f(s, e)}))

    def trace(self):
        """RETURN: tuple of (where, state, event, state), every transition
        fired, in order."""
        return tuple(self._trace_list)

    # ------------------------------------------------------ the model alone
    def _successor_db(self, masked=True):
        """RETURN: dict, state -> sorted list of (event, state) leaving it --
        under the masks where 'masked', as written else."""
        found = {}
        for (source, event), target_set in self._edge_db.items():
            if masked and self._masked_f(source, event): continue
            for target in target_set:
                found.setdefault(source, []).append((event, target))
        for pair_list in found.values(): pair_list.sort()
        return found

    def path_to(self, state, start=None, masked=True):
        """
        RETURN: tuple of str, the shortest sequence of events from 'start'
                -- the initial state where None, 'now' for where the
                machine stands -- into 'state', if one exists ('()' where
                'start' is 'state');
                None, else: 'state' cannot be reached from there.

        THE TESTER'S QUESTION: what must the system be told to get there.
        Among equally short paths, the one first in event order. Under the
        masks standing now; 'masked=False' asks the model as written.
        """
        if start == "now":    start_set = set(self._current)
        elif start is None:   start_set = {self.initial}
        else:                 start_set = {start}
        if state in start_set: return ()
        successor_db = self._successor_db(masked)
        queue = deque((s, ()) for s in sorted(start_set))
        seen  = set(start_set)
        while queue:
            here, path = queue.popleft()
            for event, target in successor_db.get(here, ()):
                if target in seen: continue
                if target == state: return path + (event,)
                seen.add(target)
                queue.append((target, path + (event,)))
        return None

    def state_reachable(self, state, start=None, masked=True):
        """RETURN: bool, True if 'state' can be reached from 'start' (see
        'path_to': the initial state where None, 'now' for the present;
        under the masks unless 'masked=False')."""
        return self.path_to(state, start, masked) is not None

    def _forbidden_of(self, masked):
        """RETURN: frozenset of str, the states forbidden now where
        'masked', the model's own else."""
        return self.forbidden if masked else self.model_forbidden

    def unreachable(self, masked=True):
        """RETURN: tuple of str, the states no path from the initial state
        reaches, forbidden ones left out -- sorted; under the masks unless
        'masked=False'."""
        forbidden = self._forbidden_of(masked)
        return tuple(s for s in self.state_tuple
                     if s not in forbidden
                     and not self.state_reachable(s, masked=masked))

    def dead_ends(self, masked=True):
        """RETURN: tuple of str, the states no event leaves that are neither
        final nor forbidden -- where a system would hang -- sorted; under
        the masks unless 'masked=False' (a mask can make one)."""
        successor_db = self._successor_db(masked)
        forbidden = self._forbidden_of(masked)
        return tuple(s for s in self.state_tuple
                     if s not in successor_db and s not in self.final
                     and s not in forbidden)

    def forbidden_reachable(self, masked=True):
        """RETURN: tuple of str, the forbidden states the model lets the
        system reach from the initial state -- sorted; under the masks and
        the states forbidden now unless 'masked=False'."""
        return tuple(s for s in sorted(self._forbidden_of(masked))
                     if self.state_reachable(s, masked=masked))

    def check(self, masked=True):
        """
        RETURN: int, how many findings the MODEL has, each written as one
                line 'MODEL: ...'; 0 where it has none.

        Asked of the model alone, before or without any event: states no
        path reaches, dead ends, forbidden states the model allows to be
        reached (each with the shortest way there) -- under the masks
        standing now unless 'masked=False'.
        """
        line_list = ["MODEL: '%s' cannot be reached" % s
                     for s in self.unreachable(masked)]
        line_list += ["MODEL: '%s' is a dead end -- no event leaves it" % s
                      for s in self.dead_ends(masked)]
        line_list += ["MODEL: forbidden '%s' is reachable: %s"
                      % (s, " ".join(self.path_to(s, masked=masked)))
                      for s in self.forbidden_reachable(masked)]
        for line in line_list: self.write(line)
        return len(line_list)

    # -------------------------------------------------------------- the end
    def report(self):
        """
        RETURN: int, the breaches seen, counting a non-final end; written
                before it, sorted, what the events covered of the model --
                states counted without the forbidden ones:
                    fsm: 3 of 3 states visited, 3 of 4 transitions taken, 1 breach
                      taken      idle ---( request )---> waiting   x2
                      not taken  busy ---( fault )---> crashed
                      never in   ...
                      ended in   'idle'
        A machine with final states that ends elsewhere adds a BREACH line.
        """
        all_edge = sorted((s, e, t) for (s, e), ts in self._edge_db.items()
                          for t in ts)
        breach_n = self.breach_n
        end_f = not self.final or bool(self._current & self.final)
        if not end_f: breach_n += 1
        #  A FORBIDDEN STATE IS NO GOAL OF COVERAGE: counted out.
        goal    = [s for s in self.state_tuple if s not in self.model_forbidden]
        visited = [s for s in goal if s in self._visit_db]
        self.write("%s: %d of %d states visited, %d of %d transitions taken, "
                   "%d breach%s" % (self.name, len(visited),
                                    len(goal), len(self._taken_db),
                                    len(all_edge), breach_n,
                                    "" if breach_n == 1 else "es"))
        for edge in all_edge:
            n = self._taken_db.get(edge)
            label = "taken    " if n else "not taken"
            self.write("  %s  %s ---( %s )---> %s%s"
                       % (label, edge[0], edge[1], edge[2],
                          "   x%d" % n if n and n > 1 else ""))
        for state in self.state_tuple:
            if state not in self._visit_db and state not in self.model_forbidden:
                self.write("  never in   '%s'" % state)
        self.write("  ended in   %s" % self._here())
        #  A PHASE NEVER LIFTED IS SAID: what still stands at the end.
        for (state, event), since in sorted(self._mask_db.items(),
                                            key=lambda p: (p[0][1], p[0][0] or "")):
            self.write("  disallowed '%s' %s%s"
                       % (event, "in every state" if state is None
                          else "in '%s'" % state, _since_text(since)))
        for state in sorted(set(self._forbid_db) - self.model_forbidden):
            self.write("  forbidden  '%s'%s"
                       % (state, _since_text(self._forbid_db[state])))
        for state in sorted(self._permit_db):
            self.write("  permitted  '%s'%s"
                       % (state, _since_text(self._permit_db[state])))
        if not end_f:
            self.write("BREACH: ended in %s -- final: %s"
                       % (self._here(), ", ".join(sorted(self.final))))
        return breach_n


class _Phase:
    """A block during which a mask or a forbidden state stands."""

    def __init__(self, enter_f, leave_f):
        """RETURN: _Phase, doing 'enter_f()' on entry, 'leave_f()' on exit."""
        self._enter_f, self._leave_f = enter_f, leave_f

    def __enter__(self):
        """RETURN: None. The phase begins."""
        self._enter_f()

    def __exit__(self, *_):
        """RETURN: False. The phase ends; an exception passes on."""
        self._leave_f()
        return False
