% @hwut {
%     title      = "space_iterator: every combination of a parameter basis"
%     choices {
%         product { features = ["prolog-space"] }
%         edges   { features = ["prolog-space"] }
%     }
%     interactive = true
% }
%
% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%______________________________________________________________________________
%
% PURPOSE: The Prolog port of 'python/TEST/test-space-iterator.py', choice for
%          choice, held against its GOOD files by '.link'. The points are the
%          solutions of a relation, enumerated by backtracking.
%______________________________________________________________________________
:- encoding(utf8).
:- use_module('../hwut_runner.pro').
:- use_module('../hwut_pytext.pro').
:- use_module('../space_iterator.pro').
:- initialization(main, main).

banner(Label) :- format("~n--- ~w ---~n", [Label]).

%   points(+Basis)
%   RETURN: every point of 'Basis', one per line, then the count.
points(Basis) :-
    aggregate_all(count,
                  (   space_point(Basis, Point),
                      maplist(py_str, Point, Ts), atomic_list_concat(Ts, ', ', T),
                      format("  (~w)~n", [T])
                  ),
                  N),
    format("  ~d point(s)~n", [N]).

run_product :-
    banner("[0, 2, 4] x [otto, heinz] x [1, 2] -- 3 * 2 * 2 points"),
    points([[0, 2, 4], [otto, heinz], [1, 2]]).

run_edges :-
    banner("an EMPTY basis -- one point, the empty one"),
    points([]),
    banner("a basis with an EMPTY dimension -- nothing"),
    points([[1, 2], [], [3]]),
    banner("ONE dimension -- its values one by one"),
    points([[a, b, c]]).

main :-
    hwut_runner_run("space_iterator: every combination of a parameter basis",
                    [product-run_product, edges-run_edges], []).
