// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: A STATE MACHINE AS A TEST'S MODEL OF THE SYSTEM UNDER TEST -- the
//          port of 'python/hwut_fsm.py' (README-hwut_fsm.txt). The states it
//          may be in, the events that move it, the states it must never
//          reach. A test FIRES the events it observes; every event the model
//          does not allow, and every forbidden state entered, is WRITTEN as a
//          line -- so it lands in the GOOD file and the comparison judges it.
//
//     import hwut_fsm::*;
//     Machine m = Machine::from_string({
//         "initial: idle\n",
//         "forbidden: crashed\n",
//         "idle ---( request )---> waiting ---( grant )---> busy\n",
//         "busy ---( release )---> idle\n",
//         ":    ---( fault )--->   crashed\n"});
//     if (m == null) $display("FsmError: %s", Machine::refusal);
//     void'(m.fire("request", "1"));
//     void'(m.fire("release", "2"));    -- BREACH line 2: 'release' in ...
//     void'(m.report());
//
// THE MACHINE IS THE C PORT'S ('../c/hwut_fsm.c', through DPI-C:
// 'hwut_fsm_dpi.c'): the same model text, the same words, the same sorted
// reports. This class owns it, converts, and passes every line it writes
// through its 'writer' -- '$display' by default.
//
// WHAT PYTHON RAISES (FsmError) is returned: a model that cannot be meant
// gives 'null' and 'Machine::refusal' its text; a method refused returns 0
// (or -1, a count) and 'm.error' holds the text.
//
// NONE IS ''. A 'where' (a breach's place) is a text: digits name a line
// ('line 3'), any other text stands as written, '' names no place. A state
// '' is every state; a 'start' '' is the initial state, "now" where the
// machine stands.
//
// 'with m.disallowed(...)' is a Phase: the mask stands until 'close()'.
// _____________________________________________________________________________
package hwut_fsm;

    typedef string string_list_t[$];
    typedef struct { string source; string event_; string target; } transition_t;
    typedef struct { string where; string state; string event_; string target; } trace_entry_t;

    import "DPI-C" function void   hwut_sv_fsm_builder_clear();
    import "DPI-C" function void   hwut_sv_fsm_builder_add(int what, string a, string b, string c);
    import "DPI-C" function chandle hwut_sv_fsm_build(string initial_, int dfa_f, string name, int id);
    import "DPI-C" function chandle hwut_sv_fsm_from_string(string text, int dfa_f, string name, int id);
    import "DPI-C" function string hwut_sv_fsm_refusal();
    import "DPI-C" function void   hwut_sv_fsm_free(chandle m);
    import "DPI-C" function string hwut_sv_fsm_error(chandle m);
    import "DPI-C" function string hwut_sv_fsm_to_string(chandle m);
    import "DPI-C" function void   hwut_sv_fsm_reset(chandle m);
    import "DPI-C" context function int hwut_sv_fsm_fire(chandle m, string event_, string where);
    import "DPI-C" context function int hwut_sv_fsm_disallow(chandle m, string event_, string state, string where);
    import "DPI-C" context function int hwut_sv_fsm_allow(chandle m, string event_, string state);
    import "DPI-C" context function int hwut_sv_fsm_forbid(chandle m, string state, string where);
    import "DPI-C" context function int hwut_sv_fsm_permit(chandle m, string state, string where);
    import "DPI-C" function int    hwut_sv_fsm_state(chandle m, output string state);
    import "DPI-C" function int    hwut_sv_fsm_in_state(chandle m, string state);
    import "DPI-C" function int    hwut_sv_fsm_can(chandle m, string event_);
    import "DPI-C" function int    hwut_sv_fsm_breach_n(chandle m);
    import "DPI-C" function int    hwut_sv_fsm_list_n();
    import "DPI-C" function string hwut_sv_fsm_list_at(int i);
    import "DPI-C" function int    hwut_sv_fsm_list(chandle m, int what, int masked_f);
    import "DPI-C" function int    hwut_sv_fsm_path_to(chandle m, string state, string start, int masked_f);
    import "DPI-C" function int    hwut_sv_fsm_state_reachable(chandle m, string state, string start, int masked_f);
    import "DPI-C" context function int hwut_sv_fsm_check(chandle m, int masked_f);
    import "DPI-C" context function int hwut_sv_fsm_report(chandle m);
    import "DPI-C" function int    hwut_sv_fsm_trace_n(chandle m);
    import "DPI-C" function string hwut_sv_fsm_trace_field(chandle m, int i, int k);

    typedef class Machine;

    class Writer;
        // Where a machine's lines go. Derive and override 'write' to send
        // them elsewhere -- Python's 'write=' argument.
        virtual function void write(string line);
            // RETURN: nothing; 'line' is printed on stdout.
            $display("%s", line);
        endfunction
    endclass

    class Registry;
        // The machines by number: the C core names its machine by it when it
        // writes a line.
        static Machine machine_db[int];
        static int     next_id = 1;
    endclass

    export "DPI-C" function hwut_sv_fsm_write;
    function automatic void hwut_sv_fsm_write(int id, string line);
        // RETURN: nothing; 'line', written by the C machine 'id', went
        //         through its SystemVerilog machine's writer.
        if (Registry::machine_db.exists(id)) Registry::machine_db[id].writer.write(line);
        else $display("%s", line);
    endfunction

    function automatic string_list_t listed();
        // RETURN: the names the last list question of the C core left.
        string_list_t result = {};
        for (int i = 0; i < hwut_sv_fsm_list_n(); i++) result.push_back(hwut_sv_fsm_list_at(i));
        return result;
    endfunction

    class Phase;
        // A block during which a mask or a forbidden state stands; 'close'
        // ends it -- Python's 'with' block left.
        Machine machine;
        bit     forbid_f;
        string  event_;
        string  state;
        bit     closed_f;

        function new(Machine machine, bit forbid_f, string event_, string state);
            // RETURN: the phase; what it stands for is already in force.
            this.machine  = machine;
            this.forbid_f = forbid_f;
            this.event_   = event_;
            this.state    = state;
        endfunction

        function void close();
            // RETURN: nothing; the event is allowed, or the state permitted,
            //         again; a second 'close' does nothing.
            if (closed_f) return;
            closed_f = 1;
            if (forbid_f) void'(machine.permit(state));
            else          void'(machine.allow(event_, state));
        endfunction
    endclass

    class Machine;
        chandle       handle;
        int           id;
        string        name;
        string        error;        // why the last method was refused
        Writer        writer;
        static string refusal;      // why the last machine was not made

        function new(string name, Writer writer);
            // RETURN: a machine not yet bound to a model; use 'from_string'
            //         or 'create'.
            this.name   = name;
            if (writer == null) writer = new();
            this.writer = writer;
            id          = Registry::next_id;
            Registry::next_id += 1;
        endfunction

        static function Machine bound(Machine m, chandle handle);
            // RETURN: 'm' holding the C machine 'handle'; null where 'handle'
            //         is null -- 'refusal' says why.
            if (handle == null) begin
                refusal = hwut_sv_fsm_refusal();
                return null;
            end
            m.handle = handle;
            Registry::machine_db[m.id] = m;
            return m;
        endfunction

        static function Machine from_string(string text, bit DFA = 1, string name = "fsm", Writer writer = null);
            // RETURN: the machine the model 'text' describes, standing in its
            //         initial state; null where the model cannot be meant --
            //         'Machine::refusal' says why (Python's FsmError).
            Machine m = new(name, writer);
            return bound(m, hwut_sv_fsm_from_string(text, DFA, name, m.id));
        endfunction

        static function Machine create(transition_t transition_list[$], string initial_,
                                       string forbidden[$], string final_[$], string state_list[$],
                                       bit DFA = 1, string name = "fsm", Writer writer = null);
            // RETURN: the machine of the transitions (state, event, state),
            //         standing in 'initial_', with the states 'forbidden',
            //         'final_' and those of no transition 'state_list' (each
            //         may be '{}' -- Verilator 5.020 takes no queue default);
            //         null where the model cannot be meant -- 'refusal' says why.
            Machine m = new(name, writer);
            hwut_sv_fsm_builder_clear();
            foreach (transition_list[i])
                hwut_sv_fsm_builder_add(0, transition_list[i].source, transition_list[i].event_, transition_list[i].target);
            foreach (forbidden[i])  hwut_sv_fsm_builder_add(1, forbidden[i], "", "");
            foreach (final_[i])     hwut_sv_fsm_builder_add(2, final_[i], "", "");
            foreach (state_list[i]) hwut_sv_fsm_builder_add(3, state_list[i], "", "");
            return bound(m, hwut_sv_fsm_build(initial_, DFA, name, m.id));
        endfunction

        function void free();
            // RETURN: nothing; the C machine is gone; this one is unbound.
            if (handle == null) return;
            hwut_sv_fsm_free(handle);
            Registry::machine_db.delete(id);
            handle = null;
        endfunction

        function string to_string();
            // RETURN: the model in the text 'from_string' reads, one
            //         transition per line, sorted.
            return hwut_sv_fsm_to_string(handle);
        endfunction

        function bit refused(int result);
            // RETURN: 1 where the C call 'result' was refused (-1), 'error'
            //         its text; 0 else.
            if (result >= 0) return 0;
            error = hwut_sv_fsm_error(handle);
            return 1;
        endfunction

        // ----------------------------------------------------- the run, the law
        function void reset();
            // RETURN: nothing; the machine stands in its initial state; the
            //         trace and the coverage are empty, the law the model's.
            hwut_sv_fsm_reset(handle);
        endfunction

        function bit fire(string event_, string where = "");
            // RETURN: 1 where 'event_' moved the machine and no forbidden
            //         state was entered; 0 where a breach was written.
            return hwut_sv_fsm_fire(handle, event_, where);
        endfunction

        function bit disallow(string event_, string state = "", string where = "");
            // RETURN: 1, 'event_' is disallowed in 'state' ('' every state)
            //         since 'where'; 0, the model names no such word -- 'error'.
            return !refused(hwut_sv_fsm_disallow(handle, event_, state, where));
        endfunction

        function bit allow(string event_, string state = "");
            // RETURN: 1, 'event_' is allowed again in 'state' ('' every
            //         state); 0, the model names no such word -- 'error'.
            return !refused(hwut_sv_fsm_allow(handle, event_, state));
        endfunction

        function bit forbid(string state, string where = "");
            // RETURN: 1, 'state' is forbidden since 'where' (a breach is
            //         written where the machine stands in it); 0, the model
            //         names no such state -- 'error'.
            return !refused(hwut_sv_fsm_forbid(handle, state, where));
        endfunction

        function bit permit(string state, string where = "");
            // RETURN: 1, 'state' is permitted since 'where' -- the model's own
            //         forbidden ones too; 0, the model names no such state.
            return !refused(hwut_sv_fsm_permit(handle, state, where));
        endfunction

        function Phase disallowed(string event_, string state = "", string where = "");
            // RETURN: a Phase: 'event_' disallowed (see 'disallow') until its
            //         'close()'; null where refused -- 'error'.
            Phase phase;
            if (!disallow(event_, state, where)) return null;
            phase = new(this, 0, event_, state);
            return phase;
        endfunction

        function Phase forbidding(string state, string where = "");
            // RETURN: a Phase: 'state' forbidden (see 'forbid') until its
            //         'close()'; null where refused -- 'error'.
            Phase phase;
            if (!forbid(state, where)) return null;
            phase = new(this, 1, "", state);
            return phase;
        endfunction

        // ------------------------------------------------------------ questions
        function bit state(output string one);
            // RETURN: 1, 'one' is the one state the machine stands in; 0, it
            //         stands in a set (DFA 0) -- 'error' says: ask 'current()'.
            if (hwut_sv_fsm_state(handle, one)) return 1;
            error = hwut_sv_fsm_error(handle);
            return 0;
        endfunction

        function string state_text();
            // RETURN: the one state the machine stands in; '' where it stands
            //         in a set.
            string one;
            void'(state(one));
            return one;
        endfunction

        function string_list_t current();
            // RETURN: every state the machine stands in, sorted.
            void'(hwut_sv_fsm_list(handle, 0, 1));
            return listed();
        endfunction

        function bit in_state(string state);
            // RETURN: 1 where the machine stands in 'state'; 0 else.
            return hwut_sv_fsm_in_state(handle, state);
        endfunction

        function bit can(string event_);
            // RETURN: 1 where 'event_' is allowed where the machine stands;
            //         0 else.
            return hwut_sv_fsm_can(handle, event_);
        endfunction

        function string_list_t allowed();
            // RETURN: the events allowed where the machine stands, sorted.
            void'(hwut_sv_fsm_list(handle, 1, 1));
            return listed();
        endfunction

        function void trace(ref trace_entry_t entry_list[$]);
            // RETURN: nothing; 'entry_list' holds every transition fired, in
            //         order: where ('' none), state left, event, state entered.
            entry_list = {};
            for (int i = 0; i < hwut_sv_fsm_trace_n(handle); i++) begin
                trace_entry_t entry;
                entry.where  = hwut_sv_fsm_trace_field(handle, i, 0);
                entry.state  = hwut_sv_fsm_trace_field(handle, i, 1);
                entry.event_ = hwut_sv_fsm_trace_field(handle, i, 2);
                entry.target = hwut_sv_fsm_trace_field(handle, i, 3);
                entry_list.push_back(entry);
            end
        endfunction

        function int breach_n();
            // RETURN: the breaches written so far.
            return hwut_sv_fsm_breach_n(handle);
        endfunction

        // ----------------------------------------------------- the model alone
        function bit path_to(string state, output string_list_t path, input string start = "",
                             input bit masked = 1);
            // RETURN: 1, 'path' holds the events of the shortest path from
            //         'start' ('' the initial state, "now" where the machine
            //         stands) into 'state' -- empty where 'start' is 'state';
            //         among equally short paths the first in event order,
            //         under the masks where 'masked'; 0, no path leads there
            //         (Python's None).
            int n = hwut_sv_fsm_path_to(handle, state, start, masked);
            path = listed();
            return n >= 0;
        endfunction

        function bit state_reachable(string state, string start = "", bit masked = 1);
            // RETURN: 1 where a path leads from 'start' into 'state'; 0 else.
            return hwut_sv_fsm_state_reachable(handle, state, start, masked);
        endfunction

        function string_list_t unreachable(bit masked = 1);
            // RETURN: the states no path leads to from the initial one, sorted.
            void'(hwut_sv_fsm_list(handle, 2, masked));
            return listed();
        endfunction

        function string_list_t dead_ends(bit masked = 1);
            // RETURN: the states no event leaves -- final ones aside -- sorted.
            void'(hwut_sv_fsm_list(handle, 3, masked));
            return listed();
        endfunction

        function string_list_t forbidden_reachable(bit masked = 1);
            // RETURN: the forbidden states a path leads to, sorted.
            void'(hwut_sv_fsm_list(handle, 4, masked));
            return listed();
        endfunction

        function int check(bit masked = 1);
            // RETURN: the number of findings about the model alone --
            //         unreachable states, dead ends, forbidden states the model
            //         lets the system reach -- each written as a 'MODEL:' line.
            return hwut_sv_fsm_check(handle, masked);
        endfunction

        function int report();
            // RETURN: the breaches seen, a non-final end counted; written
            //         before it, sorted, what the events covered of the model.
            return hwut_sv_fsm_report(handle);
        endfunction
    endclass

endpackage
