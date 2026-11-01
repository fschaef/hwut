%% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%%_____________________________________________________________________________
%%
%% PURPOSE: TEXT AS PYTHON PRINTS IT -- the port of what 'print', '%r' and
%%          'str()' write in the Python tests, so an Erlang test prints the
%%          Python GOOD files byte for byte.
%%
%%     pytext:repr(0.1)                 <<"0.1">>
%%     pytext:repr(1.0e-6)              <<"1e-06">>
%%     pytext:repr(<<"it's">>)          <<"\"it's\"">>
%%     pytext:repr({bytes, <<27,"[A">>}) <<"b'\\x1b[A'">>
%%     pytext:repr({<<"a">>, 1})        <<"('a', 1)">>
%%     pytext:repr([true, none])        <<"[True, None]">>
%%
%% THE MAPPING OF TERMS ONTO PYTHON VALUES (one for every module here):
%%     integer -> int        float -> float     binary (UTF-8) -> str
%%     {bytes, Binary} -> bytes                 true/false -> bool
%%     none -> None          tuple -> tuple     list -> list
%%     inf, '-inf', nan -> the floats Erlang cannot hold (HOCON's '1e999')
%% An Erlang string (a list of characters) is a LIST here, not a str: text
%% is a binary throughout the port.
%%
%% EVERY TEXT RETURNED IS A UTF-8 BINARY; the devices it is written to are
%% byte devices, so it reaches the file unchanged.
%%_____________________________________________________________________________
-module(pytext).
-include("pytext_unicode.hrl").
-export([repr/1, str/1, float_repr/1, str_repr/1, bytes_repr/1, bool/1,
         ljust/2, rjust/2, join/2, char_n/1]).

%% RETURN: binary, 'X' as Python's 'repr()' writes the value 'X' stands for
%%         (see the mapping in the head); an atom beyond it as its name.
repr(true)                      -> <<"True">>;
repr(false)                     -> <<"False">>;
repr(none)                      -> <<"None">>;
repr(inf)                       -> <<"inf">>;
repr('-inf')                    -> <<"-inf">>;
repr(nan)                       -> <<"nan">>;
repr(X) when is_integer(X)      -> integer_to_binary(X);
repr(X) when is_float(X)        -> float_repr(X);
repr(X) when is_binary(X)       -> str_repr(X);
repr({bytes, X}) when is_binary(X) -> bytes_repr(X);
repr({X})                       -> <<"(", (repr(X))/binary, ",)">>;
repr(X) when is_tuple(X)        -> <<"(", (join(<<", ">>, [repr(E) || E <- tuple_to_list(X)]))/binary, ")">>;
repr(X) when is_list(X)         -> <<"[", (join(<<", ">>, [repr(E) || E <- X]))/binary, "]">>;
repr(X) when is_atom(X)         -> atom_to_binary(X).

%% RETURN: binary, 'X' as Python's 'str()' writes it -- a str as it stands,
%%         every other value as its 'repr()' (a tuple's str items quoted).
str(X) when is_binary(X)        -> X;
str({bytes, _} = X)             -> repr(X);
str(X)                          -> repr(X).

%% RETURN: <<"True">> for true, <<"False">> for false.
bool(true)  -> <<"True">>;
bool(false) -> <<"False">>.

%% RETURN: binary, the float 'X' as Python's 'repr(float)' writes it -- the
%%         shortest decimal that reads back to the same double, fixed
%%         notation where the decimal point falls in (-4, 16], exponential
%%         ('1e-06', '6.02e+23') else; '-0.0' for the negative zero.
float_repr(X) when X == 0.0 ->
    case <<X/float>> of <<1:1, _:63>> -> <<"-0.0">>; _ -> <<"0.0">> end;
float_repr(X) when is_float(X) ->
    %  THE DIGITS ARE ERLANG'S OWN: '[short]' gives the shortest decimal
    %  that reads back -- Python's digits -- in its own layout ('1.0e-6');
    %  only the layout is Python's ('1e-06').
    {Sign, Text} = case float_to_list(X, [short]) of
                       [$- | T] -> {<<"-">>, T};
                       T        -> {<<>>, T}
                   end,
    {Mantissa, Exponent} = case string:split(Text, "e") of
                               [M, E] -> {M, list_to_integer(E)};
                               [M]    -> {M, 0}
                           end,
    [Whole, Fraction] = string:split(Mantissa, "."),
    Digits0 = string:trim(Whole ++ Fraction, leading, "0"),
    Digits  = case string:trim(Digits0, trailing, "0") of "" -> "0"; D -> D end,
    %  'Whole' is one digit or the integral part: the point stands after
    %  length(Whole) digits, shifted by the exponent and the zeros trimmed.
    Point = length(Whole) + Exponent - (length(Whole ++ Fraction) - length(Digits0)),
    N = length(Digits),
    Body = if
        Point > -4, Point =< 16, Point =< 0 ->
            "0." ++ lists:duplicate(-Point, $0) ++ Digits;
        Point > -4, Point =< 16, Point >= N ->
            Digits ++ lists:duplicate(Point - N, $0) ++ ".0";
        Point > -4, Point =< 16 ->
            {Left, Right} = lists:split(Point, Digits),
            Left ++ "." ++ Right;
        true ->
            E1 = Point - 1,
            [First | Rest] = Digits,
            Head = case Rest of [] -> [First]; _ -> [First, $. | Rest] end,
            ExpSign = if E1 < 0 -> "-"; true -> "+" end,
            Head ++ "e" ++ ExpSign ++ string:pad(integer_to_list(abs(E1)), 2, leading, $0)
    end,
    <<Sign/binary, (list_to_binary(Body))/binary>>.

%% RETURN: binary, the UTF-8 'Text' as Python's 'repr(str)' writes it: in
%%         single quotes, or in double ones where it holds a single quote
%%         and no double one; the backslash, that quote, '\n', '\t', '\r'
%%         escaped, a character that does not print as '\xNN', '\uNNNN' or
%%         '\UNNNNNNNN' (Python's 'isprintable', from Python's own table).
str_repr(Text) when is_binary(Text) ->
    quoted(unicode:characters_to_list(Text), <<>>).

%% RETURN: binary, 'Data' as Python's 'repr(bytes)' writes it: b'...', every
%%         byte below 0x20 and from 0x7f on as '\xNN' (but '\n', '\t', '\r').
bytes_repr(Data) when is_binary(Data) ->
    quoted(binary_to_list(Data), <<"b">>).

%% RETURN: binary, 'CodeList' quoted and escaped as Python's repr does it,
%%         behind 'Prefix' (<<"b">> for bytes: then every code is a byte).
quoted(CodeList, Prefix) ->
    Bytes_f = Prefix =/= <<>>,
    Quote = case {lists:member($', CodeList), lists:member($", CodeList)} of
                {true, false} -> $";
                _             -> $'
            end,
    Body = << <<(escaped(C, Quote, Bytes_f))/binary>> || C <- CodeList >>,
    <<Prefix/binary, Quote, Body/binary, Quote>>.

%% RETURN: binary, the code 'C' as it stands inside Python's quotes 'Q'.
escaped($\\, _, _)                       -> <<"\\\\">>;
escaped(Q, Q, _)                         -> <<$\\, Q>>;
escaped($\n, _, _)                       -> <<"\\n">>;
escaped($\t, _, _)                       -> <<"\\t">>;
escaped($\r, _, _)                       -> <<"\\r">>;
escaped(C, _, _) when C < 16#20; C == 16#7f -> hex(C, "\\x", 2);
escaped(C, _, true) when C >= 16#80     -> hex(C, "\\x", 2);
escaped(C, _, _) when C =< 16#ff ->
    case printable_f(C) of true -> <<C/utf8>>; false -> hex(C, "\\x", 2) end;
escaped(C, _, _) when C =< 16#ffff ->
    case printable_f(C) of true -> <<C/utf8>>; false -> hex(C, "\\u", 4) end;
escaped(C, _, _) ->
    case printable_f(C) of true -> <<C/utf8>>; false -> hex(C, "\\U", 8) end.

%% RETURN: binary, 'Lead' and 'C' in 'Width' lower-case hexadecimal digits.
hex(C, Lead, Width) ->
    list_to_binary([Lead, string:pad(string:lowercase(integer_to_list(C, 16)), Width, leading, $0)]).

%% RETURN: true where Python's 'str.isprintable' holds for the code 'C',
%%         false else -- Python's own table ('pytext_unicode.hrl').
printable_f(C) -> not within(C, ?NOT_PRINTABLE, 1, tuple_size(?NOT_PRINTABLE)).

%% RETURN: true, 'C' lies in one of the sorted ranges Low..High of 'Ranges';
%%         false else (a binary search).
within(_, _, Low, High) when Low > High -> false;
within(C, Ranges, Low, High) ->
    Middle = (Low + High) div 2,
    case element(Middle, Ranges) of
        {From, _} when C < From -> within(C, Ranges, Low, Middle - 1);
        {_, To}   when C > To   -> within(C, Ranges, Middle + 1, High);
        _                       -> true
    end.

%% RETURN: integer >= 0, the number of CHARACTERS of the UTF-8 'Text' -- what
%%         Python's 'len(str)' and its '%-6s' count, not the bytes.
char_n(Text) when is_binary(Text) -> length(unicode:characters_to_list(Text)).

%% RETURN: binary, 'Text' filled with blanks on the right to 'Width'
%%         characters -- Python's '%-6s'; unchanged where it is longer.
ljust(Text, Width) ->
    T = iolist_to_binary(Text),
    <<T/binary, (binary:copy(<<" ">>, max(0, Width - char_n(T))))/binary>>.

%% RETURN: binary, 'Text' filled with blanks on the left to 'Width'
%%         characters -- Python's '%6s'; unchanged where it is longer.
rjust(Text, Width) ->
    T = iolist_to_binary(Text),
    <<(binary:copy(<<" ">>, max(0, Width - char_n(T))))/binary, T/binary>>.

%% RETURN: binary, the texts of the list joined by 'Separator' -- Python's
%%         'Separator.join(List)'; <<>> for the empty list.
join(_, [])               -> <<>>;
join(Separator, [H | T])  -> iolist_to_binary([H | [[Separator, X] || X <- T]]).
