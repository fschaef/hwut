-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: A STATE MACHINE AS A TEST'S MODEL OF THE SYSTEM UNDER TEST -- the
--          port of 'python/hwut_fsm.py' (README-hwut_fsm.txt): a THIN FACE
--          over the C module '../c/hwut_fsm.c' by VHPIDIRECT, which reads the
--          model text and keeps the run. The states it may be in, the events
--          that move it, the states it must never reach. A test FIRES the
--          events it observes; every event the model does not allow, and
--          every forbidden state entered, is WRITTEN as a line on stdout -- so
--          it lands in the GOOD file and the comparison judges it.
--
--     variable m : Machine;
--     if not m.from_string("initial: idle" & LF
--                        & "idle ---( request )---> waiting ---( grant )---> busy" & LF) then
--         print("FsmError: " & m.error);
--     end if;
--     moved := m.fire("request", "1");    -- 'where' "1": line 1
--     m.fire("release", "2");             -- BREACH line 2: 'release' in ...
--     n := m.print_report;               -- 'report' is a reserved word
--     m.free;
--
-- The same model text, the same words, the same sorted reports as Python.
--
-- WHERE PYTHON RAISES FsmError, a method returns false (a function giving a
-- text: "") and 'error' is the FsmError's text. A list of states or events is
-- a str_list ('hwut_pytext'). Python's None -- for 'state', 'where', 'start'
-- -- is "". 'where' is a text: digits name a line ('line 3'), any other text
-- stands as written. 'start' "now" is where the machine stands.
--
-- NO 'with' IN VHDL, and no block to hand over: 'with m.disallowed(e, s):'
-- is 'm.disallow(e, s, where); ...; m.allow(e, s);', 'm.forbidding(s)' is
-- 'forbid' ... 'permit' -- what the context manager does on leaving.
-- A machine is read from its model text ('from_string'); 'free' gives it back.
-- _____________________________________________________________________________
use std.textio.all;
use work.hwut_vhpi.all;
use work.hwut_pytext.all;

package hwut_fsm is
    type Machine is protected
        impure function from_string(text : string; dfa : boolean := true; name : string := "fsm") return boolean;
        procedure free;
        impure function error return string;
        impure function to_string return string;
        procedure reset;
        impure function fire(event : string; where : string := "") return boolean;
        procedure fire(event : string; where : string := "");
        impure function disallow(event : string; state_name : string := ""; where : string := "") return boolean;
        impure function allow(event : string; state_name : string := "") return boolean;
        impure function forbid(state_name : string; where : string := "") return boolean;
        impure function permit(state_name : string; where : string := "") return boolean;
        procedure disallow(event : string; state_name : string := ""; where : string := "");
        procedure allow(event : string; state_name : string := "");
        procedure forbid(state_name : string; where : string := "");
        procedure permit(state_name : string; where : string := "");
        impure function state return string;
        impure function current return str_list;
        impure function in_state(state_name : string) return boolean;
        impure function can(event : string) return boolean;
        impure function allowed return str_list;
        impure function trace return str_list;
        impure function breach_n return natural;
        impure function path_to(state_name : string; start : string := ""; masked : boolean := true) return str_list;
        impure function state_reachable(state_name : string; start : string := ""; masked : boolean := true) return boolean;
        impure function unreachable(masked : boolean := true) return str_list;
        impure function dead_ends(masked : boolean := true) return str_list;
        impure function forbidden_reachable(masked : boolean := true) return str_list;
        impure function check(masked : boolean := true) return natural;
        impure function print_report return natural;
    end protected;
end package;

