%% @hwut {
%%     title     = "Demo: a shop's stock -- what the directory's hwut.conf arranges"
%%     tolerance { stderr_ignored = true }
%%     choices {
%%         sell   { features = ["unordered-table", "stderr-ignored", "collision"] }
%%         report { features = ["output-file", "keyed-table-separator", "dependency",
%%                              "frame-scripts", "test-scripts", "stderr-ignored"]
%%                  output   = ["<stdout>", "stock.csv"] }
%%     }
%% }
%%
%%_____________________________________________________________________________
%% SUBJECT  the stock of a small shop, kept in a database ('shop_db.hrl': one
%%          file, one writer at a time): a delivery comes in, three clerks
%%          sell at once, and the stock is reported.
%% REQUIREMENT  Every movement of the stock is journalled, so that the stock
%%              always ADDS UP: opening quantity plus the journal's movements.
%%
%% THE DIRECTORY ARRANGES WHAT NO SINGLE TEST CAN -- in 'hwut.conf' beside
%% this file, read it first. hwut, when it enters this directory:
%%
%%     on_entry        'fixture.erl open': a fresh 'TMP/shop.db', stocked
%%     on_before_test  'fixture.erl check before $HWUT_TEST $HWUT_CHOICE',
%%     on_after_test   'fixture.erl check after ...': around every test run,
%%                     whether the stock adds up, into 'TMP/frame.log' --
%%                     hwut sets the two variables for the run
%%     on_exit         'fixture.erl close'
%%     apps            'delivery.json' is a test, though it carries no
%%                     header: JSON has no comment to carry one. 'admit'
%%                     takes it out of the files hwut ignores by default
%%                     ('*.json'); 'execute' says how it is run --
%%                     'escript shop.erl deliver delivery.json'.
%%     collision       'delivery.json' and 'shop.erl sell' both write the
%%                     database. One writer at a time holds it; one that
%%                     waits too long fails with 'database is locked'. hwut
%%                     never runs the two at once.
%%     dependency      'shop.erl report' runs after both, whatever their
%%                     verdict: it reports what they left.
%%
%% STDERR  Every step on the database is logged on stderr, as a server would.
%% A word on stderr fails a run ('unexpected stderr') unless the header says
%% 'stderr_ignored = true': the words there are on purpose, and no error.
%%
%% CHOICES
%%
%% sell     three clerks sell at once, each a process of its own. The sales
%%          are printed as '##! table unordered sep={;}': rows of 'item;qty',
%%          in any order -- and no column is a key, 'apple;1' stands four
%%          times.
%%
%% report   the stock, as '##! table key=0 sep={;}', and the same rows
%%          written to 'stock.csv': 'output' names the file, hwut reads it
%%          after the run and compares it with its own GOOD. Then the frame
%%          log of the shop's tests: what 'on_before_test' and 'on_after_test'
%%          found around the delivery and the sale ('##! potpourri': which
%%          ran first is free), and before this report.
%%
%% deliver  (no choice -- 'execute' of 'delivery.json' calls it) books a
%%          delivery note: every line on the stock and into the journal, in
%%          one transaction.
%%_____________________________________________________________________________
-mode(compile).
-include("shop_db.hrl").

%% What each clerk sells, one item per sale.
-define(CLERKS, [{"anna",  ["apple", "apple", "pear"]},
                 {"ben",   ["apple", "plum"]},
                 {"chloe", ["apple"]}]).

%% RETURN: never; the VM halts with 0 after the command 'Argv' names and
%%         '<hwut-end>'; with 1, where the database does not stand, a sale
%%         failed, or 'Argv' names no command.
main(Argv) ->
    case Argv of
        ["deliver", Path | _] -> deliver(Path);
        ["sell" | _]          -> sell();
        ["report" | _]        -> report();
        _                     -> io:format("choices: sell, report~n"), halt(1)
    end,
    io:format("<hwut-end>~n").

%% RETURN: ok, the shop's database stands; never else: halts with 1, saying
%%         so on stderr -- 'on_entry' writes it.
connect() ->
    case filelib:is_regular(db_path()) of
        true  -> ok;
        false -> io:put_chars(standard_error,
                              ["shop.erl: no ", db_path(), " -- 'on_entry' writes it; by hand: "
                               "'hwut.execute fixture open'\n"]),
                 halt(1)
    end.

%% RETURN: ok, the stock of 'Item' was changed by 'Delta' and journalled, in
%%         one transaction; {error, Text}, else.
move(Item, Delta, Source) ->
    case db_begin() of
        {ok, Db}             -> db_commit(db_move(Db, Item, Delta, Source));
        {error, _} = Error   -> Error
    end.

