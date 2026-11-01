// @hwut {
//     title    = "Demo: a garage's space counter -- a space, a stream and races, generated"
//     build    { framework = "make", executable = "%.exe"
//                caps { memory_mb = 2048  file_size_mb = 256  disk_mb = 1024 } }
//     interactive = true
//     choices {
//         space       { features = ["space-from-hocon", "space-iterator", "hwut-runner"]
//                       tolerance { constraints = ["mismatches == 0"] } }
//         random      { features = ["deterministic-stream", "hwut-runner"]
//                       tolerance { constraints = ["mismatches == 0"] } }
//         race-naive  { features = ["deterministic-timeline", "space-iterator", "hwut-runner"]
//                       tolerance { constraints = ["overbooked > 0"] } }
//         race-atomic { features = ["deterministic-timeline", "space-iterator", "hwut-runner"]
//                       tolerance { constraints = ["overbooked == 0"] } }
//     }
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// SUBJECT  the counter of free spaces at a garage's gates: which cars it
//          admits, which it refuses, and how many stand inside.
// REQUIREMENT  The garage admits a car only while a space is free, lets a car
//              out only while one stands inside, and never holds more cars
//              than it has spaces -- also when two gates admit at once.
//
// No choice writes its cases out by hand. Each GENERATES them, with one of
// hwut's packages for writing tests in SystemVerilog
// (hwut/support/test_writing/verilog):
//
// space        'garage-space.hocon' states the tested space -- capacities,
//              cars arriving, cars leaving -- in hwut's HOCON, read by
//              'hwut_hocon'. A reviewer edits the space without reading
//              SystemVerilog. 'SpaceIterator::do_' walks every combination:
//              3 x 5 x 4 = 60 cases. Each is printed as one cell of a
//              matrix, and checked against the model: admitted =
//              min(arriving, capacity), out = min(leaving, admitted).
//
// random       'DeterministicStream' seeded 4711 draws 1000 cars arriving
//              and leaving at a garage of 5. The draw is the same on every
//              machine and in every language hwut supports -- the stream is
//              a linear congruential generator, not '$urandom' -- so the
//              GOOD is exact (the Python demonstration's own), and a failing
//              run can be replayed by its seed.
//
// race-naive   two gates, one free space. A gate CHECKS whether a space is
//              free, and later ADMITS its car. 'deterministic_timeline' runs
//              the two gates as Triggers on timelines drawn as strings --
//              '1 1 ' fires at tick 0 and tick 2 -- so every interleaving is
//              played exactly, not hoped for with delays. 'SpaceIterator'
//              generates all six interleavings of two two-step gates in four
//              ticks. Where both gates check before either admits, both
//              admit: the garage is overbooked. The law is 'overbooked > 0':
//              the GOOD is the accepted violation report.
//
// race-atomic  the same six interleavings, the gate checking and admitting
//              in ONE step under the counter's lock. 'overbooked == 0'.
//
// THE FRONT END is hwut's HwutRunner: the test derives it, and its 'play'
// is the whole choice map, '--hwut-info' included. The header says
// 'interactive = true': hwut starts the simulation ONCE and asks for the
// choices one after another (each in a child of its own) -- an accelerator
// only: a choice's output equals what it prints when run alone.
// _____________________________________________________________________________
import hwut_runner::*;
import hwut_pytext::*;
import hwut_hocon::*;
import space_iterator::*;
import deterministic_random::*;
import deterministic_timeline::*;

class Garage;
    // The unit under test: a counter of the spaces a garage has.
    int capacity;
    int occupied;

    function new(int capacity);
        // RETURN: an empty garage of 'capacity' spaces.
        this.capacity = capacity;
        this.occupied = 0;
    endfunction

    function int free();
        // RETURN: the number of spaces free now -- negative where the garage
        //         is overbooked.
        return capacity - occupied;
    endfunction

    function bit arrive();
        // RETURN: 1, a car was admitted, if a space was free;
        //         0, else (the car is refused).
        if (free() <= 0) return 0;
        occupied += 1;
        return 1;
    endfunction

    function bit leave();
        // RETURN: 1, a car drove out, if one stood inside;
        //         0, else.
        if (occupied == 0) return 0;
        occupied -= 1;
        return 1;
    endfunction
endclass

class EventLog;
    // What the gates of one interleaving did, in order.
    string text_list[$];
endclass