package body hwut_fsm is
    impure function hwut_vhpi_fsm_from_string(text : string; dfa_f : integer; name : string) return integer;
    attribute foreign of hwut_vhpi_fsm_from_string : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_from_string";
    impure function hwut_vhpi_fsm_from_string(text : string; dfa_f : integer; name : string) return integer is
    begin assert false severity failure; return 0; end function;

    procedure hwut_vhpi_fsm_free(h : integer);
    attribute foreign of hwut_vhpi_fsm_free : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_free";
    procedure hwut_vhpi_fsm_free(h : integer) is begin assert false severity failure; end procedure;

    procedure hwut_vhpi_fsm_error(h : integer);
    attribute foreign of hwut_vhpi_fsm_error : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_error";
    procedure hwut_vhpi_fsm_error(h : integer) is begin assert false severity failure; end procedure;

    procedure hwut_vhpi_fsm_to_string(h : integer);
    attribute foreign of hwut_vhpi_fsm_to_string : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_to_string";
    procedure hwut_vhpi_fsm_to_string(h : integer) is begin assert false severity failure; end procedure;

    procedure hwut_vhpi_fsm_reset(h : integer);
    attribute foreign of hwut_vhpi_fsm_reset : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_reset";
    procedure hwut_vhpi_fsm_reset(h : integer) is begin assert false severity failure; end procedure;

    impure function hwut_vhpi_fsm_fire(h : integer; event : string; where : string) return integer;
    attribute foreign of hwut_vhpi_fsm_fire : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_fire";
    impure function hwut_vhpi_fsm_fire(h : integer; event : string; where : string) return integer is
    begin assert false severity failure; return 0; end function;

    impure function hwut_vhpi_fsm_disallow(h : integer; event : string; state : string; where : string) return integer;
    attribute foreign of hwut_vhpi_fsm_disallow : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_disallow";
    impure function hwut_vhpi_fsm_disallow(h : integer; event : string; state : string; where : string) return integer is
    begin assert false severity failure; return 0; end function;

    impure function hwut_vhpi_fsm_allow(h : integer; event : string; state : string) return integer;
    attribute foreign of hwut_vhpi_fsm_allow : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_allow";
    impure function hwut_vhpi_fsm_allow(h : integer; event : string; state : string) return integer is
    begin assert false severity failure; return 0; end function;

    impure function hwut_vhpi_fsm_forbid(h : integer; state : string; where : string) return integer;
    attribute foreign of hwut_vhpi_fsm_forbid : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_forbid";
    impure function hwut_vhpi_fsm_forbid(h : integer; state : string; where : string) return integer is
    begin assert false severity failure; return 0; end function;

    impure function hwut_vhpi_fsm_permit(h : integer; state : string; where : string) return integer;
    attribute foreign of hwut_vhpi_fsm_permit : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_permit";
    impure function hwut_vhpi_fsm_permit(h : integer; state : string; where : string) return integer is
    begin assert false severity failure; return 0; end function;

    impure function hwut_vhpi_fsm_state(h : integer) return integer;
    attribute foreign of hwut_vhpi_fsm_state : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_state";
    impure function hwut_vhpi_fsm_state(h : integer) return integer is
    begin assert false severity failure; return 0; end function;

    procedure hwut_vhpi_fsm_current(h : integer);
    attribute foreign of hwut_vhpi_fsm_current : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_current";
    procedure hwut_vhpi_fsm_current(h : integer) is begin assert false severity failure; end procedure;

    procedure hwut_vhpi_fsm_allowed(h : integer);
    attribute foreign of hwut_vhpi_fsm_allowed : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_allowed";
    procedure hwut_vhpi_fsm_allowed(h : integer) is begin assert false severity failure; end procedure;

    impure function hwut_vhpi_fsm_in_state(h : integer; state : string) return integer;
    attribute foreign of hwut_vhpi_fsm_in_state : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_in_state";
    impure function hwut_vhpi_fsm_in_state(h : integer; state : string) return integer is
    begin assert false severity failure; return 0; end function;

    impure function hwut_vhpi_fsm_can(h : integer; event : string) return integer;
    attribute foreign of hwut_vhpi_fsm_can : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_can";
    impure function hwut_vhpi_fsm_can(h : integer; event : string) return integer is
    begin assert false severity failure; return 0; end function;

    procedure hwut_vhpi_fsm_trace(h : integer);
    attribute foreign of hwut_vhpi_fsm_trace : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_trace";
    procedure hwut_vhpi_fsm_trace(h : integer) is begin assert false severity failure; end procedure;

    impure function hwut_vhpi_fsm_breach_n(h : integer) return integer;
    attribute foreign of hwut_vhpi_fsm_breach_n : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_breach_n";
    impure function hwut_vhpi_fsm_breach_n(h : integer) return integer is
    begin assert false severity failure; return 0; end function;

    impure function hwut_vhpi_fsm_path_to(h : integer; state : string; start : string; masked_f : integer) return integer;
    attribute foreign of hwut_vhpi_fsm_path_to : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_path_to";
    impure function hwut_vhpi_fsm_path_to(h : integer; state : string; start : string; masked_f : integer) return integer is
    begin assert false severity failure; return 0; end function;

    impure function hwut_vhpi_fsm_state_reachable(h : integer; state : string; start : string; masked_f : integer) return integer;
    attribute foreign of hwut_vhpi_fsm_state_reachable : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_state_reachable";
    impure function hwut_vhpi_fsm_state_reachable(h : integer; state : string; start : string; masked_f : integer) return integer is
    begin assert false severity failure; return 0; end function;

    procedure hwut_vhpi_fsm_unreachable(h : integer; masked_f : integer);
    attribute foreign of hwut_vhpi_fsm_unreachable : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_unreachable";
    procedure hwut_vhpi_fsm_unreachable(h : integer; masked_f : integer) is begin assert false severity failure; end procedure;

    procedure hwut_vhpi_fsm_dead_ends(h : integer; masked_f : integer);
    attribute foreign of hwut_vhpi_fsm_dead_ends : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_dead_ends";
    procedure hwut_vhpi_fsm_dead_ends(h : integer; masked_f : integer) is begin assert false severity failure; end procedure;

    procedure hwut_vhpi_fsm_forbidden_reachable(h : integer; masked_f : integer);
    attribute foreign of hwut_vhpi_fsm_forbidden_reachable : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_forbidden_reachable";
    procedure hwut_vhpi_fsm_forbidden_reachable(h : integer; masked_f : integer) is begin assert false severity failure; end procedure;

    impure function hwut_vhpi_fsm_check(h : integer; masked_f : integer) return integer;
    attribute foreign of hwut_vhpi_fsm_check : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_check";
    impure function hwut_vhpi_fsm_check(h : integer; masked_f : integer) return integer is
    begin assert false severity failure; return 0; end function;

    impure function hwut_vhpi_fsm_report(h : integer) return integer;
    attribute foreign of hwut_vhpi_fsm_report : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_fsm_report";
    impure function hwut_vhpi_fsm_report(h : integer) return integer is
    begin assert false severity failure; return 0; end function;

    type Machine is protected body
        variable handle     : integer := 0;
        variable error_text : line    := new string'("");

        procedure refused is
            -- RETURN: nothing; the machine's last refusal is 'error'.
        begin
            hwut_vhpi_fsm_error(handle);
            error_text := new string'(result);
        end procedure;

        impure function said(status : integer) return boolean is
            -- RETURN: true, 'status' (C's) is 0: done; false, else -- the
            --         refusal is 'error'.
        begin
            if status = 0 then return true; end if;
            refused;
            return false;
        end function;

        impure function from_string(text : string; dfa : boolean := true; name : string := "fsm") return boolean is
            -- RETURN: true, the machine is the model 'text' describes -- one
            --         state at a time where 'dfa', a SET else; its lines are
            --         headed by 'name'; false, else -- the text cannot be
            --         meant: 'error' is the FsmError's text.
        begin
            if handle /= 0 then hwut_vhpi_fsm_free(handle); end if;
            handle := hwut_vhpi_fsm_from_string(text, boolean'pos(dfa), name);
            if handle = 0 then error_text := new string'(result); return false; end if;
            return true;
        end function;

        procedure free is
            -- RETURN: nothing; the machine is given back; 'from_string' may
            --         read a new one.
        begin
            if handle /= 0 then hwut_vhpi_fsm_free(handle); end if;
            handle := 0;
        end procedure;

        impure function error return string is
            -- RETURN: string, the text of the last FsmError -- the last
            --         refusal of a method that returned false (or "").
        begin return error_text.all; end function;

        impure function to_string return string is
            -- RETURN: string, the model written back as model text.
        begin hwut_vhpi_fsm_to_string(handle); return result; end function;

        procedure reset is
            -- RETURN: nothing; the machine stands where its run began; the
            --         trace is empty.
        begin hwut_vhpi_fsm_reset(handle); end procedure;

        impure function fire(event : string; where : string := "") return boolean is
            -- RETURN: true, 'event' moved the machine; false, the model does
            --         not allow it where the machine stands -- a BREACH line
            --         was written, naming 'where'. Entering a forbidden state
            --         writes one too.
        begin return hwut_vhpi_fsm_fire(handle, event, where) /= 0; end function;

        procedure fire(event : string; where : string := "") is
            -- RETURN: nothing; as the function 'fire', its answer dropped.
            variable moved_f : boolean;
        begin moved_f := fire(event, where); end procedure;

        impure function disallow(event : string; state_name : string := ""; where : string := "") return boolean is
            -- RETURN: true, 'event' is no longer allowed in 'state_name' ("":
            --         every state), since 'where'; false, the model names no
            --         such word -- see 'error'.
        begin return said(hwut_vhpi_fsm_disallow(handle, event, state_name, where)); end function;

        impure function allow(event : string; state_name : string := "") return boolean is
            -- RETURN: true, the mask 'disallow' put on 'event' in 'state_name' is
            --         lifted; false, the model names no such word -- 'error'.
        begin return said(hwut_vhpi_fsm_allow(handle, event, state_name)); end function;

        impure function forbid(state_name : string; where : string := "") return boolean is
            -- RETURN: true, entering 'state_name' is a breach from now, since
            --         'where'; false, the model names no such state -- 'error'.
        begin return said(hwut_vhpi_fsm_forbid(handle, state_name, where)); end function;

        impure function permit(state_name : string; where : string := "") return boolean is
            -- RETURN: true, entering 'state_name' is no breach from now -- the
            --         model's own forbidden ones too; false, no such state.
        begin return said(hwut_vhpi_fsm_permit(handle, state_name, where)); end function;

        procedure disallow(event : string; state_name : string := ""; where : string := "") is
            -- RETURN: nothing; as the function 'disallow', its answer dropped.
            variable done_f : boolean;
        begin done_f := disallow(event, state_name, where); end procedure;

        procedure allow(event : string; state_name : string := "") is
            -- RETURN: nothing; as the function 'allow', its answer dropped.
            variable done_f : boolean;
        begin done_f := allow(event, state_name); end procedure;

        procedure forbid(state_name : string; where : string := "") is
            -- RETURN: nothing; as the function 'forbid', its answer dropped.
            variable done_f : boolean;
        begin done_f := forbid(state_name, where); end procedure;

        procedure permit(state_name : string; where : string := "") is
            -- RETURN: nothing; as the function 'permit', its answer dropped.
            variable done_f : boolean;
        begin done_f := permit(state_name, where); end procedure;

        impure function state return string is
            -- RETURN: string, the one state the machine stands in, if
            --         success; "", else -- it stands in a set (dfa false):
            --         'error' says so.
        begin
            if hwut_vhpi_fsm_state(handle) = 0 then error_text := new string'(result); return ""; end if;
            return result;
        end function;

        impure function current return str_list is
            -- RETURN: str_list, every state the machine stands in, sorted.
        begin hwut_vhpi_fsm_current(handle); return result; end function;

        impure function in_state(state_name : string) return boolean is
            -- RETURN: true, the machine stands in 'state'; false, else.
        begin return hwut_vhpi_fsm_in_state(handle, state_name) /= 0; end function;

        impure function can(event : string) return boolean is
            -- RETURN: true, 'event' is allowed where the machine stands.
        begin return hwut_vhpi_fsm_can(handle, event) /= 0; end function;

        impure function allowed return str_list is
            -- RETURN: str_list, every event allowed now, sorted.
        begin hwut_vhpi_fsm_allowed(handle); return result; end function;

        impure function trace return str_list is
            -- RETURN: str_list, one item per firing since the run began:
            --         where, state, event, target, separated by HT -- where
            --         "" for no place.
        begin hwut_vhpi_fsm_trace(handle); return result; end function;

        impure function breach_n return natural is
            -- RETURN: natural, the number of breaches written so far.
        begin return hwut_vhpi_fsm_breach_n(handle); end function;

        impure function path_to(state_name : string; start : string := ""; masked : boolean := true) return str_list is
            -- RETURN: str_list, the shortest path of events from 'start'
            --         ("": the initial state, "now": where it stands) to
            --         'state_name' -- masked events taken out where 'masked'; ""
            --         where none leads there ('state_reachable' says which).
            variable n : integer;
        begin
            n := hwut_vhpi_fsm_path_to(handle, state_name, start, boolean'pos(masked));
            return result;
        end function;

        impure function state_reachable(state_name : string; start : string := ""; masked : boolean := true) return boolean is
            -- RETURN: true, a path leads from 'start' to 'state_name'; false, else.
        begin return hwut_vhpi_fsm_state_reachable(handle, state_name, start, boolean'pos(masked)) /= 0; end function;

        impure function unreachable(masked : boolean := true) return str_list is
            -- RETURN: str_list, every state no path reaches, sorted.
        begin hwut_vhpi_fsm_unreachable(handle, boolean'pos(masked)); return result; end function;

        impure function dead_ends(masked : boolean := true) return str_list is
            -- RETURN: str_list, every state no event leaves that is not final.
        begin hwut_vhpi_fsm_dead_ends(handle, boolean'pos(masked)); return result; end function;

        impure function forbidden_reachable(masked : boolean := true) return str_list is
            -- RETURN: str_list, every forbidden state a path reaches.
        begin hwut_vhpi_fsm_forbidden_reachable(handle, boolean'pos(masked)); return result; end function;

        impure function check(masked : boolean := true) return natural is
            -- RETURN: natural, the number of model findings -- each written
            --         as a line.
        begin return hwut_vhpi_fsm_check(handle, boolean'pos(masked)); end function;

        impure function print_report return natural is
            -- RETURN: natural, the number of breaches; the coverage report
            --         -- states visited, edges taken, breaches -- is written.
        begin return hwut_vhpi_fsm_report(handle); end function;
    end protected body;
end package body;
