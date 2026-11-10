% @hwut {
%     title     = "Demo: a shop's stock -- what the directory's hwut.conf arranges"
%     tolerance { stderr_ignored = true }
%     choices {
%         sell   { features = ["demo-prolog+cover-unordered-table", "demo-prolog+cover-stderr-ignored", "demo-prolog+cover-collision"] }
%         report { features = ["demo-prolog+cover-output-file", "demo-prolog+cover-keyed-table-separator", "demo-prolog+cover-dependency",
%                              "demo-prolog+cover-frame-scripts", "demo-prolog+cover-test-scripts", "demo-prolog+cover-stderr-ignored"]
%                  output   = ["<stdout>", "stock.csv"] }
%     }
% }
%
/*
______________________________________________________________________________
SUBJECT  the stock of a small shop, kept in an SQLite database: a delivery
         comes in, three clerks sell at once, and the stock is reported.
REQUIREMENT  Every movement of the stock is journalled, so that the stock
             always ADDS UP: opening quantity plus the journal's movements.

THE DIRECTORY ARRANGES WHAT NO SINGLE TEST CAN -- in 'hwut.conf' beside
this file, read it first. hwut, when it enters this directory:

    on_entry        'fixture.pro open': a fresh 'TMP/shop.db', stocked
    on_before_test  'fixture.pro check before $HWUT_TEST $HWUT_CHOICE',
    on_after_test   'fixture.pro check after ...': around every test run,
                    whether the stock adds up, into 'TMP/frame.log' --
                    hwut sets the two variables for the run
    on_exit         'fixture.pro close'
    apps            'delivery.json' is a test, though it carries no
                    header: JSON has no comment to carry one. 'admit'
                    takes it out of the files hwut ignores by default
                    ('*.json'); 'execute' says how it is run --
                    'swipl shop.pro deliver delivery.json'.
    collision       'delivery.json' and 'shop.pro sell' both write the
                    database. SQLite lets one writer at a time hold the
                    file; one that waits too long fails with 'database
                    is locked'. hwut never runs the two at once.
    dependency      'shop.pro report' runs after both, whatever their
                    verdict: it reports what they left.

STDERR  Every SQL statement is logged on stderr, as a server would. A
word on stderr fails a run ('unexpected stderr') unless the header says
'stderr_ignored = true': the words there are on purpose, and no error.

CHOICES

sell     three clerks sell at once, each in a thread of its own. The sales
         are printed as '##! table unordered sep={;}': rows of 'item;qty',
         in any order -- and no column is a key, 'apple;1' stands four
         times.

report   the stock, as '##! table key=0 sep={;}', and the same rows
         written to 'stock.csv': 'output' names the file, hwut reads it
         after the run and compares it with its own GOOD. Then the frame
         log of the shop's tests: what 'on_before_test' and 'on_after_test'
         found around the delivery and the sale ('##! potpourri': which
         ran first is free), and before this report.

deliver  (no choice -- 'execute' of 'delivery.json' calls it) books a
         delivery note: every line on the stock and into the journal, in
         one transaction.

PROLOG'S WAYS: SQLite is reached through 'shop_db.pro', a foreign library
of SWI-Prolog built here by 'make' ('Makefile'); a clerk is a thread with a
connection of its own.
______________________________________________________________________________
*/
:- encoding(utf8).
:- use_module(library(http/json)).
:- use_module('shop_db.pro').
:- initialization(main, main).

:- prolog_load_context(directory, Here), asserta(here(Here)).

db_path(Path)  :- here(H), directory_file_path(H, 'TMP/shop.db', Path).
log_path(Path) :- here(H), directory_file_path(H, 'TMP/frame.log', Path).

%  What each clerk sells, one item per sale.
clerk(anna,  [apple, apple, pear]).
clerk(ben,   [apple, plum]).
clerk(chloe, [apple]).

%   connect(-Db)
%   RETURN: Db, a connection to the shop's database, every statement it
%           executes logged on stderr. Halts with 1 where the database does
%           not stand: 'on_entry' writes it.
connect(Db) :-
    db_path(Path),
    (   exists_file(Path)
    ->  db_connect(Path, [timeout_ms(10000), trace(true)], Db)
    ;   format(user_error, "shop.pro: no ~w -- 'on_entry' writes it; by hand: 'hwut.execute fixture open'~n", [Path]),
        halt(1)
    ).

