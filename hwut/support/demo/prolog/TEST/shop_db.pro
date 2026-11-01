/*  SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
    ___________________________________________________________________________

    PURPOSE: THE SHOP'S DATABASE, for 'shop.pro' and 'fixture.pro' -- no
             test, a helper. SQLite through 'shop_db4pl.c', a foreign library
             of SWI-Prolog: Prolog's own library has no SQLite, as Python's
             has 'sqlite3'.

        db_connect(Path, [timeout_ms(10000), trace(true)], Db),
        db_execute(Db, "UPDATE stock SET qty = qty + ? WHERE item = ?", [1, "pear"]),
        db_rows(Db, "SELECT item, qty FROM stock", [], Rows),   % [["pear", 6], ...]
        db_close(Db)

    Statements run in autocommit, as Python's 'isolation_level=None': a
    transaction is the caller's 'BEGIN IMMEDIATE' ... 'COMMIT'. A fault
    raises error(sqlite_error(Message), _), Message SQLite's own ('database
    is locked', ...). 'trace(true)' writes every statement to stderr as
    'sql: ...', as Python's 'set_trace_callback' does in 'shop.py'.

    THE FOREIGN LIBRARY IS BUILT ON LOAD: 'make' in this directory makes
    'shop_db4pl.so' current (see 'Makefile'), then it is loaded.
    ___________________________________________________________________________
*/
:- module(shop_db, [db_connect/3, db_execute/3, db_rows/4, db_close/1]).
:- use_module(library(process)).
:- use_module(library(option)).

:- prolog_load_context(directory, Dir), asserta(here(Dir)).

%   foreign_built
%   RETURN: true, once 'make' has made 'shop_db4pl.so' current and it is
%           loaded; make's own output is kept off stdout -- stdout is the
%           test's; the compiler's complaints stand on stderr. Raises
%           error(sqlite_error(_), _) where it could not be built.
foreign_built :-
    here(Dir),
    process_create(path(make), ['-s', '-C', Dir, 'shop_db4pl.so'],
                   [stdout(null), process(Pid)]),
    process_wait(Pid, Status),
    (   Status == exit(0)
    ->  directory_file_path(Dir, 'shop_db4pl.so', Library),
        load_foreign_library(Library)
    ;   throw(error(sqlite_error("'shop_db4pl.so' could not be built (make: see stderr)"), _))
    ).

:- initialization(foreign_built, now).

%   db_connect(+Path, +Options, -Db)
%   RETURN: Db, a connection to the database 'Path', if success; raises
%           sqlite_error else. Options: timeout_ms(Ms) (5000), how long a
%           statement waits for another writer's lock; trace(Bool) (false).
db_connect(Path, Options, db(Handle)) :-
    option(timeout_ms(Ms), Options, 5000),
    option(trace(Trace), Options, false),
    ( Trace == true -> T = 1 ; T = 0 ),
    '$db_open'(Path, Ms, T, Handle).

%   db_execute(+Db, +Sql, +Parameters)
%   RETURN: true, once the one statement 'Sql' ran, its '?' bound to
%           'Parameters' (integers and texts); raises sqlite_error else.
db_execute(Db, Sql, Parameters) :- db_rows(Db, Sql, Parameters, _).

%   db_rows(+Db, +Sql, +Parameters, -Rows)
%   RETURN: Rows, the rows of the one statement 'Sql', each a list of its
%           columns -- integers, floats, strings, 'null'; raises sqlite_error
%           else.
db_rows(db(Handle), Sql, Parameters, Rows) :- '$db_execute'(Handle, Sql, Parameters, Rows).

%   db_close(+Db)
%   RETURN: true; the connection is closed and names nothing from now on.
db_close(db(Handle)) :- '$db_close'(Handle).
