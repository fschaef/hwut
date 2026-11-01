/*  SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
    ___________________________________________________________________________

    PURPOSE: The front end of a HWUT test application -- the port of
             'python/hwut_runner.py'. A Prolog test ends in one call:

        :- use_module('../hwut_runner.pro').
        :- initialization(main, main).

        main :- hwut_runner_run("my title", [plain-plain, tricky-tricky], []).

    The command line (SWI's 'argv' flag: what follows the file) selects the
    mode:

        swipl t.pro --hwut-info     the info block; exit 0
        swipl t.pro <choice>        normal mode: one choice; its output on
                                    stdout and stderr, then '<hwut-end>'.
                                    '-' runs a choice-less application
        swipl t.pro --interactive   interactive mode: choices are started by
                                    commands on stdin (the protocol of
                                    'hwut_runner.py', see 'mode_interactive')
        swipl t.pro                 the choice-less test; where the
                                    application has choices, refused, naming
                                    them -- the menu is 'hwut.play's (E-189)

    THE CHOICE MAP is a list of 'Name-Goal' pairs, each goal called in the
    caller's module; a choice-less application gives ONE goal instead of a
    list. The options:

        happy(Patterns)     the info block's 'HAPPY:' lines (texts)
        same(true)          the info block carries 'SAME;'
        parallel(process)   interactive mode runs the choices concurrently

    A CHOICE ENDS by succeeding. One that fails or raises ends with status 1,
    the reason on stderr (Python's traceback); 'halt(N)' in a choice ends it
    with N. In interactive mode every choice runs in a CHILD PROCESS (fork),
    so a 'halt' ends that choice alone, never the session.
    ___________________________________________________________________________
*/
:- module(hwut_runner,
          [ hwut_runner_run/3,                  % +Title, :ChoiceMap, +Options
            hwut_runner_levenshtein_distance/3, % +A, +B, -Distance
            hwut_runner_levenshtein_best_match/3 % +Needle, +Haystack, -Best
          ]).
:- encoding(utf8).
:- use_module(library(unix)).
:- use_module(library(lists)).
:- use_module(library(option)).

:- meta_predicate hwut_runner_run(+, :, +).

%  A PROCESS THAT FORKS HOLDS NO THREADS: SWI's garbage collector of atoms
%  and clauses runs in the main thread here, not in a thread of its own,
%  so every child of interactive mode is a whole copy (and 'halt' names
%  no thread that would not die).
:- set_prolog_flag(gc_thread, false).

%!  hwut_runner_run(+Title, :ChoiceMap, +Options) is det.
%
%   RETURN: true, upon the end of the mode the command line selects; a
%           refusal halts with status 1, '--hwut-info' with 0 (see the head).
hwut_runner_run(Title, Module:Map, Options) :-
    set_stream(user_output, encoding(utf8)),
    set_stream(user_error,  encoding(utf8)),
    runner(Title, Module, Map, Options, Runner),
    current_prolog_flag(argv, Argv),
    ( Argv = [Word|_] -> true ; Word = '$no_word' ),
    dispatch(Word, Runner).

%   runner(+Title, +Module, +Map, +Options, -Runner)
%   RETURN: the runner as one term
%           -- runner(Title, Choices, Sorted, Happy, Same, Parallel), Choices a list
%           of Name-Module:Goal, Sorted the names in Python's order ('-' alone for a
%           choice-less application).
runner(Title, M, Map, Options, runner(Title, Choices, Sorted, Happy, Same, Parallel)) :-
    (   is_list(Map)
    ->  findall(N-(M:G), member(N-G, Map), Choices),
        findall(N, member(N-_, Choices), Names), msort(Names, Sorted)
    ;   Choices = [('-')-(M:Map)], Sorted = ['-']
    ),
    option(happy(Happy0), Options, []),
    ( is_list(Happy0) -> Happy = Happy0 ; Happy = [Happy0] ),
    ( option(same(true), Options) -> Same = true ; Same = false ),
    ( option(parallel(process), Options) -> Parallel = process ; Parallel = none ).

none_f(runner(_, [('-')-_], _, _, _, _)).

dispatch(W, R) :- memberchk(W, ['-h', '--hi', '--hwut-info', '--sos', '--wtf']), !,
    forall(info_line(R, L), format("~w~n", [L])), halt(0).
dispatch('--interactive', R) :- !, mode_interactive(R).
dispatch('$no_word', R) :- !,
    (   none_f(R) -> R = runner(_, [_-G], _, _, _, _), run_one(G)
    ;   choice_list_text(R, T),
        format("error: a choice is required: ~w -- name one, or let 'hwut.play' ask.~n", [T]),
        halt(1)
    ).
