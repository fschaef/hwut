-- @hwut {
--     title      = "hwut_fsm: a state machine as the test's model of the system"
--     build      { framework = "make", executable = "%.exe" }
--     choices {
--         syntax    { features = ["vhdl-fsm"] }
--         refused   { features = ["vhdl-fsm"] }
--         dfa       { features = ["vhdl-fsm"] }
--         nfa       { features = ["vhdl-fsm"] }
--         forbidden { features = ["vhdl-fsm"] }
--         model     { features = ["vhdl-fsm"] }
--         report    { features = ["vhdl-fsm"] }
--         masks     { features = ["vhdl-fsm"] }
--     }
--     interactive = true
-- }
--
-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: The VHDL port of 'python/TEST/test-hwut_fsm.py', choice for choice,
--          held against its GOOD files by '.link'. What Python prints of its
--          own values -- True, None, a tuple -- is printed so here, since the
--          GOOD file is one. Where Python raises FsmError, the method returns
--          false and its 'error' is printed the same way.
-- _____________________________________________________________________________
use std.textio.all;
use work.hwut_runner.all;
use work.hwut_pytext.all;
use work.hwut_fsm.all;

entity test_hwut_fsm is
    generic (HWUT_ARGC : natural := 0; HWUT_ARGV1 : string := "");
end entity;

