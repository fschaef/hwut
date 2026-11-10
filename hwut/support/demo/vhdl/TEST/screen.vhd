-- @hwut {
--     title     = "Demo: a terminal program's screen, as a person sees it"
--     build     { framework = "make", target = "%.exe" }
--     tolerance { regions    = false
--                 comment    = false
--                 whitespace = false }
--     choices {
--         open   { features = ["demo-vhdl+cover-terminal-screen", "demo-vhdl+cover-screen-as-seen"] }
--         scroll { features = ["demo-vhdl+cover-terminal-screen", "demo-vhdl+cover-screen-as-seen"] }
--     }
-- }
--
-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
-- SUBJECT  the screen of 'viewer.exe' (of 'viewer.vhd'), a full-screen file
--          viewer, run in a terminal of 9 rows and 40 columns and driven by
--          its keys.
-- REQUIREMENT  The viewer shows a title bar in reverse video, the file's lines
--              as they fit, and a status line -- the keys flush left, the
--              lines shown flush right; 'j' and the down key go one line
--              further, 'k' one back.
--
-- The support's 'Terminal' (package 'hwut_vterm_terminal') runs the viewer on
-- a pseudo-terminal: the viewer cannot tell it from a real one. The test
-- PRESSES KEYS and is told what CHANGED: three regions are declared -- title,
-- body, status -- and after every key, once the viewer has gone quiet, each
-- region whose text changed is told to 'show', the instance's 'on_change'.
--
-- THE SCREEN IS COMPARED AS A PERSON SEES IT -- 'regions', 'comment' and
-- 'whitespace' off in the header; why each, the Python demonstration says
-- ('../../python/TEST/screen.py'). The GOOD is this test's own: its first
-- line names the program started, 'viewer.exe' (RATIONALE DEMO-VHDL-4).
--
-- libvterm must be installed ('apt install libvterm0'); where it is not, the
-- test prints why and probes nothing.
--
-- CHOICES  open    the viewer opened, then quit.
--          scroll  down, down, 'j', then 'k': three lines on, one back.
-- _____________________________________________________________________________
use std.textio.all;
use work.hwut_vhpi.all;
use work.hwut_pytext.all;
use work.hwut_vterm.all;
use work.demo_vhpi.all;

entity screen is
    generic (HWUT_ARGC : natural := 0; HWUT_ARGV1 : string := ""; HERE : string := ".");
end entity;

architecture test of screen is
    constant SAMPLE : str_list :=
        "## demo.py race -- three workers" & LF &
        "start" & LF &
        "##! potpourri" & LF &
        "worker B done: 5 jobs" & LF &
        "worker A done: 3 jobs" & LF &
        "worker C done: 2 jobs" & LF &
        "####" & LF &
        "all joined" & LF &
        "## the order between the markers is" & LF &
        "## free; the lines are not." & LF;

    procedure show(name : string; lines : str_list) is
        -- RETURN: nothing; prints one region that changed, its rows as they
        --         stand on the screen, from the first column.
    begin
        print("-- " & name);
        for i in 0 to item_n(lines) - 1 loop print(item(lines, i)); end loop;
    end procedure;

    package watched is new work.hwut_vterm_terminal
        generic map (on_event => no_event, on_change => show);
    use watched.all;

    procedure view(keys : str_list) is
        -- RETURN: nothing; runs the viewer on the sample, presses 'keys',
        --         quits, and prints what changed after each step. Ends the
        --         process (1) where libvterm cannot be had.
        constant path : string := HERE & "/TMP/race.txt";
        file     f    : text;
        variable l    : line;
        variable t    : Terminal;
        variable cell : VtermCell;
        variable key  : line;
    begin
        make_directory(HERE & "/TMP");
        file_open(f, path, write_mode);
        for i in 0 to item_n(SAMPLE) - 1 loop write(l, item(SAMPLE, i)); writeline(f, l); end loop;
        file_close(f);
        if not t.create(9, 40) then
            print(t.error_message);
            process_exit(1);
        end if;
        t.region("title",  0);
        t.region("body",   1, 7);
        t.region("status", -1);
        print("> viewer.exe race.txt");
        t.run(HERE & "/viewer.exe" & NUL & path & NUL);
        cell := t.cell(0, 1);
        if attribute_text(cell) = "" then print("title bar: plain");
        else                              print("title bar: " & attribute_text(cell));
        end if;
        for i in 0 to item_n(keys) - 1 loop
            key := new string'(item(keys, i));
            print("> " & key.all);
            if key'length = 1 then t.send(key.all);
            else                   t.press(key.all);
            end if;
        end loop;
        t.send("q");
        print("> q -- exit status " & integer'image(t.wait_exit));
        t.free;
    end procedure;
begin
    main : process
    begin
        if    HWUT_ARGV1 = "open"   then view("");
        elsif HWUT_ARGV1 = "scroll" then view("down" & LF & "down" & LF & "j" & LF & "k" & LF);
        else
            print("choices: open, scroll");
            process_exit(1);
        end if;
        print("<hwut-end>");
        wait;
    end process;
end architecture;
