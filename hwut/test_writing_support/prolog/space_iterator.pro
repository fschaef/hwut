/*  SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
    ___________________________________________________________________________

    PURPOSE: Every combination of a parameter basis -- the port of
             'python/space_iterator.py'.

    IN PROLOG THE ITERATOR IS A RELATION: 'space_point(Basis, Point)' holds
    for every point of the cartesian product, and BACKTRACKING is the
    iteration. The last choice made is the first one retried, so the
    RIGHTMOST dimension changes fastest -- the order 'itertools.product'
    yields, with nothing written to make it so.

        forall(space_point([[0, 2, 4], [otto, heinz], [1, 2]], Point),
               print(Point))                  % [0,otto,1], [0,otto,2], ...

        findall(P, space_point(Basis, P), Points)

    An EMPTY basis has one point, the empty one ('[]'); a basis with an empty
    dimension has none -- the relation is false.
    ___________________________________________________________________________
*/
:- module(space_iterator, [space_point/2]).   % +Basis, -Point

%!  space_point(+Basis, -Point) is nondet.
%
%   RETURN: Point, one list holding one value of each dimension of 'Basis'
%           (a list of lists), in the dimensions' order -- on backtracking
%           every point, the rightmost dimension fastest; fails where a
%           dimension is empty, and where every point was given.
space_point(Basis, Point) :- maplist(dimension_value, Basis, Point).

dimension_value(Dimension, Value) :- member(Value, Dimension).