%% RETURN: ok; the delivery note in 'Path' is booked and printed.
deliver(Path) ->
    {ok, Text} = file:read_file(Path),
    #{<<"note">> := Note, <<"supplier">> := Supplier, <<"lines">> := Lines} = json_object(Text),
    connect(),
    {ok, Db0} = db_begin(),
    db_commit(lists:foldl(fun(#{<<"item">> := Item, <<"qty">> := Qty}, Db) ->
                                  db_move(Db, binary_to_list(Item), Qty, binary_to_list(Note))
                          end, Db0, Lines)),
    io:format("delivery note ~ts from ~ts:~n", [Note, Supplier]),
    [io:format("    ~ts +~b~n", [string:pad(Item, 6), Qty])
     || #{<<"item">> := Item, <<"qty">> := Qty} <- Lines],
    ok.

%% RETURN: ok; three clerks sell at once, a process each; every sale is
%%         printed. Halts with 1 where a sale failed, the reason on stderr.
sell() ->
    connect(),
    Self  = self(),
    Clerk = fun(Name, Items) ->
                    fun() ->
                            [case move(Item, -1, Name) of
                                 ok              -> Self ! {sale, Item ++ ";1"};
                                 {error, Reason} -> Self ! {failed, Name ++ ": " ++ Reason}, exit(normal)
                             end || Item <- Items]
                    end
            end,
    Refs = [monitor(process, spawn(Clerk(Name, Items))) || {Name, Items} <- ?CLERKS],
    [receive {'DOWN', Ref, process, _, _} -> ok end || Ref <- Refs],
    {Sales, Failures} = mailbox([], []),
    Failures == [] orelse begin
                              io:put_chars(standard_error, ["shop.erl: a sale failed -- ",
                                                            lists:join("; ", Failures), "\n"]),
                              halt(1)
                          end,
    io:format("sales, item;qty -- in the order the clerks booked them:~n"),
    io:format("##! table unordered sep={;}~n"),
    [io:format("~s~n", [Row]) || Row <- Sales],
    io:format("####~n").

%% RETURN: {Sales, Failures}, every 'sale' and 'failed' message in the
%%         mailbox, each in the order it arrived.
mailbox(Sales, Failures) ->
    receive
        {sale, Row}     -> mailbox([Row | Sales], Failures);
        {failed, Text}  -> mailbox(Sales, [Text | Failures])
    after 0 -> {lists:reverse(Sales), lists:reverse(Failures)}
    end.

%% RETURN: ok; prints the stock and the frame log; writes 'stock.csv'.
report() ->
    connect(),
    #{stock := Stock} = db_read(),
    db_trace("SELECT item, qty FROM stock ORDER BY qty, item"),
    Here = filename:dirname(filename:absname(escript:script_name())),
    ok = file:write_file(filename:join(Here, "stock.csv"),
                         ["item;qty\n", [io_lib:format("~s;~b~n", [I, Q]) || {I, Q} <- lists:sort(maps:to_list(Stock))]]),
    io:format("stock, item;qty (also written to stock.csv):~n"),
    io:format("##! table key=0 sep={;}~n"),
    [io:format("~s;~b~n", [I, Q]) || {Q, I} <- lists:sort([{Q, I} || {I, Q} <- maps:to_list(Stock)])],
    io:format("####~n"),
    {ok, Log} = file:read_file(log_path()),
    Lines = [string:trim(L, trailing) || L <- string:split(Log, "\n", all), L =/= <<>>],
    Mine  = fun(L) -> string:find(L, "shop.erl report") =/= nomatch end,
    io:format("the frame, around the delivery and the sale:~n"),
    io:format("##! potpourri~n"),
    [io:format("~ts~n", [L]) || L <- Lines, not Mine(L)],
    io:format("####~n"),
    [io:format("~ts~n", [L]) || L <- Lines, Mine(L)],
    ok.

%% ____________________________________________________________________________
%% A JSON READER for the delivery note: OTP 25 has no 'json' module (27
%% has). Objects, arrays, strings without escapes, integers -- what a note
%% holds; anything else crashes the run.
%%
%% RETURN: map, the JSON object 'Text' holds; its keys and strings binaries.
json_object(Text) ->
    {Value, Rest} = json_value(skip(Text)),
    <<>> = skip(Rest),
    true = is_map(Value),
    Value.

%% RETURN: binary, 'Text' without the white space it begins with.
skip(<<C, Rest/binary>>) when C == $\s; C == $\t; C == $\n; C == $\r -> skip(Rest);
skip(Text) -> Text.

%% RETURN: {Value, Rest}, the JSON value 'Text' begins with, and what follows.
json_value(<<${, Rest/binary>>) -> json_members(skip(Rest), #{});
json_value(<<$[, Rest/binary>>) -> json_items(skip(Rest), []);
json_value(<<$", Rest/binary>>) ->
    [String, After] = binary:split(Rest, <<"\"">>),
    {String, After};
json_value(Text) ->
    {match, [Digits]} = re:run(Text, "^-?[0-9]+", [{capture, first, binary}]),
    {binary_to_integer(Digits), binary:part(Text, byte_size(Digits), byte_size(Text) - byte_size(Digits))}.

%% RETURN: {Map, Rest}, the object's members after '{' put into 'Map'.
json_members(<<$}, Rest/binary>>, Map) -> {Map, Rest};
json_members(<<$,, Rest/binary>>, Map) -> json_members(skip(Rest), Map);
json_members(Text, Map) ->
    {Key, AfterKey}   = json_value(Text),
    <<$:, AfterColon/binary>> = skip(AfterKey),
    {Value, Rest}     = json_value(skip(AfterColon)),
    json_members(skip(Rest), Map#{Key => Value}).

%% RETURN: {List, Rest}, the array's items after '[' ('Items' reversed).
json_items(<<$], Rest/binary>>, Items) -> {lists:reverse(Items), Rest};
json_items(<<$,, Rest/binary>>, Items) -> json_items(skip(Rest), Items);
json_items(Text, Items) ->
    {Value, Rest} = json_value(Text),
    json_items(skip(Rest), [Value | Items]).
