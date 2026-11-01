%% @hwut {
%%     title      = "hwut_fsm: a state machine as the test's model of the system"
%%     choices {
%%         syntax    { features = ["erlang-fsm"] }
%%         refused   { features = ["erlang-fsm"] }
%%         dfa       { features = ["erlang-fsm"] }
%%         nfa       { features = ["erlang-fsm"] }
%%         forbidden { features = ["erlang-fsm"] }
%%         model     { features = ["erlang-fsm"] }
%%         report    { features = ["erlang-fsm"] }
%%         masks     { features = ["erlang-fsm"] }
%%     }
%%     interactive = true
%% }
%%
%% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%%_____________________________________________________________________________
%%
%% PURPOSE: The Erlang port of 'python/TEST/test-hwut_fsm.py', choice for
%%          choice, held against its GOOD files by '.link'. The machine is a
%%          value: each event fired gives the machine that follows.
%%_____________________________________________________________________________
-mode(compile).
-include("../hwut_boot.hrl").

%%  THE PROTOCOL OF EVERY CHOICE: a request is waited on, granted, released;
%%  a fault while busy crashes it -- which must never happen.
-define(PROTOCOL, <<"
    initial:   idle
    forbidden: crashed
    final:     idle
    idle    ---( request )---> waiting ---( grant )---> busy
    busy    ---( release )---> idle
    :       ---( fault )--->   crashed       # the state that began line 6
    waiting ---( cancel )---> idle
">>).

main(Argv) ->
    hwut_boot(),
    hwut_runner:run(Argv, "hwut_fsm: a state machine as the test's model of the system",
                    #{"syntax"    => fun run_syntax/0,
                      "refused"   => fun run_refused/0,
                      "dfa"       => fun run_dfa/0,
                      "nfa"       => fun run_nfa/0,
                      "forbidden" => fun run_forbidden/0,
                      "model"     => fun run_model/0,
                      "report"    => fun run_report/0,
                      "masks"     => fun run_masks/0}).

%% RETURN: ok; the section heading is printed.
banner(Label) -> io:format("~n--- ~ts ---~n", [Label]).

%% RETURN: ok; one line printed.
say(Format, Arguments) -> io:format(Format ++ "~n", Arguments).

