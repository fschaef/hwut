from __future__ import annotations

from itertools   import chain
from dataclasses import dataclass

class Attribute:
    value: Any
    def is_equivalent(other: Attribute):
        # Note, that may be defined tolerant, an attribute 'diameter' may consider a deviation of 1e-6 as 'nothing'
        pass

@dataclass
@dataclass
class Now:
    """The jiffy where an event actually is existent.
    """
    events: list[Event]

    def has(self, spec: EventSpec) -> bool:
        """RETURNS: True, If any event living in now fits the given specification
                    False, else.
        """
        return any(spec.matches(ev) for ev in self.events)

@dataclass
class Event:
    name:       str
    attributes: dict[str, Any]
    
@dataclass(frozen=True)
class AttributeConstraint:
    name: str
    expected: Any

    def matches(self, value: Any) -> bool:
        # can later be tolerant, fuzzy, etc.
        return value == self.expected

@dataclass(frozen=True)
class EventSpec:
    name:        str
    constraints: tuple[AttributeConstraint, ...] = ()

    def matches(self, event: Event) -> bool:
        if event.name != self.name: return False
        return all(c.matches(event.attributes.get(c.name, None)))

@dataclass
class TScope:
    on_event:    Event
    until_event: Event

    def react(self, now: Now):
        """RETURNS: True,  'activating'    <= an event in Now
                    False, 'de-activating' <= an event int Now
                    None   indifferent with anything in Now
        """
        if   now.has(self.on_event):    return True
        elif now.has(self.until_event): return False
        else:                           return None

@dataclass
class RuleSet:
    tscope:    TScope             # temporal scope
    on_entry:  LuaCompiledCode
    on_exit:   LuaCompiledCode
    rule_list: RuleList

class E_TemporalLogicMode(Enum):
    COMPLIANCE  = auto()
    OBSERVATION = auto()

@dataclass
class Engine:
    mode:               E_TemporalLogicMode

    universe:        Universe

    rule_set_manager:   RuleSetManager

    event_stream_api:   EventStreamAPI

    def initialize(self, 
                   mode:               E_TemporalLogicMode, 
                   header_source_file: str):
        self.mode = mode
        self.universe.initialize(self.boot_strap_file_name, mode)

        # Lua-header with convenience functions, enum definitions etc.
        self.parse_test_specific_lua_header(header_source_file)
        # Event definitions:
        #    META-EVENTS
        #    EVENT-structure specifications
        self.parse_test_specific_event_definitions(header_source_file)

    def _jiffy_step(self, event: Event, time_sec: float):
        """RETURNS: [0] True, if no violation happend; False, else.
                    [1] sorted list of actions to be considered as a consequence of
                        rule sets being activated by events of now.

        The list of actions is sorted by provenance, as it defines the order 
        of execution.
        """
        # 'now' = set of events that exist in this particular jiffy
        now = self.event_space.create_now(event, self.history) 
        self.history.register_now(now, time_sec)

        active_rule_sets,     \
        activated_rule_sets,  \
        deactivated_rule_sets = self.rule_set_manager.apply(now, self.history, time_sec)

        verdict = self.universe.judge(active_rule_sets)
        if verdict is False and self.mode is E_TemporalLogicMode.COMPLIANCE:
            return None

        def provenance_priority(action):
            """Key for sorting the actions: A 'file priority index' gives the
            priority of the file where the action is located. 'line_n' is the 
            number of the line where the action has been specified.
            """
            return action.file_priority_index, action.line_n

        return sorted((chain([rset.on_entry for rset in activated_rule_sets], 
                             [rset.on_exit  for rset in deactivated_rule_sets])),
                      key = provenance_priority)

    def process_external_event(self, event: Event, time_sec: float):
        """RETURNS: True, if no violation occurred
                    False, if a rule violation occurred

        If the engine is setup in COMPLIANCE mode, a violation caused a immediate
        abort of the process. Else, it continues in order to run through all 
        jiffy steps related to an external event.
        """
        verdict   = True
        work_list = [ self.rule_space.new_now_by_event(event) ]

        while work_list:
            now = work_list.pop()

            sub_verdict,        \
            sorted_action_list = self._jiffy_step(now, time_sec)

            if sub_verdict is False:
                verdict = False
                if self.mode == E_TemporalLogicMode.COMPLIANCE: break

            for action in sorted_action_list:
                work_list.append(self.universe.new_now_by_action(action))

        return verdict

class LuaObjectSpace:
    lua_executer: Any

    def do(self, action):
        """RETURNS: [0] events triggered directly by action's actions
                    [1] state changes in the lua space, caused by action's actions
        """
        # snapshot the hidden object space with respect to all objects 
        # possibly subject to change
        relevant = self.lua_inspector.get_affected_objects(action)

        # before: state of objects subject to change by action, before execution
        # after:  state of objects subject to change by action, after execution
        before           = self.object_space.snapshot(relevant)
        triggered_events = self.lua_executer.do(action)
        after            = self.object_space.snapshot(relevant)

        state_changes    = self.determine_state_changes(before, after)

        return triggered_events, state_changes

@dataclass(frozen=True)
class ImplicationRule:
    condition: EventSpec        # may reference HISTORY internally
    produces:  Event

@dataclass
class EventSpace:
    history:           History
    implication_rules: Any

    def __init__(self, implication_rules: list[ImplicationRule]):
        self.implication_rules = implication_rules

    def imply(self, event_list: list[Event]):
        """RETURNS: event_list + list of implied events

        Finds implied (meta-events) and add them to the current set 
        of events of 'Now'.
        """
    def imply(self, initial_events: list[Event]) -> Now:
        events = list(initial_events)
        seen_signatures = set()

        while True:
            signature = frozenset((e.name, frozenset(e.attributes.items()))
                                  for e in events)
            if signature in seen_signatures:
                raise RuntimeError("Circular meta-event implication detected")

            seen_signatures.add(signature)

            added = False
            for rule in self.implication_rules:
                if   not rule.condition_matches(events, self.history): continue
                elif any(rule.produces == e for e in events):          continue
                events.append(rule.produces)
                added = True

            if not added:
                return Now(events)

@dataclass
class Universe:
    event_space:  EventSpace
    object_space: LuaObjectSpace

    def initialize(self, bootstrap_file):
        self.initialize_lua()
        self.parse_bootstrap(bootstrap_file)

    def new_now_by_event(self, event, time: float) -> Now:
        """RETURNS: a new 'now' = list of events

        Given the meta-events in the event space, an event may imply other
        events. This function determines all implied events in order to define
        the set of all events at this particular 'now'.
        """
        return self.event_space.imply([event], time)

    def new_now_by_action(self, action, time: float) -> Now:
        """RETURNS: a new 'now' = list of events

        Executes action, collects the events it triggered and determines what
        events are triggered by the state changes it performed.
        """
        events, state_changes = self.object_space.do(action)

        return self.event_space.imply(events, time, state_changes)

@dataclass
class EventStreamAPI:
    def __init__(self, engine: Engine, mode: E_TemporalLogicMode):
        self._mode = mode

    def initialize(self, header_source_file):
        self._engine.initialize(header_source_file)

    def process(self, event: Event, time_sec: float = -1.0) -> bool:
        """RETURNS: True, if no rule violation occurred.
                    False, if a rule violation occurred.
        """
        time_sec = time_sec if time_sec != -1.0 else time.time()
        return self._engine.process_external_event(event, time_sec)

    def terminate(self):
        pass

    def report(self):
        if self.mode != E_TemporalLogicMode.OBSERVATION: return None
        pass 
