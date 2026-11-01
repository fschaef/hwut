/*  SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
    ___________________________________________________________________________

    PURPOSE: TEXT AS PYTHON PRINTS IT -- the values a Python test prints of
             its own ('%r', 'print(x)'), written by a Prolog test the same,
             since the GOOD file it is held against is the Python test's.

        py_repr(0.1, T)                 T = "0.1"
        py_repr("it's", T)              T = "\"it's\""
        py_repr(bytes(`\e[A`), T)       T = "b'\\x1b[A'"
        py_repr(tuple([a]), T)          T = "('a',)"
        py_repr([1, 2.5, none], T)      T = "[1, 2.5, None]"
        py_str(Value, T)                str(): a text as it stands, else repr

    THE PYTHON VALUE A PROLOG TERM STANDS FOR:

        integer           int            float          float
        string, atom      str            true, false    True, False
        none              None           bytes(Codes)   bytes
        tuple(List)       tuple          List           list

    THE FLOAT: SWI-Prolog writes the SHORTEST text that reads back ('~w',
    1.0e-6, 7.0e+212); its digits and exponent are laid out as Python lays
    them: fixed where the decimal point falls in (-4, 16], else 'd.ddde+XX'
    -- '1e-06', '7e+212', '1500.0'.
    ___________________________________________________________________________
*/
:- module(hwut_pytext,
          [ py_repr/2,          % +Value, -String
            py_str/2,           % +Value, -String
            py_float_repr/2,    % +Float, -String
            py_bool/2,          % :Goal or true/false, -String
            py_ljust/3,         % +Text, +Width, -String
            py_rjust/3,         % +Text, +Width, -String
            py_signed/2,        % +Integer, -String   ('%+d')
            py_round/2,         % +Float, -Integer    (round half to even)
            py_print/1          % +Value              print(Value)
          ]).
:- encoding(utf8).

%!  py_repr(+Value, -String) is det.
%
%   RETURN: String, what Python's 'repr' writes of the value 'Value' stands
%           for (see the table above); an atom stands for a str.
py_repr(V, S) :- integer(V), !, number_string(V, S).
py_repr(V, S) :- float(V), !, py_float_repr(V, S).
py_repr(true, "True") :- !.
py_repr(false, "False") :- !.
py_repr(none, "None") :- !.
py_repr(bytes(Codes), S) :- !, quoted(Codes, bytes, Q), string_concat("b", Q, S).
py_repr(tuple([X]), S) :- !, py_repr(X, T), format(string(S), "(~w,)", [T]).
py_repr(tuple(L), S) :- !, items(L, T), format(string(S), "(~w)", [T]).
py_repr(L, S) :- is_list(L), !, items(L, T), format(string(S), "[~w]", [T]).
py_repr(V, S) :- (string(V) ; atom(V)), !, string_codes(V, Codes), quoted(Codes, str, S).
py_repr(V, S) :- format(string(S), "~q", [V]).

items(L, T) :- maplist(py_repr, L, Ts), atomic_list_concat(Ts, ', ', A), atom_string(A, T).

%!  py_str(+Value, -String) is det.
%
%   RETURN: String, what Python's 'str' writes: a str (string or atom other
%           than true, false, none) as it stands; any other value as 'repr'.
py_str(V, S) :- string(V), !, S = V.
py_str(V, S) :- atom(V), \+ memberchk(V, [true, false, none]), !, atom_string(V, S).
py_str(V, S) :- py_repr(V, S).

%!  py_print(+Value) is det.
%
%   RETURN: true; 'py_str(Value)' and a newline are written on the current
%           output -- Python's 'print(Value)'.
py_print(V) :- py_str(V, S), format("~w~n", [S]).

%!  py_bool(+Goal, -String) is det.
%
%   RETURN: "True", if 'Goal' succeeds (once) -- or is the atom 'true';
%           "False", else.
:- meta_predicate py_bool(0, -).
py_bool(_:true, S) :- !, S = "True".
py_bool(_:false, S) :- !, S = "False".
py_bool(G, S) :- ( call(G) -> S = "True" ; S = "False" ).

