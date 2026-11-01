%% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%%_____________________________________________________________________________
%%
%% PURPOSE: THE HOCON SUBSET OF THE SPECIFICATION LANGUAGE, PARSED INTO THE
%%          ANNOTATED TREE -- the port of 'python/hwut_hocon.py' (its manual:
%%          '../python/README-hwut_hocon.txt'): every key, value and block
%%          carries its file-relative position; faults are collected, the
%%          parse recovers at the next line and never raises.
%%
%%     -include("hwut_hocon.hrl").
%%     Lines = [#source_line{text = T, line = N, column_offset = 0} || ...],
%%     {#hocon_object{entry_list = Entries}, Faults} = hwut_hocon:parse(Lines, <<"f.hocon">>)
%%
%% THE PARSER IS BINARY MATCHING over each line's UTF-8 text: the cursor is
%% a record threaded through every function -- line, byte offset, the faults
%% so far -- and every function returns what it read with the cursor after
%% it. The bytes HOCON gives meaning to are ASCII, so a byte scan never
%% splits a character; a COLUMN is counted in characters, as Python's
%% index is, where a line holds more than ASCII.
%%
%% THE TREE is the records of 'hwut_hocon.hrl'; 'position_text' and
%% 'fault_text' write a position and a fault as Python's '__str__' does.
%%_____________________________________________________________________________
-module(hwut_hocon).
-include("hwut_hocon.hrl").
-export([parse/2, get/2, keys/1, position_text/1, fault_text/1, cleandoc/1]).

-record(cursor, {lines, n, il = 1, ic = 0, text = <<>>, ascii_f = true,
                 file, faults = []}).

-define(TRIPLE, <<"\"\"\"">>).
-define(SUBSTITUTION_MESSAGE, "substitutions '${...}' do not exist here: a "
                              "specification refers to nothing outside its file").

%% ------------------------------------------------------------------ public
%% RETURN: {Object, Faults}: the document -- an #hocon_object{} of every
%%         entry of the outermost level, possibly empty -- and every
%%         #hocon_fault{} found, in the order found; [] on a clean parse.
%%         'LineList' are #source_line{}s; 'File' names the file for faults.
parse(LineList, File) ->
    Lines = list_to_tuple(LineList),
    C0 = enter(1, #cursor{lines = Lines, n = tuple_size(Lines), file = iolist_to_binary(File)}),
    {Document, C} = parse_body(C0, none),
    {Document, lists:reverse(C#cursor.faults)}.

%% RETURN: #hocon_entry{}, the entry named 'Key'; none, no such entry.
get(Key, #hocon_object{entry_list = Entries}) ->
    case lists:keyfind(Key, #hocon_entry.key, Entries) of false -> none; Entry -> Entry end.

%% RETURN: [binary], the keys in written order.
keys(#hocon_object{entry_list = Entries}) -> [E#hocon_entry.key || E <- Entries].

%% RETURN: binary, 'line:column'.
position_text({Line, Column}) -> iolist_to_binary(io_lib:format("~b:~b", [Line, Column])).

%% RETURN: binary, 'file:line:column: KIND: message'.
fault_text(#hocon_fault{kind = Kind, file = File, position = Position, message = Message}) ->
    iolist_to_binary([File, ":", position_text(Position), ": ",
                      string:uppercase(atom_to_list(Kind)), ": ", Message]).

%% ------------------------------------------------------------------ cursor
%% RETURN: cursor, at the beginning of line 'I' (1-based; beyond the last:
%%         at the end).
enter(I, #cursor{n = N} = C) when I > N -> C#cursor{il = I, ic = 0, text = <<>>, ascii_f = true};
enter(I, #cursor{lines = Lines} = C) ->
    Text = (element(I, Lines))#source_line.text,
    C#cursor{il = I, ic = 0, text = Text, ascii_f = ascii_f(Text)}.

%% RETURN: true, the text holds nothing beyond ASCII; false else.
ascii_f(<<C, _/binary>>) when C >= 16#80 -> false;
ascii_f(<<_, Rest/binary>>)              -> ascii_f(Rest);
ascii_f(<<>>)                            -> true.

%% RETURN: true, no character remains; false else.
at_end(#cursor{il = I, n = N}) -> I > N.

%% RETURN: byte, the one 'Ahead' places from here, on this line;
%%         $\n, at this line's end; eof, beyond the last line.
peek(C) -> peek(C, 0).
peek(#cursor{il = I, n = N}, _) when I > N -> eof;
peek(#cursor{ic = Ic, text = Text}, Ahead) ->
    case Ic + Ahead of
        J when J < byte_size(Text) -> binary:at(Text, J);
        _                          -> $\n
    end.

%% RETURN: binary, the CHARACTER at the cursor, stripped as Python's
%%         'peek().strip()' -- <<>> at a line's end, beyond the last line,
%%         and for a blank.
peek_text(C) ->
    case peek(C) of
        eof -> <<>>;
        $\n -> <<>>;
        _   -> <<_:(C#cursor.ic)/binary, Rest/binary>> = C#cursor.text,
               case Rest of
                   <<Char/utf8, _/binary>> -> trim(<<Char/utf8>>);
                   <<Byte, _/binary>>      -> <<Byte>>
               end
    end.

%% RETURN: cursor, 'N' bytes further WITHIN the current line.
skip(N, #cursor{ic = Ic} = C) -> C#cursor{ic = Ic + N}.

%% RETURN: cursor, at the beginning of the next line.
skip_line(#cursor{il = I} = C) -> enter(I + 1, C).

%% RETURN: {Line, Column}, file-relative, of the character at the cursor --
%%         past the last line's end where no line remains; {1, 1} for no
%%         text at all.
position(#cursor{n = 0}) -> {1, 1};
position(#cursor{il = I, n = N, lines = Lines}) when I > N ->
    #source_line{line = Line, column_offset = Offset, text = Text} = element(N, Lines),
    {Line, Offset + pytext:char_n(Text) + 1};
position(#cursor{il = I, ic = Ic, lines = Lines, text = Text, ascii_f = AsciiF}) ->
    #source_line{line = Line, column_offset = Offset} = element(I, Lines),
    Column = case AsciiF of
                 true  -> Ic;
                 false -> K = min(Ic, byte_size(Text)),
                          <<Prefix:K/binary, _/binary>> = Text,
                          pytext:char_n(Prefix) + (Ic - K)
             end,
    {Line, Offset + Column + 1}.

%% RETURN: cursor, with one more fault recorded.
fault(Kind, Position, Message, #cursor{faults = Faults, file = File} = C) ->
    C#cursor{faults = [#hocon_fault{kind = Kind, file = File, position = Position,
                                    message = iolist_to_binary(Message)} | Faults]}.

%% ------------------------------------------------------------------ parsing
%% RETURN: {Object, Cursor}, the entries up to 'Terminator' ($} or none for
%%         the end of the text).
parse_body(C0, Terminator) ->
    body(C0, Terminator, #hocon_object{position = position(C0)}).

%% RETURN: {Object, Cursor}, 'Object' with the entries up to 'Terminator'.
body(C0, Terminator, Object) ->
    C = skip_blank(C0),
    case at_end(C) of
        true when Terminator == none ->
            {finished(Object), C};
        true ->
            {finished(Object), fault(syntax, position(C), "unterminated object: '}' missing", C)};
        false ->
            case peek(C) of
                Terminator -> {finished(Object), skip(1, C)};
                $} -> body(skip(1, fault(syntax, position(C), "unmatched '}'", C)), Terminator, Object);
                _  -> {Object1, C1} = parse_entry(C, Object),
                      body(C1, Terminator, Object1)
            end
    end.

%% RETURN: #hocon_object{}, its entries in written order (collected reversed).
finished(#hocon_object{entry_list = Entries} = Object) ->
    Object#hocon_object{entry_list = lists:reverse(Entries)}.

%% RETURN: {Object, Cursor}, one 'key = value' pair parsed into 'Object';
%%         a fault recovers at the next line.
parse_entry(C0, #hocon_object{entry_list = Entries} = Object) ->
    KeyPosition = position(C0),
    case parse_key(C0) of
        {none, C1} -> {Object, skip_line(C1)};
        {<<"include">>, C1} ->
            {Object, skip_line(fault(refused, KeyPosition,
                                     "'include' does not exist here: a specification refers to "
                                     "nothing outside its file", C1))};
        {Key, C1} ->
            C2 = skip_space(C1),
            Bound = case peek(C2) of
                        B when B == $=; B == $: -> {ok, skip_space(skip(1, C2))};
                        ${ -> {ok, C2};                 % a brace binds without a sign
                        $+ -> case peek(C2, 1) of
                                  $= -> {stop, fault(refused, position(C2), "'+=' does not exist here", C2)};
                                  _  -> {stop, expected(Key, C2)}
                              end;
                        _  -> {stop, expected(Key, C2)}
                    end,
            case Bound of
                {stop, C3} -> {Object, skip_line(C3)};
                {ok, C3} ->
                    case parse_value(C3, false) of
                        %  The value parser has recovered already (line
                        %  skipped or cursor at the fault); a second skip
                        %  here would eat the NEXT line.
                        {none, C4} -> {Object, C4};
                        {Node, C4} ->
                            case lists:keymember(Key, #hocon_entry.key, Entries) of
                                true ->
                                    {Object, fault(syntax, KeyPosition,
                                                   ["duplicate key '", Key, "'; the first stands, "
                                                    "this one is refused"], C4)};
                                false ->
                                    Entry = #hocon_entry{key = Key, key_position = KeyPosition, node = Node},
                                    {Object#hocon_object{entry_list = [Entry | Entries]}, C4}
                            end
                    end
            end
    end.

%% RETURN: cursor, with the fault that no binder follows the key recorded.
expected(Key, C) ->
    fault(syntax, position(C), ["expected '=', ':' or '{' after key '", Key, "'"], C).

%% RETURN: {Key, Cursor}, the key; {none, Cursor}, no key stands here (fault
%%         recorded). A key runs to the first character that binds, opens,
%%         closes or separates.
parse_key(C) ->
    case peek(C) of
        $" -> parse_quoted(C);
        _  ->
            case token(C#cursor.text, C#cursor.ic) of
                <<>> -> {none, fault(syntax, position(C), ["expected a key, found '", peek_text(C), "'"], C)};
                Key  -> {Key, skip(byte_size(Key), C)}
            end
    end.

%% RETURN: {Node, Cursor}, the value here -- #hocon_scalar{}, #hocon_list{}
%%         or #hocon_object{}; {none, Cursor}, nothing usable stands here
%%         (fault recorded). 'InListF': an empty value is a fault, not
%%         nothing -- in a list there is no key it could belong to.
parse_value(C0, InListF) ->
    C = skip_space(C0),
    Position = position(C),
    case {peek(C), peek(C, 1)} of
        {${, _}  -> parse_body(skip(1, C), $});
        {$[, _}  -> parse_list(skip(1, C), Position);
        {$", $"} when C#cursor.ic + 2 < byte_size(C#cursor.text) ->
            case peek(C, 2) of
                $" -> scalar(parse_triple_quoted(C), Position);
                _  -> scalar(parse_quoted(C), Position)
            end;
        {$", _}  -> scalar(parse_quoted(C), Position);
        {$$, ${} -> {none, skip_line(fault(refused, Position, ?SUBSTITUTION_MESSAGE, C))};
        _        -> parse_bare(C, Position, InListF)
    end.

%% RETURN: {Scalar, Cursor} of a read string; {none, Cursor} where none was.
scalar({none, C}, _)          -> {none, C};
scalar({Value, C}, Position) -> {#hocon_scalar{position = Position, value = Value}, C}.

%% RETURN: {List, Cursor}, the items up to ']'.
parse_list(C, Position) -> list_items(C, Position, []).

%% RETURN: {List, Cursor}, the list with 'Items' (reversed) and the rest.
list_items(C0, Position, Items) ->
    C = skip_blank(C0),
    Done = fun(Cx) -> {#hocon_list{position = Position, item_list = lists:reverse(Items)}, Cx} end,
    case at_end(C) of
        true -> Done(fault(syntax, position(C), "unterminated list: ']' missing", C));
        false ->
            case peek(C) of
                $] -> Done(skip(1, C));
                $, -> list_items(skip(1, C), Position, Items);
                $} ->
                    %  A BRACE CLOSES THE OBJECT AROUND THE LIST: the ']'
                    %  was forgotten. Said once, the brace left to its owner.
                    Done(fault(syntax, position(C), "unterminated list: ']' missing before '}'", C));
                _ ->
                    case parse_value(C, true) of
                        {none, C1} when C1#cursor.il == C#cursor.il, C1#cursor.ic == C#cursor.ic ->
                            %  NO VALUE READ AND NOTHING CONSUMED: step over
                            %  the character refused, or the loop never ends.
                            list_items(skip(1, C1), Position, Items);
                        {none, C1} -> list_items(C1, Position, Items);
                        {Item, C1} -> list_items(C1, Position, [Item | Items])
                    end
            end
    end.

%% RETURN: {Text, Cursor}, the text between three double quotes and the next
%%         three, over as many lines as it takes, AS WRITTEN (no escape is
%%         resolved), laid out as a docstring ('cleandoc');
%%         {none, Cursor}, no closing three quotes before the text's end
%%         (fault recorded).
parse_triple_quoted(C0) ->
    Begin = position(C0),
    triple_pieces(skip(3, C0), Begin, []).

%% RETURN: {Text | none, Cursor}, the pieces of the text read on.
triple_pieces(C, Begin, Pieces) ->
    case at_end(C) of
        true ->
            {none, fault(syntax, Begin, "unterminated triple-quoted string: closing '\"\"\"' missing", C)};
        false ->
            #cursor{text = Text, ic = Ic} = C,
            From = min(Ic, byte_size(Text)),
            case binary:match(Text, ?TRIPLE, [{scope, {From, byte_size(Text) - From}}]) of
                {End, 3} ->
                    Piece = binary:part(Text, From, End - From),
                    {cleandoc(lists:join(<<"\n">>, lists:reverse([Piece | Pieces]))),
                     C#cursor{ic = End + 3}};
                nomatch ->
                    triple_pieces(skip_line(C), Begin, [binary:part(Text, From, byte_size(Text) - From) | Pieces])
            end
    end.

%% RETURN: {Text, Cursor}, the string's content, escapes resolved;
%%         {none, Cursor}, it is unterminated at its line's end (fault
%%         recorded). The common case -- no backslash -- is taken in one
%%         step: the closing quote is FOUND, not walked to.
parse_quoted(#cursor{text = Text, ic = Ic} = C) ->
    Begin = position(C),
    case plain_end(Text, Ic + 1) of
        {ok, End} -> {binary:part(Text, Ic + 1, End - Ic - 1), C#cursor{ic = End + 1}};
        slow      -> quoted(Text, Ic + 1, Begin, [], C)
    end.

%% RETURN: {ok, Index}, the closing quote's index, no backslash before it;
%%         slow, the string must be walked.
plain_end(Text, I) when I >= byte_size(Text) -> slow;
plain_end(Text, I) ->
    case binary:at(Text, I) of
        $"  -> {ok, I};
        $\\ -> slow;
        $\n -> slow;
        _   -> plain_end(Text, I + 1)
    end.

%% RETURN: {Text | none, Cursor}, the string walked from byte 'I' on.
quoted(Text, I, Begin, _Pieces, C) when I >= byte_size(Text) ->
    {none, fault(syntax, Begin, "unterminated string", C#cursor{ic = I})};
quoted(Text, I, Begin, Pieces, C) ->
    case binary:at(Text, I) of
        $" -> {iolist_to_binary(lists:reverse(Pieces)), C#cursor{ic = I + 1}};
        $\\ ->
            <<_:(I + 1)/binary, After/binary>> = Text,
            {Escaped, Width} = case After of
                                   <<>>                -> {<<>>, 1};
                                   <<E/utf8, _/binary>> -> {<<E/utf8>>, byte_size(<<E/utf8>>)};
                                   <<B, _/binary>>      -> {<<B>>, 1}
                               end,
            Piece = case Escaped of
                        <<"n">> -> <<"\n">>;
                        <<"t">> -> <<"\t">>;
                        _       -> Escaped              % '"', '\' and the rest as written
                    end,
            quoted(Text, I + 1 + Width, Begin, [Piece | Pieces], C);
        Byte ->
            quoted(Text, I + 1, Begin, [Byte | Pieces], C)
    end.

%% RETURN: {Scalar, Cursor}, the bare token here -- a boolean, a number, or
%%         a spelling of nothing; {none, Cursor}, it is none of those (fault
%%         recorded): a string value is written in double quotes.
parse_bare(#cursor{text = Text, ic = Ic} = C, Position, InListF) ->
    Raw0 = token(Text, Ic),
    case sign_apart(Raw0, C) of
        {ok, Value, C1} -> {#hocon_scalar{position = Position, value = Value}, C1};
        no ->
            case Raw0 of
                <<"${", _/binary>> ->
                    {none, skip_line(fault(refused, position(C), "substitutions '${...}' do not exist here", C))};
                _ ->
                    Raw = case binary:match(Raw0, <<"//">>) of
                              {Cut, 2} -> binary:part(Raw0, 0, Cut);
                              nomatch  -> Raw0
                          end,
                    C1 = skip(byte_size(Raw), C),
                    case Raw of
                        <<>> when InListF ->
                            {none, fault(syntax, Position, ["expected a value, found '", peek_text(C1), "'"], C1)};
                        <<>> ->
                            {#hocon_scalar{position = Position, value = none}, C1};   % empty: nothing
                        _ ->
                            case interpret(Raw) of
                                not_a_token ->
                                    {none, fault(syntax, Position,
                                                 ["a string is written in double quotes: \"", Raw, "\""], C1)};
                                Value ->
                                    {#hocon_scalar{position = Position, value = Value}, C1}
                            end
                    end
            end
    end.

%% RETURN: {ok, Number, Cursor}, a lone sign joined to the number after the
%%         blanks behind it; no, it is no such sign.
sign_apart(Sign, #cursor{text = Text, ic = Ic} = C) when Sign == <<"+">>; Sign == <<"-">> ->
    %  A SIGN STANDING APART from its digits: '- 0.12'. The two must make ONE
    %  number: '- -0.12' does not, and is read as what it is.
    From  = blank_end(Text, Ic + 1),
    After = token(Text, From),
    case After =/= <<>> andalso number(After) =/= not_a_token
             andalso number(<<Sign/binary, After/binary>>) of
        false       -> no;
        not_a_token -> no;
        Joined      -> {ok, Joined, C#cursor{ic = From + byte_size(After)}}
    end;
sign_apart(_, _) -> no.

%% RETURN: none, true, false or a number -- what the bare text says;
%%         not_a_token, the text is an unquoted string, which this language
%%         has none of.
interpret(Raw) when Raw == <<"null">>; Raw == <<"nil">>; Raw == <<"none">>; Raw == <<"nihil">> -> none;
interpret(Raw) when Raw == <<"true">>;  Raw == <<"yes">> -> true;
interpret(Raw) when Raw == <<"false">>; Raw == <<"no">>  -> false;
interpret(Raw) -> number(Raw).

%% RETURN: integer | float | inf | '-inf', the number the text spells, in
%%         whatever radix; '_' is a visual helper and enters no value;
%%         not_a_token, the text spells no number.
number(Raw) ->
    {Sign, Body} = case Raw of
                       <<"-", B/binary>> -> {-1, B};
                       <<"+", B/binary>> -> {1, B};
                       _                 -> {1, Raw}
                   end,
    case Body of
        <<"0", R, Digits/binary>> when R == $r; R == $R ->
            case roman(Digits) of not_a_token -> not_a_token; V -> Sign * V end;
        <<"0", R, Digits/binary>> when R == $x; R == $X -> radix(Sign, Digits, 16);
        <<"0", R, Digits/binary>> when R == $b; R == $B -> radix(Sign, Digits, 2);
        <<"0", R, Digits/binary>> when R == $o; R == $O -> radix(Sign, Digits, 8);
        _ -> decimal(Raw)
    end.

%% RETURN: integer, 'Digits' in 'Radix', signed; not_a_token, no number.
radix(Sign, Digits, Radix) ->
    case without_helper(Digits, Radix) of
        none -> not_a_token;
        Text -> Sign * binary_to_integer(Text, Radix)
    end.

%% RETURN: binary, the text with every '_' removed; none, it carries no
%%         digit, a character that is no digit of 'Radix', or an '_' that
%%         separates nothing.
without_helper(<<>>, _)        -> none;
without_helper(<<"_", _/binary>>, _) -> none;
without_helper(Text, Radix) ->
    case binary:last(Text) == $_ orelse binary:match(Text, <<"__">>) =/= nomatch of
        true  -> none;
        false ->
            Stripped = binary:replace(Text, <<"_">>, <<>>, [global]),
            case Stripped =/= <<>> andalso lists:all(fun(D) -> digit_f(D, Radix) end, binary_to_list(Stripped)) of
                true  -> Stripped;
                false -> none
            end
    end.

%% RETURN: true, the byte 'D' is a digit of the radix; false else.
digit_f(D, 16) -> (D >= $0 andalso D =< $9) orelse (D >= $a andalso D =< $f) orelse (D >= $A andalso D =< $F);
digit_f(D, 8)  -> D >= $0 andalso D =< $7;
digit_f(D, 2)  -> D == $0 orelse D == $1.

-define(DECIMAL_RE, "^[-+]?(?:[0-9](?:_?[0-9])*(?:\\.(?:[0-9](?:_?[0-9])*)?)?|\\.[0-9](?:_?[0-9])*)"
                    "(?:[eE][-+]?[0-9](?:_?[0-9])*)?$").

%% RETURN: integer | float | inf | '-inf', the decimal the text spells;
%%         not_a_token, it spells none.
decimal(Raw) ->
    case re:run(Raw, ?DECIMAL_RE, [{capture, none}]) of
        nomatch -> not_a_token;
        match ->
            Text = binary:replace(Raw, <<"_">>, <<>>, [global]),
            case binary:match(Text, [<<".">>, <<"e">>, <<"E">>]) of
                nomatch -> binary_to_integer(Text);
                _       -> to_float(Text)
            end
    end.

%% RETURN: float, what Python's 'float(Text)' gives for the decimal 'Text'
%%         ('.5', '1e-6', '+7e212' included -- Erlang's own reader wants a
%%         digit on both sides of the point); inf or '-inf' beyond the
%%         double's range.
to_float(Text) ->
    [Sign, Whole, Fraction, Exponent] =
        case re:run(Text, "^([-+]?)([0-9]*)\\.?([0-9]*)(?:[eE]([-+]?[0-9]+))?$",
                    [{capture, all_but_first, binary}]) of
            {match, [S, W, F]}    -> [S, W, F, <<"0">>];
            {match, [S, W, F, E]} -> [S, W, F, E]
        end,
    Mantissa = case {Whole, Fraction} of
                   {<<>>, _} -> <<"0.", Fraction/binary>>;
                   {_, <<>>} -> <<Whole/binary, ".0">>;
                   _         -> <<Whole/binary, ".", Fraction/binary>>
               end,
    Minus = case Sign of <<"-">> -> <<"-">>; _ -> <<>> end,
    ZeroF = binary:replace(<<Whole/binary, Fraction/binary>>, <<"0">>, <<>>, [global]) == <<>>,
    try binary_to_float(<<Minus/binary, Mantissa/binary, "e", Exponent/binary>>)
    catch error:badarg when ZeroF ->
        binary_to_float(<<Minus/binary, "0.0">>);
    error:badarg ->
        %  BEYOND THE DOUBLE: Python's float() says inf; Erlang holds none.
        case Minus of <<"-">> -> '-inf'; _ -> inf end
    end.

-define(ROMAN_RE, "^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$").

%% RETURN: integer, the number the roman numeral spells; not_a_token, the
%%         text is no roman numeral in the strict form ('IIII', 'VX' are not).
roman(<<>>) -> not_a_token;
roman(Text) ->
    case re:run(Text, ?ROMAN_RE, [{capture, none}]) of
        nomatch -> not_a_token;
        match ->
            {Total, _} = lists:foldl(fun(Char, {T, Previous}) ->
                                             V = roman_value(Char),
                                             {if V < Previous -> T - V; true -> T + V end, max(Previous, V)}
                                     end, {0, 0}, lists:reverse(binary_to_list(Text))),
            Total
    end.

%% RETURN: integer, the value of one roman digit.
roman_value($I) -> 1;    roman_value($V) -> 5;   roman_value($X) -> 10;
roman_value($L) -> 50;   roman_value($C) -> 100; roman_value($D) -> 500;
roman_value($M) -> 1000.

%% ------------------------------------------------------------------ tokens
%% RETURN: binary, the token from byte 'I' on: up to the first character
%%         that binds, opens, closes or separates, or a blank -- Python's
%%         '[^\s{}\[\]=,:"#]*' (\s: every Unicode blank).
token(Text, I) when I >= byte_size(Text) -> <<>>;
token(Text, I) ->
    <<_:I/binary, Rest/binary>> = Text,
    binary:part(Rest, 0, token_n(Rest, 0)).

%% RETURN: integer, the bytes of the token at the start of the text, plus 'N'.
token_n(<<C, _/binary>>, N) when C == ${; C == $}; C == $[; C == $]; C == $=; C == $,;
                                 C == $:; C == $"; C == $# -> N;
token_n(<<C/utf8, Rest/binary>> = Text, N) ->
    case space_f(C) of
        true  -> N;
        false -> token_n(Rest, N + (byte_size(Text) - byte_size(Rest)))
    end;
token_n(<<_, Rest/binary>>, N) -> token_n(Rest, N + 1);
token_n(<<>>, N) -> N.

%% RETURN: true, the code 'C' is a blank to Python ('str.isspace'); false.
space_f(C) when C == $\s; C >= $\t, C =< $\r; C >= 16#1c, C =< 16#1f; C == 16#85; C == 16#a0;
                C == 16#1680; C >= 16#2000, C =< 16#200a; C == 16#2028; C == 16#2029;
                C == 16#202f; C == 16#205f; C == 16#3000 -> true;
space_f(_) -> false.

%% RETURN: binary, the UTF-8 'Text' without the blanks at both ends --
%%         Python's 'str.strip()'.
trim(Text) ->
    Chars = unicode:characters_to_list(Text),
    Strip = fun(L) -> lists:dropwhile(fun space_f/1, L) end,
    unicode:characters_to_binary(lists:reverse(Strip(lists:reverse(Strip(Chars))))).

%% RETURN: integer, the index of the first byte at or after 'I' that is no
%%         blank or tab.
blank_end(Text, I) when I < byte_size(Text) ->
    case binary:at(Text, I) of
        B when B == $\s; B == $\t -> blank_end(Text, I + 1);
        _                         -> I
    end;
blank_end(_, I) -> I.

%% RETURN: cursor, past the blanks of the current line -- at the next line
%%         where a comment follows them.
skip_space(#cursor{text = Text, ic = Ic} = C) ->
    I = blank_end(Text, Ic),
    case Text of
        <<_:I/binary, "#", _/binary>>  -> skip_line(C);
        <<_:I/binary, "//", _/binary>> -> skip_line(C);
        _                              -> C#cursor{ic = I}
    end.

%% RETURN: cursor, past blanks, line ends, commas and comments.
skip_blank(#cursor{il = I, n = N} = C) when I > N -> C;
skip_blank(#cursor{text = Text, ic = Ic} = C) ->
    case separator_end(Text, Ic) of
        J when J >= byte_size(Text) -> skip_blank(skip_line(C));
        J ->
            case Text of
                <<_:J/binary, "#", _/binary>>  -> skip_blank(skip_line(C));
                <<_:J/binary, "//", _/binary>> -> skip_blank(skip_line(C));
                _                              -> C#cursor{ic = J}
            end
    end.

%% RETURN: integer, the index of the first byte at or after 'I' that is no
%%         blank, tab or comma.
separator_end(Text, I) when I < byte_size(Text) ->
    case binary:at(Text, I) of
        B when B == $\s; B == $\t; B == $, -> separator_end(Text, I + 1);
        _                                  -> I
    end;
separator_end(_, I) -> I.

%% ------------------------------------------------------------------ layout
%% RETURN: binary, the text laid out as Python's 'inspect.cleandoc' does:
%%         tabs expanded, the indentation common to the lines after the
%%         first removed, the first line's leading blanks removed, empty
%%         lines at both ends dropped.
cleandoc(Text) ->
    Lines = string:split(expandtabs(unicode:characters_to_list(iolist_to_binary(Text))), "\n", all),
    Margin = lists:min([infinity | [length(L) - length(Content)
                                    || L <- tl(Lines), Content <- [string:trim(L, leading, " ")],
                                       Content =/= []]]),
    [First | Rest] = Lines,
    Indented = [string:trim(First, leading, " ")
                | [case Margin of infinity -> L; _ -> lists:nthtail(min(Margin, length(L)), L) end
                   || L <- Rest]],
    Kept = lists:dropwhile(fun(L) -> L == [] end,
                           lists:reverse(lists:dropwhile(fun(L) -> L == [] end, lists:reverse(Indented)))),
    unicode:characters_to_binary(lists:join($\n, Kept)).

%% RETURN: string, 'Chars' with every tab replaced by the blanks to the next
%%         multiple of 8 -- Python's 'str.expandtabs()'.
expandtabs(Chars) -> expandtabs(Chars, 0, []).
expandtabs([], _, Acc) -> lists:reverse(Acc);
expandtabs([$\t | Rest], Column, Acc) ->
    N = 8 - Column rem 8,
    expandtabs(Rest, Column + N, lists:duplicate(N, $\s) ++ Acc);
expandtabs([C | Rest], _, Acc) when C == $\n; C == $\r -> expandtabs(Rest, 0, [C | Acc]);
expandtabs([C | Rest], Column, Acc) -> expandtabs(Rest, Column + 1, [C | Acc]).
