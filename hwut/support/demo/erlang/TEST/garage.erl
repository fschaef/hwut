%% @hwut {
%%     title    = "Demo: a garage's space counter -- a space, a stream and races, generated"
%%     interactive = true
%%     choices {
%%         space       { features = ["space-from-hocon", "space-iterator", "hwut-runner"]
%%                       tolerance { constraints = ["mismatches == 0"] } }
%%         random      { features = ["deterministic-stream", "hwut-runner"]
%%                       tolerance { constraints = ["mismatches == 0"] } }
%%         race-naive  { features = ["deterministic-timeline", "space-iterator", "hwut-runner"]
%%                       tolerance { constraints = ["overbooked > 0"] } }
%%         race-atomic { features = ["deterministic-timeline", "space-iterator", "hwut-runner"]
%%                       tolerance { constraints = ["overbooked == 0"] } }
%%     }
%% }
%%
%%_____________________________________________________________________________
%% SUBJECT  the counter of free spaces at a garage's gates: which cars it
%%          admits, which it refuses, and how many stand inside.
%% REQUIREMENT  The garage admits a car only while a space is free, lets a car
%%              out only while one stands inside, and never holds more cars
%%              than it has spaces -- also when two gates admit at once.
%%
%% No choice writes its cases out by hand. Each GENERATES them, with one of
%% hwut's helpers for writing tests (hwut/support/test_writing/erlang, found
%% by 'hwut_support.hrl'):
%%
%% space        'garage-space.hocon' states the tested space -- capacities,
%%              cars arriving, cars leaving -- in hwut's HOCON, read by
%%              'hwut_hocon'. A reviewer edits the space without reading
%%              Erlang. 'space_iterator:do' walks every combination: 3 x 5 x
%%              4 = 60 cases. Each is printed as one cell of a matrix, and
%%              checked against the model: admitted = min(arriving,
%%              capacity), out = min(leaving, admitted).
%%
%% random       'deterministic_random:new(4711)' draws 1000 cars arriving and
%%              leaving at a garage of 5. The draw is the same on every
%%              machine and in every language hwut supports -- the stream is
%%              a linear congruential generator, not Erlang's 'rand' -- so
%%              the GOOD is exact (the Python demo's), and a failing run can
%%              be replayed by its seed.
%%
%% race-naive   two gates, one free space. A gate CHECKS whether a space is
%%              free, and later ADMITS its car. 'deterministic_timeline'
%%              runs the two gates as triggers on timelines drawn as
%%              strings -- '1 1 ' fires at tick 0 and tick 2 -- so every
%%              interleaving is played exactly, not hoped for with sleeps.
%%              'space_iterator' generates all six interleavings of two
%%              two-step gates in four ticks. Where both gates check before
%%              either admits, both admit: the garage is overbooked. The law
%%              is 'overbooked > 0': the GOOD is the accepted violation
%%              report.
%%
%% race-atomic  the same six interleavings, the gate checking and admitting
%%              in ONE step -- one call to the process that holds the counter.
%%              'overbooked == 0'.
%%
%% THE GARAGE IS A VALUE where one process drives it (space, random), and a
%% PROCESS holding that value where two gates share it (race): each gate is
%% a trigger process of its own, and a step of a gate is a CALL to the
%% garage -- answered before the gate answers the dispatcher, so the log is
%% in the drawn order.
%%
%% THE FRONT END is hwut's 'hwut_runner': the choice map below is the whole
%% command line, '--hwut-info' included. The header says
%% 'interactive = true': hwut starts the application ONCE and asks for the
%% choices one after another in that one VM -- an accelerator only: a
%% choice's output equals what it prints when run alone.
%%_____________________________________________________________________________
-mode(compile).
-include("hwut_support.hrl").

%% THE TREE OF 'hwut_hocon', as its 'hwut_hocon.hrl' states it: an escript
%% includes what it includes when it is compiled, before 'hwut_support()'
%% has found where the support stands.
-record(source_line,  {text, line, column_offset}).
-record(hocon_object, {position, entry_list = []}).
-record(hocon_list,   {position, item_list  = []}).
-record(hocon_scalar, {position, value}).
-record(hocon_entry,  {key, key_position, node}).

-record(garage, {capacity, occupied = 0}).

%% RETURN: never; 'hwut_runner' halts the VM (see its head).
main(Argv) ->
    hwut_support(),
    hwut_runner:run(Argv, "Demo: a garage's space counter -- a space, a stream and races, generated;",
                    #{"space"       => fun space/0,
                      "random"      => fun random_stream/0,
                      "race-naive"  => fun race_naive/0,
                      "race-atomic" => fun race_atomic/0}).

