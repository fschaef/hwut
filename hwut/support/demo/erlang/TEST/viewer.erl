#! /usr/bin/env escript
%%! -noinput
%%_____________________________________________________________________________
%% A TERMINAL FILE VIEWER -- the program 'screen.erl' tests; no test itself.
%%
%%     escript viewer.erl <file>
%%
%% Full screen, on the terminal's alternate screen: a title bar (reverse
%% video), as many lines of the file as fit, and a status line: the keys
%% flush left, the lines shown flush right. Keys: 'j' or down one line
%% further, 'k' or up one line back, 'q' quits.
%%
%% THE TERMINAL IS THE VM'S FILE DESCRIPTORS, not its I/O system: '-noinput'
%% (the line above, escript's line for the emulator) keeps the VM from
%% reading the keyboard itself, and fd 0 and fd 1 become one PORT -- keys
%% arrive as messages, bytes leave unchanged. Erlang/OTP 25 has no raw mode
%% of its own: 'stty' sets it, and sets back what it found, on the terminal
%% the VM's fd 0 is.
%%_____________________________________________________________________________
-mode(compile).

%% RETURN: never; the VM halts with 0 once 'q' was pressed.
main([Path]) ->
    {ok, Data} = file:read_file(Path),
    Lines      = string:split(string:trim(Data, trailing, "\n"), "\n", all),
    [Rows, Columns] = [list_to_integer(N) || N <- string:lexemes(stty("size"), " \n")],
    Saved = string:trim(stty("-g")),
    stty("raw -echo"),
    Tty = open_port({fd, 0, 1}, [binary, eof]),
    port_command(Tty, "\e[?1049h"),
    loop(Tty, filename:basename(Path), Lines, 0, Rows, Columns),
    port_command(Tty, "\e[?1049l"),
    stty(Saved),
    halt(0).

%% RETURN: string, what 'stty <Arguments>' printed about the VM's terminal --
%%         the device its fd 0 stands for: a command 'os:cmd' runs has no
%%         controlling terminal, so '/dev/tty' would be none.
stty(Arguments) ->
    {ok, Device} = file:read_link("/proc/self/fd/0"),
    os:cmd("stty -F " ++ Device ++ " " ++ Arguments).

%% RETURN: ok, once 'q' arrived; draws the screen with the file's line 'Top'
%%         first, and goes one line on or back for each key until then.
loop(Tty, Name, Lines, Top, Rows, Columns) ->
    draw(Tty, Name, Lines, Top, Rows, Columns),
    Last = max(0, length(Lines) - (Rows - 2)),
    receive
        {Tty, {data, <<"q">>}}                          -> ok;
        {Tty, {data, K}} when K == <<"j">>; K == <<"\e[B">> -> loop(Tty, Name, Lines, min(Top + 1, Last), Rows, Columns);
        {Tty, {data, K}} when K == <<"k">>; K == <<"\e[A">> -> loop(Tty, Name, Lines, max(Top - 1, 0), Rows, Columns);
        {Tty, {data, _}}                                -> loop(Tty, Name, Lines, Top, Rows, Columns);
        {Tty, eof}                                      -> ok
    end.

%% RETURN: ok; the whole screen is drawn with the file's line 'Top' first.
draw(Tty, Name, Lines, Top, Rows, Columns) ->
    BodyN = Rows - 2,
    Shown = lists:sublist(lists:nthtail(Top, Lines), BodyN),
    Cut   = fun(Text) -> string:slice(Text, 0, Columns) end,
    Where = io_lib:format("lines ~b-~b of ~b", [Top + 1, Top + length(Shown), length(Lines)]),
    Keys  = "j k q",
    port_command(Tty, unicode:characters_to_binary(
                        ["\e[H\e[2J",
                         "\e[7m", Cut(string:pad([" ", Name], Columns)), "\e[0m\r\n",
                         [[Cut(Line), "\r\n"] || Line <- Shown],
                         lists:duplicate(BodyN - length(Shown), "\r\n"),
                         io_lib:format("\e[~b;1H", [Rows]),
                         Keys, string:pad(Where, Columns - 1 - length(Keys), leading)])).
