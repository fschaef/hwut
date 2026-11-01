%% @hwut {
%%     title      = "A terminal's screen read by a test: libvterm through an Erlang port."
%%     choices {
%%         attributes { features = ["erlang-vterm"] }
%%         colours    { features = ["erlang-vterm"] }
%%         events     { features = ["erlang-vterm"] }
%%         keys       { features = ["erlang-vterm"] }
%%         missing    { features = ["erlang-vterm"] }
%%         regions    { features = ["erlang-vterm"] }
%%         screen     { features = ["erlang-vterm"] }
%%         text       { features = ["erlang-vterm"] }
%%         unnoticed  { features = ["erlang-vterm"] }
%%     }
%%     interactive = true
%% }
%%
%% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%%_____________________________________________________________________________
%%
%% PURPOSE: The Erlang port of 'python/TEST/test-hwut_vterm.py', choice for
%%          choice, held against its GOOD files by '.link'. WANTS libvterm
%%          (and cc and make, which build the port program on first use).
%%          The two APPLICATIONS a terminal runs here are the Python test's,
%%          unchanged, run by 'python3': they are the system under test, and
%%          what they print is in the shared GOOD files. What Python's
%%          callbacks print, this test prints from the messages the terminal
%%          sends -- after each call, as they stand in the mailbox.
%%_____________________________________________________________________________
-mode(compile).
-include("../hwut_boot.hrl").

-define(ESC, "\e").

main(Argv) ->
    hwut_boot(),
    hwut_runner:run(Argv, "A terminal's screen read by a test: libvterm through an Erlang port.",
                    #{"text"       => probe(fun run_text/0),
                      "screen"     => probe(fun run_screen/0),
                      "attributes" => probe(fun run_attributes/0),
                      "colours"    => probe(fun run_colours/0),
                      "unnoticed"  => probe(fun run_unnoticed/0),
                      "keys"       => probe(fun run_keys/0),
                      "regions"    => probe(fun run_regions/0),
                      "events"     => probe(fun run_events/0),
                      "missing"    => fun run_missing/0}).

%% RETURN: ok; one line printed.
say(Format, Arguments) -> io:format(Format ++ "~n", Arguments).

%% RETURN: fun, 'Function' run on a library that is there; one line where
%%         it is not.
probe(Function) ->
    fun() ->
            try Function()
            catch throw:{library_missing, Text} -> say("NOT PROBED: ~ts", [Text])
            end
    end.

%% RETURN: the screen or terminal made; throws to 'probe' where libvterm is
%%         not found.
made({ok, Object})                    -> Object;
made({error, {library_missing, Text}}) -> throw({library_missing, Text}).

%% RETURN: ok; every row that holds something, framed, then the cursor.
shown(S) ->
    lists:foldl(fun(<<>>, Row) -> Row + 1;
                   (Line, Row) -> say("    ~b |~ts|", [Row, Line]), Row + 1
                end, 0, hwut_vterm:line_list(S)),
    say("    cursor ~ts", [pytext:repr(hwut_vterm:cursor(S))]).

%% RETURN: map, the cell at that place.
cell(S, Row, Column) -> {ok, Cell} = hwut_vterm:cell(S, Row, Column), Cell.

%% RETURN: binary, the cell's attributes by name, or '(none)'.
said(Cell) ->
    case hwut_vterm:attribute_text(Cell) of <<>> -> <<"(none)">>; Text -> Text end.

%% RETURN: ok; every report of 'T' standing in the mailbox shown, in order.
told(T, Show) ->
    receive {hwut_vterm, T, Report} -> Show(Report), told(T, Show)
    after 0 -> ok
    end.