dispatch(W, R) :-
    R = runner(_, Choices, Sorted, _, _, _),
    (   memberchk(W-G, Choices) -> run_one(G)
    ;   none_f(R)
    ->  format("error: '~w': this application has no choices -- call it without one.~n", [W]),
        halt(1)
    ;   format("error: choice '~w' not available.~n", [W]),
        choice_list_text(R, T),
        format("error: available: ~w.~n", [T]),
        (   hwut_runner_levenshtein_best_match(W, Sorted, Best)
        ->  format("error: did you mean '~w'?~n", [Best])
        ;   true
        ),
        halt(1)
    ).

%   run_one(+Goal)
%   RETURN: normal mode -- the choice, then the terminal token (R-70).
run_one(G) :-
    choice_status(G, Status),
    (   Status =:= 0 -> format("<hwut-end>~n"), flush_output
    ;   halt(Status)
    ).

%!  choice_status(:Goal, -Status) is det.
%
%   RETURN: Status 0, 'Goal' succeeded;
%           1, it failed or raised -- the reason written on stderr, as
%              Python's traceback is.
choice_status(G, Status) :-
    catch(( call(G) -> Status = 0
          ; print_message(error, format("choice failed: ~q", [G])), Status = 1 ),
          E,
          ( print_message(error, E), Status = 1 )),
    flush_output(user_output), flush_output(user_error).

%!  info_line(+Runner, -Line) is nondet.
%
%   RETURN: Line, one line of the info block after the other: title, CHOICES,
%           HAPPY patterns, SAME, INTERACTIVE.
info_line(runner(Title, _, _, _, _, _), L) :-
    text_to_string(Title, T),
    ( string_concat(_, ";", T) -> L = T ; string_concat(T, ";", L) ).
info_line(R, L) :-
    \+ none_f(R), choice_list_text(R, T), format(string(L), "CHOICES: ~w;", [T]).
info_line(runner(_, _, _, Happy, _, _), L) :-
    member(H, Happy), format(string(L), "HAPPY: ~w;", [H]).
info_line(runner(_, _, _, _, true, _), "SAME;").
info_line(_, "INTERACTIVE;").

choice_list_text(runner(_, _, Sorted, _, _, _), T) :-
    atomic_list_concat(Sorted, ', ', A), atom_string(A, T).

/* --------------------------------------------------------- interactive mode

   THE SESSION'S CHANNELS:
       stdin            DOWN: commands from the framework
       stdout           UP:   protocol replies -- the session's own fd 1
       per-choice sinks test output: two files named in the 'run' command

   NO CHOICE RUNS IN THE SESSION'S PROCESS: each runs in a child (fork) whose
   fd 1 and fd 2 are pointed at its sinks; so nothing but the protocol is
   written on the session's fd 1. Its fd 2 points at a stray sink.

   DOWN (one command per line):  run <choice> <sink-out> <sink-err> | info
                                 | quit | q | exit
   UP (one message per line):    done <choice> <status> | fail <choice>
                                 <reason> | info: <line> | bye
*/
mode_interactive(R) :-
    flush_output(user_output), flush_output(user_error),
    tmp_file_stream(text, StrayPath, Stray),
    dup(Stray, 2), close(Stray),
    nb_setval(hwut_runner_stray, StrayPath),
    session(R, [], Pending),
    drain(Pending),
    up("bye"),
    halt(0).

%   session(+Runner, +Pending0, -Pending)
%   RETURN: commands read and executed until
%           'quit' or the end of stdin; Pending the children of parallel mode.
session(R, P0, P) :-
    read_line_to_string(user_input, Line0),
    (   Line0 == end_of_file -> P = P0
    ;   split_string(Line0, " \t\r", " \t\r", Fields0),
        exclude(==(""), Fields0, Fields),
        (   Fields == [] -> session(R, P0, P)
        ;   interprete(Fields, R, P0, P1, Go),
            ( Go == true -> session(R, P1, P) ; P = P1 )
        )
    ).

%   interprete(+Fields, +Runner, +Pending0, -Pending, -Go)
%   RETURN: one DOWN command;
%           Go 'false' where the session ends.
interprete([Q], _, P, P, false) :- memberchk(Q, ["quit", "q", "exit"]), !.
interprete(["info"], R, P, P, true) :- !,
    forall(info_line(R, L), ( string_concat("info: ", L, U), up(U) )),
    up("done - 0").
interprete(["run", Token, Out, Err], R, P0, P, true) :- !,
    (   find_choice(Token, R, G)
    ->  R = runner(_, _, _, _, _, Parallel),
        run_into_sinks(Parallel, Token, G, Out, Err, P0, P)
    ;   format(string(U), "fail ~w unknown-choice", [Token]), up(U), P = P0
    ).
interprete(_, _, P, P, true) :- up("fail - bad-command").

