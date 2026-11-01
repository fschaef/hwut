// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: FRONT END OF A HWUT TEST APPLICATION IN SYSTEMVERILOG -- the port
//          of 'python/hwut_runner.py': the same modes, the same words.
//
//     app --hwut-info      the info block; exit 0.
//     app <choice>         one choice; test output on stdout and stderr,
//                          '<hwut-end>' after it. '-' runs a choice-less test.
//     app --interactive    choices started over stdin, output into two named
//                          sink files per choice, 'done' on the original stdout.
//     app                  the choice-less test; where the application has
//                          choices, refused, naming them.
//
// USAGE: a test DERIVES its runner and says in 'play' what each choice does:
//
//     class Test extends hwut_runner::HwutRunner;
//         function new(); super.new("What this tests", '{"plain", "tricky"}); endfunction
//         virtual task play(string choice);
//             case (choice)
//                 "plain":  run_plain();
//                 "tricky": run_tricky();
//             endcase
//         endtask
//     endclass
//
//     module test_x; initial begin Test t = new(); t.run(); end endmodule
//
// 'run' ENDS THE PROCESS with the mode's exit status -- a simulation ends by
// '$finish' or not at all, and the protocol wants the status. A choice is a
// TASK: it may wait, fork and consume simulation time. A choice-less test
// names its one choice "-". Before 'run' a test may set 'happy' (patterns),
// 'same_f' and 'parallel_f' (interactive: choices run concurrently).
//
// THE INTERACTIVE PROTOCOL is Python's, line for line:
//     DOWN  run <choice> <sink-out> <sink-err> | info | quit | q | exit
//     UP    done <choice> <status> | fail <choice> <reason> | info: <line> | bye
// EVERY CHOICE RUNS IN A CHILD PROCESS of its own ('fork', through DPI-C): the
// child is the whole simulation, copied where the parent stood, so it runs
// the choice and ends; a choice that exits or crashes ends that choice, not
// the session, and no choice inherits another's state.
//
// THE OPERATING SYSTEM (the command line, fork, the file descriptors, exit)
// is reached through 'hwut_runner_dpi.c'; the rest is SystemVerilog.
// _____________________________________________________________________________
package hwut_runner;

    import "DPI-C" function int    hwut_sv_argc();
    import "DPI-C" function string hwut_sv_argv(int i);
    import "DPI-C" function void   hwut_sv_exit(int status);
    import "DPI-C" function void   hwut_sv_flush();
    import "DPI-C" function int    hwut_sv_env_defined(string name);
    import "DPI-C" function int    hwut_sv_interactive_begin();
    import "DPI-C" function void   hwut_sv_up(string message);
    import "DPI-C" function int    hwut_sv_read_line(output string line);
    import "DPI-C" function int    hwut_sv_fork_into_sinks(string sink_out, string sink_err);
    import "DPI-C" function int    hwut_sv_reap(int pid, int block_f, output int status);

    localparam string NONE = "-";

    function automatic void exit_(int status);
        // RETURN: never; the process ends with 'status', stdout and stderr
        //         flushed -- Python's 'sys.exit(status)'.
        hwut_sv_exit(status);
    endfunction

    function automatic int levenshtein_distance(string a, string b);
        // RETURN: the Levenshtein distance between 'a' and 'b', >= 0.
        int prev[$] = {};
        int cur[$] = {};
        string t;
        if (a == b)       return 0;
        if (a.len() == 0) return b.len();
        if (b.len() == 0) return a.len();
        if (a.len() < b.len()) begin t = a; a = b; b = t; end
        for (int j = 0; j <= b.len(); j++) begin prev.push_back(j); cur.push_back(0); end
        for (int i = 1; i <= a.len(); i++) begin
            cur[0] = i;
            for (int j = 1; j <= b.len(); j++) begin
                int ins = cur[j - 1] + 1;
                int del = prev[j] + 1;
                int sub = prev[j - 1] + (a[i - 1] != b[j - 1]);
                int m   = ins < del ? ins : del;
                cur[j]  = m < sub ? m : sub;
            end
            prev = cur;
        end
        return prev[b.len()];
    endfunction

    function automatic string levenshtein_best_match(string needle, string haystack[$]);
        // RETURN: the element of 'haystack' least distant from 'needle', the
        //         first of equals; '' where 'haystack' is empty.
        string best   = "";
        int    best_d = -1;
        foreach (haystack[i]) if (haystack[i] == needle) return needle;
        foreach (haystack[i]) begin
            int d = levenshtein_distance(needle, haystack[i]);
            if (best_d < 0 || d < best_d) begin best_d = d; best = haystack[i]; end
        end
        return best;
    endfunction

    virtual class HwutRunner;
        string title;
        string choice_list[$];      // as given
        string sorted[$];           // as hwut is told them
        string happy[$];            // 'HAPPY: <pattern>;' each
        bit    same_f;              // 'SAME;'
        bit    parallel_f;          // interactive: choices run concurrently
        protected int    pending_pid[$];
        protected string pending_token[$];

        function new(string title, string choice_list[$]);
            // RETURN: a runner of the application 'title' with the choices
            //         'choice_list' -- '{"-"}' for a choice-less test.
            this.title       = title;
            this.choice_list = choice_list;
            this.sorted      = choice_list;
            this.sorted.sort();
        endfunction

        pure virtual task play(string choice);
        // RETURN: nothing; the choice 'choice' -- one of 'choice_list' -- ran.

        function bit none_f();
            // RETURN: 1 where the application is choice-less ('-' its one
            //         choice); 0 else.
            return choice_list.size() == 1 && choice_list[0] == NONE;
        endfunction

        function bit known_f(string name);
            // RETURN: 1 where 'name' is one of the choices; 0 else.
            foreach (choice_list[i]) if (choice_list[i] == name) return 1;
            return 0;
        endfunction

        function void info_lines(ref string line_list[$]);
            // RETURN: nothing; 'line_list' holds the info block, line by line.
            string text = title;
            if (text.len() == 0 || text[text.len() - 1] != ";") text = {text, ";"};
            line_list = {text};
            if (!none_f()) begin
                text = "CHOICES: ";
                foreach (sorted[i]) text = {text, (i ? string'(", ") : string'("")), sorted[i]};
                line_list.push_back({text, ";"});
            end
            foreach (happy[i]) line_list.push_back({"HAPPY: ", happy[i], ";"});
            if (same_f) line_list.push_back("SAME;");
            line_list.push_back("INTERACTIVE;");
        endfunction

        function string choice_list_text();
            // RETURN: the sorted choices, ', ' between each two.
            string text = "";
            foreach (sorted[i]) text = {text, (i ? string'(", ") : string'("")), sorted[i]};
            return text;
        endfunction

        task run();
            // RETURN: never; the mode the command line selects ran (see the
            //         head) and the process ended with its exit status -- a
            //         refusal exits 1.
            string word = hwut_sv_argc() > 1 ? hwut_sv_argv(1) : "";
            string best;
            if (hwut_sv_argc() > 1 && word inside {"-h", "--hi", "--hwut-info", "--sos", "--wtf"}) begin
                string line_list[$] = {};
                info_lines(line_list);
                foreach (line_list[i]) $display("%s", line_list[i]);
                exit_(0);
            end
            if (word == "--interactive") begin
                mode_interactive();
                exit_(0);
            end
            if (hwut_sv_argc() <= 1) begin
                if (none_f()) run_one(NONE);
                $display("error: a choice is required: %s -- name one, or let 'hwut.play' ask.", choice_list_text());
                exit_(1);
            end
            if (known_f(word)) run_one(word);
            if (none_f()) begin
                $display("error: '%s': this application has no choices -- call it without one.", word);
                exit_(1);
            end
            $display("error: choice '%s' not available.", word);
            $display("error: available: %s.", choice_list_text());
            best = levenshtein_best_match(word, sorted);
            if (best != "") $display("error: did you mean '%s'?", best);
            exit_(1);
        endtask

        protected task run_one(string choice);
            // RETURN: never; the choice ran, then '<hwut-end>' (R-70), and
            //         the process ended with 0.
            play(choice);
            $display("<hwut-end>");
            exit_(0);
        endtask

        // ---------------------------------------------------- interactive mode
        protected function void reap(bit block_f);
            // RETURN: nothing; every child that has ended is reported 'done';
            //         with 'block_f' it waits until none is left.
            int status;
            while (pending_pid.size() > 0) begin
                int pid = hwut_sv_reap(-1, block_f, status);
                if (pid <= 0) return;
                foreach (pending_pid[i]) begin
                    if (pending_pid[i] != pid) continue;
                    hwut_sv_up($sformatf("done %s %0d", pending_token[i], status));
                    pending_pid.delete(i);
                    pending_token.delete(i);
                    break;
                end
            end
        endfunction

        protected function bit find_choice(string token, output string choice);
            // RETURN: 1, 'token' names a choice -- by name, by its index into
            //         the sorted list, or '-' for the choice-less test -- and
            //         'choice' is its name; 0, else.
            int index = 0;
            choice = "";
            if (known_f(token)) begin choice = token; return 1; end
            if (token.len() == 0) return 0;
            for (int i = 0; i < token.len(); i++) begin
                if (token[i] < "0" || token[i] > "9") return 0;
                index = 10 * index + (token[i] - "0");
                if (index > sorted.size()) return 0;
            end
            if (index >= sorted.size()) return 0;
            choice = sorted[index];
            return 1;
        endfunction

        protected task run_into_sinks(string choice, string sink_out, string sink_err, string token,
                                      output int status, output bit later_f);
            // RETURN: nothing; 'status' is the exit status of the child that
            //         ran 'choice' into the sinks (1 where none could be
            //         made); with 'parallel_f' it runs on, 'later_f' is 1 and
            //         it is reported when reaped.
            int pid = hwut_sv_fork_into_sinks(sink_out, sink_err);
            later_f = 0;
            status  = 1;
            if (pid < 0) return;
            if (pid == 0) begin                                      // the child
                play(choice);
                if (!hwut_sv_env_defined("HWUT_NO_TERMINAL")) $display("<hwut-end>");
                exit_(0);
            end
            if (parallel_f) begin
                pending_pid.push_back(pid);
                pending_token.push_back(token);
                later_f = 1;
                return;
            end
            void'(hwut_sv_reap(pid, 1, status));
        endtask

        protected function void words_of(string line, ref string word_list[$]);
            // RETURN: nothing; 'word_list' holds the words of 'line', split
            //         at blanks and tabs.
            string word = "";
            word_list = {};
            for (int i = 0; i <= line.len(); i++) begin
                if (i == line.len() || line[i] == " " || line[i] == "\t") begin
                    if (word.len()) word_list.push_back(word);
                    word = "";
                end else word = {word, string'(line[i])};
            end
        endfunction

        protected task interprete(string line, output bit go_on_f);
            // RETURN: nothing; the command 'line' was served; 'go_on_f' 1,
            //         the session goes on; 0, it ends.
            string field[$] = {};
            string choice;
            go_on_f = 1;
            words_of(line, field);
            if (field.size() == 1 && field[0] inside {"quit", "q", "exit"}) begin
                go_on_f = 0;
                return;
            end
            if (field.size() == 1 && field[0] == "info") begin
                string line_list[$] = {};
                info_lines(line_list);
                foreach (line_list[i]) hwut_sv_up({"info: ", line_list[i]});
                hwut_sv_up("done - 0");
                return;
            end
            if (field.size() == 4 && field[0] == "run") begin
                if (!find_choice(field[1], choice)) hwut_sv_up({"fail ", field[1], " unknown-choice"});
                else begin
                    int status;
                    bit later_f;
                    run_into_sinks(choice, field[2], field[3], field[1], status, later_f);
                    if (!later_f) hwut_sv_up($sformatf("done %s %0d", field[1], status));
                end
                return;
            end
            hwut_sv_up("fail - bad-command");
        endtask

        protected task mode_interactive();
            // RETURN: nothing; the session ended ('quit' or the end of the
            //         input), every child reported, 'bye' said.
            string line;
            bit    go_on_f;
            void'(hwut_sv_interactive_begin());
            while (1) begin
                reap(0);
                if (!hwut_sv_read_line(line)) break;
                if (line.len() == 0) continue;
                interprete(line, go_on_f);
                if (!go_on_f) break;
            end
            reap(1);
            hwut_sv_up("bye");
        endtask
    endclass

endpackage
