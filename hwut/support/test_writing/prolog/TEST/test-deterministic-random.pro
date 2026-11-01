% @hwut {
%     title      = "DeterministicStream RNG and SelectionMarker spread"
%     choices {
%         gauss      { features = ["prolog-random"] }
%         primitives { features = ["prolog-random"] }
%         ranges     { features = ["prolog-random"] }
%         sample     { features = ["prolog-random"] }
%         seed_sweep { features = ["prolog-random"] }
%         select     { features = ["prolog-random"] }
%         unchosen   { features = ["prolog-random"] }
%     }
%     interactive = true
% }
%
% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%______________________________________________________________________________
%
% PURPOSE: The Prolog port of 'python/TEST/test-deterministic-random.py',
%          choice for choice, held against its GOOD files by '.link': the two
%          modules owe the same stream, byte for byte. The stream is THREADED
%          -- every sequence of draws below is a DCG body over it.
%______________________________________________________________________________
:- encoding(utf8).
:- use_module('../hwut_runner.pro').
:- use_module('../hwut_pytext.pro').
:- use_module('../deterministic_random.pro').
:- initialization(main, main).

seed(0x42).

tolerance_region_begin("##! table numeric={1:1e-12}").
region_end("####").

banner(Label) :- format("~n--- ~w ---~n", [Label]).

%   draws(+N, :Draw, -Values)//
%   RETURN: 'Draw' N times, its values in order.
draws(0, _, []) --> !.
draws(N, Draw, [X|Xs]) --> call(Draw, X), { N1 is N - 1 }, draws(N1, Draw, Xs).

fresh(S) :- seed(Seed), dr_stream_new(Seed, S).

%   on_fresh(:Body)
%   RETURN: 'Body' -- a DCG body -- over a fresh stream at SEED.
on_fresh(Body) :- fresh(S), call_dcg(Body, S, _).

joined(Xs, Sep) :- maplist(py_str, Xs, Ts), atomic_list_concat(Ts, Sep, A), format("~w~n", [A]).

numbered(Xs, Format) :-
    forall(nth0(I, Xs, X), ( py_repr(X, T), format(Format, [I, T]) )).

run_primitives :-
    banner("next_int(0, 1000000) -- first 20"),
    on_fresh(draws(20, dr_next_int(0, 1000000), A)),
    numbered(A, "[~|~`0t~d~2+] ~w~n"),
    banner("next_float -- first 10 (full precision)"),
    on_fresh(draws(10, dr_next_float, B)),
    numbered(B, "[~|~`0t~d~2+] ~w~n"),
    banner("coin(0.5) -- 40 draws"),
    on_fresh(draws(40, dr_coin(0.5), C)),
    maplist([Bool, T]>>( Bool == true -> T = 'T' ; T = 'F' ), C, Ts),
    joined(Ts, ' ').

run_ranges :-
    banner("next_int(0, 9) -- 30 draws"),
    on_fresh(draws(30, dr_next_int(0, 9), A)), joined(A, ' '),
    banner("next_int(5, 5) -- degenerate range returns the bound"),
    on_fresh(draws(5, dr_next_int(5, 5), B)), joined(B, ' '),
    banner("next_int(-3, 3) -- spanning zero"),
    on_fresh(draws(20, dr_next_int(-3, 3), C)),
    maplist(py_signed, C, Cs), joined(Cs, ' ').

run_gauss :-
    tolerance_region_begin(Begin), region_end(End),
    banner("gauss(0, 1) -- 10 draws (full precision)"),
    on_fresh(draws(10, dr_gauss(0.0, 1.0), A)),
    format("~w~n", [Begin]), numbered(A, "[~|~`0t~d~2+] ~w~n"), format("~w~n", [End]),
    banner("gauss(0, 1) clamped to [-1, 1]"),
    on_fresh(draws(10, dr_gauss(0.0, 1.0, -1.0, 1.0), B)),
    format("~w~n", [Begin]), numbered(B, "[~|~`0t~d~2+] ~w~n"), format("~w~n", [End]),
    banner("gauss_int(100, 15) -- 20 draws"),
    on_fresh(draws(20, dr_gauss_int(100.0, 15.0), C)), joined(C, ' ').