%!  find_choice(+Token, +Runner, -Goal) is semidet.
%
%   RETURN: Goal, of the choice 'Token' names -- by name, by its decimal
%           index into the sorted list, or '-' for the choice-less test;
%           fails, else.
find_choice(Token, runner(_, Choices, Sorted, _, _, _), G) :-
    atom_string(A, Token),
    (   memberchk(A-G, Choices) -> true
    ;   string_codes(Token, Cs), Cs \== [], forall(member(C, Cs), code_type(C, digit)),
        number_codes(I, Cs), nth0(I, Sorted, Name), memberchk(Name-G, Choices)
    ).

%   run_into_sinks(+Parallel, +Token, +Goal, +Out, +Err, +Pending0, -Pending):
%   sequential -- the child is waited for and 'done' said here; parallel --
%   a WAITER child runs the choice in a grandchild and says 'done' itself
%   when it ends, so the session reads on (no thread, no WNOHANG: SWI's
%   'wait/2' blocks, and a forking process should hold no threads).
run_into_sinks(none, Token, G, Out, Err, P, P) :-
    flush_output(user_output), flush_output(user_error),
    fork(Pid),
    (   Pid == child -> child_run(G, Out, Err)
    ;   wait(Pid, Status), exit_code(Status, Code),
        format(string(U), "done ~w ~d", [Token, Code]), up(U)
    ).
run_into_sinks(process, Token, G, Out, Err, P, [Pid|P]) :-
    flush_output(user_output), flush_output(user_error),
    fork(Pid),
    (   Pid == child
    ->  fork(Grand),
        (   Grand == child -> child_run(G, Out, Err)
        ;   wait(Grand, Status), exit_code(Status, Code),
            format(string(U), "done ~w ~d", [Token, Code]), up(U),
            halt(0)
        )
    ;   true
    ).

%   child_run(+Goal, +Out, +Err)
%   RETURN: never returns -- fd 1 and fd 2 on the
%           sinks, the choice run, '<hwut-end>' after a normal return unless
%           HWUT_NO_TERMINAL is set (a pype owns stdout), halted with its status.
child_run(G, Out, Err) :-
    catch(( open(Out, write, O, [encoding(utf8)]), open(Err, write, E, [encoding(utf8)]),
            dup(O, 1), dup(E, 2), close(O), close(E) ),
          _, halt(1)),
    choice_status(G, Status),
    (   Status =:= 0, \+ getenv('HWUT_NO_TERMINAL', _)
    ->  format("<hwut-end>~n")
    ;   true
    ),
    flush_output(user_output), flush_output(user_error),
    halt(Status).

exit_code(exited(N), N) :- !.
exit_code(signaled(S), N) :- !, N is -S.
exit_code(_, 1).

%   drain(+Pending)
%   RETURN: every waiter of parallel mode has ended.
drain([]).
drain([Pid|Ps]) :- catch(wait(Pid, _), _, true), drain(Ps).

%   up(+Message)
%   RETURN: one line on the UP channel, flushed.
up(M) :- format(user_output, "~w~n", [M]), flush_output(user_output).

/* ------------------------------------------------------- the suggestion */

%!  hwut_runner_levenshtein_best_match(+Needle, +Haystack, -Best) is semidet.
%
%   RETURN: Best, the element of 'Haystack' least distant from 'Needle' --
%           the first of equally distant ones; 'Needle' itself where it is
%           an element; fails where 'Haystack' is empty.
hwut_runner_levenshtein_best_match(N, H, N) :- memberchk(N, H), !.
hwut_runner_levenshtein_best_match(N, [K|Ks], Best) :-
    hwut_runner_levenshtein_distance(N, K, D),
    foldl(closer(N), Ks, D-K, _-Best).

closer(N, K, D0-B0, D-B) :-
    hwut_runner_levenshtein_distance(N, K, DK),
    ( DK < D0 -> D-B = DK-K ; D-B = D0-B0 ).

%!  hwut_runner_levenshtein_distance(+A, +B, -Distance) is det.
%
%   RETURN: Distance >= 0, the Levenshtein distance between the texts 'A'
%           and 'B' -- insertions, deletions, substitutions.
hwut_runner_levenshtein_distance(A, B, D) :-
    atom_codes(A, As), atom_codes(B, Bs),
    length(Bs, NB), numlist(0, NB, Row0),
    foldl(lev_row(Bs), As, 1-Row0, _-Row),
    last(Row, D).

lev_row(Bs, Ca, I-Prev, I1-[I|Cur]) :-
    I1 is I + 1,
    Prev = [P0|PrevT],
    lev_cells(Bs, Ca, P0, PrevT, I, Cur).

lev_cells([], _, _, [], _, []).
lev_cells([Cb|Bs], Ca, Diag, [Up|Ups], Left, [C|Cs]) :-
    ( Ca == Cb -> Sub is Diag ; Sub is Diag + 1 ),
    C is min(min(Left + 1, Up + 1), Sub),
    lev_cells(Bs, Ca, Up, Ups, C, Cs).
