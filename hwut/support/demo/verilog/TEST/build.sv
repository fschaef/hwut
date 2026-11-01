// @hwut {
//     title   = "Demo: a recursive build, serial and parallel -- one summary, by a pype system"
//     build   { framework = "make", executable = "%.exe"
//               caps { memory_mb = 2048  file_size_mb = 256  disk_mb = 1024 } }
//     pype    = "build.pypes"
//     same    = true
//     choices = ["serial", "parallel"]
//     features = ["pype-in-header", "pype-system", "same-nominal", "choices-as-list",
//                 "pype-push-pop", "pype-entry-exit", "pype-import", "pype-repeat-group",
//                 "pype-quantity", "pype-anchors-globs-flush"]
//     tolerance { constraints = ["compile < 5 s", "breaches == 0"] }
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// SUBJECT  the log of a recursive build -- configure, then the directories
//          'lib', 'app' and, inside 'app', 'app/plugins' -- and the summary
//          a pype system makes of it.
// REQUIREMENT  A parallel build builds what the serial build builds: the same
//              sources, the same warnings, the same archives and the same
//              program, linked from the same parts.
//
// The application only REPORTS the build as it happens, as 'make -w' would.
// The header's 'pype = "build.pypes"' puts a SYSTEM of two pype scripts
// between it and the comparison (hwut runs it; the application prints no
// '<hwut-end>'):
//
//     build.pypes       --> normalise.pype         stdin to the first
//                       normalise.pype --> build.pype
//     normalise.pype    a parallel build tags each line with its job,
//                       'job2: cc -c ...'; the tag goes, every other line
//                       passes unchanged ('flush')
//     build.pype        the summary, sorted -- see its own comments: modes
//                       pushed on 'Entering directory' and popped on
//                       'Leaving' (nested: 'app/plugins' inside 'app'),
//                       '<entry>'/'<exit>' around each, a vocabulary
//                       imported from 'compiler.pype', a repeat group over
//                       the parts of a link, durations read as quantities
//
// 'same = true': BOTH CHOICES SHARE ONE GOOD, 'GOOD/build.sv.txt'. Serial or
// parallel, the summary must be the same -- that is the requirement, and
// the header says it once. 'choices' is a list: no choice states anything
// of its own.
//
// The laws: the compile times sum to under 5 s ('((compile: ...))', in
// s, whatever unit the log used), and nothing in the log broke the build's
// grammar ('((breaches: 0))').
//
// THE JOBS ARE PROCESSES of the simulation ('fork ... join'), a compilation
// a delay drawn at random, in SIMULATED time: which job finishes first is
// the draw's.
//
// A HEADER'S PYPE READS THE OUTPUT AFTER THE RUN: the whole stream at once.
// Time as the pype sees it -- 'pype.time()', 'tick:' -- is no time of the
// build here; a pype that judges time is fed live ('protocol.sh slow').
// _____________________________________________________________________________
import hwut_runner::*;
import deterministic_random::*;