%% ------------------------------------------------------------------ Screen
%% RETURN: ok; plain bytes, UTF-8, a wide character, a wrapping line.
run_text() ->
    S1 = made(hwut_vterm:screen(4, 12)),
    say("-- plain, then carriage return and line feed", []),
    hwut_vterm:feed(S1, <<"hello\r\nworld">>),
    shown(S1), hwut_vterm:close(S1),
    S2 = made(hwut_vterm:screen(4, 12)),
    say("-- UTF-8: two bytes, one cell; a wide character, two", []),
    hwut_vterm:feed(S2, [16#e4, 16#65e5, $x]),                      % 'ä日x'
    shown(S2),
    [begin
         #{text := Text, width := Width} = cell(S2, 0, Column),
         say("    column ~b: ~ts width ~b", [Column, pytext:ljust(pytext:repr(Text), 6), Width])
     end || Column <- lists:seq(0, 3)],
    hwut_vterm:close(S2),
    S3 = made(hwut_vterm:screen(3, 5)),
    say("-- seven characters on five columns: the line wraps", []),
    hwut_vterm:feed(S3, <<"abcdefg">>),
    shown(S3), hwut_vterm:close(S3),
    S4 = made(hwut_vterm:screen(2, 4)),
    say("-- a str is sent as UTF-8; the bytes taken are counted", []),
    say("    taken: ~b", [hwut_vterm:feed(S4, [$a, 16#e4])]),
    say("-- a place off the screen", []),
    {error, {index_error, Error}} = hwut_vterm:cell(S4, 2, 0),
    say("    IndexError: ~ts", [Error]),
    hwut_vterm:close(S4).

%% RETURN: ok; the sequences a full-screen program writes.
run_screen() ->
    S = made(hwut_vterm:screen(5, 20)),
    say("-- three lines, then '<esc>[2;4H' (it counts from 1) and 'X'", []),
    hwut_vterm:feed(S, <<"first line\r\nsecond line\r\nthird line">>),
    hwut_vterm:feed(S, <<?ESC "[2;4H" "X">>),
    shown(S),
    say("-- erase to the end of that line", []),
    hwut_vterm:feed(S, <<?ESC "[K">>),
    shown(S),
    say("-- clear the screen, home, one word", []),
    hwut_vterm:feed(S, <<?ESC "[2J" ?ESC "[H" "clean">>),
    shown(S),
    hwut_vterm:close(S).

%% RETURN: ok; each attribute by its SGR code, all at once, then reset.
run_attributes() ->
    S = made(hwut_vterm:screen(3, 20)),
    Names = hwut_vterm:attribute_names(),
    [hwut_vterm:feed(S, [?ESC "[", hwut_vterm:attribute_sgr(N), "m", hd(atom_to_list(N)), ?ESC "[0m"])
     || N <- Names],
    say("-- one cell per attribute, set by its own code", []),
    lists:foldl(fun(Name, Column) ->
                        Cell = cell(S, 0, Column),
                        %  'conceal' IS NOT KNOWN TO EVERY LIBRARY: said, not pinned.
                        Said = case Name of conceal -> <<"conceal, or (none) on libvterm 0.1">>; _ -> said(Cell) end,
                        say("    ~ts  ~ts", [pytext:repr(maps:get(text, Cell)), Said]),
                        Column + 1
                end, 0, Names),
    say("-- bold, underline and reverse at once; then reset", []),
    hwut_vterm:feed(S, <<"\r\n" ?ESC "[1;4;7mA" ?ESC "[0mB">>),
    [begin
         Cell = cell(S, 1, Column),
         say("    ~ts  ~ts", [pytext:repr(maps:get(text, Cell)), said(Cell)])
     end || Column <- [0, 1]],
    say("-- double underline (SGR 21) is underlined", []),
    hwut_vterm:feed(S, <<?ESC "[21mD">>),
    say("    ~ts  ~ts", [pytext:repr(<<"D">>), hwut_vterm:attribute_text(cell(S, 1, 2))]),
    hwut_vterm:close(S).

%% RETURN: ok; the default, an indexed, a palette and a direct colour.
run_colours() ->
    S = made(hwut_vterm:screen(2, 20)),
    hwut_vterm:feed(S, <<"d" ?ESC "[31mr" ?ESC "[0m" ?ESC "[38;5;196mp" ?ESC "[0m" ?ESC "[38;2;10;20;30mt" ?ESC "[0m">>),
    hwut_vterm:feed(S, <<?ESC "[48;2;1;2;3mb" ?ESC "[0m">>),
    lists:foldl(fun(What, Column) ->
                        #{text := Text, foreground := Fg, background := Bg} = cell(S, 0, Column),
                        %  THE EIGHT NAMED COLOURS ARE THE LIBRARY'S OWN PALETTE:
                        %  that one is a colour and mostly red is the claim.
                        Said = case {What, Fg} of
                                   {"indexed 31", {R, G, B}} ->
                                       ["fg mostly red: ", pytext:bool(R > 2 * max(G, B))];
                                   _ ->
                                       ["fg ", pytext:repr(Fg), "  bg ", pytext:repr(Bg)]
                               end,
                        say("    ~ts ~ts  ~ts", [pytext:ljust(What, 18), pytext:repr(Text), Said]),
                        Column + 1
                end, 0, ["default", "indexed 31", "palette 196", "direct 10;20;30", "background 1;2;3"]),
    hwut_vterm:close(S).

%%  THE APPLICATION UNDER OBSERVATION -- the Python test's own, byte for
%%  byte: it says what it sees, asks the terminal where the cursor is, then
%%  names every key until 'q'.
-define(SEEING_APP, <<"
import os, sys, tty, termios
print(\"streams are terminals: %s %s %s\"
      % (sys.stdin.isatty(), sys.stdout.isatty(), sys.stderr.isatty()))
try:    os.close(os.open(\"/dev/tty\", os.O_RDWR)); print(\"controlling terminal: yes\")
except OSError: print(\"controlling terminal: no\")
print(\"size: %d columns, %d rows\" % tuple(os.get_terminal_size()))
print(\"TERM=%s COLUMNS=%s\" % (os.environ.get(\"TERM\"), os.environ.get(\"COLUMNS\")))
old = termios.tcgetattr(0); tty.setraw(0)
sys.stdout.write(\"\\x1b[6;9H\\x1b[6n\"); sys.stdout.flush()
reply = b\"\"
while not reply.endswith(b\"R\"): reply += os.read(0, 1)
sys.stdout.write(\"\\r\\x1b[7;1Hthe terminal answered: %r\" % reply); sys.stdout.flush()
while True:
    key = os.read(0, 32)
    sys.stdout.write(\"\\x1b[9;1H\\x1b[Kread: %r\" % key); sys.stdout.flush()
    if key == b\"q\": break
termios.tcsetattr(0, termios.TCSADRAIN, old)
print(\"\\r\\nleaving\"); sys.exit(3)
">>).

%%  AN APPLICATION WITH A HEAD, A BODY AND A FOOT: 'n' counts in the body,
%%  'f' rewrites the foot, 'r' redraws everything unchanged, 'q' leaves.
-define(DRAWING_APP, <<"
import os, sys, tty, termios
old = termios.tcgetattr(0); tty.setraw(0)
count, foot = 0, \"q=quit\"
def draw():
    out = \"\\x1b[2J\\x1b[1;1H\\x1b[7m the head \\x1b[0m\"
    out += \"\\x1b[3;1Hcount: %d\\x1b[4;1H(press n)\" % count
    out += \"\\x1b[8;1H%s\" % foot
    sys.stdout.write(out); sys.stdout.flush()
draw()
while True:
    key = os.read(0, 1)
    if   key == b\"n\": count += 1
    elif key == b\"f\": foot = \"q=quit  f=pressed\"
    elif key == b\"q\": break
    draw()
termios.tcsetattr(0, termios.TCSADRAIN, old)
">>).

%% ---------------------------------------------------------------- Terminal
%% RETURN: ok; what the application sees: a real terminal.
run_unnoticed() ->
    os:putenv("COLUMNS", "300"),
    T = made(hwut_vterm:terminal(10, 44)),
    say("-- still running after its first screen: ~ts",
        [pytext:bool(hwut_vterm:run(T, ["python3", "-c", ?SEEING_APP]))]),
    shown(T),
    hwut_vterm:send(T, "q"),
    {ok, Status} = hwut_vterm:wait(T),
    say("-- after 'q': exit status ~b", [Status]),
    shown(T),
    hwut_vterm:close(T).

%% RETURN: ok; named keys, function keys, modifiers, a non-ASCII character:
%%         what the application READS for each.
run_keys() ->
    T = made(hwut_vterm:terminal(10, 44)),
    hwut_vterm:region(T, "read", 8),
    hwut_vterm:on_change(T),
    Pressed = fun(Label) -> told(T, fun({change, _, [Line | _]}) ->
                                            say("    ~ts ~ts", [pytext:ljust(Label, 22), Line])
                                    end)
              end,
    hwut_vterm:run(T, ["python3", "-c", ?SEEING_APP]),
    Pressed("(start)"),
    [begin
         hwut_vterm:press(T, Key, Modifiers),
         Pressed(lists:join(" ", [atom_to_list(M) || M <- Modifiers] ++ [Key]))
     end || {Key, Modifiers} <- [{"up", []}, {"enter", []}, {"tab", []}, {"escape", []},
                                 {"f5", []}, {"delete", []}, {"c", [ctrl]}, {"x", [alt]},
                                 {"up", [shift]}]],
    hwut_vterm:send(T, [16#e4]),
    Pressed([<<"send '">>, <<16#e4/utf8>>, <<"'">>]),
    hwut_vterm:send(T, "q"),
    Pressed("send 'q'"),
    hwut_vterm:wait(T),
    hwut_vterm:close(T).

%% RETURN: ok; of three regions only the one that changed is told, once per
%%         pause.
run_regions() ->
    %  A LONGER PAUSE THAN THE DEFAULT: three redraws typed at once must be
    %  ONE report on a loaded machine too.
    T = made(hwut_vterm:terminal(8, 30, 0.3)),
    hwut_vterm:region(T, "head", 0),
    hwut_vterm:region(T, "body", 2, #{row_n => 2}),
    hwut_vterm:region(T, "foot", -1),
    hwut_vterm:on_change(T),
    Changed = fun({change, Name, Lines}) ->
                      say("    changed  ~ts ~ts", [pytext:ljust(Name, 5), pytext:repr(Lines)])
              end,
    [begin
         say("-- ~ts", [Said]),
         Act(),
         told(T, Changed)
     end || {Said, Act} <- [{"run",                        fun() -> hwut_vterm:run(T, ["python3", "-c", ?DRAWING_APP]) end},
                            {"'n'",                        fun() -> hwut_vterm:send(T, "n") end},
                            {"'n'",                        fun() -> hwut_vterm:send(T, "n") end},
                            {"'r': a redraw, nothing new", fun() -> hwut_vterm:send(T, "r") end},
                            {"'f'",                        fun() -> hwut_vterm:send(T, "f") end},
                            {"'nnn', typed at once",       fun() -> hwut_vterm:send(T, "nnn") end},
                            {"'q'",                        fun() -> hwut_vterm:send(T, "q") end}]],
    {ok, Status} = hwut_vterm:wait(T),
    told(T, Changed),
    {ok, Body} = hwut_vterm:region_text(T, "body"),
    say("-- exit status ~b; a region asked by name: ~ts", [Status, pytext:repr(Body)]),
    {error, {key_error, Error}} = hwut_vterm:region_text(T, "nosuch"),
    say("-- no such region: KeyError ~ts", [Error]),
    hwut_vterm:close(T).

%% RETURN: ok; the raw layer on bytes the test feeds itself, and the
%%         terminal's answer with no application to take it.
run_events() ->
    T = made(hwut_vterm:terminal(4, 20)),
    hwut_vterm:on_event(T),
    Event = fun({event, E}) -> say("    ~ts", [hwut_vterm:event_text(E)]) end,
    [begin
         say("-- fed: ~ts", [Said]),
         hwut_vterm:feed(T, Data),
         told(T, Event)
     end || {Said, Data} <- [{"'ab'",                         <<"ab">>},
                             {"a line feed and 'c'",          <<"\r\nc">>},
                             {"the cursor to row 4, hidden",  <<?ESC "[4;1H" ?ESC "[?25l">>},
                             {"the alternate screen",         <<?ESC "[?1049h">>},
                             {"the bell",                     <<7>>},
                             {"nothing that draws: a reset of attributes", <<?ESC "[0m">>}]],
    say("-- asked where the cursor is, nobody running: the answer waits", []),
    hwut_vterm:feed(T, <<?ESC "[2;5H" ?ESC "[6n">>),
    told(T, Event),
    say("    answer() = ~ts", [pytext:repr({bytes, hwut_vterm:answer(T)})]),
    say("-- a key pressed with nobody running", []),
    hwut_vterm:press(T, "f1", [], 0),
    told(T, Event),
    say("    answer() = ~ts", [pytext:repr({bytes, hwut_vterm:answer(T)})]),
    hwut_vterm:close(T).

%% RETURN: ok; HWUT_LIBVTERM naming no file: 'library_missing', with the
%%         hint how to install the library.
run_missing() ->
    os:putenv(hwut_vterm:library_variable(), "/nowhere/libvterm.so"),
    case hwut_vterm:screen(24, 80) of
        {ok, S} ->
            say("a Screen stands on a library that is not there", []),
            hwut_vterm:close(S);
        {error, {library_missing, Text}} ->
            %  THE SYSTEM'S OWN WORDS for the failed load are left out; what
            %  this module says -- the line, and the way to install -- stands.
            [First | Rest] = binary:split(Text, <<"\n">>, [global]),
            [Line | _] = binary:split(First, <<" -- ">>),
            say("LibraryMissing: ~ts", [Line]),
            [say("~ts", [L]) || L <- Rest]
    end.
