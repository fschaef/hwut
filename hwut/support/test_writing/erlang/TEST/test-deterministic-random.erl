%% @hwut {
%%     title      = "DeterministicStream RNG and SelectionMarker spread"
%%     choices {
%%         gauss      { features = ["erlang-random"] }
%%         primitives { features = ["erlang-random"] }
%%         ranges     { features = ["erlang-random"] }
%%         sample     { features = ["erlang-random"] }
%%         seed_sweep { features = ["erlang-random"] }
%%         select     { features = ["erlang-random"] }
%%         unchosen   { features = ["erlang-random"] }
%%     }
%%     interactive = true
%% }
%%
%% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%%_____________________________________________________________________________
%%
%% PURPOSE: The Erlang port of 'python/TEST/test-deterministic-random.py',
%%          choice for choice, held against its GOOD files by '.link'. The
%%          stream is a value threaded through each draw ('lists:mapfoldl').
%%_____________________________________________________________________________
-mode(compile).
-include("../hwut_boot.hrl").

-define(SEED, 16#42).
-define(TOLERANCE_REGION_BEGIN, "##! table numeric={1:1e-12}").
-define(REGION_END, "####").

main(Argv) ->
    hwut_boot(),
    hwut_runner:run(Argv, "DeterministicStream RNG and SelectionMarker spread",
                    #{"primitives" => fun run_primitives/0,
                      "ranges"     => fun run_ranges/0,
                      "gauss"      => fun run_gauss/0,
                      "sample"     => fun run_sample/0,
                      "select"     => fun run_select/0,
                      "unchosen"   => fun run_unchosen/0,
                      "seed_sweep" => fun run_seed_sweep/0}).

%% RETURN: ok; the section heading is printed.
banner(Label) -> io:format("~n--- ~ts ---~n", [Label]).

%% RETURN: [term], 'N' draws by 'Draw(Stream) -> {Value, Stream}' from a
%%         fresh stream of the seed.
draws(N, Draw) ->
    {List, _} = lists:mapfoldl(fun(_, S) -> Draw(S) end,
                               deterministic_random:new(?SEED), lists:seq(1, N)),
    List.

%% RETURN: ok; the words are printed on one line, separated by blanks.
line(Words) -> io:format("~ts~n", [lists:join(" ", Words)]).

%% RETURN: integer; every value printed as '[NN] <Show(V)>'.
indexed(Values, Show) ->
    lists:foldl(fun(V, I) -> io:format("[~2..0b] ~ts~n", [I, Show(V)]), I + 1 end, 0, Values).

%% RETURN: ok; the bare generator: next_int, next_float, coin.
run_primitives() ->
    banner("next_int(0, 1000000) -- first 20"),
    indexed(draws(20, fun(S) -> deterministic_random:next_int(0, 1000000, S) end), fun integer_to_list/1),
    banner("next_float -- first 10 (full precision)"),
    indexed(draws(10, fun deterministic_random:next_float/1), fun pytext:repr/1),
    banner("coin(0.5) -- 40 draws"),
    line([if Coin -> "T"; true -> "F" end
          || Coin <- draws(40, fun(S) -> deterministic_random:coin(0.5, S) end)]).

%% RETURN: ok; next_int over small and degenerate ranges.
run_ranges() ->
    banner("next_int(0, 9) -- 30 draws"),
    line([integer_to_list(N) || N <- draws(30, fun(S) -> deterministic_random:next_int(0, 9, S) end)]),
    banner("next_int(5, 5) -- degenerate range returns the bound"),
    line([integer_to_list(N) || N <- draws(5, fun(S) -> deterministic_random:next_int(5, 5, S) end)]),
    banner("next_int(-3, 3) -- spanning zero"),
    line([io_lib:format("~s~b", [if N < 0 -> "-"; true -> "+" end, abs(N)])
          || N <- draws(20, fun(S) -> deterministic_random:next_int(-3, 3, S) end)]).

%% RETURN: ok; the libm path: gauss, clamped gauss, gauss_int.
run_gauss() ->
    banner("gauss(0, 1) -- 10 draws (full precision)"),
    io:format("~s~n", [?TOLERANCE_REGION_BEGIN]),
    indexed(draws(10, fun(S) -> deterministic_random:gauss(0.0, 1.0, S) end), fun pytext:repr/1),
    io:format("~s~n", [?REGION_END]),
    banner("gauss(0, 1) clamped to [-1, 1]"),
    io:format("~s~n", [?TOLERANCE_REGION_BEGIN]),
    indexed(draws(10, fun(S) -> deterministic_random:gauss(0.0, 1.0, -1.0, 1.0, S) end), fun pytext:repr/1),
    io:format("~s~n", [?REGION_END]),
    banner("gauss_int(100, 15) -- 20 draws"),
    line([integer_to_list(N) || N <- draws(20, fun(S) -> deterministic_random:gauss_int(100.0, 15.0, S) end)]).

