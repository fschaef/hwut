%% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%%_____________________________________________________________________________
%%
%% PURPOSE: A RANDOM STREAM THAT IS THE SAME EVERYWHERE -- the port of
%%          'python/deterministic_random.py': Park-Miller MINSTD, 'state =
%%          48271 * state mod (2^31 - 1)', drawn seed for seed as Python
%%          draws it.
%%
%%     S0        = deterministic_random:new(16#42),
%%     {N, S1}   = deterministic_random:next_int(0, 9, S0),
%%     {F, S2}   = deterministic_random:next_float(S1),
%%     {X, S3}   = deterministic_random:select([a, b, c], S2),
%%     M0        = deterministic_random:marker(),
%%     {Y, M1, S4} = deterministic_random:select_unchosen([a, b, c], M0, S3)
%%
%% THE STREAM IS A VALUE, NOT AN OBJECT: every draw takes the stream and
%% returns the draw with the stream that follows -- the convention of OTP's
%% own 'rand:uniform_s(N, State) -> {X, NewState}', the state LAST. A stream
%% kept is a stream that can be drawn from again, at the same place: replay
%% is a variable, not a reseed. A SelectionMarker is a value too.
%%
%% A MARKER KEYS ON THE CANDIDATE'S VALUE. Erlang terms have no identity, so
%% two equal candidates are one alternative; a caller that wants two equal
%% ones kept apart tags them ({make_ref(), X}). A fresh container of equal
%% candidates is the same pool -- which is what Python gets from identity
%% where its candidates are long-lived objects.
%%_____________________________________________________________________________
-module(deterministic_random).
-export([new/0, new/1, next_int/3, next_float/1, coin/2, select/2,
         select_unchosen/3, marker/0, marker_reset/1, gauss/3, gauss/5,
         gauss_int/3, gauss_int/5, choice/2, sample_indices/3, sample/3]).

-record(deterministic_stream, {state :: non_neg_integer()}).
-record(selection_marker,     {chosen = #{} :: map()}).

%% RETURN: stream, seeded with Python's default 0x42.
new() -> new(16#42).

%% RETURN: stream, seeded with 'Seed' (its low 31 bits, as Python's).
new(Seed) when is_integer(Seed) -> #deterministic_stream{state = Seed band 16#7FFFFFFF}.

%% RETURN: {Int, Stream}, an integer in [Min, Max] and the stream after the
%%         draw -- one step of the generator also where Min == Max (the
%%         bound is returned, the step taken all the same).
next_int(Min, Max, #deterministic_stream{state = State}) ->
    Next = (48271 * State) rem 2147483647,
    S    = #deterministic_stream{state = Next},
    if Min == Max -> {Min, S};
       true       -> {Min + Next rem (Max - Min + 1), S}
    end.

%% RETURN: {Float, Stream}, a float in [0.0, 1.0): 'next_int(0, 1000000)'
%%         divided by 1000001.0 -- one of 1000001 values.
next_float(S0) ->
    {N, S} = next_int(0, 1000000, S0),
    {N / 1000001.0, S}.

%% RETURN: {true, Stream} with 'Probability', {false, Stream} else.
%%         THE FLOOR (TW-1): the probability is resolved in steps of
%%         1/1000001 -- any 0 < p <= 1/1000001 comes out as 1/1000001.
coin(Probability, S0) ->
    {F, S} = next_float(S0),
    {F < Probability, S}.

%% RETURN: {Candidate, Stream}, a uniformly drawn element of the list or
%%         tuple 'Candidates' -- of a binary (a str), one of its characters. Stateless: the same stream and the same
%%         candidates always give the same element.
select(Candidates, S0) when is_tuple(Candidates) ->
    select(tuple_to_list(Candidates), S0);
select(Candidates, S0) when is_binary(Candidates) ->
    select([<<C/utf8>> || <<C/utf8>> <= Candidates], S0);
select(Candidates, S0) when is_list(Candidates) ->
    {I, S} = next_int(0, length(Candidates) - 1, S0),
    {lists:nth(I + 1, Candidates), S}.

%% RETURN: {Element, Stream}, as 'select' -- Python's 'choice'.
choice(Sequence, S0) -> select(Sequence, S0).

%% RETURN: marker, with nothing chosen yet.
marker() -> #selection_marker{}.

%% RETURN: marker, every chosen candidate forgotten; the next cycle restarts.
marker_reset(#selection_marker{}) -> #selection_marker{}.

%% RETURN: {Candidate, Marker, Stream}, a candidate drawn uniformly among
%%         those 'Marker' has not seen, the marker that has seen it too, and
%%         the stream after the draw. Where every candidate was seen, the
%%         marker is reset and the draw is from the full pool.
select_unchosen(Candidates, Marker, S0) when is_tuple(Candidates) ->
    select_unchosen(tuple_to_list(Candidates), Marker, S0);
select_unchosen(Candidates, #selection_marker{chosen = Chosen} = Marker0, S0) ->
    {Pool, Marker} = case [C || C <- Candidates, not is_map_key(C, Chosen)] of
                         []       -> {Candidates, marker_reset(Marker0)};
                         Unchosen -> {Unchosen, Marker0}
                     end,
    {Choice, S} = select(Pool, S0),
    #selection_marker{chosen = Seen} = Marker,
    {Choice, Marker#selection_marker{chosen = Seen#{Choice => true}}, S}.

%% RETURN: {Float, Stream}, a draw of the normal distribution (Mu, Sigma)
%%         by the Box-Muller transform. 'math' is the platform's libm, as
%%         Python's 'math' is (S3: not bit-portable across platforms).
gauss(Mu, Sigma, S0) ->
    {U1, S1} = next_float(S0),
    {U2, S2} = next_float(S1),
    Z0 = math:sqrt(-2.0 * math:log(U1 + 1.0e-9)) * math:cos(2.0 * math:pi() * U2),
    {Z0 * Sigma + Mu, S2}.

%% RETURN: {Float, Stream}, 'gauss' clipped to [Lower, Upper] (numbers).
gauss(Mu, Sigma, Lower, Upper, S0) ->
    {X, S} = gauss(Mu, Sigma, S0),
    if X < Lower -> {Lower, S};
       X > Upper -> {Upper, S};
       true      -> {X, S}
    end.

%% RETURN: {Int, Stream}, 'gauss' rounded to the nearest integer.
gauss_int(Mu, Sigma, S0) ->
    {X, S} = gauss(Mu, Sigma, S0),
    {round_half_even(X), S}.

%% RETURN: {Int, Stream}, the clipped 'gauss' rounded to the nearest integer.
gauss_int(Mu, Sigma, Lower, Upper, S0) ->
    {X, S} = gauss(Mu, Sigma, float(Lower), float(Upper), S0),
    {round_half_even(X), S}.

%% RETURN: integer, 'X' rounded as Python's 'round' does: to the nearest,
%%         a half to the EVEN neighbour (Erlang's 'round' goes away from 0).
round_half_even(X) ->
    F = floor(X),
    D = X - F,
    if D > 0.5  -> F + 1;
       D < 0.5  -> F;
       F rem 2 == 0 -> F;
       true     -> F + 1
    end.

%% RETURN: {[Int], Stream}, 'K' distinct indices of 0 .. PopulationN-1, in
%%         the order a Fisher-Yates walk swaps them to the front.
sample_indices(PopulationN, K, S0) when PopulationN >= K ->
    Index0 = maps:from_list([{I, I} || I <- lists:seq(0, PopulationN - 1)]),
    {Result, _, S} =
        lists:foldl(fun(I, {Acc, Index, Si}) ->
                            {J, Sj} = next_int(I, PopulationN - 1, Si),
                            #{I := At, J := Other} = Index,
                            {[Other | Acc], Index#{I => Other, J => At}, Sj}
                    end, {[], Index0, S0}, lists:seq(0, K - 1)),
    {lists:reverse(Result), S}.

%% RETURN: {[Element], Stream}, 'N' distinct elements of the list
%%         'Population', drawn by 'sample_indices'.
sample(Population, N, S0) when length(Population) >= N ->
    {Index, S} = sample_indices(length(Population), N, S0),
    Tuple = list_to_tuple(Population),
    {[element(I + 1, Tuple) || I <- Index], S}.
