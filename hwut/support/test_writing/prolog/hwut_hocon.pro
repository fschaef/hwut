/*  SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
    ___________________________________________________________________________

    PURPOSE: Parse the HOCON subset of the specification language into the
             ANNOTATED TREE -- the port of 'python/hwut_hocon.py' (its README
             explains the subset: objects, lists, numbers in every radix,
             booleans, the spellings of nothing, strings in double quotes,
             texts of several lines in triple quotes; 'include', '${...}' and
             '+=' refused by name). Faults accumulate; the parse never raises.

        hocon_lines("a = 1\nb = \"x\"", 0, 0, Lines),
        hocon_parse(Lines, "f.hocon", Document, Faults)

    THE TREE, as terms -- the Python dataclasses, field for field:

        source_line(Text, Line, ColumnOffset)
        position(Line, Column)                          1-based
        object_node(Position, Entries)                  entry(Key, KeyPosition, Node)
        list_node(Items, Position)
        scalar_node(Value, Position)    Value: a string (str), an integer, a
                                        float, true/false (bool), none (None)
        parse_fault(Kind, File, Position, Message)      Kind: syntax | refused

    THE PARSER IS A GRAMMAR OVER CODES (DCG). The lines are laid end to end,
    each followed by a newline: the list of codes IS the cursor -- what is
    left of it says where the parse stands, and a position is computed from
    its length through the lines' offsets. Python's regular expressions are
    nonterminals: the decimal, the radix forms, and the roman numeral, whose
    backtracking is the grammar's own. The faults are threaded through every
    nonterminal as a difference list.
    ___________________________________________________________________________
*/
:- module(hwut_hocon,
          [ hocon_parse/4,              % +Lines, +File, -Document, -Faults
            hocon_lines/4,              % +Text, +LineOffset, +ColumnOffset, -Lines
            hocon_get/3,                % +ObjectNode, +Key, -Entry
            hocon_keys/2,               % +ObjectNode, -Keys
            hocon_position_text/2,      % +Position, -String
            hocon_fault_text/2,         % +Fault, -String
            hocon_type_name/2           % +Value, -PythonTypeName
          ]).
:- encoding(utf8).
:- use_module(library(lists)).
:- use_module(library(apply)).

/* ------------------------------------------------------------- the faces */

%!  hocon_lines(+Text, +LineOffset, +ColumnOffset, -Lines) is det.
%
%   RETURN: Lines, 'Text' split at its newlines into source_line terms --
%           line i (from 1) numbered i + LineOffset, every one with
%           ColumnOffset.
hocon_lines(Text, LineOffset, ColumnOffset, Lines) :-
    split_string(Text, "\n", "", Parts),
    foldl([P, source_line(P, L, ColumnOffset), I0, I]>>( I is I0 + 1, L is I0 + LineOffset ),
          Parts, Lines, 1, _).

%!  hocon_parse(+Lines, +File, -Document, -Faults) is det.
%
%   RETURN: Document, the object_node of every entry of the outermost level
%           (possibly none); Faults, every parse_fault found -- [] on a clean
%           parse. 'File' names the file in the faults. Never raises; never
%           fails.
hocon_parse(Lines, File, Document, Faults) :-
    context(Lines, File, Ctx, Codes),
    phrase(body(none, Ctx, Document, Faults, []), Codes, _).

%!  hocon_get(+ObjectNode, +Key, -Entry) is semidet.
%
%   RETURN: Entry, the entry named 'Key' (a string); fails where none is.
hocon_get(object_node(_, Entries), Key, Entry) :-
    Entry = entry(K, _, _), member(Entry, Entries), K == Key, !.

%!  hocon_keys(+ObjectNode, -Keys) is det.
%
%   RETURN: Keys, the keys in written order.
hocon_keys(object_node(_, Entries), Keys) :- maplist([entry(K, _, _), K]>>true, Entries, Keys).

%!  hocon_position_text(+Position, -String) is det.
%
%   RETURN: String, 'line:column'.
hocon_position_text(position(L, C), S) :- format(string(S), "~d:~d", [L, C]).

