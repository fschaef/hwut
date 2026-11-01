%% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%%_____________________________________________________________________________
%%
%% PURPOSE: EVERY COMBINATION OF A PARAMETER BASIS -- the port of
%%          'python/space_iterator.py': the cartesian product, the RIGHTMOST
%%          dimension changing fastest.
%%
%%     [{0, otto, 1}, {0, otto, 2}, {0, heinz, 1} | _] =
%%         space_iterator:do([[0, 2, 4], [otto, heinz], [1, 2]])
%%
%%     space_iterator:fold(fun({X, Name, N}, Acc) -> ... end, Acc0, Basis)
%%
%% NO GENERATOR: a fold over the dimensions, nested outer first, so the
%% rightmost changes fastest -- the order of a list comprehension's
%% generators. 'do' returns the points as a list; 'fold' walks them one by
%% one without building it -- Python's lazy 'yield', for a space too large
%% to hold.
%%
%% THE EDGES (Python's NOTES): an empty basis yields ONE point, the empty
%% tuple; a basis with an empty dimension yields nothing.
%%_____________________________________________________________________________
-module(space_iterator).
-export([do/1, fold/3]).

%% RETURN: [tuple()], every point of the basis -- a list of dimensions, each
%%         a list of values -- one value of each dimension in basis order,
%%         the rightmost dimension changing fastest; [{}] for the empty
%%         basis, [] where a dimension is empty.
do(Basis) -> lists:reverse(fold(fun(Point, Acc) -> [Point | Acc] end, [], Basis)).

%% RETURN: term, 'Acc0' passed through 'Fun(Point, Acc)' for every point of
%%         'Basis' in the order 'do' lists them.
fold(Fun, Acc0, Basis) -> fold(Fun, Acc0, Basis, []).

%% RETURN: term, the fold over the points that begin with the values of
%%         'Prefix' (reversed) and go on through the dimensions 'Rest'.
fold(Fun, Acc, [], Prefix) ->
    Fun(list_to_tuple(lists:reverse(Prefix)), Acc);
fold(Fun, Acc0, [Dimension | Rest], Prefix) ->
    lists:foldl(fun(Value, Acc) -> fold(Fun, Acc, Rest, [Value | Prefix]) end,
                Acc0, Dimension).
