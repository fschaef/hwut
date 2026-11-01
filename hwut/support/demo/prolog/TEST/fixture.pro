#! /usr/bin/env swipl
/*
______________________________________________________________________________
THE SHOP'S FIXTURE -- no test, a helper the directory's 'hwut.conf' calls.

    fixture.pro open            a fresh 'TMP/shop.db', stocked as below, and
                                an empty 'TMP/frame.log' ('on_entry', and
                                'hwut.execute fixture open')
    fixture.pro close           both removed ('on_exit')
    fixture.pro check <when> <app> [<choice>]
                                'when' is 'before' or 'after': whether the
                                stock adds up around the test run '<app>
                                <choice>', appended to 'TMP/frame.log'
                                ('on_before_test', 'on_after_test')

'hwut.conf' passes '<app>' and '<choice>' as '$HWUT_TEST $HWUT_CHOICE',
which hwut sets for the run the check stands around; a test without
choices has none. 'check' concerns the shop's tests alone. The stock
ADDS UP where every item's quantity is its opening quantity plus every
movement of the journal.

Loading 'shop_db.pro' builds its foreign library where it is not current
('make'): 'on_entry' runs first, so the tests find it built.
______________________________________________________________________________
*/
:- encoding(utf8).
:- use_module('shop_db.pro').
:- initialization(main, main).

:- prolog_load_context(directory, Here), asserta(here(Here)).

db_path(Path)  :- here(H), directory_file_path(H, 'TMP/shop.db', Path).
log_path(Path) :- here(H), directory_file_path(H, 'TMP/frame.log', Path).

opening(apple, 10).
opening(pear,   5).
opening(plum,   5).

shop_test("delivery.json").
shop_test("shop.pro").

remove_if_there(Path) :- ( exists_file(Path) -> delete_file(Path) ; true ).

%   open_shop
%   RETURN: true. Writes a fresh, stocked database and an empty log.
open_shop :-
    db_path(Db), log_path(Log),
    file_directory_name(Db, Dir), make_directory_path(Dir),
    remove_if_there(Db), remove_if_there(Log),
    setup_call_cleanup(db_connect(Db, [], C),
        ( db_execute(C, "BEGIN", []),
          db_execute(C, "CREATE TABLE opening (item TEXT PRIMARY KEY, qty INTEGER)", []),
          db_execute(C, "CREATE TABLE stock   (item TEXT PRIMARY KEY, qty INTEGER)", []),
          db_execute(C, "CREATE TABLE journal (item TEXT, delta INTEGER, source TEXT)", []),
          forall(opening(Item, Qty),
                 ( db_execute(C, "INSERT INTO opening VALUES (?, ?)", [Item, Qty]),
                   db_execute(C, "INSERT INTO stock   VALUES (?, ?)", [Item, Qty]) )),
          db_execute(C, "COMMIT", []) ),
        db_close(C)),
    setup_call_cleanup(open(Log, write, S), true, close(S)).

%   close_shop
%   RETURN: true. Removes the database and the log.
close_shop :-
    db_path(Db), log_path(Log),
    remove_if_there(Db), remove_if_there(Log).

%   adds_up
%   RETURN: success, if every item's stock is its opening quantity plus its
%           journal's movements;
%           failure, else.
adds_up :-
    db_path(Db),
    setup_call_cleanup(db_connect(Db, [], C),
        db_rows(C, "SELECT o.item, o.qty + COALESCE(SUM(j.delta), 0), s.qty
                      FROM opening o JOIN stock s ON s.item = o.item
                      LEFT JOIN journal j ON j.item = o.item GROUP BY o.item", [], Rows),
        db_close(C)),
    forall(member([_, Expected, Got], Rows), Expected =:= Got).

%   check(+When, +Test, +Choice)
%   RETURN: true. Appends one line to the log for a shop test run.
check(When, Test, Choice) :-
    (   shop_test(Test)
    ->  ( Choice == "" -> Run = Test ; atomic_list_concat([Test, ' ', Choice], Run) ),
        ( adds_up -> Verdict = "stock adds up" ; Verdict = "STOCK BROKEN" ),
        log_path(Log),
        setup_call_cleanup(open(Log, append, S, [encoding(utf8)]),
                           format(S, "~|~w~t~6+ ~|~w~t~15+ ~s~n", [When, Run, Verdict]),
                           close(S))
    ;   true
    ).

main :-
    current_prolog_flag(argv, Argv0),
    maplist([A, S]>>atom_string(A, S), Argv0, Argv),
    (   Argv = ["open"]                    -> open_shop
    ;   Argv = ["close"]                   -> close_shop
    ;   Argv = ["check", When, Test]       -> check(When, Test, "")
    ;   Argv = ["check", When, Test, Choice] -> check(When, Test, Choice)
    ;   format(user_error, "usage: fixture.pro open | close | check before|after <app> <choice>~n", []),
        halt(2)
    ).