%!  hocon_fault_text(+Fault, -String) is det.
%
%   RETURN: String, 'file:line:column: KIND: message'.
hocon_fault_text(parse_fault(Kind, File, Pos, Message), S) :-
    hocon_position_text(Pos, P), upcase_atom(Kind, K),
    format(string(S), "~w:~w: ~w: ~w", [File, P, K, Message]).

%!  hocon_type_name(+Value, -Name) is det.
%
%   RETURN: Name, the name of the Python type the scalar stands for: 'str',
%           'int', 'float', 'bool', 'NoneType'.
hocon_type_name(V, str) :- string(V), !.
hocon_type_name(V, int) :- integer(V), !.
hocon_type_name(V, float) :- float(V), !.
hocon_type_name(none, 'NoneType') :- !.
hocon_type_name(_, bool).

/* -------------------------------------------------------------- the cursor

   ctx(Total, Starts, File): Total the codes laid out, Starts one
   line(StartIndex, Line, ColumnOffset, Length) per line, the LAST first.  */

context(Lines, File, ctx(Total, Starts, File), Codes) :-
    foldl(lay, Lines, 0-[], Total-Starts),
    foldl([source_line(T, _, _), C0, C]>>( string_codes(T, Cs), append(Cs, [0'\n], L),
                                           append(C0, L, C) ), Lines, [], Codes).

lay(source_line(T, L, O), I0-S0, I-[line(I0, L, O, N)|S0]) :- string_length(T, N), I is I0 + N + 1.

%   here(-Rest)//
%   RETURN: what is left of the text, consuming nothing.
here(R, R, R).

%   pos(+Ctx, +Rest, -Position)
%   RETURN: the file-relative position of the cursor
%           that has 'Rest' left -- past the last line: the place after its end.
pos(ctx(_, [], _), _, position(1, 1)) :- !.
pos(ctx(Total, Starts, _), Rest, position(L, C)) :-
    length(Rest, N), I is Total - N,
    (   N =:= 0
    ->  Starts = [line(_, L, O, Len)|_], C is O + Len + 1
    ;   member(line(S, L, O, _), Starts), S =< I, !, C is O + I - S + 1
    ).

position(Ctx, P) --> here(R), { pos(Ctx, R, P) }.

%   peek(-Code)//
%   RETURN: the code at the cursor ('end' past the text), consuming
%           nothing.
peek(C, S, S) :- ( S = [C0|_] -> C = C0 ; C = end ).
peek2(C1, C2, S, S) :- ( S = [C1, C2|_] -> true ; S = [C1] -> C2 = end ; C1 = end, C2 = end ).
peek3(C1, C2, C3, S, S) :- ( S = [C1, C2, C3|_] -> true ; C3 = end, peek2(C1, C2, S, _) ).

at_end([], []).

skip(0) --> !.
skip(N) --> [_], !, { N1 is N - 1 }, skip(N1).
skip(_) --> [].

%   skip_line//
%   RETURN: to the beginning of the next line (past the text: stays).
skip_line --> [C], !, ( { C == 0'\n } -> [] ; skip_line ).
skip_line --> [].

blank(0' ).
blank(0'\t).

blanks --> [C], { blank(C) }, !, blanks.
blanks --> [].

%   skip_space//
%   RETURN: blanks and a comment on the current line.
skip_space --> blanks, ( comment_start -> skip_line ; [] ).

comment_start, [0'#] --> [0'#].
comment_start, `//` --> `//`.

%   skip_blank//
%   RETURN: blanks, newlines, commas and comments.
skip_blank --> [C], { blank(C) ; C == 0', ; C == 0'\n }, !, skip_blank.
skip_blank --> comment_start, !, skip_line, skip_blank.
skip_blank --> [].

%   token(-Codes)//
%   RETURN: the run up to the first code that binds, opens, closes
%           or separates -- [^\s{}\[\]=,:"#]*.
token([C|Cs]) --> [C], { token_code(C) }, !, token(Cs).
token([]) --> [].

token_code(C) :- \+ code_type(C, space), \+ memberchk(C, `{}[]=,:"#`).

fault(Ctx, Kind, Pos, Message, [parse_fault(Kind, File, Pos, Message)|F], F) :- Ctx = ctx(_, _, File).

fault_at(Ctx, Kind, Format, Args, F0, F) -->
    position(Ctx, P), { format(string(M), Format, Args), fault(Ctx, Kind, P, M, F0, F) }.

%   found_text(-Text)//
%   RETURN: what Python's 'peek().strip()' says is here: the
%           code, or '' at a line's end, a blank, or past the text.
found_text(T) --> peek(C), { C == end -> T = "" ; code_type(C, space) -> T = "" ; string_codes(T, [C]) }.

/* -------------------------------------------------------------- the grammar */

%   body(+Terminator, +Ctx, -ObjectNode, F0, F)//
%   RETURN: the entries up to
%           'Terminator' ('}', or none for the end of the text).
body(Term, Ctx, object_node(P, Entries), F0, F) -->
    position(Ctx, P), body_loop(Term, Ctx, [], Entries, F0, F).

body_loop(Term, Ctx, Acc, Entries, F0, F) -->
    skip_blank, peek(C),
    (   { C == end }
    ->  (   { Term == none } -> { F0 = F }
        ;   fault_at(Ctx, syntax, "unterminated object: '}' missing", [], F0, F)
        ),
        { reverse(Acc, Entries) }
    ;   { C == Term }
    ->  skip(1), { reverse(Acc, Entries), F0 = F }
    ;   { C == 0'} }
    ->  fault_at(Ctx, syntax, "unmatched '}'", [], F0, F1), skip(1),
        body_loop(Term, Ctx, Acc, Entries, F1, F)
    ;   entry(Ctx, Acc, Acc1, F0, F1),
        body_loop(Term, Ctx, Acc1, Entries, F1, F)
    ).

%   entry(+Ctx, +Acc0, -Acc, F0, F)//
%   RETURN: one 'key = value' pair; faults recover
%           at the next line.
entry(Ctx, Acc0, Acc, F0, F) -->
    position(Ctx, KeyPos),
    key(Ctx, Key, F0, F1),
    (   { Key == none }
    ->  skip_line, { Acc = Acc0, F1 = F }
    ;   { Key == "include" }
    ->  { fault(Ctx, refused, KeyPos,
                "'include' does not exist here: a specification refers to nothing outside its file",
                F1, F) },
        skip_line, { Acc = Acc0 }
    ;   skip_space, peek2(C, C2),
        (   { C == 0'= ; C == 0': }
        ->  skip(1), skip_space, binding(Ctx, Key, KeyPos, Acc0, Acc, F1, F)
        ;   { C == 0'{ }
        ->  binding(Ctx, Key, KeyPos, Acc0, Acc, F1, F)
        ;   { C == 0'+, C2 == 0'= }
        ->  fault_at(Ctx, refused, "'+=' does not exist here", [], F1, F), skip_line, { Acc = Acc0 }
        ;   fault_at(Ctx, syntax, "expected '=', ':' or '{' after key '~w'", [Key], F1, F),
            skip_line, { Acc = Acc0 }
        )
    ).

binding(Ctx, Key, KeyPos, Acc0, Acc, F0, F) -->
    value(Ctx, false, Node, F0, F1),
    {   Node == none
    ->  Acc = Acc0, F1 = F              % the value recovered already
    ;   memberchk(entry(Key, _, _), Acc0)
    ->  format(string(M), "duplicate key '~w'; the first stands, this one is refused", [Key]),
        fault(Ctx, syntax, KeyPos, M, F1, F), Acc = Acc0
    ;   Acc = [entry(Key, KeyPos, Node)|Acc0], F1 = F
    }.

%   key(+Ctx, -Key, F0, F)//
%   RETURN: the key as a string; none where no key stands
%           here (fault recorded).
key(Ctx, Key, F0, F) -->
    peek(C),
    (   { C == 0'" }
    ->  quoted(Ctx, Key, F0, F)
    ;   here(R), token(Cs),
        (   { Cs == [] }
        ->  { phrase(found_text(T), R, _) },
            fault_at(Ctx, syntax, "expected a key, found '~w'", [T], F0, F), { Key = none }
        ;   { string_codes(Key, Cs), F0 = F }
        )
    ).

%   value(+Ctx, +InList, -Node, F0, F)//
%   RETURN: the value here; none where nothing
%           usable stands (fault recorded). 'InList': an empty value is a fault, not
%           null -- in a list there is no key it could belong to.
value(Ctx, InList, Node, F0, F) -->
    skip_space, position(Ctx, P), peek3(C, C2, C3),
    (   { C == 0'{ }
    ->  skip(1), body(0'}, Ctx, Node, F0, F)
    ;   { C == 0'[ }
    ->  skip(1), list(Ctx, P, Node, F0, F)
    ;   { C == 0'", C2 == 0'", C3 == 0'" }
    ->  triple(Ctx, V, F0, F), { V == none -> Node = none ; Node = scalar_node(V, P) }
    ;   { C == 0'" }
    ->  quoted(Ctx, V, F0, F), { V == none -> Node = none ; Node = scalar_node(V, P) }
    ;   { C == 0'$, C2 == 0'{ }
    ->  { fault(Ctx, refused, P,
                "substitutions '${...}' do not exist here: a specification refers to nothing outside its file",
                F0, F) },
        skip_line, { Node = none }
    ;   bare(Ctx, P, InList, Node, F0, F)
    ).

%   list(+Ctx, +Position, -ListNode, F0, F)//
%   RETURN: the items up to ']'.
list(Ctx, P, list_node(Items, P), F0, F) --> list_loop(Ctx, [], Items, F0, F).

list_loop(Ctx, Acc, Items, F0, F) -->
    skip_blank, peek(C),
    (   { C == end }
    ->  fault_at(Ctx, syntax, "unterminated list: ']' missing", [], F0, F), { reverse(Acc, Items) }
    ;   { C == 0'] }
    ->  skip(1), { reverse(Acc, Items), F0 = F }
    ;   { C == 0', }
    ->  skip(1), list_loop(Ctx, Acc, Items, F0, F)
    ;   { C == 0'} }
    ->  %  A BRACE CLOSES THE OBJECT AROUND THE LIST: the ']' was forgotten.
        %  Said once, the brace left to its owner.
        fault_at(Ctx, syntax, "unterminated list: ']' missing before '}'", [], F0, F),
        { reverse(Acc, Items) }
    ;   here(Before), value(Ctx, true, Item, F0, F1), here(After),
        (   { Item == none }
        ->  %  NO VALUE READ AND NOTHING CONSUMED: step over the code the
            %  value refused, or the loop never ends.
            ( { same_length(Before, After) } -> skip(1) ; [] ),
            list_loop(Ctx, Acc, Items, F1, F)
        ;   list_loop(Ctx, [Item|Acc], Items, F1, F)
        )
    ).

%   triple(+Ctx, -Value, F0, F)//
%   RETURN: the text from three double quotes to the
%           next three, AS WRITTEN, laid out as a docstring ('inspect.cleandoc');
%           none where no closing three quotes stand before the text's end.
triple(Ctx, V, F0, F) -->
    position(Ctx, Begin), skip(3), pieces(Pieces, Closed),
    (   { Closed == true }
    ->  { atomic_list_concat_codes(Pieces, Cs), cleandoc(Cs, Clean),
          string_codes(V, Clean), F0 = F }
    ;   { fault(Ctx, syntax, Begin,
                "unterminated triple-quoted string: closing '\"\"\"' missing", F0, F),
          V = none }
    ).

pieces(Pieces, Closed) -->
    (   at_end -> { Pieces = [], Closed = false }
    ;   line_piece(Cs, Found),
        (   { Found == true } -> { Pieces = [Cs], Closed = true }
        ;   { Pieces = [Cs|Ps] }, pieces(Ps, Closed)
        )
    ).

%   line_piece(-Codes, -Found)//
%   RETURN: up to '"""' on this line (consumed, Found
%           true), or the rest of the line and its end (Found false).
line_piece([], true) --> `"""`, !.
line_piece([], false) --> [0'\n], !.
line_piece([], false) --> at_end, !.
line_piece([C|Cs], F) --> [C], line_piece(Cs, F).

%   quoted(+Ctx, -Value, F0, F)//
%   RETURN: the string's content, escapes resolved;
%           none where it is unterminated at its line's end (the cursor stays there).
quoted(Ctx, V, F0, F) -->
    position(Ctx, Begin), skip(1), string_body(Cs, Ok),
    (   { Ok == true } -> { string_codes(V, Cs), F0 = F }
    ;   { fault(Ctx, syntax, Begin, "unterminated string", F0, F), V = none }
    ).

string_body(Cs, Ok) -->
    peek(C),
    (   { C == end ; C == 0'\n } -> { Cs = [], Ok = false }
    ;   { C == 0'" } -> skip(1), { Cs = [], Ok = true }
    ;   { C == 0'\\ }
    ->  skip(1), peek(E),
        (   { E == end ; E == 0'\n } -> { Cs = [], Ok = false }
        ;   skip(1), { escape(E, X), Cs = [X|Cs1] }, string_body(Cs1, Ok)
        )
    ;   skip(1), { Cs = [C|Cs1] }, string_body(Cs1, Ok)
    ).

escape(0'n, 0'\n) :- !.
escape(0't, 0'\t) :- !.
escape(C, C).

%   bare(+Ctx, +Position, +InList, -Node, F0, F)//
%   RETURN: a boolean, a number or a
%           spelling of nothing; none where the token is none of those (a string is
%           written in double quotes).
bare(Ctx, P, InList, Node, F0, F) -->
    here(R), { phrase(token(Raw0), R, _) },
    (   { memberchk(Raw0, [`+`, `-`]),
          R = [_|R1], phrase(blanks, R1, R2), phrase(token(After), R2, R3),
          After \== [], number_value(After, _),
          append(Raw0, After, Joined), number_value(Joined, Value) }
    ->  %  A SIGN STANDING APART from its digits ('- 0.12'): the two are ONE
        %  number, where they make one ('- -1.5e3' makes none).
        rest_is(R3), { Node = scalar_node(Value, P), F0 = F }
    ;   { Raw0 = [0'$, 0'{|_] }
    ->  fault_at(Ctx, refused, "substitutions '${...}' do not exist here", [], F0, F),
        skip_line, { Node = none }
    ;   { ( append(Raw, [0'/, 0'/|_], Raw0) -> true ; Raw = Raw0 ), length(Raw, N) },
        skip(N),
        (   { Raw == [] }
        ->  (   { InList == true }
            ->  found_text(T),
                { format(string(M), "expected a value, found '~w'", [T]),
                  fault(Ctx, syntax, P, M, F0, F), Node = none }
            ;   { Node = scalar_node(none, P), F0 = F }
            )
        ;   { interpret(Raw, Value) }
        ->  { Node = scalar_node(Value, P), F0 = F }
        ;   { format(string(M), "a string is written in double quotes: \"~s\"", [Raw]),
              fault(Ctx, syntax, P, M, F0, F), Node = none }
        )
    ).

%   rest_is(+Rest)//
%   RETURN: the cursor moved on to 'Rest'.
rest_is(R, _, R).

%   interpret(+Raw, -Value) is semidet: none for the spellings of nothing,
%   true/false, or the number Raw spells; fails where Raw is no bare token
%   (an unquoted string, which this language has not).
interpret(Raw, V) :- atom_codes(A, Raw), ( nothing(A) -> V = none ; boolean(A, V) -> true ; number_value(Raw, V) ).

nothing(null). nothing(nil). nothing(none). nothing(nihil).
boolean(true, true). boolean(yes, true). boolean(false, false). boolean(no, false).

/* THE NUMBER, in every radix, '_' admitted between digits as a visual helper
   and carried by none of them into the value.                            */

%   number_value(+Codes, -Number) is semidet: the integer or float 'Codes'
%   spell; fails where they spell none.
number_value(Raw, V) :-
    (   Raw = [S|Body], memberchk(S, `+-`) -> true ; Body = Raw, S = 0'+ ),
    ( S == 0'- -> Sign = -1 ; Sign = 1 ),
    (   Body = [0'0, R|Digits], memberchk(R, `rR`)
    ->  phrase(roman(Value), Digits), V is Sign * Value
    ;   Body = [0'0, X|Digits], radix(X, Radix)
    ->  without_helper(Digits, Radix, Stripped),
        foldl([D, A0, A]>>( code_type(D, xdigit(W)), A is A0 * Radix + W ), Stripped, 0, Value),
        V is Sign * Value
    ;   phrase(decimal(Int, Frac, Exp, Kind), Raw),
        (   Kind == int -> number_codes(V, Int)
        ;   float_of(Int, Frac, Exp, V)
        )
    ).

radix(0'x, 16). radix(0'X, 16). radix(0'b, 2). radix(0'B, 2). radix(0'o, 8). radix(0'O, 8).

radix_digit(16, C) :- code_type(C, xdigit(_)), C < 128.
radix_digit(2, C) :- memberchk(C, `01`).
radix_digit(8, C) :- C >= 0'0, C =< 0'7.

%   without_helper(+Codes, +Radix, -Digits) is semidet: Codes with every '_'
%   removed; fails where they carry no digit, a code no digit of the radix,
%   or an '_' that separates nothing.
without_helper(Cs, Radix, Ds) :-
    Cs = [First|_], First \== 0'_, last(Cs, Last), Last \== 0'_,
    \+ append(_, [0'_, 0'_|_], Cs),
    exclude(==(0'_), Cs, Ds), Ds \== [],
    forall(member(D, Ds), radix_digit(Radix, D)).

%   decimal(-Int, -Frac, -Exp, -Kind)//
%   RETURN: [-+]? ( digits ( . digits? )? |
%           . digits ) ( [eE] [-+]? digits )? -- the helper '_' between digits;
%           Int with its sign, Frac and Exp without helpers ([] where absent); Kind
%           int, or float where a point or an exponent stands.
decimal(Int, Frac, Exp, Kind) -->
    sign(S),
    (   digits(D) -> ( "." -> ( digits(F) -> [] ; { F = [] } ), { P = true } ; { F = [], P = false } )
    ;   ".", digits(F), { D = [], P = true }
    ),
    ( [E], { memberchk(E, `eE`) } -> sign(XS), digits(X0), { append(XS, X0, Exp), X = true } ; { Exp = [], X = false } ),
    { append(S, D, Int), ( P == false, X == false -> Kind = int ; Kind = float ), Frac = F }.

sign([0'-]) --> "-", !.
sign([]) --> "+", !.
sign([]) --> [].

%   digits(-Digits)//
%   RETURN: [0-9](_?[0-9])*, the helpers left out.
digits([D|Ds]) --> digit(D), digits_rest(Ds).
digits_rest([D|Ds]) --> "_", digit(D), !, digits_rest(Ds).
digits_rest([D|Ds]) --> digit(D), !, digits_rest(Ds).
digits_rest([]) --> [].
digit(D) --> [D], { D >= 0'0, D =< 0'9 }.

%   float_of(+Int, +Frac, +Exp, -Float)
%   RETURN: Python's 'float(text)' -- written
%           so that Prolog reads it; beyond the double's range inf (or 0.0), as
%           Python's.
float_of(Int0, Frac0, Exp0, V) :-
    ( Int0 == [] -> Int = `0` ; Int0 == `-` -> Int = `-0` ; Int = Int0 ),
    ( Frac0 == [] -> Frac = `0` ; Frac = Frac0 ),
    ( Exp0 == [] -> Exp = `0` ; Exp = Exp0 ),
    append([Int, `.`, Frac, `e`, Exp], Cs),
    catch(number_codes(V, Cs), _, out_of_range(Int, Exp, V)).

out_of_range(Int, Exp, V) :-
    ( Exp = [0'-|_] -> V0 = 0.0 ; V0 = inf ),
    ( Int = [0'-|_] -> V is -V0 ; V is V0 ).

%   roman(-Value)//
%   RETURN: M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})
%           and nothing behind it -- the strict form ('IIII', 'VX' are none) -- not
%           empty; the grammar backtracks as the expression does.
roman(V) --> { true }, roman_digits(Cs), { Cs \== [], roman_value(Cs, V) }.

roman_digits(Cs) -->
    upto(3, 0'M, Ms), group(0'C, 0'D, 0'M, Cs1), group(0'X, 0'L, 0'C, Cs2), group(0'I, 0'V, 0'X, Cs3),
    { append([Ms, Cs1, Cs2, Cs3], Cs) }.

%   group(+One, +Five, +Ten, -Codes)//
%   RETURN: One Ten | One Five | Five? One{0,3}.
group(O, _, T, [O, T]) --> [O, T].
group(O, F, _, [O, F]) --> [O, F].
group(O, F, _, Cs) --> ( [F] -> { Cs = [F|Os] } ; { Cs = Os } ), upto(3, O, Os).

upto(N, C, [C|Cs]) --> { N > 0 }, [C], { N1 is N - 1 }, upto(N1, C, Cs).
upto(_, _, []) --> [].

roman_value(Cs, V) :-
    reverse(Cs, Rs),
    foldl([C, T0-P0, T-P]>>( roman_digit(C, X), ( X < P0 -> T is T0 - X ; T is T0 + X ), P is max(P0, X) ),
          Rs, 0-0, V-_).

roman_digit(0'I, 1). roman_digit(0'V, 5). roman_digit(0'X, 10). roman_digit(0'L, 50).
roman_digit(0'C, 100). roman_digit(0'D, 500). roman_digit(0'M, 1000).

/* THE TEXT OF SEVERAL LINES laid out as Python's 'inspect.cleandoc': tabs
   expanded, the indentation common to the lines after the first removed,
   the first line's leading blanks removed, empty lines at both ends
   dropped.                                                               */
cleandoc(Cs, Clean) :-
    expand_tabs(Cs, 0, Expanded),
    split_codes(Expanded, Lines),
    Lines = [First|Rest],
    foldl(margin, Rest, inf, Margin),
    lstrip_blanks(First, First1),
    (   Margin == inf -> Rest1 = Rest
    ;   maplist(drop(Margin), Rest, Rest1)
    ),
    trim_empty([First1|Rest1], Trimmed),
    atomic_list_concat_codes(Trimmed, Clean).

expand_tabs([], _, []).
expand_tabs([0'\t|Cs], Col, Out) :- !,
    N is 8 - Col mod 8, length(Bs, N), maplist(=(0' ), Bs),
    append(Bs, Out1, Out), Col1 is Col + N, expand_tabs(Cs, Col1, Out1).
expand_tabs([0'\n|Cs], _, [0'\n|Out]) :- !, expand_tabs(Cs, 0, Out).
expand_tabs([C|Cs], Col, [C|Out]) :- Col1 is Col + 1, expand_tabs(Cs, Col1, Out).

split_codes(Cs, [L|Ls]) :- ( append(L, [0'\n|Rest], Cs) -> split_codes(Rest, Ls) ; L = Cs, Ls = [] ).

margin(Line, M0, M) :-
    lstrip_blanks(Line, Content),
    (   Content == [] -> M = M0
    ;   length(Line, N), length(Content, K), I is N - K,
        ( M0 == inf -> M = I ; M is min(M0, I) )
    ).

lstrip_blanks([0' |Cs], R) :- !, lstrip_blanks(Cs, R).
lstrip_blanks(Cs, Cs).

drop(N, L, R) :- ( length(P, N), append(P, R, L) -> true ; R = [] ).

trim_empty(Ls, R) :-
    reverse(Ls, Rev), drop_empty(Rev, Rev1), reverse(Rev1, L1), drop_empty(L1, R).
drop_empty([[]|Ls], R) :- !, drop_empty(Ls, R).
drop_empty(Ls, Ls).

atomic_list_concat_codes([], []).
atomic_list_concat_codes([L], L) :- !.
atomic_list_concat_codes([L|Ls], Cs) :- atomic_list_concat_codes(Ls, Rest), append(L, [0'\n|Rest], Cs).
