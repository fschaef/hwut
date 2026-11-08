// @hwut {
//     title     = "Demo: a terminal program's screen, as a person sees it"
//     build     { framework = "make", target = "%.exe"
//                 caps { memory_mb = 2048  file_size_mb = 256  disk_mb = 1024 } }
//     tolerance { regions    = false
//                 comment    = false
//                 whitespace = false }
//     choices {
//         open   { features = ["terminal-screen", "screen-as-seen"] }
//         scroll { features = ["terminal-screen", "screen-as-seen"] }
//     }
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// SUBJECT  the screen of 'viewer.exe' ('viewer.sv'), a full-screen file
//          viewer, run in a terminal of 9 rows and 40 columns and driven by
//          its keys.
// REQUIREMENT  The viewer shows a title bar in reverse video, the file's lines
//              as they fit, and a status line -- the keys flush left, the
//              lines shown flush right; 'j' and the down key go one line
//              further, 'k' one back.
//
// hwut_vterm's 'Terminal' runs the viewer on a pseudo-terminal: the viewer
// cannot tell it from a real one. The test PRESSES KEYS and is told what
// CHANGED: three regions are declared -- title, body, status -- and after
// every key, once the viewer has gone quiet, each region whose text changed
// is printed. A redraw that changes nothing is not told: the title is told
// once.
//
// THE SCREEN IS COMPARED AS A PERSON SEES IT -- three tolerances switched
// off, in the header:
//
//     regions = false     the file shown is a GOOD file of hwut, with a
//                         '##! potpourri' ... '####' block. On this screen
//                         those are characters, not a region to open.
//     comment = false     '## ...' lines are characters too, not notes.
//     whitespace = false  the status line's two halves stand flush left and
//                         flush right: every blank between them counts. A
//                         half moved by one column is red. (A line's leading
//                         and trailing blanks are stripped all the same.)
//
// libvterm must be installed ('apt install libvterm0'); where it is not, the
// test prints why and probes nothing -- its output differs from GOOD and the
// reason stands in the difference.
//
// CHOICES  open    the viewer opened, then quit.
//          scroll  down, down, 'j', then 'k': three lines on, one back.
// _____________________________________________________________________________
import hwut_runner::*;
import hwut_vterm::*;

class Shown extends ChangeCallback;
    virtual function void on_change(string name, string line_list[$]);
        // RETURN: nothing; one region that changed was printed, its rows as
        //         they stand on the screen, from the first column.
        $display("-- %s", name);
        foreach (line_list[i]) $display("%s", line_list[i]);
    endfunction
endclass

function automatic bit write_sample(string path);
    // RETURN: 1, the sample -- a GOOD file of 'demo.sv race' -- stands in
    //         'path'; 0, it cannot be written.
    int fd;
    void'($system("mkdir -p TMP"));
    fd = $fopen(path, "w");
    if (fd == 0) return 0;
    $fwrite(fd, "## demo.sv race -- three workers\n");
    $fwrite(fd, "start\n");
    $fwrite(fd, "##! potpourri\n");
    $fwrite(fd, "worker B done: 5 jobs\n");
    $fwrite(fd, "worker A done: 3 jobs\n");
    $fwrite(fd, "worker C done: 2 jobs\n");
    $fwrite(fd, "####\n");
    $fwrite(fd, "all joined\n");
    $fwrite(fd, "## the order between the markers is\n");
    $fwrite(fd, "## free; the lines are not.\n");
    $fclose(fd);
    return 1;
endfunction

task automatic view(string key_list[$]);
    // RETURN: nothing; the viewer ran on the sample, 'key_list' was pressed,
    //         'q' quit it, and what changed after each step was printed.
    //         Where libvterm is missing, why -- and the process exits 1.
    string   path = "TMP/race.txt";
    Terminal terminal;
    Shown    shown = new();
    Cell     corner;
    string   attribute;
    int      status;
    string   argv[$] = {};
    if (!write_sample(path)) begin
        $display("cannot write %s", path);
        exit_(1);
    end
    terminal = Terminal::create(9, 40);
    if (terminal == null) begin
        $display("%s", last_error.message);
        exit_(1);
    end
    terminal.region("title",  0);
    terminal.region("body",   1, 7);
    terminal.region("status", -1);
    terminal.on_change(shown);
    $display("> viewer.exe race.txt");
    argv.push_back("./viewer.exe");
    argv.push_back(path);
    void'(terminal.run(argv));
    corner = terminal.cell_(0, 1);
    attribute = corner.attribute_text();
    $display("title bar: %s", attribute.len() ? attribute : "plain");
    foreach (key_list[i]) begin
        $display("> %s", key_list[i]);
        if (key_list[i].len() == 1) void'(terminal.send(key_list[i]));
        else                        void'(terminal.press(key_list[i]));
    end
    void'(terminal.send("q"));
    void'(terminal.wait_(status));
    $display("> q -- exit status %0d", status);
    terminal.close();
endtask

module screen;
    initial begin
        string choice = hwut_sv_argc() > 1 ? hwut_sv_argv(1) : "";
        string key_list[$] = {};
        case (choice)
            "open":   view(key_list);
            "scroll": begin
                key_list.push_back("down");
                key_list.push_back("down");
                key_list.push_back("j");
                key_list.push_back("k");
                view(key_list);
            end
            default: begin
                $display("choices: open, scroll");
                exit_(1);
            end
        endcase
        $display("<hwut-end>");
        exit_(0);
    end
endmodule
