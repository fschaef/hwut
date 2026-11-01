/*  SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
    ___________________________________________________________________________

    PURPOSE: A random stream that is the same everywhere -- the port of
             'python/deterministic_random.py': Park-Miller MINSTD,
             'state = 48271 * state mod (2^31 - 1)', integer arithmetic.

    THE STREAM IS A VALUE, THREADED: 'stream(State)'. Every draw takes the
    stream before and gives the stream after as its LAST TWO arguments -- the
    shape of a DCG's hidden pair, so draws compose as a grammar body does:

        dr_stream_new(0x42, S0),
        call_dcg(( dr_next_int(0, 9, A), dr_next_int(0, 9, B) ), S0, S) ...

    or, plainer, the pair written out:

        dr_next_int(0, 9, A, S0, S1), dr_next_int(0, 9, B, S1, S2)

    and inside the test's own DCG rules, 'dr_next_int(0, 9, A)' alone. Nothing
    is global: two streams never meet, and a draw that is backtracked over is
    undone -- the stream after it was never made.

    A SELECTION MARKER is a value too: 'marker(Chosen)', the candidates seen
    at one selection site. Prolog has no object identity -- a term IS its
    value -- so two equal candidates are one (as in the Perl and bash ports).
    ___________________________________________________________________________
*/
:- module(deterministic_random,
          [ dr_stream_new/1,            % -Stream                (seed 0x42)
            dr_stream_new/2,            % +Seed, -Stream
            dr_next_int//3,             % +Min, +Max, -Int
            dr_next_float//1,           % -Float
            dr_coin//2,                 % +Probability, -Bool
            dr_select//2,               % +Candidates, -Candidate
            dr_select_unchosen//4,      % +Candidates, +Marker0, -Marker, -Candidate
            dr_marker_new/1,            % -Marker
            dr_marker_reset/2,          % +Marker0, -Marker
            dr_gauss//3,                % +Mu, +Sigma, -Float
            dr_gauss//5,                % +Mu, +Sigma, +Lower, +Upper, -Float
            dr_gauss_int//3,            % +Mu, +Sigma, -Int
            dr_gauss_int//5,            % +Mu, +Sigma, +Lower, +Upper, -Int
            dr_choice//2,               % +List, -Element
            dr_sample_indices//3,       % +PopulationN, +K, -Indices
            dr_sample//3                % +Population, +N, -Sample
          ]).
:- encoding(utf8).
:- use_module('hwut_pytext.pro').

%!  dr_stream_new(-Stream) is det.
%!  dr_stream_new(+Seed, -Stream) is det.
%
%   RETURN: Stream, 'stream(State)' at 'Seed' (0x42 where none is given),
%           its state the seed's low 31 bits.
dr_stream_new(S) :- dr_stream_new(0x42, S).
dr_stream_new(Seed, stream(State)) :- State is Seed /\ 0x7FFFFFFF.

%!  dr_next_int(+Min, +Max, -Int)// is det.
%
%   RETURN: Int, uniformly in [Min, Max]: Min + state mod (Max - Min + 1) of
%           the next state; 'Min' itself where Min = Max (a state is drawn
%           all the same).
dr_next_int(Min, Max, V, stream(S0), stream(S)) :-
    S is (48271 * S0) mod 2147483647,
    (   Min =:= Max -> V = Min
    ;   V is Min + S mod (Max - Min + 1)
    ).

%!  dr_next_float(-Float)// is det.
%
%   RETURN: Float, in [0.0, 1.0): next_int(0, 1000000) / 1000001.0.
dr_next_float(F) --> dr_next_int(0, 1000000, I), { F is I / 1000001.0 }.

%!  dr_coin(+Probability, -Bool)// is det.
%
%   RETURN: Bool 'true' with probability 'Probability', 'false' else -- a
%           value, not success: a coin that FAILED would take the draw back.
%           THE FLOOR (TW-1): resolved in steps of 1/1000001.
dr_coin(P, B) --> dr_next_float(F), { F < P -> B = true ; B = false }.

%!  dr_select(+Candidates, -Candidate)// is det.
%
%   RETURN: Candidate, a uniformly random element of the list 'Candidates'
%           (or a one-character string of the string 'Candidates').
%           Stateless: the same stream and the same candidates give the same.
dr_select(Cs, X) --> { candidate_list(Cs, L), length(L, N), Max is N - 1 },
    dr_next_int(0, Max, I), { nth0(I, L, X) }.