class Gate extends Trigger;
    // A gate on a timeline: its first tick checks, its second admits.
    Garage   garage;
    bit      atomic;
    EventLog log;
    int      step;
    bit      saw_free;

    function new(string name, string timeline, Garage garage, bit atomic, EventLog log);
        // RETURN: the gate 'name' firing at the digits of 'timeline'.
        super.new(timeline, name);
        this.garage   = garage;
        this.atomic   = atomic;
        this.log      = log;
        this.step     = 0;
        this.saw_free = 0;
    endfunction

    virtual task fire(int pseudo_time);
        // RETURN: nothing; the gate's next step was performed at
        //         'pseudo_time'.
        if (step == 0 && atomic) begin
            saw_free = garage.arrive();
            log.text_list.push_back(saw_free ? {name, " checks+admits"} : {name, " refuses"});
        end
        else if (step == 0) begin
            saw_free = garage.free() > 0;
            log.text_list.push_back($sformatf("%s sees %0d free", name, garage.free()));
        end
        else if (atomic) begin
            log.text_list.push_back(saw_free ? {name, " opens"} : {name, " stays shut"});
        end
        else if (saw_free) begin
            garage.occupied += 1;                         // the naive admit
            log.text_list.push_back({name, " admits"});
        end
        else begin
            log.text_list.push_back({name, " refuses"});
        end
        step += 1;
    endtask
endclass

function automatic string rstripped(string text);
    // RETURN: 'text' without its trailing blanks.
    int n = text.len();
    while (n > 0 && text[n - 1] == " ") n -= 1;
    return n == 0 ? "" : text.substr(0, n - 1);
endfunction