%% ____________________________________________________________________________
%% the unit under test: a counter of the spaces a garage has
%%
%% RETURN: #garage{}, empty, of 'Capacity' spaces.
garage(Capacity) -> #garage{capacity = Capacity}.

%% RETURN: integer, the number of spaces free now -- negative where the
%%         garage is overbooked.
free(#garage{capacity = C, occupied = O}) -> C - O.

%% RETURN: {true, Garage}, a car was admitted, if a space was free;
%%         {false, Garage}, else (the car is refused).
arrive(G) ->
    case free(G) =< 0 of
        true  -> {false, G};
        false -> {true, G#garage{occupied = G#garage.occupied + 1}}
    end.

%% RETURN: {true, Garage}, a car drove out, if one stood inside;
%%         {false, Garage}, else.
leave(#garage{occupied = 0} = G) -> {false, G};
leave(G)                         -> {true, G#garage{occupied = G#garage.occupied - 1}}.

%% RETURN: {Refused, Garage}, 'G' after 'N' cars tried to arrive, and how
%%         many of them were refused.
arrive_n(N, G) ->
    lists:foldl(fun(_, {R, Gi}) -> {Admitted, Gj} = arrive(Gi),
                                   {R + case Admitted of true -> 0; false -> 1 end, Gj}
                end, {0, G}, lists:seq(1, N)).

%% ____________________________________________________________________________
%% space -- the tested space from HOCON, walked by space_iterator
%%
%% RETURN: [{binary, list}], the dimensions of the space in 'Path', in the
%%         order written: {Name, Values}. Every fault the HOCON reader found
%%         is printed with '!!' first.
read_space(Path) ->
    {ok, Data} = file:read_file(Path),
    Parts = binary:split(Data, <<"\n">>, [global]),
    Texts = case lists:last(Parts) of <<>> -> lists:droplast(Parts); _ -> Parts end,
    Lines = [#source_line{text = T, line = I, column_offset = 0}
             || {I, T} <- lists:zip(lists:seq(1, length(Texts)), Texts)],
    {Document, Faults} = hwut_hocon:parse(Lines, filename:basename(Path)),
    [io:format("!! ~ts~n", [hwut_hocon:fault_text(F)]) || F <- Faults],
    #hocon_entry{node = #hocon_object{entry_list = Entries}} = hwut_hocon:get(<<"space">>, Document),
    [{Key, [V || #hocon_scalar{value = V} <- Items]}
     || #hocon_entry{key = Key, node = #hocon_list{item_list = Items}} <- Entries].

%% RETURN: ok; prints every case of the space as a matrix cell.
space() ->
    Here = filename:dirname(filename:absname(escript:script_name())),
    Dimensions = read_space(filename:join(Here, "garage-space.hocon")),
    [Capacities, Arrivings, Leavings] = Values = [V || {_, V} <- Dimensions],
    io:format("space: ~ts~n", [lists:join("  x  ", [[N, " ", pytext:repr(V)] || {N, V} <- Dimensions])]),
    io:format("cell: cars inside / cars refused at the gate ('!!' differs from the model)~n"),
    {Cells, MismatchN} =
        lists:foldl(
          fun({Capacity, Arriving, Leaving}, {Cells0, M}) ->
                  {Refused, G1} = arrive_n(Arriving, garage(Capacity)),
                  G2 = lists:foldl(fun(_, Gi) -> element(2, leave(Gi)) end, G1, lists:seq(1, Leaving)),
                  Admitted = min(Arriving, Capacity),
                  Expected = {Admitted - min(Leaving, Admitted), Arriving - Admitted},
                  Got      = {G2#garage.occupied, Refused},
                  Mark     = case Got == Expected of true -> "  "; false -> "!!" end,
                  Cell     = io_lib:format("~b/~b~s", [element(1, Got), Refused, Mark]),
                  {maps:update_with({Capacity, Arriving}, fun(L) -> L ++ [Cell] end, [Cell], Cells0),
                   M + case Got == Expected of true -> 0; false -> 1 end}
          end, {#{}, 0}, space_iterator:do(Values)),
    Pad = fun(Text, N) -> string:pad(lists:flatten(Text), N) end,
    [begin
         io:format("capacity ~b   ~s~n",
                   [Capacity, string:trim(lists:join("  ", [Pad(io_lib:format("leave ~b", [L]), 9)
                                                           || L <- Leavings]), trailing)]),
         [io:format("~s~n", [string:trim(io_lib:format("  arrive ~b   ~s",
                                                         [Arriving, lists:join("  ", [Pad(C, 9) || C <- maps:get({Capacity, Arriving}, Cells)])]),
                                         trailing)])
          || Arriving <- Arrivings]
     end || Capacity <- Capacities],
    io:format("cases ~b, differing from the model ((mismatches: ~b))~n",
              [map_size(Cells) * length(Leavings), MismatchN]).

%% ____________________________________________________________________________
%% random -- a deterministic stream of arrivals and departures
%%
%% RETURN: ok; prints the summary of 1000 drawn cars, model-checked.
random_stream() ->
    Step = fun(_, {S0, G, Model, Count, Histogram, MismatchN, Strip}) ->
                   {Arrives, S} = deterministic_random:coin(0.55, S0),
                   {G1, Model1, Count1, Mark} =
                       case Arrives of
                           true  -> {Admitted, Ga} = arrive(G),
                                    {Ga, min(5, Model + 1),
                                     bump(arrive, bump(refused, Count, not Admitted), true), $+};
                           false -> {Left, Gl} = leave(G),
                                    {Gl, max(0, Model - 1),
                                     bump(leave, bump(empty, Count, not Left), true), $-}
                       end,
                   Inside = G1#garage.occupied,
                   {S, G1, Model1, Count1,
                    setelement(Inside + 1, Histogram, element(Inside + 1, Histogram) + 1),
                    MismatchN + case Inside == Model1 of true -> 0; false -> 1 end,
                    [Mark | Strip]}
           end,
    {_, _, _, Count, Histogram, MismatchN, Strip} =
        lists:foldl(Step, {deterministic_random:new(4711), garage(5), 0,
                           #{arrive => 0, refused => 0, leave => 0, empty => 0},
                           list_to_tuple(lists:duplicate(6, 0)), 0, []}, lists:seq(1, 1000)),
    io:format("seed 4711, garage of 5, 1000 cars drawn: '+' arrives, '-' leaves~n"),
    io:format("first 60: ~s~n", [lists:sublist(lists:reverse(Strip), 60)]),
    io:format("arrivals ~b, refused ~b; departures ~b, from an empty garage ~b~n",
              [maps:get(K, Count) || K <- [arrive, refused, leave, empty]]),
    io:format("cars inside after each event:~n"),
    [io:format("    ~b  ~4b  ~s~n", [N, C, lists:duplicate(C div 10, $#)])
     || {N, C} <- lists:zip(lists:seq(0, 5), tuple_to_list(Histogram))],
    io:format("steps differing from the model ((mismatches: ~b))~n", [MismatchN]).

%% RETURN: map, 'Count' with 'Key' one more where 'Flag', else unchanged.
bump(Key, Count, true)  -> maps:update_with(Key, fun(N) -> N + 1 end, Count);
bump(_,   Count, false) -> Count.

%% ____________________________________________________________________________
%% race -- two gates on drawn timelines, sharing one garage
%%
%% RETURN: pid, a process holding the garage 'G' and the log of the race;
%%         it ends with the process that made it.
shared(G) ->
    Owner = self(),
    spawn(fun() -> monitor(process, Owner), serve({G, []}) end).

%% RETURN: ok, once the owner ended; serves one call at a time until then.
serve(State) ->
    receive
        {call, From, Ref, Fun} -> {Reply, State1} = Fun(State),
                                  From ! {Ref, Reply},
                                  serve(State1);
        {'DOWN', _, process, _, _} -> ok
    end.

%% RETURN: term, the 'Reply' of '{Reply, NewState} = Fun({Garage, Log})',
%%         run in the garage's process.
call(Shared, Fun) ->
    Ref = make_ref(),
    Shared ! {call, self(), Ref, Fun},
    receive {Ref, Reply} -> Reply end.

%% RETURN: ok; 'Text' is appended to the race's log.
log(Shared, Text) ->
    call(Shared, fun({G, Log}) -> {ok, {G, [lists:flatten(Text) | Log]}} end).

%% RETURN: {ok, State}, the gate after its next step at 'Tick': its first
%%         step checks (and, atomic, admits), its second admits (or, atomic,
%%         opens).
gate_fire(_Tick, #{step := Step, atomic := Atomic, name := Name, shared := Shared} = Gate) ->
    SawFree =
        if Step == 0, Atomic ->
               Admitted = call(Shared, fun({G, Log}) -> {A, G1} = arrive(G), {A, {G1, Log}} end),
               log(Shared, case Admitted of true -> [Name, " checks+admits"];
                                            false -> [Name, " refuses"] end),
               Admitted;
           Step == 0 ->
               Free = call(Shared, fun({G, _} = S) -> {free(G), S} end),
               log(Shared, io_lib:format("~s sees ~b free", [Name, Free])),
               Free > 0;
           Atomic ->
               log(Shared, case maps:get(saw_free, Gate) of true  -> [Name, " opens"];
                                                            false -> [Name, " stays shut"] end),
               maps:get(saw_free, Gate);
           true ->
               case maps:get(saw_free, Gate) of
                   true  -> call(Shared, fun({G, Log}) ->              % the naive admit
                                                 {ok, {G#garage{occupied = G#garage.occupied + 1}, Log}}
                                         end),
                            log(Shared, [Name, " admits"]);
                   false -> log(Shared, [Name, " refuses"])
               end,
               maps:get(saw_free, Gate)
        end,
    {ok, Gate#{step := Step + 1, saw_free := SawFree}}.

%% RETURN: [{string, string}], every pair of timelines in four ticks in
%%         which each of two gates fires twice, never at the same tick:
%%         gate A's and gate B's.
interleaving_list() ->
    Line = fun(X, Y) -> [case T == X orelse T == Y of true -> $1; false -> $\s end
                         || T <- lists:seq(0, 3)] end,
    [{Line(A1, A2), Line(B1, B2)}
     || {A1, A2, B1, B2} <- space_iterator:do(lists:duplicate(4, lists:seq(0, 3))),
        A1 < A2, B1 < B2, length(lists:usort([A1, A2, B1, B2])) == 4].

%% RETURN: ok; plays every interleaving of two gates at one space.
race(Atomic) ->
    io:format("one free space, two gates, one car at each; timelines: a digit fires~n"),
    io:format("    gate A  gate B  what happens                                    inside~n"),
    OverbookedN = lists:sum(
      [begin
           Shared = shared(garage(1)),
           Gate = fun(Name, Timeline) ->
                          deterministic_timeline:trigger(
                            #{fire => fun gate_fire/2}, Timeline, Name,
                            #{name => Name, atomic => Atomic, shared => Shared,
                              step => 0, saw_free => false})
                  end,
           ok = deterministic_timeline:run(deterministic_timeline:dispatcher(
                                             [Gate("A", TimelineA), Gate("B", TimelineB)])),
           {G, Log} = call(Shared, fun(S) -> {S, S} end),
           Over = G#garage.occupied > G#garage.capacity,
           Text = io_lib:format("    \"~s\"  \"~s\"  ~s  ~b ~s",
                                [TimelineA, TimelineB,
                                 string:pad(lists:join(", ", lists:reverse(Log)), 46),
                                 G#garage.occupied, case Over of true -> "!!"; false -> "  " end]),
           io:format("~s~n", [string:trim(Text, trailing)]),
           case Over of true -> 1; false -> 0 end
       end || {TimelineA, TimelineB} <- interleaving_list()]),
    io:format("interleavings overbooking the garage ((overbooked: ~b)) of ~b~n",
              [OverbookedN, length(interleaving_list())]).

%% RETURN: ok; the gates check, then admit, in two steps.
race_naive() -> race(false).

%% RETURN: ok; the gates check and admit in one step.
race_atomic() -> race(true).
