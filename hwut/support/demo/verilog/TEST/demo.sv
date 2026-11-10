// @hwut {
//     title   = "Demo: what hwut tolerates, and where it is said"
//     build   { framework = "make", target = "%.exe"
//               caps { memory_mb = 2048  file_size_mb = 256  disk_mb = 1024 } }
//     choices {
//         plain       { features = ["demo-verilog", "demo-verilog+cover-exact-comparison"] }
//         tolerance   { features = ["demo-verilog", "demo-verilog+cover-equivalence-pattern", "demo-verilog+cover-numeric-ratio"]
//                       tolerance {
//                           eq_pattern    = ["(hello|bonjour|hallo|buongiorno|hola|ahoj)"]
//                           numeric_ratio = 0.01
//                       } }
//         constraints { features = ["demo-verilog", "demo-verilog+cover-constraints"]
//                       tolerance {
//                           constraints = ["load >= 0 and load <= 100",
//                                          "even % 2 == 0",
//                                          "twice == 2 * once"]
//                       } }
//         analogies   { features = ["demo-verilog", "demo-verilog+cover-analogies"] }
//         race        { features = ["demo-verilog", "demo-verilog+cover-order-free-block"] }
//         pool        { features = ["demo-verilog", "demo-verilog+cover-potpourri-subset-duplicates"] }
//         progress    { features = ["demo-verilog", "demo-verilog+cover-visible-nothing"]
//                       tolerance { nothing = ["[.]+"] } }
//         lisp        { features = ["demo-verilog", "demo-verilog+cover-analogy-markers"]
//                       tolerance { analogy = ["{", "}"] } }
//         clusters    { features = ["demo-verilog", "demo-verilog+cover-point-cloud-pair-distance"] }
//     }
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// A TEST APPLICATION OF HWUT, FOR READING -- in SystemVerilog, a simulation
// built by Verilator ('make demo.exe'; hwut builds it by the header's 'build').
//
//     hwut.run                   runs every choice below, compares with GOOD/
//     hwut.play demo.sv plain    runs one choice and records it in OUT/
//     hwut.accept demo.sv plain  blesses that recording as GOOD; it runs
//                                nothing. Where a GOOD stands, the change
//                                is 'hwut.merge's -- or '--force' (also
//                                '--as-is') replaces it whole.
//     hwut.merge                 shows OUTPUT against GOOD, key by key
//     hwut.config.show demo.sv   prints what hwut READ from the header above
//
// The header above is the whole configuration: a title, the build, and one
// scope per choice. hwut calls 'demo.exe <choice>' and compares what it
// prints on stdout with 'GOOD/demo.sv--<choice>.txt' -- a link to the Python
// demonstration's GOOD: the same choice prints the same text. '<hwut-end>'
// closes the stream: a stream without it never COMPLETED and is not accepted.
//
// Every run is seeded anew (64 bits of '/dev/urandom' -- a simulation has no
// clock of the world), so the output differs from run to run -- and every
// choice passes anyway. Each shows WHY:
//
// plain        nothing varies; nothing is tolerated. The output must equal
//              GOOD, line by line.
//
// tolerance    'eq_pattern': a greeting drawn at random; any greeting the
//              pattern names is EQUIVALENT to any other.
//              'numeric_ratio': a value drawn from [19.91, 20.09]. The band
//              belongs to the GOOD's number, |n| x ratio: GOOD 19.91 against
//              20.09 differs by 0.18, inside 19.91 x 0.01 = 0.1991. Every
//              pair from the interval passes; 20.30 would not.
//
// constraints  '((name: value))' BINDS a value; the expressions under
//              'constraints' judge it, not the GOOD's value. 'load' may be
//              anything from 0 to 100; 'even' any even number; 'twice' must
//              be twice 'once', whatever 'once' is. A law over two variables
//              is checked once both are bound. A binding that breaks its law
//              is red.
//
// race         '##! potpourri' ... '####' opens a block whose lines may
//              arrive in ANY order -- three workers, three PROCESSES of the
//              simulation ('fork ... join'), print as they finish after a
//              delay drawn at random. The same lines must stand on both
//              sides, each once; the order is free. The program prints the
//              markers, and so does GOOD.
//
// analogies    '((x))' is a placeholder: '((a7f3))' against GOOD's
//              '((91c2))' is equivalent where the mapping holds throughout
//              the stream -- the same handle opened, read and closed. A
//              handle that changes in mid-stream is red.
//
// pool         '##! potpourri subset duplicates': four worker processes
//              share twelve jobs; who takes how many is the draw of their
//              delays. 'subset': a worker that got no job is no fault --
//              every line of the run must stand in GOOD, not every line of
//              GOOD in the run. 'duplicates': a worker named twice is one
//              line. The GOOD was recorded from a run in which all four
//              worked.
//
// progress     'nothing': a line made only of what the pattern names counts
//              as no line. A download prints dots while it waits -- none, or
//              a few lines of them -- and the dots are no fact.
//
// lisp         'analogy = ["{", "}"]': the output is Lisp, where '((' is
//              syntax, so the placeholder is marked otherwise. An object is
//              printed with its address, '{10044C1F33}'; the address differs
//              per run, and must be the same object throughout.
//
// clusters     '##! point-cloud limit=0.3 pair dist=Linf': three centroids of
//              a clustering, in whatever order the run finds them. 'pair':
//              each centroid pairs with ONE point of GOOD -- two centroids in
//              one cluster are red. 'dist=Linf': within 0.3 in x AND in y.
// _____________________________________________________________________________
import hwut_runner::*;
import deterministic_random::*;