class Test extends HwutRunner;
    function new();
        // RETURN: the runner of this test, its four choices.
        super.new("Demo: a garage's space counter -- a space, a stream and races, generated;",
                  '{"space", "random", "race-naive", "race-atomic"});
    endfunction

    virtual task play(string choice);
        // RETURN: nothing; the choice 'choice' ran.
        case (choice)
            "space":       space();
            "random":      random_stream();
            "race-naive":  race(0);
            "race-atomic": race(1);
        endcase
    endtask

    // _________________________________________________________________________
    // space -- the tested space from HOCON, walked by SpaceIterator
    //
    function void read_space(string path, ref string name_list[$], ref basis_t basis);
        // RETURN: nothing; 'name_list' holds the dimensions of the space in
        //         'path', in the order written, and 'basis' their values.
        //         Every fault the HOCON reader found is printed with '!!'
        //         first.
        SourceLine line_list[$] = {};
        Fault      fault_list[$] = {};
        ObjectNode document, space_;
        string     text;
        int        fd, number = 0;
        name_list = {};
        basis     = {};
        fd = $fopen(path, "r");
        if (fd != 0) begin
            forever begin
                if ($fgets(text, fd) == 0) break;           // never a 'while' condition
                number += 1;
                if (text.len() && text[text.len() - 1] == "\n") text = text.substr(0, text.len() - 2);
                line_list.push_back(SourceLine::make(text, number, 0));
            end
            $fclose(fd);
        end
        document = parse(line_list, path, fault_list);
        foreach (fault_list[i]) $display("!! %s", fault_list[i].to_string());
        $cast(space_, document.get("space"));
        foreach (space_.entry_list[i]) begin
            ListNode    values;
            dimension_t dimension = {};
            $cast(values, space_.entry_list[i].node);
            foreach (values.item_list[k]) begin
                ScalarNode item;
                $cast(item, values.item_list[k]);
                dimension.push_back(item.value_repr());
            end
            name_list.push_back(space_.entry_list[i].key);
            basis.push_back(dimension);
        end
    endfunction

    task space();
        // RETURN: nothing; every case of the space was printed as a matrix
        //         cell.
        string        name_list[$] = {};
        basis_t       basis = {};
        SpaceIterator it;
        string        point[$] = {};
        string        row_db[string];        // "capacity arriving" -> its cells
        string        text = "";
        int           mismatch_n = 0, case_n = 0;
        read_space("garage-space.hocon", name_list, basis);
        foreach (name_list[i]) text = {text, (i ? string'("  x  ") : string'("")), name_list[i], " ",
                                       list_repr_int(basis[i])};
        $display("space: %s", text);
        $display("cell: cars inside / cars refused at the gate ('!!' differs from the model)");
        it = SpaceIterator::do_(basis);
        while (it.next_point(point)) begin
            int    capacity = point[0].atoi(), arriving = point[1].atoi(), leaving = point[2].atoi();
            Garage garage   = new(capacity);
            int    refused  = 0, admitted, expected_in, expected_refused;
            string key      = {point[0], " ", point[1]};
            string mark;
            for (int k = 0; k < arriving; k++) if (!garage.arrive()) refused += 1;
            for (int k = 0; k < leaving; k++) void'(garage.leave());
            admitted         = arriving < capacity ? arriving : capacity;
            expected_in      = admitted - (leaving < admitted ? leaving : admitted);
            expected_refused = arriving - admitted;
            mark = (garage.occupied == expected_in && refused == expected_refused) ? string'("  ") : string'("!!");
            if (mark == "!!") mismatch_n += 1;
            if (!row_db.exists(key)) row_db[key] = "";
            else                     row_db[key] = {row_db[key], "  "};
            row_db[key] = {row_db[key], padded($sformatf("%0d/%0d%s", garage.occupied, refused, mark), 9)};
            case_n += 1;
        end
        foreach (basis[0][c]) begin
            string leave_text = "";
            foreach (basis[2][l]) leave_text = {leave_text, (l ? string'("  ") : string'("")),
                                                "leave ", padded(basis[2][l], 3)};
            $display("capacity %s   %s", basis[0][c], rstripped(leave_text));
            foreach (basis[1][a])
                $display("%s", rstripped({"  arrive ", basis[1][a], "   ", row_db[{basis[0][c], " ", basis[1][a]}]}));
        end
        $display("cases %0d, differing from the model ((mismatches: %0d))", case_n, mismatch_n);
    endtask

    function string list_repr_int(dimension_t values);
        // RETURN: 'values' -- integers' texts -- as Python prints a list of
        //         integers: '[1, 2, 3]'.
        return {"[", join_text(values), "]"};
    endfunction

    // _________________________________________________________________________
    // random -- a deterministic stream of arrivals and departures
    //
    task random_stream();
        // RETURN: nothing; the summary of 1000 drawn cars was printed,
        //         model-checked.
        DeterministicStream stream = new(4711);
        Garage garage = new(5);
        int    model = 0, mismatch_n = 0;
        int    arrive_n = 0, refused_n = 0, leave_n = 0, empty_n = 0;
        int    histogram[6] = '{0, 0, 0, 0, 0, 0};
        string strip = "";
        for (int i = 0; i < 1000; i++) begin
            if (stream.coin(0.55)) begin
                arrive_n += 1;
                if (!garage.arrive()) refused_n += 1;
                model = model + 1 < 5 ? model + 1 : 5;
                if (i < 60) strip = {strip, "+"};
            end
            else begin
                leave_n += 1;
                if (!garage.leave()) empty_n += 1;
                model = model - 1 > 0 ? model - 1 : 0;
                if (i < 60) strip = {strip, "-"};
            end
            if (garage.occupied != model) mismatch_n += 1;
            histogram[garage.occupied] += 1;
        end
        $display("seed 4711, garage of 5, 1000 cars drawn: '+' arrives, '-' leaves");
        $display("first 60: %s", strip);
        $display("arrivals %0d, refused %0d; departures %0d, from an empty garage %0d",
                 arrive_n, refused_n, leave_n, empty_n);
        $display("cars inside after each event:");
        foreach (histogram[n]) begin
            string bar = "";
            for (int k = 0; k < histogram[n] / 10; k++) bar = {bar, "#"};
            $display("    %0d  %4d  %s", n, histogram[n], bar);
        end
        $display("steps differing from the model ((mismatches: %0d))", mismatch_n);
    endtask

    // _________________________________________________________________________
    // race -- two gates on drawn timelines
    //
    function void interleavings(ref string a_list[$], ref string b_list[$]);
        // RETURN: nothing; 'a_list'/'b_list' hold every pair of timelines in
        //         four ticks in which each of two gates fires twice, never at
        //         the same tick: gate A's and gate B's.
        int           size_list[$] = {};
        int           at[$] = {};
        SpaceIterator it;
        a_list = {};
        b_list = {};
        for (int d = 0; d < 4; d++) size_list.push_back(4);
        it = new(size_list);
        while (it.next(at)) begin
            int a1 = at[0], a2 = at[1], b1 = at[2], b2 = at[3];
            string a = "", b = "";
            if (!(a1 < a2 && b1 < b2 && a1 != b1 && a1 != b2 && a2 != b1 && a2 != b2)) continue;
            for (int t = 0; t < 4; t++) begin
                a = {a, (t == a1 || t == a2) ? string'("1") : string'(" ")};
                b = {b, (t == b1 || t == b2) ? string'("1") : string'(" ")};
            end
            a_list.push_back(a);
            b_list.push_back(b);
        end
    endfunction

    task race(bit atomic);
        // RETURN: nothing; every interleaving of two gates at one space was
        //         played and printed.
        string a_list[$] = {}, b_list[$] = {};
        int    overbooked_n = 0;
        interleavings(a_list, b_list);
        $display("one free space, two gates, one car at each; timelines: a digit fires");
        $display("    gate A  gate B  what happens                                    inside");
        foreach (a_list[i]) begin
            Garage            garage = new(1);
            EventLog          log = new();
            Gate              gate_a = new("A", a_list[i], garage, atomic, log);
            Gate              gate_b = new("B", b_list[i], garage, atomic, log);
            Trigger           gate_list[$] = {};
            TriggerDispatcher dispatcher;
            string            mark;
            gate_list.push_back(gate_a);
            gate_list.push_back(gate_b);
            dispatcher = new(gate_list);
            dispatcher.run();
            mark = garage.occupied > garage.capacity ? string'("!!") : string'("  ");
            if (garage.occupied > garage.capacity) overbooked_n += 1;
            $display("%s", rstripped($sformatf("    \"%s\"  \"%s\"  %s  %0d %s", a_list[i], b_list[i],
                                               padded(join_text(log.text_list), 46), garage.occupied, mark)));
        end
        $display("interleavings overbooking the garage ((overbooked: %0d)) of %0d", overbooked_n, a_list.size());
    endtask
endclass

module garage;
    initial begin
        Test t = new();
        t.run();
    end
endmodule