%% RETURN: ok; sample_indices (Fisher-Yates) and sample over a list.
run_sample() ->
    banner("sample_indices(10, 10) -- full permutation"),
    io:format("~ts~n", [pytext:repr(first(deterministic_random:sample_indices(10, 10, new())))]),
    banner("sample_indices(20, 5) -- partial draw"),
    io:format("~ts~n", [pytext:repr(first(deterministic_random:sample_indices(20, 5, new())))]),
    banner("choice from a list -- 20 draws"),
    Pool = [<<"alpha">>, <<"beta">>, <<"gamma">>, <<"delta">>, <<"epsilon">>],
    line(draws(20, fun(S) -> deterministic_random:choice(Pool, S) end)),
    banner("sample(list, 4) -- unique elements"),
    Letters = [<<C>> || C <- "ABCDEFGH"],
    io:format("~ts~n", [pytext:repr(first(deterministic_random:sample(Letters, 4, new())))]).

%% RETURN: stream, fresh, of the seed.
new() -> deterministic_random:new(?SEED).

%% RETURN: term, the draw of a {Value, Stream} pair.
first({Value, _Stream}) -> Value.

%% RETURN: ok; stateless select: the same state and pool, the same element.
run_select() ->
    banner("select over a list -- 20 draws"),
    line(draws(20, fun(S) -> deterministic_random:select([<<"a">>, <<"b">>, <<"c">>, <<"d">>], S) end)),
    banner("select over a tuple -- 12 draws"),
    line(draws(12, fun(S) -> deterministic_random:select({<<"p">>, <<"q">>, <<"r">>}, S) end)).

%% RETURN: {[Candidate], Marker, Stream}, 'N' unchosen draws, the I-th from
%%         the pool 'Pools(I)'.
unchosen(N, Pools, Marker0, S0) ->
    {Chosen, {Marker, S}} =
        lists:mapfoldl(fun(I, {M, S1}) ->
                               {C, M1, S2} = deterministic_random:select_unchosen(Pools(I), M, S1),
                               {C, {M1, S2}}
                       end, {Marker0, S0}, lists:seq(1, N)),
    {Chosen, Marker, S}.

%% RETURN: ok; select_unchosen's spread keys on the candidate, not on its
%%         container: a clean cycle, the same over fresh containers, coherent
%%         over differing sub-pools, restarted by a reset.
run_unchosen() ->
    Abcd = fun(_) -> [<<"a">>, <<"b">>, <<"c">>, <<"d">>] end,
    banner("stable pool -- three full cycles of 4 elements"),
    {Stable, _, _} = unchosen(12, Abcd, deterministic_random:marker(), new()),
    line(Stable),
    banner("FRESH container each call -- identical to the stable pool above"),
    {Fresh, _, _} = unchosen(12, fun(_) -> [<<"a">>, <<"b">>, <<"c">>, <<"d">>] end,
                             deterministic_random:marker(), new()),
    line(Fresh),
    banner("sub-pool coherence -- draw from [a,b] then the full [a,b,c,d]"),
    {First, M1, S1} = deterministic_random:select_unchosen([<<"a">>, <<"b">>], deterministic_random:marker(), new()),
    {Rest, _, _} = unchosen(3, Abcd, M1, S1),
    io:format("first(from sub): ~ts  then(from full): ~ts~n", [First, lists:join(" ", Rest)]),
    banner("reset() restarts the cycle"),
    {Before, M2, S2} = unchosen(4, Abcd, deterministic_random:marker(), new()),
    {After, _, _} = unchosen(4, Abcd, deterministic_random:marker_reset(M2), S2),
    io:format("before reset: ~ts~n", [lists:join(" ", Before)]),
    io:format("after  reset: ~ts~n", [lists:join(" ", After)]).

%% RETURN: list; the first next_int per seed 0..15 is printed.
run_seed_sweep() ->
    banner("first next_int(0, 1000000) per seed 0..15"),
    [io:format("seed=~2b -> ~b~n", [Seed, first(deterministic_random:next_int(0, 1000000, deterministic_random:new(Seed)))])
     || Seed <- lists:seq(0, 15)].