module build;
    timeunit 1ms;
    timeprecision 1us;

    DeterministicStream stream;
    //  What each directory does: its sources, warnings and products.
    string source_db[string][$];
    string warning_db[string];      // source -> its warning
    string product_db[string];

    function automatic void setup();
        // RETURN: nothing; the stream is seeded by 64 bits of '/dev/urandom'
        //         and the directories are known.
        longint seed = 0;
        int     fd;
        fd = $fopen("/dev/urandom", "rb");
        if (fd != 0) begin void'($fread(seed, fd)); $fclose(fd); end
        seed   = (seed ^ (seed >> 31)) & 'h7FFFFFFF;
        stream = new(seed == 0 ? 1 : seed);
        source_db["lib"].push_back("lib/str.c");
        source_db["lib"].push_back("lib/num.c");
        source_db["lib"].push_back("lib/map.c");
        warning_db["lib/num.c"] = "lib/num.c:14:9: warning: unused variable 'n'";
        product_db["lib"] = "ar rcs lib/libcore.a lib/str.o lib/num.o lib/map.o";
        source_db["app/plugins"].push_back("app/plugins/png.c");
        source_db["app/plugins"].push_back("app/plugins/svg.c");
        warning_db["app/plugins/svg.c"] = "app/plugins/svg.c:3:1: warning: implicit declaration of 'xml_open'";
        product_db["app/plugins"] = "ar rcs app/plugins/libplug.a app/plugins/png.o app/plugins/svg.o";
        source_db["app"].push_back("app/main.c");
        source_db["app"].push_back("app/cli.c");
        product_db["app"] = "ld -o app/demo app/main.o app/cli.o lib/libcore.a app/plugins/libplug.a";
    endfunction

    task automatic compile_lines(string name, ref string line_list[$]);
        // RETURN: nothing; what building directory 'name' prints was added to
        //         'line_list', its sources compiled in the time each takes.
        foreach (source_db[name][i]) begin
            string source = source_db[name][i];
            real   took   = 0.04 + 0.08 * stream.next_float();
            string spent;
            #(took * 1000.0);
            spent = took < 0.1 ? $sformatf("%0d ms", $rtoi(took * 1000.0)) : $sformatf("%.2f s", took);
            line_list.push_back($sformatf("cc -c %s -o %s.o (took %s)", source,
                                          source.substr(0, source.len() - 3), spent));
            if (warning_db.exists(source)) line_list.push_back(warning_db[source]);
        end
    endtask

    task automatic directory_block(string name, int level, string inner, ref string line_list[$]);
        // RETURN: nothing; the block 'make -w' prints for 'name' at 'level'
        //         was added to 'line_list', the block of 'inner' ('' none)
        //         nested before the product.
        line_list.push_back($sformatf("make[%0d]: Entering directory '%s'", level, name));
        compile_lines(name, line_list);
        if (inner.len()) begin
            line_list.push_back($sformatf("make[%0d]: Entering directory '%s'", level + 1, inner));
            compile_lines(inner, line_list);
            line_list.push_back(product_db[inner]);
            line_list.push_back($sformatf("make[%0d]: Leaving directory '%s'", level + 1, inner));
        end
        line_list.push_back(product_db[name]);
        line_list.push_back($sformatf("make[%0d]: Leaving directory '%s'", level, name));
    endtask

    function automatic void configure();
        // RETURN: nothing; what 'configure' prints was printed, and that make
        //         enters the top directory.
        $display("configure: checking for cc... cc");
        $display("configure: checking for ar... ar");
        $display("make: Entering directory 'demo'");
    endfunction

    task automatic serial();
        // RETURN: nothing; one directory was built after the other.
        string line_list[$] = {};
        configure();
        directory_block("lib", 1, "", line_list);
        directory_block("app", 1, "app/plugins", line_list);
        foreach (line_list[i]) $display("%s", line_list[i]);
        $display("make: Leaving directory 'demo'");
    endtask

    task automatic job(int slot, string name, string inner);
        // RETURN: nothing; the job 'slot' built 'name' and printed its block
        //         whole when done ('make -O'), every line tagged with the job.
        string line_list[$] = {};
        directory_block(name, 1, inner, line_list);
        foreach (line_list[i]) $display("job%0d: %s", slot, line_list[i]);
    endtask

    task automatic parallel();
        // RETURN: nothing; 'lib' and 'app' were built at once; which job
        //         finished first is the draw's.
        configure();
        fork
            job(1, "lib", "");
            job(2, "app", "app/plugins");
        join
        $display("make: Leaving directory 'demo'");
    endtask

    initial begin
        string choice = hwut_sv_argc() > 1 ? hwut_sv_argv(1) : "";
        setup();
        case (choice)
            "serial":   serial();
            "parallel": parallel();
            default: begin
                $display("choices: serial, parallel");
                exit_(1);
            end
        endcase
        exit_(0);
    end
endmodule
