// @hwut {
//     title      = "hwut_fsm: a state machine as the test's model of the system"
//     build      { framework = "make", executable = "%.exe"
//                  caps { memory_mb = 2048 } }
//     choices {
//         syntax    { features = ["sv-fsm"] }
//         refused   { features = ["sv-fsm"] }
//         dfa       { features = ["sv-fsm"] }
//         nfa       { features = ["sv-fsm"] }
//         forbidden { features = ["sv-fsm"] }
//         model     { features = ["sv-fsm"] }
//         report    { features = ["sv-fsm"] }
//         masks     { features = ["sv-fsm"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: The SystemVerilog port of 'python/TEST/test-hwut_fsm.py', choice for
//          choice, held against its GOOD files by '.link'. What Python prints
//          of its own values -- True, None, a tuple -- is printed so here, since
//          the GOOD file is one. Where Python raises FsmError, the call returns
//          null or 0 and the error text is printed the same way.
// _____________________________________________________________________________
import hwut_runner::*;
import hwut_pytext::*;
import hwut_fsm::*;

class Test extends HwutRunner;
    //  THE PROTOCOL OF EVERY CHOICE: a request is waited on, granted,
    //  released; a fault while busy crashes it -- which must never happen.
    localparam string PROTOCOL = {
        "\n",
        "    initial:   idle\n",
        "    forbidden: crashed\n",
        "    final:     idle\n",
        "    idle    ---( request )---> waiting ---( grant )---> busy\n",
        "    busy    ---( release )---> idle\n",
        "    :       ---( fault )--->   crashed       # the state that began line 6\n",
        "    waiting ---( cancel )---> idle\n"};

    function new();
        // RETURN: the runner of this test.
        super.new("hwut_fsm: a state machine as the test's model of the system",
                  '{"syntax", "refused", "dfa", "nfa", "forbidden", "model", "report", "masks"});
    endfunction

    function void banner(string label);
        // RETURN: nothing; the section heading is printed.
        $display("");
        $display("--- %s ---", label);
    endfunction

    function string path_text(Machine m, string state, string start = "", bit masked = 1);
        // RETURN: the path as Python prints the tuple 'path_to' returns --
        //         "('request', 'grant')", "('grant',)", "()" -- 'None' where none.
        string_list_t path;
        if (!m.path_to(state, path, start, masked)) return "None";
        return tuple_repr(path);
    endfunction

    function void run_syntax();
        // RETURN: nothing; models read from text and written back.
        Machine m;
        banner("the protocol, written back");
        m = Machine::from_string(PROTOCOL);
        $display("%s", m.to_string());
        banner("the author's form: 'state', a chain, ':', blanks around '-->'");
        m = Machine::from_string({
            "\n",
            "        state A ---( event )---> state B\n",
            "        :                ---(event2)---> state C ---(event) --> state D\n",
            "        state E          # no transition yet\n",
            "    "});
        $display("%s", m.to_string());
    endfunction

    function void run_refused();
        // RETURN: nothing; each model that cannot be meant, and why.
        string text_list[$] = '{
            "A ---( x )---> B\n: ---( x )---> C",
            "A ---(  )---> B",
            ": ---( x )---> B",
            "A B ---( x )---> C",
            "initial: A, B\nA ---( x )---> B",
            "forbidden: Q\nA ---( x )---> B",
            "# nothing but a comment"};
        foreach (text_list[k]) begin
            string text  = text_list[k];
            string label = "";
            for (int i = 0; i < text.len(); i++) label = {label, (text[i] == "\n") ? string'(" | ") : string'(text[i])};
            banner(label);
            if (Machine::from_string(text) != null) $display("accepted");
            else                                    $display("FsmError: %s", Machine::refusal);
        end
    endfunction

    function void run_dfa();
        // RETURN: nothing; events fired, one machine.
        Machine       m = Machine::from_string(PROTOCOL);
        string        event_list[$] = '{"request", "release", "grant", "release", "jump", "request"};
        trace_entry_t trace[$] = {};
        string        said = "trace:";
        foreach (event_list[i]) begin
            bit moved = m.fire(event_list[i], $sformatf("%0d", i + 1));
            $display("    %s -> %s now %s allowed: %s", padded(event_list[i], 8), padded(bool_repr(moved), 5),
                     padded(m.state_text(), 8), join_text(m.allowed()));
        end
        banner("questions where it stands");
        $display("can('grant')   %s", bool_repr(m.can("grant")));
        $display("can('release') %s", bool_repr(m.can("release")));
        $display("in_state('waiting') %s", bool_repr(m.in_state("waiting")));
        m.trace(trace);
        foreach (trace[i]) said = {said, " ", trace[i].where, ":", trace[i].event_, ">", trace[i].target};
        $display("%s", said);
    endfunction

    function void run_nfa();
        // RETURN: nothing; DFA 0: several states at once.
        Machine m = Machine::from_string({
            "\n",
            "        A ---( x )---> B ---( y )---> D\n",
            "        : ---( x )---> C ---( y )---> E\n",
            "        C ---( z )---> F\n",
            "    "}, .DFA(0));
        string  event_list[$] = '{"x", "z", "y"};
        string  one;
        foreach (event_list[i]) begin
            void'(m.fire(event_list[i], {"t=", event_list[i]}));
            $display("    after %s: %s", event_list[i], join_text(m.current()));
        end
        banner("'state' asked of a set");
        m.reset();
        void'(m.fire("x"));
        if (m.state(one)) $display("%s", one);
        else              $display("FsmError: %s", m.error);
    endfunction

    function void run_forbidden();
        // RETURN: nothing; a forbidden state entered.
        Machine m = Machine::from_string(PROTOCOL);
        string  event_list[$] = '{"request", "grant", "fault"};
        foreach (event_list[i]) begin
            bit moved = m.fire(event_list[i], $sformatf("%0d", i + 1));
            $display("    %s -> %s", padded(event_list[i], 8), bool_repr(moved));
        end
        $display("now in %s -- breaches: %0d", m.state_text(), m.breach_n());
    endfunction

    function void run_model();
        // RETURN: nothing; the model alone.
        Machine m = Machine::from_string({PROTOCOL, "\n    state limbo\n    limbo ---( kick )---> idle\n"});
        string  goal[$] = '{"busy", "crashed", "limbo", "idle"};
        int     n = m.check();
        $display("check: %0d", n);
        banner("path_to");
        foreach (goal[i]) $display("    %s %s", padded(goal[i], 8), path_text(m, goal[i]));
        void'(m.fire("request"));
        $display("    busy from now: %s", path_text(m, "busy", "now"));
        $display("    state_reachable('idle', start='now'): %s", bool_repr(m.state_reachable("idle", "now")));
    endfunction

    function void run_report();
        // RETURN: nothing; coverage, and an end outside the final states.
        Machine m = Machine::from_string(PROTOCOL, .name("protocol"));
        string  event_list[$] = '{"request", "grant", "release", "request", "grant"};
        int     breach_n;
        foreach (event_list[i]) void'(m.fire(event_list[i]));
        breach_n = m.report();
        $display("report returns %0d", breach_n);
    endfunction

    function void run_masks();
        // RETURN: nothing; the law changing while the machine runs.
        Machine m = Machine::from_string(PROTOCOL);
        Phase   phase;
        bit     moved;
        int     n;
        banner("'grant' disallowed in every state, since line 2");
        void'(m.disallow("grant", .where("2")));
        void'(m.fire("request", "3"));
        $display("    allowed now: %s -- can('grant'): %s", join_text(m.allowed()), bool_repr(m.can("grant")));
        void'(m.fire("grant", "4"));
        $display("    path_to('busy'):               %s", path_text(m, "busy"));
        $display("    path_to('busy', masked=False): %s", path_text(m, "busy", .masked(0)));
        n = m.check();
        $display("    check(): %0d", n);
        n = m.check(.masked(0));
        $display("    check(masked=False): %0d", n);
        banner("allowed again; 'busy' forbidden while standing in it");
        void'(m.allow("grant"));
        void'(m.fire("grant", "6"));
        void'(m.forbid("busy", "7"));
        void'(m.fire("release", "8"));
        void'(m.fire("request", "9"));
        void'(m.fire("grant", "10"));
        banner("permitted: 'busy', and the model's own 'crashed'");
        void'(m.permit("busy", "11"));
        void'(m.permit("crashed", "12"));
        moved = m.fire("fault", "13");
        $display("    fault -> %s -- now in %s", bool_repr(moved), m.state_text());
        banner("a phase: 'release' disallowed in 'busy' for a block");
        m.reset();
        void'(m.fire("request"));
        void'(m.fire("grant"));
        phase = m.disallowed("release", .state("busy"), .where("phase"));
        void'(m.fire("release", "20"));
        phase.close();
        void'(m.fire("release", "21"));
        void'(m.disallow("cancel", .where("22")));
        void'(m.report());
        banner("refused: a word the model never names");
        if (!m.disallow("jump"))              $display("FsmError: %s", m.error);
        if (!m.forbid("limbo"))               $display("FsmError: %s", m.error);
        if (!m.allow("grant", .state("nowhere"))) $display("FsmError: %s", m.error);
    endfunction

    virtual task play(string choice);
        // RETURN: nothing; the choice 'choice' ran.
        case (choice)
            "syntax":    run_syntax();
            "refused":   run_refused();
            "dfa":       run_dfa();
            "nfa":       run_nfa();
            "forbidden": run_forbidden();
            "model":     run_model();
            "report":    run_report();
            "masks":     run_masks();
        endcase
    endtask
endclass

module test_hwut_fsm;
    initial begin
        Test test = new();
        test.run();
    end
endmodule