candidate_list(Cs, L) :- string(Cs), !, string_chars(Cs, Chars), maplist([C, S]>>string_chars(S, [C]), Chars, L).
candidate_list(L, L).

%!  dr_marker_new(-Marker) is det.
%
%   RETURN: Marker, 'marker([])', nothing chosen yet.
dr_marker_new(marker([])).

%!  dr_marker_reset(+Marker0, -Marker) is det.
%
%   RETURN: Marker, with every chosen candidate forgotten: the next cycle
%           restarts.
dr_marker_reset(_, marker([])).

%!  dr_select_unchosen(+Candidates, +Marker0, -Marker, -Candidate)// is det.
%
%   RETURN: Candidate, uniformly among the candidates 'Marker0' has not seen;
%           Marker, 'Marker0' with it recorded. Where every candidate was
%           seen, the marker is reset first and the whole list drawn from.
dr_select_unchosen(Cs, marker(Seen0), marker([X|Seen]), X) -->
    { candidate_list(Cs, L),
      exclude([C]>>memberchk(C, Seen0), L, Unchosen0),
      (   Unchosen0 == [] -> Unchosen = L, Seen = [] ; Unchosen = Unchosen0, Seen = Seen0 ),
      length(Unchosen, N), Max is N - 1 },
    dr_next_int(0, Max, I), { nth0(I, Unchosen, X) }.

%!  dr_gauss(+Mu, +Sigma, -Float)// is det.
%!  dr_gauss(+Mu, +Sigma, +Lower, +Upper, -Float)// is det.
%
%   RETURN: Float, a draw of the normal distribution (Mu, Sigma) by the
%           Box-Muller transform, clipped to [Lower, Upper] (unbounded where
%           not given). NOT BIT-PORTABLE (S3): log, cos and sqrt are the
%           platform's libm -- the uniform draws are exact.
dr_gauss(Mu, Sigma, X) --> dr_gauss(Mu, Sigma, -inf, inf, X).
dr_gauss(Mu, Sigma, Lower, Upper, X) -->
    dr_next_float(F1), dr_next_float(U2),
    {   U1 is F1 + 1.0e-9,
        Z0 is sqrt(-2.0 * log(U1)) * cos(2.0 * pi * U2),
        R  is Z0 * Sigma + Mu,
        (   R < Lower -> X is float(Lower)
        ;   R > Upper -> X is float(Upper)
        ;   X = R
        )
    }.

%!  dr_gauss_int(+Mu, +Sigma, -Int)// is det.
%!  dr_gauss_int(+Mu, +Sigma, +Lower, +Upper, -Int)// is det.
%
%   RETURN: Int, 'dr_gauss' rounded to the nearest integer, a half to the
%           even one (Python's 'round').
dr_gauss_int(Mu, Sigma, I) --> dr_gauss_int(Mu, Sigma, -inf, inf, I).
dr_gauss_int(Mu, Sigma, Lower, Upper, I) -->
    dr_gauss(Mu, Sigma, Lower, Upper, X), { py_round(X, I) }.

%!  dr_choice(+List, -Element)// is det.
%
%   RETURN: Element, a uniformly random element of 'List'.
dr_choice(L, X) --> dr_select(L, X).

%!  dr_sample_indices(+PopulationN, +K, -Indices)// is det.
%
%   RETURN: Indices, K distinct indices of 0..PopulationN-1, drawn by
%           Fisher-Yates: at step i the index at i is swapped with one drawn
%           from [i, PopulationN-1] and taken.
dr_sample_indices(N, K, Result) -->
    { N >= K, Last is N - 1, numlist(0, Last, Pool0), Pool =.. [pool|Pool0] },
    sample_steps(0, K, Last, Pool, Result).

sample_steps(I, K, _, _, []) --> { I >= K }, !.
sample_steps(I, K, Last, Pool, [X|Xs]) -->
    dr_next_int(I, Last, J),
    {   A is I + 1, B is J + 1,
        arg(A, Pool, VI), arg(B, Pool, VJ),
        setarg(A, Pool, VJ), setarg(B, Pool, VI),
        X = VJ, I1 is I + 1
    },
    sample_steps(I1, K, Last, Pool, Xs).

%!  dr_sample(+Population, +N, -Sample)// is det.
%
%   RETURN: Sample, N distinct elements of the list 'Population', in the
%           order 'dr_sample_indices' draws their indices.
dr_sample(Pop, N, Sample) -->
    { length(Pop, PN) }, dr_sample_indices(PN, N, Is),
    { maplist([I, X]>>nth0(I, Pop, X), Is, Sample) }.