%!  py_float_repr(+Float, -String) is det.
%
%   RETURN: String, 'Float' as Python's 'repr(float)' writes it -- the
%           shortest decimal that reads back to the same double, fixed where
%           the decimal point falls in (-4, 16], exponential else; 'inf',
%           '-inf', 'nan' for what is no number.
py_float_repr(X, S) :- X =\= X, !, S = "nan".
py_float_repr(X, S) :- X =:= inf, !, S = "inf".
py_float_repr(X, S) :- X =:= -inf, !, S = "-inf".
py_float_repr(X, S) :-
    format(codes(Cs), "~w", [X]),
    (   Cs = [0'-|Body] -> Sign = "-" ; Body = Cs, Sign = "" ),
    shortest(Body, Digits0, Exponent),            % value = d.ddd * 10^Exponent
    trim_zeros(Digits0, Digits),
    (   Digits == [0'0] -> layout_zero(Sign, S)
    ;   Point is Exponent + 1,                    % value = 0.ddd * 10^Point
        layout(Sign, Digits, Point, S)
    ).

layout_zero(Sign, S) :- string_concat(Sign, "0.0", S).

%   shortest(+Body, -Digits, -Exponent)
%   RETURN: SWI's text 'I.Fe±X' or 'I.F', with
%           the digits normalised to one before the point.
shortest(Body, Digits, Exponent) :-
    (   append(Mantissa, [E|ExponentCs], Body), memberchk(E, `eE`)
    ->  number_codes(X0, ExponentCs)
    ;   Mantissa = Body, X0 = 0
    ),
    (   append(Int, [0'.|Frac], Mantissa) -> true ; Int = Mantissa, Frac = [] ),
    append(Int, Frac, All0),
    length(Int, IntN),
    strip_leading(All0, All, Stripped),
    (   All == []
    ->  Digits = [0'0], Exponent = 0
    ;   Digits = All, Exponent is X0 + IntN - 1 - Stripped
    ).

strip_leading([0'0|T], R, N) :- !, strip_leading(T, R, N0), N is N0 + 1.
strip_leading(L, L, 0).

trim_zeros(Ds, R) :-
    reverse(Ds, Rev), strip_leading(Rev, Rev1, _),
    ( Rev1 == [] -> R = [0'0] ; reverse(Rev1, R) ).

layout(Sign, Digits, Point, S) :-
    Point > -4, Point =< 16, !,
    length(Digits, N),
    (   Point =< 0
    ->  Z is -Point, zeros(Z, Zs), append([`0.`, Zs, Digits], Cs)
    ;   Point >= N
    ->  Z is Point - N, zeros(Z, Zs), append([Digits, Zs, `.0`], Cs)
    ;   length(Head, Point), append(Head, Tail, Digits), append([Head, `.`, Tail], Cs)
    ),
    string_codes(T, Cs), string_concat(Sign, T, S).
layout(Sign, [D|Ds], Point, S) :-
    E is Point - 1,
    ( Ds == [] -> Mantissa = [D] ; Mantissa = [D, 0'.|Ds] ),
    ( E < 0 -> ESign = "-" ; ESign = "+" ),
    AE is abs(E),
    format(string(S), "~w~se~w~|~`0t~d~2+", [Sign, Mantissa, ESign, AE]).

zeros(N, Zs) :- length(Zs, N), maplist(=(0'0), Zs).

%   quoted(+Codes, +Kind, -String)
%   RETURN: the literal in the quotes Python's repr
%           chooses -- single, or double where the text holds a single quote and no
%           double one -- with the backslash, that quote and what does not print
%           escaped; 'bytes' escapes every byte from 0x7f on, 'str' keeps what
%           prints.
quoted(Codes, Kind, S) :-
    (   memberchk(0'', Codes), \+ memberchk(0'", Codes) -> Q = 0'" ; Q = 0'' ),
    phrase(escaped(Codes, Q, Kind), Body),
    append([[Q], Body, [Q]], All),
    string_codes(S, All).

escaped([], _, _) --> [].
escaped([C|Cs], Q, K) --> escape(C, Q, K), escaped(Cs, Q, K).

escape(0'\\, _, _) --> !, `\\\\`.
escape(Q, Q, _)    --> !, [0'\\, Q].
escape(0'\n, _, _) --> !, `\\n`.
escape(0'\r, _, _) --> !, `\\r`.
escape(0'\t, _, _) --> !, `\\t`.
escape(C, _, K) -->
    { C < 0x20 ; C =:= 0x7f ; K == bytes, C > 0x7f ; K == str, C >= 0x80, C < 0xa0 }, !,
    { format(codes(Hex), "\\x~|~`0t~16r~2+", [C]) }, Hex.
escape(C, _, _) --> [C].

%!  py_ljust(+Text, +Width, -String) is det.
%
%   RETURN: String, 'Text' padded with blanks on the right to 'Width'
%           characters (code points, as Python counts) -- '%-6s'; unchanged
%           where it is as long or longer.
py_ljust(T, W, S) :-
    text_to_string(T, S0), string_length(S0, N),
    P is max(0, W - N), length(Bs, P), maplist(=(0' ), Bs),
    string_codes(B, Bs), string_concat(S0, B, S).

%!  py_rjust(+Text, +Width, -String) is det.
%
%   RETURN: String, 'Text' padded with blanks on the left to 'Width'
%           characters -- '%6s'.
py_rjust(T, W, S) :-
    text_to_string(T, S0), string_length(S0, N),
    P is max(0, W - N), length(Bs, P), maplist(=(0' ), Bs),
    string_codes(B, Bs), string_concat(B, S0, S).

%!  py_signed(+Integer, -String) is det.
%
%   RETURN: String, 'Integer' with its sign always written -- '%+d': "+0".
py_signed(I, S) :- ( I < 0 -> format(string(S), "~d", [I]) ; format(string(S), "+~d", [I]) ).

%!  py_round(+Float, -Integer) is det.
%
%   RETURN: Integer, 'Float' rounded to the nearest integer, a half to the
%           EVEN one -- Python's 'round', where Prolog's 'round' takes a half
%           away from zero.
py_round(X, I) :-
    F is floor(X), D is X - F,
    (   D > 0.5 -> I is F + 1
    ;   D < 0.5 -> I = F
    ;   F mod 2 =:= 0 -> I = F
    ;   I is F + 1
    ).