class Draw;
    // The run's random numbers: hwut's stream, seeded anew per run.
    DeterministicStream stream;

    function new();
        // RETURN: a stream seeded by 64 bits of '/dev/urandom' -- by the
        //         clock, where that cannot be read.
        longint seed = 0;
        int     fd;
        fd = $fopen("/dev/urandom", "rb");
        if (fd != 0) begin void'($fread(seed, fd)); $fclose(fd); end
        if (seed == 0) seed = longint'($realtime);
        seed = (seed ^ (seed >> 31)) & 'h7FFFFFFF;
        stream = new(seed == 0 ? 1 : seed);
    endfunction

    function real uniform(real low, real high);
        // RETURN: a number drawn from [low, high).
        return low + (high - low) * stream.next_float();
    endfunction

    function int randint(int low, int high);
        // RETURN: an integer drawn from [low, high].
        return int'(stream.next_int(low, high));
    endfunction

    function real gauss(real mu, real sigma);
        // RETURN: a draw of the normal distribution (mu, sigma).
        return stream.gauss(mu, sigma);
    endfunction
endclass

module demo;
    timeunit 1ms;
    timeprecision 1us;

    Draw draw = new();

    task automatic plain();
        // RETURN: nothing; what never varies was printed.
        $display("the first line");
        $display("the second line: 1 2 3");
    endtask

    task automatic tolerance();
        // RETURN: nothing; a greeting and a value were printed, both drawn.
        string greeting[$] = {};
        greeting.push_back("hello");      greeting.push_back("bonjour");
        greeting.push_back("hallo");      greeting.push_back("buongiorno");
        greeting.push_back("hola");       greeting.push_back("ahoj");
        $display("greeting: %s, world", draw.stream.choice(greeting));
        $display("value:    %.2f", draw.uniform(19.91, 20.09));
    endtask

    task automatic constraints();
        // RETURN: nothing; bindings were printed, each drawn, each lawful.
        int once;
        $display("load  ((load: %.1f)) %%", draw.uniform(0.0, 100.0));
        $display("even  ((even: %0d))", 2 * draw.randint(0, 500));
        once = draw.randint(1, 50);
        $display("once  ((once: %0d))", once);
        $display("twice ((twice: %0d))", 2 * once);
    endtask

    task automatic analogies();
        // RETURN: nothing; two handles were printed, each drawn, each used
        //         consistently from opening to closing.
        int first  = draw.randint('h1000, 'hFFFF);
        int second = draw.randint('h1000, 'hFFFF);
        while (second == first) second = draw.randint('h1000, 'hFFFF);
        $display("open  ((%04h)) input.txt", first[15:0]);
        $display("open  ((%04h)) output.txt", second[15:0]);
        $display("read  ((%04h)) 17 lines", first[15:0]);
        $display("write ((%04h)) 17 lines", second[15:0]);
        $display("close ((%04h))", first[15:0]);
        $display("close ((%04h))", second[15:0]);
    endtask

    task automatic race();
        // RETURN: nothing; three workers printed as they finished; the order
        //         is the draw's, the facts are not. The program frames the
        //         unordered block itself: '##! potpourri' ... '####'.
        $display("start");
        $display("##! potpourri");
        fork
            begin #(draw.uniform(0.0, 20.0)); $display("worker A done: 3 jobs"); end
            begin #(draw.uniform(0.0, 20.0)); $display("worker B done: 5 jobs"); end
            begin #(draw.uniform(0.0, 20.0)); $display("worker C done: 2 jobs"); end
        join
        $display("####");
        $display("all joined");
    endtask

    task automatic worker(string name, ref int job_queue[$], ref string done_list[$]);
        // RETURN: nothing; the worker 'name' took jobs from 'job_queue' until
        //         none was left, each one it finished noted in 'done_list'.
        while (job_queue.size() > 0) begin
            void'(job_queue.pop_front());
            #(draw.uniform(0.0, 5.0));
            done_list.push_back({"job done by worker ", name});
        end
    endtask

    task automatic pool();
        // RETURN: nothing; four workers took twelve jobs from one queue, each
        //         reported the job it finished. Who takes how many is the
        //         draw's.
        int    job_queue[$] = {};
        string done_list[$] = {};
        for (int job = 0; job < 12; job++) job_queue.push_back(job);
        fork
            worker("A", job_queue, done_list);
            worker("B", job_queue, done_list);
            worker("C", job_queue, done_list);
            worker("D", job_queue, done_list);
        join
        $display("twelve jobs, four workers:");
        $display("##! potpourri subset duplicates");
        foreach (done_list[i]) $display("%s", done_list[i]);
        $display("####");
        $display("jobs done: %0d", done_list.size());
    endtask

    task automatic progress();
        // RETURN: nothing; a download printed dots while it waited; how many
        //         is the draw's.
        int line_n = draw.randint(0, 3);
        $display("connecting to mirror");
        for (int i = 0; i < line_n; i++) begin
            string dots = "";
            int    dot_n = draw.randint(1, 8);
            for (int k = 0; k < dot_n; k++) dots = {dots, "."};
            $display("%s", dots);
        end
        $display("connected");
        $display("received 1024 bytes");
    endtask

    function automatic string address(longint value);
        // RETURN: 'value' in upper-case hex, '{...}' around it.
        string text = $sformatf("%0h", value);
        return {"{", text.toupper(), "}"};
    endfunction

    task automatic lisp();
        // RETURN: nothing; a Lisp session at its prompt: two objects, each
        //         printed with its address '{...}', drawn anew per run, and
        //         each used again.
        longint cache  = draw.stream.next_int(64'h10_0000_0000, 64'h10_FFFF_FFFF);
        longint thread = draw.stream.next_int(64'h10_0000_0000, 64'h10_FFFF_FFFF);
        while (thread == cache) thread = draw.stream.next_int(64'h10_0000_0000, 64'h10_FFFF_FFFF);
        $display("* (defvar *cache* (make-hash-table))");
        $display("#<HASH-TABLE :TEST EQL :COUNT 0 %s>", address(cache));
        $display("* (defvar *worker* (make-thread (lambda () (loop (sleep 1))) :name \"worker\"))");
        $display("#<THREAD \"worker\" RUNNING %s>", address(thread));
        $display("* (let ((key (list 1 2))) (setf (gethash key *cache*) *worker*))");
        $display("#<THREAD \"worker\" RUNNING %s>", address(thread));
        $display("* *cache*");
        $display("#<HASH-TABLE :TEST EQL :COUNT 1 %s>", address(cache));
    endtask

    function automatic real distance2(real ax, real ay, real bx, real by);
        // RETURN: the square of the distance between (ax, ay) and (bx, by).
        return (ax - bx) * (ax - bx) + (ay - by) * (ay - by);
    endfunction

    task automatic clusters();
        // RETURN: nothing; 90 noisy points around three centres were
        //         clustered and the centroids printed in the order found.
        real px[$] = {}, py[$] = {};
        real cx[$] = {}, cy[$] = {};
        real centre_x[3] = '{1.0, 5.0, 9.0};
        real centre_y[3] = '{1.0, 4.0, 1.0};
        int  start;
        for (int c = 0; c < 3; c++)
            for (int k = 0; k < 30; k++) begin
                px.push_back(centre_x[c] + draw.gauss(0.0, 0.3));
                py.push_back(centre_y[c] + draw.gauss(0.0, 0.3));
            end
        for (int i = px.size() - 1; i > 0; i--) begin           // the shuffle
            int  j = draw.randint(0, i);
            real t;
            t = px[i]; px[i] = px[j]; px[j] = t;
            t = py[i]; py[i] = py[j]; py[j] = t;
        end
        //  The start: one point at random, then twice the point farthest from
        //  every start chosen so far -- one start per cluster.
        start = draw.randint(0, px.size() - 1);
        cx.push_back(px[start]);
        cy.push_back(py[start]);
        while (cx.size() < 3) begin
            int  far_i = 0;
            real far_d = -1.0;
            foreach (px[i]) begin
                real d = -1.0;
                foreach (cx[c]) begin
                    real e = distance2(px[i], py[i], cx[c], cy[c]);
                    if (d < 0.0 || e < d) d = e;
                end
                if (d > far_d) begin far_d = d; far_i = i; end
            end
            cx.push_back(px[far_i]);
            cy.push_back(py[far_i]);
        end
        for (int round_ = 0; round_ < 10; round_++) begin
            real sx[3] = '{0.0, 0.0, 0.0}, sy[3] = '{0.0, 0.0, 0.0};
            int  n[3]  = '{0, 0, 0};
            foreach (px[i]) begin
                int nearest = 0;
                for (int c = 1; c < 3; c++)
                    if (distance2(px[i], py[i], cx[c], cy[c]) < distance2(px[i], py[i], cx[nearest], cy[nearest]))
                        nearest = c;
                sx[nearest] += px[i];
                sy[nearest] += py[i];
                n[nearest]  += 1;
            end
            for (int c = 0; c < 3; c++) begin
                cx[c] = sx[c] / n[c];
                cy[c] = sy[c] / n[c];
            end
        end
        $display("centroids (x y), in the order found:");
        $display("##! point-cloud limit=0.3 pair dist=Linf");
        foreach (cx[c]) $display("    %5.2f %5.2f", cx[c], cy[c]);
        $display("####");
    endtask

    initial begin
        string choice = hwut_sv_argc() > 1 ? hwut_sv_argv(1) : "";
        case (choice)
            "plain":       plain();
            "tolerance":   tolerance();
            "constraints": constraints();
            "analogies":   analogies();
            "race":        race();
            "pool":        pool();
            "progress":    progress();
            "lisp":        lisp();
            "clusters":    clusters();
            default: begin
                $display("choices: plain, tolerance, constraints, analogies, race, pool, progress, lisp, clusters");
                exit_(1);
            end
        endcase
        $display("<hwut-end>");
        exit_(0);
    end
endmodule
