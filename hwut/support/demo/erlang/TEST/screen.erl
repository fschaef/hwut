%% @hwut {
%%     title     = "Demo: a terminal program's screen, as a person sees it"
%%     tolerance { regions    = false
%%                 comment    = false
%%                 whitespace = false }
%%     choices {
%%         open   { features = ["terminal-screen", "screen-as-seen"] }
%%         scroll { features = ["terminal-screen", "screen-as-seen"] }
%%     }
%% }
%%
%%_____________________________________________________________________________
%% SUBJECT  the screen of 'viewer.erl', a full-screen file viewer, run in a
%%          terminal of 9 rows and 40 columns and driven by its keys.
%% REQUIREMENT  The viewer shows a title bar in reverse video, the file's lines
%%              as they fit, and a status line -- the keys flush left, the lines
%%              shown flush right; 'j' and the down key go one line further,
%%              'k' one back.
%%
%% hwut_vterm's terminal runs the viewer on a pseudo-terminal: the viewer
%% cannot tell it from a real one. The test PRESSES KEYS and is told what
%% CHANGED: three regions are declared -- title, body, status -- and after
%% every key, once the viewer has gone quiet, each region whose text changed
%% arrives as a message, and is printed. A redraw that changes nothing is
%% not told: the title is told once.
%%
%% THE SCREEN IS COMPARED AS A PERSON SEES IT -- three tolerances switched
%% off, in the header:
%%
%%     regions = false     the file shown is a GOOD file of hwut, with a
%%                         '##! potpourri' ... '####' block. On this screen
%%                         those are characters, not a region to open.
%%     comment = false     '## ...' lines are characters too, not notes.
%%     whitespace = false  the status line's two halves stand flush left and
%%                         flush right: every blank between them counts. A
%%                         half moved by one column is red. (A line's leading
%%                         and trailing blanks are stripped all the same.)
%%
%% libvterm must be installed ('apt install libvterm0'), and a C compiler
%% for the support's port program; where the library is not, the test
%% prints why and probes nothing -- its output differs from GOOD and the
%% reason stands in the difference.
%%
%% CHOICES  open    the viewer opened, then quit.
%%          scroll  down, down, 'j', then 'k': three lines on, one back.
%%_____________________________________________________________________________
-mode(compile).
-include("hwut_support.hrl").

-define(SAMPLE, "## demo.py race -- three workers\n"
                "start\n"
                "##! potpourri\n"
                "worker B done: 5 jobs\n"
                "worker A done: 3 jobs\n"
                "worker C done: 2 jobs\n"
                "####\n"
                "all joined\n"
                "## the order between the markers is\n"
                "## free; the lines are not.\n").

%% RETURN: never; the VM halts with 0 after the screens of the choice 'Argv'
%%         names and '<hwut-end>'; with 1, naming the choices, or saying why
%%         libvterm is not there.
main(Argv) ->
    hwut_support(),
    case Argv of
        ["open" | _]   -> view([]);
        ["scroll" | _] -> view(["down", "down", "j", "k"]);
        _              -> io:format("choices: open, scroll~n"), halt(1)
    end,
    io:format("<hwut-end>~n").

%% RETURN: ok; every region that changed is printed -- its rows as they
%%         stand on the screen, from the first column -- in the order the
%%         messages arrived.
show(T) ->
    receive
        {hwut_vterm, T, {change, Name, Lines}} ->
            io:format("-- ~ts~n", [Name]),
            [io:format("~ts~n", [Line]) || Line <- Lines],
            show(T)
    after 0 -> ok
    end.

%% RETURN: ok; runs the viewer on the sample, presses 'Keys', quits, and
%%         prints what changed after each step; halts with 1 where libvterm
%%         is missing.
view(Keys) ->
    Here = filename:dirname(filename:absname(escript:script_name())),
    Path = filename:join([Here, "TMP", "race.txt"]),
    ok   = filelib:ensure_dir(Path),
    ok   = file:write_file(Path, ?SAMPLE),
    case hwut_vterm:terminal(9, 40) of
        {error, {_, Text}} -> io:format("~ts~n", [Text]), halt(1);
        {ok, T} ->
            ok = hwut_vterm:region(T, <<"title">>,  0),
            ok = hwut_vterm:region(T, <<"body">>,   1, #{row_n => 7}),
            ok = hwut_vterm:region(T, <<"status">>, -1),
            ok = hwut_vterm:on_change(T),
            io:format("> viewer.erl race.txt~n"),
            true = hwut_vterm:run(T, [os:find_executable("escript"), filename:join(Here, "viewer.erl"), Path]),
            show(T),
            {ok, Cell} = hwut_vterm:cell(T, 0, 1),
            io:format("title bar: ~ts~n", [case hwut_vterm:attribute_text(Cell) of <<>> -> <<"plain">>;
                                                                                    A    -> A end]),
            [begin
                 io:format("> ~s~n", [Key]),
                 case length(Key) of 1 -> hwut_vterm:send(T, Key);
                                     _ -> hwut_vterm:press(T, Key) end,
                 show(T)
             end || Key <- Keys],
            hwut_vterm:send(T, "q"),
            show(T),
            {ok, Status} = hwut_vterm:wait(T),
            show(T),
            io:format("> q -- exit status ~b~n", [Status]),
            hwut_vterm:close(T)
    end.
