%% @hwut {
%%     title      = "space_iterator: every combination of a parameter basis"
%%     choices {
%%         product { features = ["erlang-space"] }
%%         edges   { features = ["erlang-space"] }
%%     }
%%     interactive = true
%% }
%%
%% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%%_____________________________________________________________________________
%%
%% PURPOSE: The Erlang port of 'python/TEST/test-space-iterator.py', choice
%%          for choice, held against its GOOD files by '.link'.
%%_____________________________________________________________________________
-mode(compile).
-include("../hwut_boot.hrl").

main(Argv) ->
    hwut_boot(),
    hwut_runner:run(Argv, "space_iterator: every combination of a parameter basis",
                    #{"product" => fun run_product/0,
                      "edges"   => fun run_edges/0}).

%% RETURN: ok; the section heading is printed.
banner(Label) -> io:format("~n--- ~ts ---~n", [Label]).

%% RETURN: ok; every point of 'Basis' is printed, one per line, then the
%%         count.
points(Basis) ->
    N = space_iterator:fold(fun(Point, K) ->
                                    Values = [pytext:str(V) || V <- tuple_to_list(Point)],
                                    io:format("  (~ts)~n", [pytext:join(<<", ">>, Values)]),
                                    K + 1
                            end, 0, Basis),
    io:format("  ~b point(s)~n", [N]).

%% RETURN: ok; three dimensions, the rightmost changing fastest.
run_product() ->
    banner("[0, 2, 4] x [otto, heinz] x [1, 2] -- 3 * 2 * 2 points"),
    points([[0, 2, 4], [<<"otto">>, <<"heinz">>], [1, 2]]).

%% RETURN: ok; the empty basis, an empty dimension, one dimension.
run_edges() ->
    banner("an EMPTY basis -- one point, the empty one"),
    points([]),
    banner("a basis with an EMPTY dimension -- nothing"),
    points([[1, 2], [], [3]]),
    banner("ONE dimension -- its values one by one"),
    points([[<<"a">>, <<"b">>, <<"c">>]]).