architecture test of test_hwut_fsm is
    constant PROTOCOL : string :=
        LF &
        "    initial:   idle" & LF &
        "    forbidden: crashed" & LF &
        "    final:     idle" & LF &
        "    idle    ---( request )---> waiting ---( grant )---> busy" & LF &
        "    busy    ---( release )---> idle" & LF &
        "    :       ---( fault )--->   crashed       # the state that began line 6" & LF &
        "    waiting ---( cancel )---> idle" & LF;

    procedure banner(label_text : string) is
    begin print(""); print("--- " & label_text & " ---"); end procedure;

    procedure protocol_machine(variable m : inout Machine; name : string := "fsm") is
        -- RETURN: nothing; 'm' is the PROTOCOL -- a valid model.
    begin
        assert m.from_string(PROTOCOL, true, name) severity failure;
    end procedure;

    procedure say_path(prefix : string; variable m : inout Machine; state_name : string;
                       start : string := ""; masked : boolean := true) is
        -- RETURN: nothing; 'prefix' and the path were printed as Python
        --         prints the tuple 'path_to' returns -- "('request', 'grant')",
        --         "('grant',)", "()" -- or 'None' where none leads there.
    begin
        if m.state_reachable(state_name, start, masked) then print(prefix & tuple_repr(m.path_to(state_name, start, masked)));
        else                                                 print(prefix & "None");
        end if;
    end procedure;

    function field(entry : string; k : natural) return string is
        -- RETURN: string, the k-th (from 0) of the HT-separated fields of 'entry'.
        variable text : string(1 to entry'length) := entry;
    begin
        for i in text'range loop
            if text(i) = HT then text(i) := LF; end if;
        end loop;
        return item(text & LF, k);
    end function;

    procedure run_syntax is
        variable m : Machine;
    begin
        protocol_machine(m);
        banner("the protocol, written back");
        print(m.to_string);
        m.free;
        banner("the author's form: 'state', a chain, ':', blanks around '-->'");
        assert m.from_string(LF &
            "        state A ---( event )---> state B" & LF &
            "        :                ---(event2)---> state C ---(event) --> state D" & LF &
            "        state E          # no transition yet" & LF) severity failure;
        print(m.to_string);
        m.free;
    end procedure;

    procedure refused_one(text : string) is
        -- RETURN: nothing; 'text' was offered as a model: 'accepted', or the
        --         FsmError's text, under a banner of the text on one line.
        variable label_text : line := new string'("");
        variable m          : Machine;
    begin
        for i in text'range loop
            if text(i) = LF then write(label_text, string'(" | "));
            else                 write(label_text, text(i to i));
            end if;
        end loop;
        banner(label_text.all);
        if m.from_string(text) then print("accepted"); m.free;
        else                        print("FsmError: " & m.error);
        end if;
    end procedure;

    procedure run_refused is
    begin
        refused_one("A ---( x )---> B" & LF & ": ---( x )---> C");
        refused_one("A ---(  )---> B");
        refused_one(": ---( x )---> B");
        refused_one("A B ---( x )---> C");
        refused_one("initial: A, B" & LF & "A ---( x )---> B");
        refused_one("forbidden: Q" & LF & "A ---( x )---> B");
        refused_one("# nothing but a comment");
    end procedure;

    procedure run_dfa is
        constant event : str_list := "request" & LF & "release" & LF & "grant" & LF & "release" & LF
                                     & "jump" & LF & "request" & LF;
        variable m     : Machine;
        variable moved : boolean;
        variable text  : line := new string'("trace:");
    begin
        protocol_machine(m);
        for i in 0 to item_n(event) - 1 loop
            moved := m.fire(item(event, i), integer'image(i + 1));
            print("    " & ljust(item(event, i), 8) & " -> " & ljust(bool_repr(moved), 5) & " now "
                  & ljust(m.state, 8) & " allowed: " & joined(m.allowed, ", "));
        end loop;
        banner("questions where it stands");
        print("can('grant')   " & bool_repr(m.can("grant")));
        print("can('release') " & bool_repr(m.can("release")));
        print("in_state('waiting') " & bool_repr(m.in_state("waiting")));
        for i in 0 to item_n(m.trace) - 1 loop
            write(text, " " & field(item(m.trace, i), 0) & ":" & field(item(m.trace, i), 2) & ">"
                        & field(item(m.trace, i), 3));
        end loop;
        print(text.all);
        m.free;
    end procedure;

    procedure run_nfa is
        constant event : str_list := "x" & LF & "z" & LF & "y" & LF;
        variable m     : Machine;
    begin
        assert m.from_string(LF &
            "        A ---( x )---> B ---( y )---> D" & LF &
            "        : ---( x )---> C ---( y )---> E" & LF &
            "        C ---( z )---> F" & LF, false) severity failure;
        for i in 0 to item_n(event) - 1 loop
            m.fire(item(event, i), "t=" & item(event, i));
            print("    after " & item(event, i) & ": " & joined(m.current, ", "));
        end loop;
        banner("'state' asked of a set");
        m.reset;
        m.fire("x");
        if m.state /= "" then print(m.state);
        else                  print("FsmError: " & m.error);
        end if;
        m.free;
    end procedure;

    procedure run_forbidden is
        constant event : str_list := "request" & LF & "grant" & LF & "fault" & LF;
        variable m     : Machine;
    begin
        protocol_machine(m);
        for i in 0 to item_n(event) - 1 loop
            print("    " & ljust(item(event, i), 8) & " -> " & bool_repr(m.fire(item(event, i), integer'image(i + 1))));
        end loop;
        print("now in " & m.state & " -- breaches: " & integer'image(m.breach_n));
        m.free;
    end procedure;

    procedure run_model is
        constant goal : str_list := "busy" & LF & "crashed" & LF & "limbo" & LF & "idle" & LF;
        variable m    : Machine;
    begin
        assert m.from_string(PROTOCOL & LF & "    state limbo" & LF & "    limbo ---( kick )---> idle" & LF)
            severity failure;
        print("check: " & integer'image(m.check));
        banner("path_to");
        for i in 0 to item_n(goal) - 1 loop say_path("    " & ljust(item(goal, i), 8) & " ", m, item(goal, i)); end loop;
        m.fire("request");
        say_path("    busy from now: ", m, "busy", "now");
        print("    state_reachable('idle', start='now'): " & bool_repr(m.state_reachable("idle", "now")));
        m.free;
    end procedure;

    procedure run_report is
        constant event : str_list := "request" & LF & "grant" & LF & "release" & LF & "request" & LF
                                     & "grant" & LF;
        variable m     : Machine;
        variable n     : natural;
    begin
        protocol_machine(m, "protocol");
        for i in 0 to item_n(event) - 1 loop m.fire(item(event, i)); end loop;
        n := m.print_report;
        print("report returns " & integer'image(n));
        m.free;
    end procedure;

    procedure run_masks is
        variable m     : Machine;
        variable n     : natural;
        variable fault : boolean;
    begin
        protocol_machine(m);

        banner("'grant' disallowed in every state, since line 2");
        m.disallow("grant", "", "2");
        m.fire("request", "3");
        print("    allowed now: " & joined(m.allowed, ", ") & " -- can('grant'): " & bool_repr(m.can("grant")));
        m.fire("grant", "4");
        say_path("    path_to('busy'):               ", m, "busy");
        say_path("    path_to('busy', masked=False): ", m, "busy", "", false);
        n := m.check;        print("    check(): " & integer'image(n));
        n := m.check(false); print("    check(masked=False): " & integer'image(n));

        banner("allowed again; 'busy' forbidden while standing in it");
        m.allow("grant");
        m.fire("grant", "6");
        m.forbid("busy", "7");
        m.fire("release", "8");
        m.fire("request", "9");
        m.fire("grant", "10");

        banner("permitted: 'busy', and the model's own 'crashed'");
        m.permit("busy", "11");
        m.permit("crashed", "12");
        fault := m.fire("fault", "13");
        print("    fault -> " & bool_repr(fault) & " -- now in " & m.state);

        banner("a phase: 'release' disallowed in 'busy' for a block");
        m.reset;
        m.fire("request"); m.fire("grant");
        m.disallow("release", "busy", "phase");             -- with m.disallowed(...):
        m.fire("release", "20");
        m.allow("release", "busy");                         -- ... the block left
        m.fire("release", "21");
        m.disallow("cancel", "", "22");
        n := m.print_report;

        banner("refused: a word the model never names");
        if not m.disallow("jump")           then print("FsmError: " & m.error); end if;
        if not m.forbid("limbo")            then print("FsmError: " & m.error); end if;
        if not m.allow("grant", "nowhere")  then print("FsmError: " & m.error); end if;
        m.free;
    end procedure;
begin
    main : process
        variable runner : HwutRunner;
    begin
        runner.init(HWUT_ARGC, HWUT_ARGV1, "hwut_fsm: a state machine as the test's model of the system");
        runner.add("syntax"); runner.add("refused"); runner.add("dfa");    runner.add("nfa");
        runner.add("forbidden"); runner.add("model"); runner.add("report"); runner.add("masks");
        while runner.dispatch loop
            if    runner.choice = "syntax"    then run_syntax;
            elsif runner.choice = "refused"   then run_refused;
            elsif runner.choice = "dfa"       then run_dfa;
            elsif runner.choice = "nfa"       then run_nfa;
            elsif runner.choice = "forbidden" then run_forbidden;
            elsif runner.choice = "model"     then run_model;
            elsif runner.choice = "report"    then run_report;
            elsif runner.choice = "masks"     then run_masks;
            end if;
            runner.choice_done;
        end loop;
        wait;
    end process;
end architecture;
