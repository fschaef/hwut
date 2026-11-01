%% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%%_____________________________________________________________________________
%%
%% PURPOSE: A TERMINAL'S SCREEN, READ BY A TEST -- the port of
%%          'python/hwut_vterm.py' (its manual: '../python/README-
%%          hwut_vterm.txt'): libvterm's screen, cells and events, and an
%%          application run on a pseudo-terminal it cannot tell from a
%%          person's.
%%
%%     {ok, S} = hwut_vterm:screen(24, 80),     % {error, {library_missing, Text}}
%%     hwut_vterm:feed(S, <<"\e[1mbold\e[0m plain">>),
%%     <<"bold plain">> = hwut_vterm:line(S, 0),
%%     {ok, #{bold_f := true}} = hwut_vterm:cell(S, 0, 0),
%%     hwut_vterm:close(S)
%%
%%     {ok, T} = hwut_vterm:terminal(10, 44),   % settle_s 0.1
%%     hwut_vterm:region(T, <<"read">>, 8),
%%     hwut_vterm:on_change(T),                 % this process is told
%%     true = hwut_vterm:run(T, ["python3", "app.py"]),
%%     hwut_vterm:press(T, "up", [shift]),
%%     receive {hwut_vterm, T, {change, <<"read">>, Lines}} -> ... end,
%%     {ok, Status} = hwut_vterm:wait(T)
%%
%% LIBVTERM LIVES IN A PORT PROGRAM, not in the VM: 'hwut_vterm_port' -- the
%% C port's '../c/hwut_vterm.c' unchanged, behind Erlang's '{packet, 4}'
%% framing -- one program per screen or terminal, started by 'screen' or
%% 'terminal', ended by 'close' or by the end of the process that made it.
%% A NIF would put a blocking 'select' and a library that may crash into
%% the VM's own process; a port keeps both outside. The program is built by
%% 'make' here on first use (and where it is older than its sources).
%%
%% OBSERVATION IS BY MESSAGE, Erlang's callback: after 'on_event(T)' and
%% 'on_change(T)' the process that made the terminal receives
%%     {hwut_vterm, T, {event, Event}}            Event: a map, see 'event_text'
%%     {hwut_vterm, T, {change, Name, Lines}}     a region changed, once quiet
%% in the order libvterm reported them, each one in the mailbox before the
%% call that caused it returns -- Python's callbacks run during that call.
%% An object is used by the process that made it (the port's owner).
%%
%% ERRORS ARE VALUES: {error, {Kind, Text}}, Kind Python's exception in
%% Erlang's spelling -- library_missing, index_error, key_error,
%% timeout_error, runtime_error -- and Text its message.
%%_____________________________________________________________________________
-module(hwut_vterm).
-export([library_variable/0, attribute_names/0, attribute_sgr/1, detection_text/0,
         screen/2, terminal/2, terminal/3, close/1, feed/2, cursor/1, cell/3,
         attribute_text/1, line/2, line_list/1, on_event/1, on_change/1,
         event_text/1, region/3, region/4, region_text/2, report/1, answer/1,
         send/2, send/3, press/2, press/3, press/4, run/2, run/3, pump/1,
         pump/2, expect/2, expect/3, wait/1, wait/2]).

-record(vterm, {port, kind :: screen | terminal, row_n, column_n}).

%% RETURN: string, the environment variable that names libvterm's file.
library_variable() -> "HWUT_LIBVTERM".

%% RETURN: [atom], the attributes a cell is asked for, in their fixed order.
attribute_names() -> [bold, italic, underline, blink, reverse, conceal, strike].

%% RETURN: string, the SGR code that sets the attribute.
attribute_sgr(bold) -> "1";      attribute_sgr(italic) -> "3";
attribute_sgr(underline) -> "4"; attribute_sgr(blink) -> "5";
attribute_sgr(reverse) -> "7";   attribute_sgr(conceal) -> "8";
attribute_sgr(strike) -> "9".

%% ---------------------------------------------------------- the transport
%% RETURN: {ok, Path}, the port program, built first where it is missing or
%%         older than a source; {error, {runtime_error, Text}}, it cannot be
%%         built (what make said).
program() ->
    Here    = filename:dirname(filename:dirname(code:which(?MODULE))),
    Program = filename:join(Here, "hwut_vterm_port"),
    Sources = [filename:join(Here, "hwut_vterm_port.c"),
               filename:join([Here, "..", "c", "hwut_vterm.c"]),
               filename:join([Here, "..", "c", "hwut_vterm.h"])],
    Built = filelib:last_modified(Program),
    case Built == 0 orelse lists:any(fun(S) -> filelib:last_modified(S) > Built end, Sources) of
        false -> {ok, Program};
        true  ->
            Make = open_port({spawn_executable, os:find_executable("make")},
                             [{args, ["-s", "-C", Here, "hwut_vterm_port"]}, exit_status,
                              stderr_to_stdout, binary]),
            case made(Make, []) of
                ok         -> {ok, Program};
                {error, S} -> {error, {runtime_error, iolist_to_binary(["'hwut_vterm_port' cannot be built in '",
                                                                         Here, "':\n", S])}}
            end
    end.

%% RETURN: ok, make ended well; {error, Said}, it did not.
made(Port, Said) ->
    receive
        {Port, {data, Data}}     -> made(Port, [Said, Data]);
        {Port, {exit_status, 0}} -> ok;
        {Port, {exit_status, _}} -> {error, Said}
    end.

%% RETURN: {ok, Object}, a port program serving a new screen or terminal;
%%         {error, {Kind, Text}}, it cannot be made.
open(Kind, Fields, RowN, ColumnN) ->
    case program() of
        {error, _} = Error -> Error;
        {ok, Program} ->
            Port = open_port({spawn_executable, Program}, [{packet, 4}, binary, exit_status, use_stdio]),
            V = #vterm{port = Port, kind = Kind, row_n = RowN, column_n = ColumnN},
            case call(V, Fields) of
                {ok, []} -> {ok, V};
                Error    -> close(V), Error
            end
    end.

%% RETURN: binary, the fields of one message, each its length and its bytes.
encoded(Fields) -> << <<(byte_size(B)):32, B/binary>> || F <- Fields, B <- [field(F)] >>.

%% RETURN: binary, one field as the port program reads it.
field(F) when is_binary(F)  -> F;
field(F) when is_integer(F) -> integer_to_binary(F);
field(F) when is_float(F)   -> float_to_binary(F, [short]);
field(F) when is_atom(F)    -> atom_to_binary(F);
field(F) when is_list(F)    -> unicode:characters_to_binary(F).

%% RETURN: [binary], the fields of one message.
decoded(<<N:32, F:N/binary, Rest/binary>>) -> [F | decoded(Rest)];
decoded(<<>>)                               -> [].

%% RETURN: {ok, [binary]}, the fields of the port program's 'ok';
%%         {error, {Kind, Text}}, its 'err' -- or its end. What it reports
%%         while the command runs is sent to this process first.
call(#vterm{port = Port} = V, Fields) ->
    true = port_command(Port, encoded(Fields)),
    reply(V).

%% RETURN: as 'call', once the reply arrived.
reply(#vterm{port = Port} = V) ->
    receive
        {Port, {data, Data}} ->
            case decoded(Data) of
                [<<"ok">> | Rest]         -> {ok, Rest};
                [<<"err">>, Kind, Text]   -> {error, {kind(Kind), Text}};
                [<<"event">> | Event]     -> self() ! {hwut_vterm, V, {event, event(Event)}}, reply(V);
                [<<"change">>, Name | Ls] -> self() ! {hwut_vterm, V, {change, Name, Ls}}, reply(V)
            end;
        {Port, {exit_status, Status}} ->
            {error, {runtime_error, iolist_to_binary(io_lib:format("the vterm port ended (~b)", [Status]))}}
    end.

%% RETURN: atom, Python's exception name in Erlang's spelling:
%%         'LibraryMissing' -> library_missing, 'KeyError' -> key_error.
kind(Name) ->
    Snake = re:replace(Name, "([a-z])([A-Z])", "\\1_\\2", [global, {return, list}]),
    list_to_atom(string:lowercase(Snake)).

%% RETURN: map, the raw event: kind (damage, cursor, property, bell), the
%%         rows and columns, the property's name, the value (none where a
%%         property's value is a text).
event([Kind, Row, Column, RowEnd, ColumnEnd, Name, ValueF, Value]) ->
    #{kind       => binary_to_atom(Kind),
      row        => binary_to_integer(Row),
      column     => binary_to_integer(Column),
      row_end    => binary_to_integer(RowEnd),
      column_end => binary_to_integer(ColumnEnd),
      name       => Name,
      value      => case ValueF of <<"0">> -> none; _ -> binary_to_integer(Value) end}.

%% RETURN: integer, the one number an 'ok' carries.
ok({ok, [Value]}) -> binary_to_integer(Value).

%% ------------------------------------------------------------ the library
%% RETURN: binary, 'libvterm found: <name>' where the library loads; else
%%         the text of 'LibraryMissing' -- what is wrong, how to install it.
detection_text() ->
    case program() of
        {error, {_, Text}} -> Text;
        {ok, Program} ->
            Port = open_port({spawn_executable, Program}, [{packet, 4}, binary, exit_status, use_stdio]),
            V = #vterm{port = Port},
            {ok, [Text]} = call(V, [detect]),
            close(V),
            Text
    end.

%% -------------------------------------------------------------- the screen
%% RETURN: {ok, Screen}, blank, 'RowN' rows and 'ColumnN' columns, the
%%         cursor at {0, 0}; {error, {library_missing, Text}}, libvterm is
%%         not found (the text says how to install it).
screen(RowN, ColumnN) -> open(screen, [screen, RowN, ColumnN], RowN, ColumnN).

%% RETURN: ok; the screen or terminal is given back -- an application still
%%         running in it killed -- before this returns, and its program
%%         ended. A second close does nothing.
close(#vterm{port = Port} = V) ->
    case erlang:port_info(Port) of
        undefined -> ok;
        _         -> _ = call(V, [free]),
                     catch port_close(Port),
                     ok
    end.

%% RETURN: integer, the number of bytes the screen took -- all of them.
%%         'Data' is a binary of bytes, or a string (characters) sent as
%%         UTF-8. A terminal reports its raw events as it draws; what it
%%         answers waits for its application, or in 'answer'.
feed(V, Data) -> ok(call(V, [feed, bytes(Data)])).

%% RETURN: binary, 'Data' as bytes: a binary as it stands, characters UTF-8.
bytes(Data) when is_binary(Data) -> Data;
bytes(Data)                      -> unicode:characters_to_binary(Data).

%% RETURN: {Row, Column}, the cursor's place, from 0.
cursor(V) ->
    {ok, [Row, Column]} = call(V, [cursor]),
    {binary_to_integer(Row), binary_to_integer(Column)}.

%% RETURN: {ok, Cell}, what stands at that place: a map of 'text' (<<>> for
%%         a cell never written and the right half of a wide one), 'width',
%%         the attributes 'bold_f' .. 'strike_f' (booleans; one the library
%%         does not know reads false), 'foreground' and 'background' --
%%         {Red, Green, Blue}, or none for the terminal's default;
%%         {error, {index_error, Text}}, the place is off the screen.
cell(V, Row, Column) ->
    case call(V, [cell, Row, Column]) of
        {ok, [Text, Width | Rest]} ->
            [Bold, Italic, Underline, Blink, Reverse, Conceal, Strike, FgF, R1, G1, B1, BgF, R2, G2, B2] =
                [binary_to_integer(N) || N <- Rest],
            {ok, #{text        => Text,
                   width       => binary_to_integer(Width),
                   bold_f      => Bold == 1,  italic_f  => Italic == 1,
                   underline_f => Underline == 1, blink_f => Blink == 1,
                   reverse_f   => Reverse == 1, conceal_f => Conceal == 1,
                   strike_f    => Strike == 1,
                   foreground  => colour(FgF, R1, G1, B1),
                   background  => colour(BgF, R2, G2, B2)}};
        Error -> Error
    end.

%% RETURN: {R, G, B}, a colour set; none, the default.
colour(0, _, _, _) -> none;
colour(_, R, G, B) -> {R, G, B}.

%% RETURN: binary, the attributes set, by name in their fixed order and
%%         separated by blanks -- 'bold reverse'; <<>> where none is set.
attribute_text(Cell) ->
    pytext:join(<<" ">>, [atom_to_binary(A) || A <- attribute_names(),
                                               maps:get(list_to_atom(atom_to_list(A) ++ "_f"), Cell)]).

%% RETURN: binary, the row's characters, blanks at its end dropped.
line(V, Row) -> lists:nth(Row + 1, line_list(V)).

%% RETURN: [binary], every row as 'line' gives it, top first.
line_list(V) -> {ok, Lines} = call(V, [lines]), Lines.

%% ------------------------------------------------------------ the terminal
%% RETURN: as 'terminal/3', 'settle_s' 0.1.
terminal(RowN, ColumnN) -> terminal(RowN, ColumnN, 0.1).

%% RETURN: {ok, Terminal}, blank, nothing running in it -- 'SettleS' how
%%         long its application must write nothing before its screen is
%%         taken as drawn; {error, {library_missing, Text}}, as 'screen'.
terminal(RowN, ColumnN, SettleS) ->
    open(terminal, [terminal, RowN, ColumnN, float(SettleS)], RowN, ColumnN).

%% RETURN: ok; from now on every raw event reaches the calling process as
%%         {hwut_vterm, T, {event, Event}}.
on_event(#vterm{} = T) -> {ok, []} = call(T, [on_event]), ok.

%% RETURN: ok; from now on every region whose text changed reaches the
%%         calling process as {hwut_vterm, T, {change, Name, Lines}}, once
%%         the screen is quiet, regions in the order of declaration.
on_change(#vterm{} = T) -> {ok, []} = call(T, [on_change]), ok.

%% RETURN: binary, the event on one line, as Python's 'str(Event)' writes it.
event_text(#{kind := damage, row := R, row_end := RE, column := C, column_end := CE}) ->
    iolist_to_binary(io_lib:format("damage    rows ~b..~b  columns ~b..~b", [R, RE, C, CE]));
event_text(#{kind := cursor, row := R, column := C, value := Visible}) ->
    iolist_to_binary(io_lib:format("cursor    (~b, ~b)~ts", [R, C, case Visible of 0 -> "  hidden"; _ -> "" end]));
event_text(#{kind := property, name := Name, value := Value}) ->
    iolist_to_binary(["property  ", Name, " = ", pytext:str(Value)]);
event_text(#{kind := Kind}) ->
    atom_to_binary(Kind).

%% RETURN: as 'region/4', one row, every column.
region(T, Name, Row) -> region(T, Name, Row, #{}).

%% RETURN: ok; the rectangle 'Name' is observed from now on: 'row_n' rows
%%         (1) from 'Row', 'column_n' columns from 'column' (0) -- to the
%%         right edge where not given. A NEGATIVE 'Row' counts from the
%%         bottom: -1 is the last row. What stands there now is not news.
region(T, Name, Row, Options) ->
    {ok, []} = call(T, [region, bytes(Name), Row, maps:get(row_n, Options, 1),
                        maps:get(column, Options, 0), maps:get(column_n, Options, -1)]),
    ok.

%% RETURN: {ok, [binary]}, the region's rows as they stand now, blanks at
%%         each row's end dropped; {error, {key_error, Text}}, no such
%%         region was declared.
region_text(T, Name) ->
    case call(T, [region_text, bytes(Name)]) of
        {ok, Lines} -> {ok, Lines};
        Error       -> Error
    end.

%% RETURN: integer, the number of regions whose text differs from what was
%%         last told -- each told to the process (see 'on_change').
report(T) -> ok(call(T, [report])).

%% RETURN: binary, the bytes the terminal said since the last call and
%%         nobody took -- an answer to a question while no application runs.
answer(T) -> {ok, [Data]} = call(T, [answer]), Data.

%% RETURN: as 'send/3', 'react_s' 1.0.
send(T, Text) -> send(T, Text, 1.0).

%% RETURN: true, the application still runs after 'Text' was typed, a
%%         character at a time as a keyboard sends it, and the screen read
%%         until quiet ('ReactS' for it to begin answering); false else.
send(T, Text, ReactS) -> ok(call(T, [send, bytes(Text), float(ReactS)])) == 1.

%% RETURN: as 'press/4', 'react_s' 1.0.
press(T, Key) -> press(T, Key, [], 1.0).
press(T, Key, Modifiers) -> press(T, Key, Modifiers, 1.0).

%% RETURN: true, the application still runs after 'Key' was pressed with
%%         'Modifiers' (shift, alt, ctrl) -- 'enter', 'up', 'f5', ... or one
%%         character; false, it does not; {error, {key_error, Text}}, the
%%         key or a modifier has no name here.
press(T, Key, Modifiers, ReactS) ->
    Words = pytext:join(<<" ">>, [field(M) || M <- Modifiers]),
    case call(T, [press, bytes(Key), Words, float(ReactS)]) of
        {ok, [Running]} -> Running == <<"1">>;
        Error           -> Error
    end.

%% RETURN: as 'run/3', no options.
run(T, Argv) -> run(T, Argv, #{}).

%% RETURN: true, the application 'Argv' still runs once its first screen
%%         stands ('start_s', 10.0, for it to begin); false, it does not;
%%         {error, {runtime_error, Text}}, one was already run here.
%%         It runs on a pseudo-terminal of this terminal's size -- its three
%%         streams, its controlling terminal; TERM is 'xterm-256color',
%%         LINES and COLUMNS are taken out; else the VM's environment as it
%%         stands now; in 'cwd' where given.
run(T, Argv, Options) ->
    Environment = [unicode:characters_to_binary(V) || V <- os:getenv()],
    Cwd = maps:get(cwd, Options, <<>>),
    case call(T, [run, bytes(Cwd), float(maps:get(start_s, Options, 10.0)), length(Environment)]
                 ++ Environment ++ [bytes(A) || A <- Argv]) of
        {ok, [Running]} -> Running == <<"1">>;
        Error           -> Error
    end.

%% RETURN: as 'pump/2', 'first_s' 1.0.
pump(T) -> pump(T, 1.0).

%% RETURN: true, the application still runs, false else -- once its output
%%         was read until quiet: up to 'FirstS' for it to write at all, then
%%         on until it wrote nothing for 'settle_s'; changed regions told.
pump(T, FirstS) -> ok(call(T, [pump, float(FirstS)])) == 1.

%% RETURN: as 'expect/3', 'timeout_s' 10.0.
expect(T, Text) -> expect(T, Text, 10.0).

%% RETURN: {ok, {Row, Column}}, where 'Text' stands on the screen (the
%%         column in characters); {error, {timeout_error, Text}}, it did not
%%         appear within 'TimeoutS' -- the text carries the screen.
expect(T, Text, TimeoutS) ->
    case call(T, [expect, bytes(Text), float(TimeoutS)]) of
        {ok, [Row, Column]} -> {ok, {binary_to_integer(Row), binary_to_integer(Column)}};
        Error               -> Error
    end.

%% RETURN: as 'wait/2', 'timeout_s' 10.0.
wait(T) -> wait(T, 10.0).

%% RETURN: {ok, Status}, the application's exit status (negative: the
%%         signal that ended it), once it ended and its last words are on
%%         the screen; {ok, none}, no application was run here;
%%         {error, {timeout_error, Text}}, it still ran after 'TimeoutS' and
%%         was killed.
wait(T, TimeoutS) ->
    case call(T, [wait, float(TimeoutS)]) of
        {ok, [<<"None">>]} -> {ok, none};
        {ok, [Status]}     -> {ok, binary_to_integer(Status)};
        Error              -> Error
    end.
