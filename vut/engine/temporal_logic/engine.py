from __future__ import annotations

from dataclasses import dataclass

@dataclass
class RuleSet:
    on_entry:  LuaCompiledCode
    on_exit:   LuaCompiledCode
    rule_list: RuleList

class E_TemporalLogicMode(Enum):
    COMPLIANCE  = auto()
    OBSERVATION = auto()

@dataclass
class Engine:
    mode:               E_TemporalLogicMode
    event_stream_api:   EventStreamAPI
    meta_event_db:      EventDefDB
    history:            TriggerHistory

    rule_space:         RuleSpace

    def initialize(self, header_source_file):
        self.rule_space.initialize(self.boot_strap_file_name)
        # Lua-header with convenience functions, enum definitions etc.
        self.parse_test_specific_lua_header(header_source_file)
        # Event definitions:
        #    META-EVENTS
        #    EVENT-structure specifications
        self.parse_test_specific_event_definitions(header_source_file)

    def _apply(self, event_list: list[Event], time_sec: float):
        self.now          = self.meta_event_db(event) # determine what events are in 'now'
        active_rule_sets,  \
        on_entry_handlers, \
        on_exit_handlers   = self.rule_space.apply(now)

        verdict = self.rule_space.judge(active_rule_sets, self.mode)
        if verdict is False and self.mode is E_TemporalLogicMode.COMPLIANCE:
            return None

        return [ 
            handler
            for handler in chain([rset.on_entry for rset in activated], 
                                 [rset.on_exit  for rset in deactivated])
        ]

    def process_external_event(self, event: Event, time_sec: float):
        work_list = [[event]]

        while work_list:
            if (result := self._apply([event], time_sec)) is None: 
                return False

            handler_list = result 

            for action in sorted_action_sequence(handler_list):
                event_list = self.rule_space.process_action(action)
                work_list.append(event_list)

        return True

@dataclass
class RuleSpace:
    tscope_to_rule_db:  TscopeDb
    lua_space:          LuaSpace
    def initialize(self, bootstrap_file):
        self.initialize_lua()
        self.parse_bootstrap(bootstrap_file)

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
