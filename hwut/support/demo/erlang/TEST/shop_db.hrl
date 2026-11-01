%% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%%_____________________________________________________________________________
%%
%% THE SHOP'S DATABASE -- no test, a helper of 'shop.erl' and 'fixture.erl'.
%%
%% Erlang/OTP carries no SQLite, as Python carries 'sqlite3'. What the shop
%% needs of it is small and is had here from the file system: the database
%% is ONE FILE OF ERLANG TERMS, 'TMP/shop.db' -- the tables 'opening' and
%% 'stock' as maps item -> quantity, 'journal' as a list of {Item, Delta,
%% Source} -- and a transaction is SQLite's 'BEGIN IMMEDIATE':
%%
%%     db_begin()     takes the writer's lock, 'TMP/shop.db.lock', created
%%                    exclusively (O_EXCL: of all who try at once, one
%%                    succeeds); who finds it taken waits and tries again,
%%                    for 10 s, then fails with 'database is locked' -- as
%%                    SQLite's 'timeout=10'
%%     db_commit(Db)  writes the tables beside the file and renames them
%%                    onto it -- a reader sees the old file or the new,
%%                    never half of one -- and gives the lock back
%%
%% So one writer at a time holds the database, across processes of one VM
%% and across VMs alike: what 'collision' in 'hwut.conf' is about. Every
%% step is logged on stderr ('db: ...'), as the Python shop logs its SQL.
%%_____________________________________________________________________________

-define(DB_TIMEOUT_MS, 10000).

%% Each includer uses part of the helpers: what it does not is no fault.
-compile([nowarn_unused_function]).

%% RETURN: string, the path of 'Name' in this directory's 'TMP'.
db_tmp(Name) ->
    filename:join([filename:dirname(filename:absname(escript:script_name())), "TMP", Name]).

%% RETURN: string, the database's path.
db_path() -> db_tmp("shop.db").

%% RETURN: string, the frame log's path.
log_path() -> db_tmp("frame.log").

%% RETURN: ok; 'Text' is logged on stderr, a line of its own.
db_trace(Text) -> io:put_chars(standard_error, ["db: ", Text, "\n"]).

%% RETURN: map, the tables as they stand: #{opening, stock, journal}.
db_read() ->
    {ok, [Db]} = file:consult(db_path()),
    Db.

%% RETURN: ok, the database 'Db' was written whole, under the name
%%         'Name', unique to this process, then renamed onto the database.
db_write(Db) ->
    Part = db_path() ++ "." ++ os:getpid() ++ "." ++ integer_to_list(erlang:unique_integer([positive])),
    ok = file:write_file(Part, io_lib:format("~p.~n", [Db])),
    ok = file:rename(Part, db_path()).

%% RETURN: {ok, Db}, the lock is this process's and 'Db' the tables;
%%         {error, "database is locked"}, the lock stayed taken for 10 s.
db_begin() ->
    db_trace("BEGIN IMMEDIATE"),
    db_begin(erlang:monotonic_time(millisecond) + ?DB_TIMEOUT_MS).

%% RETURN: as 'db_begin/0', trying until 'Deadline'.
db_begin(Deadline) ->
    case file:open(db_path() ++ ".lock", [write, exclusive]) of
        {ok, Fd} -> ok = file:close(Fd),
                    {ok, db_read()};
        {error, eexist} ->
            case erlang:monotonic_time(millisecond) > Deadline of
                true  -> {error, "database is locked"};
                false -> timer:sleep(rand:uniform(5)), db_begin(Deadline)
            end
    end.

%% RETURN: ok; 'Db' is written, and the lock given back.
db_commit(Db) ->
    db_write(Db),
    db_trace("COMMIT"),
    ok = file:delete(db_path() ++ ".lock").

%% RETURN: map, 'Db' with the stock of 'Item' changed by 'Delta' and the
%%         movement journalled, from 'Source'.
db_move(Db = #{stock := Stock, journal := Journal}, Item, Delta, Source) ->
    db_trace(io_lib:format("UPDATE stock SET qty = qty + ~b WHERE item = '~s'", [Delta, Item])),
    db_trace(io_lib:format("INSERT INTO journal VALUES ('~s', ~b, '~s')", [Item, Delta, Source])),
    Db#{stock   := maps:update_with(Item, fun(Q) -> Q + Delta end, Stock),
        journal := Journal ++ [{Item, Delta, Source}]}.
