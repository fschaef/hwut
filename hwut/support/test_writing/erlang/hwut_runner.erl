%% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%%_____________________________________________________________________________
%%
%% PURPOSE: FRONT END OF A HWUT TEST APPLICATION IN ERLANG -- the port of
%%          'python/hwut_runner.py': the same modes, the same words.
%%
%%     app --hwut-info      the info block; exit 0.
%%     app <choice>         one choice; test output on stdout, '<hwut-end>'
%%                          after it. '-' runs a choice-less test.
%%     app --interactive    choices started over stdin, output into two
%%                          named sink files per choice, 'done' on the
%%                          original stdout.
%%     app                  the choice-less test; where the application has
%%                          choices, refused, naming them.
%%
%% USAGE (an escript; see README.txt for the line that finds this module):
%%
%%     main(Argv) ->
%%         hwut_runner:run(Argv, "What this tests",
%%                         #{"plain" => fun plain/0, "tricky" => fun tricky/0}).
%%
%% The choice map maps a choice name (a string) to a function of no
%% argument; the key 'none' names the single choice-less test. Options
%% (run/4): #{happy => [Pattern], same => true, parallel => process}.
%%
%% A CHOICE IS A PROCESS, in both modes: spawned for the choice, its GROUP
%% LEADER the stream its output goes to -- the process's stdout in normal
%% mode, the sink file in interactive mode. Every process the choice spawns
%% inherits that group leader, so a trigger's or a task's 'io:format' lands
%% in the choice's sink without a descriptor being touched: what Python
%% does with 'dup2', Erlang's I/O system does by design. A choice ENDS its
%% process: returning is status 0; 'hwut_runner:exit(N)' is Python's
%% 'SystemExit(N)'; an exception is status 1, its class, reason and stack
%% written to the error sink (stderr in normal mode).
%%
%% THE INTERACTIVE PROTOCOL is Python's, line for line:
%%     DOWN  run <choice> <sink-out> <sink-err> | info | quit | q | exit
%%     UP    done <choice> <status> | fail <choice> <reason> | info: <line> | bye
%% EACH CHOICE STARTS FROM THE STATE AT SESSION ENTRY, as Python's
%% 'process' scheme gives it: no process survives a choice that the next
%% one meets, and the OS environment a choice changed ('os:putenv') is set
%% back before the next choice of a sequential session starts.
%% 'parallel => process' runs choices concurrently ('done' in completion
%% order); they then share the one environment.
%%_____________________________________________________________________________
-module(hwut_runner).
-export([run/3, run/4, exit/1, levenshtein_distance/2, levenshtein_best_match/2]).

-record(runner, {title, choice_map, sorted, happy = [], same_f = false,
                 parallel = none}).

%% RETURN: never; see 'run/4'.
run(Argv, Title, ChoiceMap) -> run(Argv, Title, ChoiceMap, #{}).

%% RETURN: never; the VM halts with the status of the mode the command line
%%         'Argv' selects (see the head): 0 for the info block, a session
%%         and a choice that returned; the choice's own status else; 1 for
%%         a refusal.
run(Argv, Title, ChoiceMap, Options) when map_size(ChoiceMap) > 0 ->
    true = (not is_map_key(none, ChoiceMap)) orelse map_size(ChoiceMap) == 1,
    R = #runner{title      = iolist_to_binary(Title),
                choice_map = ChoiceMap,
                sorted     = case is_map_key(none, ChoiceMap) of
                                 true  -> [none];
                                 false -> lists:sort(maps:keys(ChoiceMap))
                             end,
                happy      = [iolist_to_binary(H) || H <- maps:get(happy, Options, [])],
                same_f     = maps:get(same, Options, false),
                parallel   = maps:get(parallel, Options, none)},
    case Argv of
        [W | _] when W == "-h"; W == "--hi"; W == "--hwut-info"; W == "--sos"; W == "--wtf" ->
            [say(L) || L <- info_lines(R)],
            halt_flushed(0);
        ["--interactive" | _] ->
            interactive(R),
            halt_flushed(0);
        [] ->
            case is_map_key(none, ChoiceMap) of
                true  -> normal(R, none);
                false -> say(["error: a choice is required: ", choice_list_text(R),
                              " -- name one, or let 'hwut.play' ask."]),
                         halt_flushed(1)
            end;
        [Word | _] ->
            case choice_of_word(R, Word) of
                {ok, Choice} -> normal(R, Choice);
                error        -> refuse(R, Word)
            end
    end.

%% RETURN: never; the running choice ends with 'Status' -- Python's
%%         'sys.exit(Status)' inside a choice.
exit(Status) when is_integer(Status) -> erlang:exit({hwut_exit, Status}).

%% RETURN: {ok, Choice}, the choice the command-line 'Word' names -- 'none'
%%         for a choice-less application's listed name '-' (ND4);
%%         error, no choice is named.
choice_of_word(#runner{choice_map = Map}, Word) ->
    case Map of
        #{Word := _}                 -> {ok, Word};
        #{none := _} when Word == "-" -> {ok, none};
        _                            -> error
    end.

%% RETURN: never; the unavailable choice 'Word', the available ones and the
%%         closest by Levenshtein distance are said; exit status 1.
refuse(#runner{choice_map = #{none := _}}, Word) ->
    say(["error: '", Word, "': this application has no choices -- call it without one."]),
    halt_flushed(1);
refuse(R, Word) ->
    say(["error: choice '", Word, "' not available."]),
    say(["error: available: ", choice_list_text(R), "."]),
    case levenshtein_best_match(Word, R#runner.sorted) of
        none       -> ok;
        Suggestion -> say(["error: did you mean '", Suggestion, "'?"])
    end,
    halt_flushed(1).

%% RETURN: never; the choice ran with the process's stdout as its output --
%%         a UNICODE device: text is written as UTF-8, a binary taken as
%%         UTF-8 ('~ts', 'put_chars') --
%%         '<hwut-end>' after it (R-70, always); the VM halts with the
%%         choice's status, an exception's report on stderr.
normal(#runner{choice_map = Map}, Choice) ->
    ok = io:setopts(standard_io, [{encoding, unicode}]),
    case run_choice(maps:get(Choice, Map), group_leader(), true) of
        {0, _}           -> halt_flushed(0);
        {Status, Report} -> io:put_chars(standard_error, Report),
                            halt_flushed(Status)
    end.

%% RETURN: {Status, Report}, once the choice 'Function' ran in a process of
%%         its own whose group leader is 'Output', and that process ended:
%%         {0, <<>>} it returned ('<hwut-end>' written after it where
%%         'TerminalF'), {N, <<>>} it called 'exit(N)', {1, Text} it raised
%%         -- the class, reason and stack in 'Text'.
run_choice(Function, Output, TerminalF) ->
    Parent = self(),
    {Pid, Ref} = spawn_monitor(
                   fun() ->
                           group_leader(Output, self()),
                           Status = try Function() of
                                        _ -> TerminalF andalso io:put_chars("<hwut-end>\n"),
                                             0
                                    catch
                                        exit:{hwut_exit, N} -> {exit, N};
                                        Class:Reason:Stack  -> {raised, Class, Reason, Stack}
                                    end,
                           Parent ! {choice_status, self(), Status}
                   end),
    receive {choice_status, Pid, Result} -> ok end,
    receive {'DOWN', Ref, process, Pid, _} -> ok end,
    case Result of
        0                               -> {0, <<>>};
        {exit, N}                       -> {N, <<>>};
        {raised, Class, Reason, Stack}  ->
            {1, iolist_to_binary(io_lib:format("~p:~p~n~p~n", [Class, Reason, Stack]))}
    end.

%% RETURN: ok; 'IoData' and a newline are written on stdout.
say(IoData) -> io:put_chars([IoData, $\n]).

%% RETURN: never; the VM halts with 'Status' once its output is written.
halt_flushed(Status) -> halt(Status, [{flush, true}]).

%% RETURN: [binary], the lines of the info block: title, CHOICES, HAPPY
%%         patterns, SAME, INTERACTIVE.
info_lines(#runner{title = Title, choice_map = Map, happy = Happy, same_f = SameF} = R) ->
    TitleLine = case binary:last(Title) of $; -> Title; _ -> <<Title/binary, ";">> end,
    Choices   = case is_map_key(none, Map) of
                    true  -> [];
                    false -> [iolist_to_binary(["CHOICES: ", choice_list_text(R), ";"])]
                end,
    [TitleLine] ++ Choices ++ [<<"HAPPY: ", H/binary, ";">> || H <- Happy]
        ++ [<<"SAME;">> || SameF] ++ [<<"INTERACTIVE;">>].

%% RETURN: iolist, the sorted choices joined by ', ' -- the choice-less one
%%         as '-'.
choice_list_text(#runner{sorted = Sorted}) ->
    lists:join(", ", [case C of none -> "-"; _ -> C end || C <- Sorted]).

%% ------------------------------------------------------------ interactive
%% RETURN: ok, once the session ended ('quit' or end of input) and every
%%         choice still running was waited for and reported; 'bye' said.
interactive(R) ->
    %  THE UP CHANNEL IS 'user', the VM's own stdout; everything else this
    %  process and the VM's logger would write goes to the STRAY sink.
    Stray = filename:join(stray_directory(), "hwut_stray_" ++ os:getpid() ++ ".txt"),
    {ok, StrayDevice} = file:open(Stray, [write, {encoding, unicode}]),
    group_leader(StrayDevice, self()),
    _ = logger:remove_handler(default),
    _ = logger:add_handler(hwut_stray, logger_std_h,
                           #{config => #{type => {file, Stray ++ ".log"}}}),
    Self = self(),
    spawn_link(fun() -> read_loop(Self) end),
    session(R, os:getenv(), #{}).

%% RETURN: string, the directory of temporary files (TMPDIR, else /tmp).
stray_directory() ->
    case os:getenv("TMPDIR") of false -> "/tmp"; "" -> "/tmp"; D -> D end.

%% RETURN: never returns before the end of stdin; every line read is sent
%%         to 'Session' stripped, the end as 'eof'.
read_loop(Session) ->
    case io:get_line(user, "") of
        eof               -> Session ! eof;
        {error, _}        -> Session ! eof;
        Line              -> Session ! {line, string:trim(Line)},
                             read_loop(Session)
    end.

%% RETURN: ok; 'Line' and a newline are written on the UP channel -- one
%%         request to 'user', so lines of concurrent choices never mix.
up(Line) -> io:put_chars(user, [Line, $\n]).

%% RETURN: ok, once the session ended; 'Pending' maps the process of every
%%         choice running in parallel to its token.
session(R, Environment, Pending) ->
    receive
        {line, <<>>} -> session(R, Environment, Pending);
        {line, ""}   -> session(R, Environment, Pending);
        {line, Line} ->
            case interprete(R, Environment, string:lexemes(Line, " \t"), Pending) of
                {continue, Pending1} -> session(R, Environment, Pending1);
                stop                 -> drain(Pending)
            end;
        eof ->
            drain(Pending);
        {done, Pid, Status} ->
            {Token, Pending1} = maps:take(Pid, Pending),
            up(["done ", Token, " ", integer_to_list(Status)]),
            session(R, Environment, Pending1)
    end.

%% RETURN: ok; every choice still running was waited for and reported,
%%         then 'bye' said.
drain(Pending) when map_size(Pending) == 0 -> up("bye");
drain(Pending) ->
    receive {done, Pid, Status} ->
            {Token, Pending1} = maps:take(Pid, Pending),
            up(["done ", Token, " ", integer_to_list(Status)]),
            drain(Pending1)
    end.

%% RETURN: {continue, Pending}, the session goes on -- 'Pending' with a
%%         parallel choice added that was started;
%%         stop, the session ends ('quit', 'q', 'exit').
%%         Replies on the UP channel; never raises.
interprete(_, _, [Quit], _) when Quit == "quit"; Quit == "q"; Quit == "exit" ->
    stop;
interprete(R, _, ["info"], Pending) ->
    [up(["info: ", L]) || L <- info_lines(R)],
    up("done - 0"),
    {continue, Pending};
interprete(R, Environment, ["run", Token, SinkOut, SinkErr], Pending) ->
    case find_choice(R, Token) of
        error ->
            up(["fail ", Token, " unknown-choice"]),
            {continue, Pending};
        {ok, Function} when R#runner.parallel == process ->
            Session = self(),
            Pid = spawn(fun() -> Session ! {done, self(), into_sinks(Function, SinkOut, SinkErr)} end),
            {continue, Pending#{Pid => Token}};
        {ok, Function} ->
            restore_environment(Environment),
            Status = into_sinks(Function, SinkOut, SinkErr),
            up(["done ", Token, " ", integer_to_list(Status)]),
            {continue, Pending}
    end;
interprete(_, _, _, Pending) ->
    up("fail - bad-command"),
    {continue, Pending}.

%% RETURN: {ok, Function}, the function of the choice 'Token' names -- by
%%         name, by its index into the sorted list, or '-' for the
%%         choice-less test;
%%         error, no choice is named.
find_choice(#runner{choice_map = Map, sorted = Sorted}, Token) ->
    case {Token, Map} of
        {"-", #{none := F}} -> {ok, F};
        {_, #{Token := F}}  -> {ok, F};
        _ ->
            case Token =/= "" andalso lists:all(fun(C) -> C >= $0 andalso C =< $9 end, Token)
                     andalso list_to_integer(Token) of
                I when is_integer(I), I < length(Sorted) -> {ok, maps:get(lists:nth(I + 1, Sorted), Map)};
                _                                        -> error
            end
    end.

%% RETURN: integer, the status the choice 'Function' ended with (see
%%         'run_choice'), once it ran with its output into the file
%%         'SinkOut' -- '<hwut-end>' after it unless HWUT_NO_TERMINAL --
%%         an exception's report into 'SinkErr', and BOTH FILES CLOSED: the
%%         'done' barrier. Every write of the choice reached its file before
%%         the close, an Erlang file's writes being requests served in order.
into_sinks(Function, SinkOut, SinkErr) ->
    {ok, Out} = file:open(SinkOut, [write, {encoding, unicode}]),
    {ok, Err} = file:open(SinkErr, [write, {encoding, unicode}]),
    {Status, Report} = run_choice(Function, Out, os:getenv("HWUT_NO_TERMINAL") == false),
    ok = file:write(Err, Report),
    ok = file:close(Out),
    ok = file:close(Err),
    Status.

%% RETURN: ok; the OS environment is 'Environment' again (a list of
%%         "NAME=value", as 'os:getenv()' gave it at session entry).
restore_environment(Environment) ->
    Then = maps:from_list([name_value(V) || V <- Environment]),
    _ = [os:unsetenv(N) || V <- os:getenv(), {N, _} <- [name_value(V)], not is_map_key(N, Then)],
    _ = [os:putenv(N, Value) || {N, Value} <- maps:to_list(Then), os:getenv(N) =/= Value],
    ok.

%% RETURN: {Name, Value}, the two sides of the first '=' of "NAME=value".
name_value(Text) ->
    case string:split(Text, "=") of [Name, Value] -> {Name, Value}; [Name] -> {Name, ""} end.

%% ------------------------------------------------------------ distance
%% RETURN: string, the element of 'Haystack' least distant from 'Needle'
%%         (the first among equals; 'Needle' itself where it is one);
%%         none, 'Haystack' is empty.
levenshtein_best_match(_, []) -> none;
levenshtein_best_match(Needle, Haystack) ->
    case lists:member(Needle, Haystack) of
        true  -> Needle;
        false ->
            {_, Best} = lists:foldl(fun(none, Acc) -> Acc;
                                       (Key, {D0, _} = Acc) ->
                                            D = levenshtein_distance(Needle, Key),
                                            if D0 == none; D < D0 -> {D, Key}; true -> Acc end
                                    end, {none, none}, Haystack),
            Best
    end.

%% RETURN: integer >= 0, the Levenshtein distance between the strings 'A'
%%         and 'B'.
levenshtein_distance(A, A)  -> 0;
levenshtein_distance([], B) -> length(B);
levenshtein_distance(A, []) -> length(A);
levenshtein_distance(A, B) when length(A) < length(B) -> levenshtein_distance(B, A);
levenshtein_distance(A, B) ->
    First = lists:seq(0, length(B)),
    {Last, _} = lists:foldl(fun(Ca, {Prev, I}) -> {row(Ca, B, Prev, [I]), I + 1} end,
                            {First, 1}, A),
    lists:last(Last).

%% RETURN: [integer], the next row of the distance table for the character
%%         'Ca' of the longer string, from the row 'Prev' above it.
row(_, [], _, Cur) -> lists:reverse(Cur);
row(Ca, [Cb | B], [Diagonal, Above | Prev], [Left | _] = Cur) ->
    Sub = Diagonal + (if Ca == Cb -> 0; true -> 1 end),
    row(Ca, B, [Above | Prev], [min(min(Left + 1, Above + 1), Sub) | Cur]).