%% RETURN: machine, the model 'Text' states.
model(Text) -> model(Text, #{}).
model(Text, Options) -> {ok, M} = hwut_fsm:from_string(Text, Options), M.

%% RETURN: the path as Python prints it: a tuple of events, or None.
tuple(Path) when is_list(Path) -> list_to_tuple(Path);
tuple(none)                    -> none.

%% RETURN: ok; models read from text and written back.
run_syntax() ->
    banner("the protocol, written back"),
    say("~ts", [hwut_fsm:to_string(model(?PROTOCOL))]),
    banner("the author's form: 'state', a chain, ':', blanks around '-->'"),
    say("~ts", [hwut_fsm:to_string(model(<<"
        state A ---( event )---> state B
        :                ---(event2)---> state C ---(event) --> state D
        state E          # no transition yet
    ">>))]).

%% RETURN: ok; each model that cannot be meant, and why.
run_refused() ->
    [begin
         banner(binary:replace(Text, <<"\n">>, <<" | ">>, [global])),
         case hwut_fsm:from_string(Text) of
             {ok, _}                     -> say("accepted", []);
             {error, {fsm_error, Error}} -> say("FsmError: ~ts", [Error])
         end
     end || Text <- [<<"A ---( x )---> B\n: ---( x )---> C">>,
                     <<"A ---(  )---> B">>,
                     <<": ---( x )---> B">>,
                     <<"A B ---( x )---> C">>,
                     <<"initial: A, B\nA ---( x )---> B">>,
                     <<"forbidden: Q\nA ---( x )---> B">>,
                     <<"# nothing but a comment">>]],
    ok.

%% RETURN: ok; events fired into one machine, then asked where it stands.
run_dfa() ->
    Events = [<<"request">>, <<"release">>, <<"grant">>, <<"release">>, <<"jump">>, <<"request">>],
    {M, _} = lists:foldl(
               fun(Event, {M0, Number}) ->
                       {Moved, M1} = hwut_fsm:fire(Event, Number, M0),
                       {ok, State} = hwut_fsm:state(M1),
                       say("    ~ts -> ~ts now ~ts allowed: ~ts",
                           [pytext:ljust(Event, 8), pytext:ljust(pytext:bool(Moved), 5),
                            pytext:ljust(State, 8), lists:join(", ", hwut_fsm:allowed(M1))]),
                       {M1, Number + 1}
               end, {model(?PROTOCOL), 1}, Events),
    banner("questions where it stands"),
    say("can('grant')   ~ts", [pytext:bool(hwut_fsm:can(<<"grant">>, M))]),
    say("can('release') ~ts", [pytext:bool(hwut_fsm:can(<<"release">>, M))]),
    say("in_state('waiting') ~ts", [pytext:bool(hwut_fsm:in_state(<<"waiting">>, M))]),
    say("trace: ~ts", [lists:join(" ", [io_lib:format("~b:~ts>~ts", [W, E, T])
                                        || {W, _, E, T} <- hwut_fsm:trace(M)])]).

%% RETURN: ok; dfa false: several states at once.
run_nfa() ->
    M0 = model(<<"
        A ---( x )---> B ---( y )---> D
        : ---( x )---> C ---( y )---> E
        C ---( z )---> F
    ">>, #{dfa => false}),
    lists:foldl(fun(Event, Mi) ->
                        {_, Mj} = hwut_fsm:fire(Event, <<"t=", Event/binary>>, Mi),
                        say("    after ~ts: ~ts", [Event, lists:join(", ", hwut_fsm:current(Mj))]),
                        Mj
                end, M0, [<<"x">>, <<"z">>, <<"y">>]),
    banner("'state' asked of a set"),
    {_, M1} = hwut_fsm:fire(<<"x">>, hwut_fsm:reset(M0)),
    case hwut_fsm:state(M1) of
        {ok, State}                 -> say("~ts", [State]);
        {error, {fsm_error, Error}} -> say("FsmError: ~ts", [Error])
    end.

%% RETURN: ok; a forbidden state entered is said, and entered.
run_forbidden() ->
    {M, _} = lists:foldl(fun(Event, {M0, Number}) ->
                                 {Moved, M1} = hwut_fsm:fire(Event, Number, M0),
                                 say("    ~ts -> ~ts", [pytext:ljust(Event, 8), pytext:bool(Moved)]),
                                 {M1, Number + 1}
                         end, {model(?PROTOCOL), 1}, [<<"request">>, <<"grant">>, <<"fault">>]),
    {ok, State} = hwut_fsm:state(M),
    say("now in ~ts -- breaches: ~b", [State, hwut_fsm:breach_n(M)]).

%% RETURN: ok; the model alone: its findings and the shortest paths.
run_model() ->
    M0 = model(<<?PROTOCOL/binary, "\n    state limbo\n    limbo ---( kick )---> idle\n">>),
    say("check: ~b", [hwut_fsm:check(M0)]),
    banner("path_to"),
    [say("    ~ts ~ts", [pytext:ljust(S, 8), pytext:repr(tuple(hwut_fsm:path_to(S, M0)))])
     || S <- [<<"busy">>, <<"crashed">>, <<"limbo">>, <<"idle">>]],
    {_, M1} = hwut_fsm:fire(<<"request">>, M0),
    say("    busy from now: ~ts", [pytext:repr(tuple(hwut_fsm:path_to(<<"busy">>, #{start => now}, M1)))]),
    say("    state_reachable('idle', start='now'): ~ts",
        [pytext:bool(hwut_fsm:state_reachable(<<"idle">>, #{start => now}, M1))]).

%% RETURN: ok; coverage, and an end outside the final states.
run_report() ->
    M = lists:foldl(fun(Event, Mi) -> element(2, hwut_fsm:fire(Event, Mi)) end,
                    model(?PROTOCOL, #{name => <<"protocol">>}),
                    [<<"request">>, <<"grant">>, <<"release">>, <<"request">>, <<"grant">>]),
    say("report returns ~b", [hwut_fsm:report(M)]).

%% RETURN: machine, after 'Event' fired at 'Where'.
fire(Event, Where, M0) -> element(2, hwut_fsm:fire(Event, Where, M0)).

%% RETURN: machine, of a change of the law that was accepted.
ok({ok, M}) -> M.

%% RETURN: ok; the law changing while the machine runs.
run_masks() ->
    M0 = model(?PROTOCOL),
    banner("'grant' disallowed in every state, since line 2"),
    M1 = fire(<<"request">>, 3, ok(hwut_fsm:disallow(<<"grant">>, #{where => 2}, M0))),
    say("    allowed now: ~ts -- can('grant'): ~ts",
        [lists:join(", ", hwut_fsm:allowed(M1)), pytext:bool(hwut_fsm:can(<<"grant">>, M1))]),
    M2 = fire(<<"grant">>, 4, M1),
    say("    path_to('busy'):               ~ts", [pytext:repr(tuple(hwut_fsm:path_to(<<"busy">>, M2)))]),
    say("    path_to('busy', masked=False): ~ts",
        [pytext:repr(tuple(hwut_fsm:path_to(<<"busy">>, #{masked => false}, M2)))]),
    say("    check(): ~b", [hwut_fsm:check(M2)]),
    say("    check(masked=False): ~b", [hwut_fsm:check(#{masked => false}, M2)]),
    banner("allowed again; 'busy' forbidden while standing in it"),
    M3 = fire(<<"grant">>, 6, ok(hwut_fsm:allow(<<"grant">>, #{where => 5}, M2))),
    M4 = ok(hwut_fsm:forbid(<<"busy">>, #{where => 7}, M3)),
    M5 = fire(<<"grant">>, 10, fire(<<"request">>, 9, fire(<<"release">>, 8, M4))),
    banner("permitted: 'busy', and the model's own 'crashed'"),
    M6 = ok(hwut_fsm:permit(<<"crashed">>, #{where => 12}, ok(hwut_fsm:permit(<<"busy">>, #{where => 11}, M5)))),
    {Moved, M7} = hwut_fsm:fire(<<"fault">>, 13, M6),
    {ok, State} = hwut_fsm:state(M7),
    say("    fault -> ~ts -- now in ~ts", [pytext:bool(Moved), State]),
    banner("a phase: 'release' disallowed in 'busy' for a block"),
    M8 = fire(<<"grant">>, none, fire(<<"request">>, none, hwut_fsm:reset(M7))),
    M9 = ok(hwut_fsm:disallowed(<<"release">>, #{state => <<"busy">>, where => <<"phase">>},
                                fun(Mi) -> fire(<<"release">>, 20, Mi) end, M8)),
    M10 = ok(hwut_fsm:disallow(<<"cancel">>, #{where => 22}, fire(<<"release">>, 21, M9))),
    hwut_fsm:report(M10),
    banner("refused: a word the model never names"),
    [case Call() of {error, {fsm_error, Error}} -> say("FsmError: ~ts", [Error]) end
     || Call <- [fun() -> hwut_fsm:disallow(<<"jump">>, #{}, M10) end,
                 fun() -> hwut_fsm:forbid(<<"limbo">>, #{}, M10) end,
                 fun() -> hwut_fsm:allow(<<"grant">>, #{state => <<"nowhere">>}, M10) end]],
    ok.