%   move(+Db, +Item, +Delta, +Source)
%   RETURN: true. Changes the stock of 'Item' by 'Delta' and journals it, in
%           one transaction.
move(Db, Item, Delta, Source) :-
    db_execute(Db, "BEGIN IMMEDIATE", []),
    db_execute(Db, "UPDATE stock SET qty = qty + ? WHERE item = ?", [Delta, Item]),
    db_execute(Db, "INSERT INTO journal VALUES (?, ?, ?)", [Item, Delta, Source]),
    db_execute(Db, "COMMIT", []).

%   deliver(+Path)
%   RETURN: true. Books the delivery note in 'Path' and prints it.
deliver(Path) :-
    setup_call_cleanup(open(Path, read, In, [encoding(utf8)]),
                       json_read_dict(In, Note, [value_string_as(string)]),
                       close(In)),
    connect(Db),
    db_execute(Db, "BEGIN IMMEDIATE", []),
    forall(member(Line, Note.lines),
           ( db_execute(Db, "UPDATE stock SET qty = qty + ? WHERE item = ?", [Line.qty, Line.item]),
             db_execute(Db, "INSERT INTO journal VALUES (?, ?, ?)", [Line.item, Line.qty, Note.note]) )),
    db_execute(Db, "COMMIT", []),
    format("delivery note ~s from ~s:~n", [Note.note, Note.supplier]),
    forall(member(Line, Note.lines),
           format("    ~|~s~t~6+ +~d~n", [Line.item, Line.qty])).

:- dynamic sale/1, failure/1.

%   sell
%   RETURN: true. Three clerks sell at once; prints every sale.
sell :-
    connect(Db0), db_close(Db0),
    findall(Id, ( clerk(Name, Items), thread_create(clerk_sells(Name, Items), Id, []) ), Ids),
    maplist(thread_join, Ids),
    (   findall(F, failure(F), Failures), Failures \== []
    ->  atomic_list_concat(Failures, '; ', Text),
        format(user_error, "shop.pro: a sale failed -- ~w~n", [Text]),
        halt(1)
    ;   true
    ),
    format("sales, item;qty -- in the order the clerks booked them:~n"),
    format("##! table unordered sep={;}~n"),
    forall(sale(Row), format("~s~n", [Row])),
    format("####~n").

clerk_sells(Name, Items) :-
    catch(( connect(Db),
            forall(member(Item, Items),
                   ( move(Db, Item, -1, Name),
                     format(string(Row), "~w;1", [Item]),
                     with_mutex(shop_sale, assertz(sale(Row))) )),
            db_close(Db) ),
          Error,
          ( message_to_codes(Error, Text), format(string(F), "~w: ~s", [Name, Text]),
            assertz(failure(F)) )).

message_to_codes(error(sqlite_error(M), _), Codes) :- !, string_codes(M, Codes).
message_to_codes(E, Codes) :- format(codes(Codes), "~q", [E]).

%   report
%   RETURN: true. Prints the stock and the frame log; writes 'stock.csv'.
report :-
    connect(Db),
    db_rows(Db, "SELECT item, qty FROM stock ORDER BY qty, item", [], Rows),
    here(H), directory_file_path(H, 'stock.csv', Csv),
    msort(Rows, Sorted),
    setup_call_cleanup(open(Csv, write, Out, [encoding(utf8)]),
                       ( format(Out, "item;qty~n", []),
                         forall(member([Item, Qty], Sorted), format(Out, "~s;~d~n", [Item, Qty])) ),
                       close(Out)),
    format("stock, item;qty (also written to stock.csv):~n"),
    format("##! table key=0 sep={;}~n"),
    forall(member([Item, Qty], Rows), format("~s;~d~n", [Item, Qty])),
    format("####~n"),
    log_path(Log),
    read_file_to_string(Log, Text, [encoding(utf8)]),
    split_string(Text, "\n", "", Lines0),
    exclude(==(""), Lines0, Lines),
    format("the frame, around the delivery and the sale:~n"),
    format("##! potpourri~n"),
    forall(( member(L, Lines), \+ sub_string(L, _, _, _, "shop.pro report") ), format("~s~n", [L])),
    format("####~n"),
    forall(( member(L, Lines), sub_string(L, _, _, _, "shop.pro report") ), format("~s~n", [L])).

main :-
    set_stream(user_output, encoding(utf8)),
    current_prolog_flag(argv, Argv),
    (   Argv = [deliver, Path] -> deliver(Path)
    ;   Argv = [sell]          -> sell
    ;   Argv = [report]        -> report
    ;   format("choices: sell, report~n"),
        halt(1)
    ),
    format("<hwut-end>~n").