run_sample :-
    banner("sample_indices(10, 10) -- full permutation"),
    on_fresh(dr_sample_indices(10, 10, A)), py_print(A),
    banner("sample_indices(20, 5) -- partial draw"),
    on_fresh(dr_sample_indices(20, 5, B)), py_print(B),
    banner("choice from a list -- 20 draws"),
    on_fresh(draws(20, dr_choice([alpha, beta, gamma, delta, epsilon]), C)), joined(C, ' '),
    banner("sample(list, 4) -- unique elements"),
    string_chars("ABCDEFGH", Chars),
    on_fresh(dr_sample(Chars, 4, D)), py_print(D).

run_select :-
    banner("select over a list -- 20 draws"),
    on_fresh(draws(20, dr_select([a, b, c, d]), A)), joined(A, ' '),
    banner("select over a tuple -- 12 draws"),
    on_fresh(draws(12, dr_select([p, q, r]), B)), joined(B, ' ').

%   unchosen(+N, +Pool, +Marker0, -Marker, -Picks)//
%   RETURN: N picks from 'Pool',
%           the marker threaded beside the stream.
unchosen(0, _, M, M, []) --> !.
unchosen(N, Pool, M0, M, [X|Xs]) -->
    dr_select_unchosen(Pool, M0, M1, X), { N1 is N - 1 }, unchosen(N1, Pool, M1, M, Xs).

%   unchosen_fresh(+N, +Marker0, -Marker, -Picks)//
%   RETURN: as 'unchosen', the pool
%           BUILT AGAIN for every pick -- a new list each time.
unchosen_fresh(0, M, M, []) --> !.
unchosen_fresh(N, M0, M, [X|Xs]) -->
    { atom_chars(abcd, Fresh) },
    dr_select_unchosen(Fresh, M0, M1, X), { N1 is N - 1 }, unchosen_fresh(N1, M1, M, Xs).

run_unchosen :-
    banner("stable pool -- three full cycles of 4 elements"),
    dr_marker_new(M0),
    on_fresh(unchosen(12, [a, b, c, d], M0, _, A)), joined(A, ' '),
    banner("FRESH container each call -- identical to the stable pool above"),
    on_fresh(unchosen_fresh(12, M0, _, B)), joined(B, ' '),
    banner("sub-pool coherence -- draw from [a,b] then the full [a,b,c,d]"),
    on_fresh(( dr_select_unchosen([a, b], M0, M1, First),
               unchosen(3, [a, b, c, d], M1, _, Rest) )),
    atomic_list_concat(Rest, ' ', R),
    format("first(from sub): ~w  then(from full): ~w~n", [First, R]),
    banner("reset() restarts the cycle"),
    on_fresh(( unchosen(4, [a, b, c, d], M0, M2, Before),
               { dr_marker_reset(M2, M3) },
               unchosen(4, [a, b, c, d], M3, _, After) )),
    atomic_list_concat(Before, ' ', BT), atomic_list_concat(After, ' ', AT),
    format("before reset: ~w~n", [BT]),
    format("after  reset: ~w~n", [AT]).

run_seed_sweep :-
    banner("first next_int(0, 1000000) per seed 0..15"),
    forall(between(0, 15, Seed),
           (   dr_stream_new(Seed, S), dr_next_int(0, 1000000, V, S, _),
               format("seed=~t~d~7| -> ~d~n", [Seed, V])
           )).

main :-
    hwut_runner_run("DeterministicStream RNG and SelectionMarker spread",
                    [ primitives-run_primitives,
                      ranges-run_ranges,
                      gauss-run_gauss,
                      sample-run_sample,
                      select-run_select,
                      unchosen-run_unchosen,
                      seed_sweep-run_seed_sweep ],
                    []).
