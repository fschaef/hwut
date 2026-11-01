#! /usr/bin/env escript
%%_____________________________________________________________________________
%% THE SHOP'S FIXTURE -- no test, a helper the directory's 'hwut.conf' calls.
%%
%%     fixture.erl open            a fresh 'TMP/shop.db', stocked as below, and
%%                                 an empty 'TMP/frame.log' ('on_entry', and
%%                                 'hwut.execute fixture open')
%%     fixture.erl close           both removed ('on_exit')
%%     fixture.erl check <when> <app> [<choice>]
%%                                 'when' is 'before' or 'after': whether the
%%                                 stock adds up around the test run '<app>
%%                                 <choice>', appended to 'TMP/frame.log'
%%                                 ('on_before_test', 'on_after_test')
%%
%% 'hwut.conf' passes '<app>' and '<choice>' as '$HWUT_TEST $HWUT_CHOICE',
%% which hwut sets for the run the check stands around; a test without
%% choices has none. 'check' concerns the shop's tests alone. The stock
%% ADDS UP where every item's quantity is its opening quantity plus every
%% movement of the journal. The database is 'shop_db.hrl's.
%%_____________________________________________________________________________
%% INTERPRETED, not '-mode(compile)': it runs around every test of the
%% directory, twice, and compiling it would cost each run more than it does.
-include("shop_db.hrl").

-define(OPENING, #{"apple" => 10, "pear" => 5, "plum" => 5}).
-define(SHOP_TESTS, ["delivery.json", "shop.erl"]).

%% RETURN: never; the VM halts with 0 once the command 'Argv' names was
%%         done; with 2, naming the commands on stderr, else.
main(Argv) ->
    case Argv of
        ["open"]                    -> open_shop();
        ["close"]                   -> close_shop();
        ["check", When, Test]       -> check(When, Test, "");
        ["check", When, Test, C | _] -> check(When, Test, C);
        _ -> io:put_chars(standard_error,
                          "usage: fixture.erl open | close | check before|after <app> <choice>\n"),
             halt(2)
    end.

%% RETURN: ok; a fresh, stocked database and an empty log are written --
%%         a writer's lock a broken run left behind removed.
open_shop() ->
    ok = filelib:ensure_dir(db_path()),
    [file:delete(P) || P <- [db_path(), db_path() ++ ".lock", log_path()]],
    db_write(#{opening => ?OPENING, stock => ?OPENING, journal => []}),
    ok = file:write_file(log_path(), <<>>).

%% RETURN: ok; the database, its lock and the log are removed.
close_shop() ->
    [file:delete(P) || P <- [db_path(), db_path() ++ ".lock", log_path()]],
    ok.

%% RETURN: true, if every item's stock is its opening quantity plus its
%%         journal's movements;
%%         false, else.
adds_up() ->
    #{opening := Opening, stock := Stock, journal := Journal} = db_read(),
    lists:all(fun({Item, Qty}) ->
                      Qty + lists:sum([D || {I, D, _} <- Journal, I == Item]) == maps:get(Item, Stock)
              end, maps:to_list(Opening)).

%% RETURN: ok; one line is appended to the log for a run of a shop test.
check(When, Test, Choice) ->
    case lists:member(Test, ?SHOP_TESTS) of
        false -> ok;
        true  ->
            Run = string:trim(Test ++ " " ++ Choice),
            ok  = file:write_file(log_path(),
                                  io_lib:format("~ts ~ts ~s~n",
                                                [string:pad(When, 6), string:pad(Run, 15), case adds_up() of true  -> "stock adds up";
                                                                              false -> "STOCK BROKEN" end]),
                                  [append])
    end.
