% @hwut {
%     title      = "TriggerDispatcher: schedule, priority, and the end of time"
%     choices {
%         abstract    { features = ["prolog-timeline"] }
%         cancel      { features = ["prolog-timeline"] }
%         edges       { features = ["prolog-timeline"] }
%         priority    { features = ["prolog-timeline"] }
%         schedule    { features = ["prolog-timeline"] }
%         stable      { features = ["prolog-timeline"] }
%         stop        { features = ["prolog-timeline"] }
%         termination { features = ["prolog-timeline"] }
%         yielding    { features = ["prolog-timeline"] }
%     }
%     interactive = true
% }
%
% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%______________________________________________________________________________
%
% PURPOSE: The Prolog port of 'python/TEST/test-deterministic-timeline.py',
%          choice for choice, held against its GOOD files by '.link'. A
%          Python Trigger subclass is a BEHAVIOUR here -- a predicate with a
%          clause per message it understands; a coroutine is a task, suspended
%          at each yield as a delimited continuation.
%______________________________________________________________________________
:- encoding(utf8).
:- use_module('../hwut_runner.pro').
:- use_module('../hwut_pytext.pro').
:- use_module('../deterministic_timeline.pro').
:- initialization(main, main).

banner(Label) :- format("~n--- ~w ---~n", [Label]).

setup_line(Name, Timeline, Tail) :-
    py_ljust(Name, 7, N), format("SETUP: ~w |~w|~w~n", [N, Timeline, Tail]).

%   THE SPEAKING TRIGGER: says what it is asked to do, and when.
speaking(Name, Timeline, T) :-
    dt_trigger_new(Timeline, Name, speaking, T), setup_line(Name, Timeline, "").

speaking(fire(Tick), Self) :-
    dt_trigger_name(Self, N), format("  [t:~d] ~w fires~n", [Tick, N]).
speaking(on_termination(End), Self) :-
    dt_trigger_name(Self, N), format("  [end:~d] ~w notified~n", [End, N]).

%   THE MUTE TRIGGER: fires, and has no clause for 'on_termination' -- the
%   base's silence is what it demonstrates.
mute(Name, Timeline, T) :-
    dt_trigger_new(Timeline, Name, mute, T),
    setup_line(Name, Timeline, "  (no on_termination override)").

mute(fire(Tick), Self) :- speaking(fire(Tick), Self).

%   THE BARE TRIGGER: understands nothing.
bare(_, _) :- fail.

dispatch(Triggers) :- dt_dispatcher_new(Triggers, D), dt_run(dt_dispatcher_run(D)).

run_schedule :-
    banner("staggered: A at 0, B at 2, C at 4"),
    speaking('A', "1    ", A), speaking('B', "  1  ", B), speaking('C', "    1", C),
    dispatch([A, B, C]),
    banner("a SHORT timeline stops contributing; the long one goes on"),
    speaking('SHORT', "11", S), speaking('LONG', "111111", L),
    dispatch([S, L]),
    banner("the SCHEDULE as built -- '[tick] (priority)name'"),
    speaking('A', "12", A2), speaking('B', "21", B2),
    dt_dispatcher_new([A2, B2], D), dt_dispatcher_text(D, Text),
    format("~w~n", [Text]).

run_priority :-
    banner("digits swap between ticks: B leads at 0, A leads at 1"),
    speaking('A', "21", A), speaking('B', "12", B), dispatch([A, B]),
    banner("0 is the strongest digit, 9 the weakest"),
    speaking('WEAK', "9", W), speaking('STRONG', "0", S), dispatch([W, S]).

run_stable :-
    banner("three triggers, all digit 1 at tick 0"),
    speaking(first, "1", A), speaking(second, "1", B), speaking(third, "1", C),
    dispatch([A, B, C]),
    banner("registered BACKWARDS -- the order follows registration, not the name"),
    speaking(third, "1", C2), speaking(second, "1", B2), speaking(first, "1", A2),
    dispatch([C2, B2, A2]).

run_termination :-
    banner("end_tick is the LENGTH -- 5 characters, last firing at tick 0"),
    speaking('EARLY', "1    ", E), dispatch([E]),
    banner("a trigger that NEVER fires is notified all the same"),
    speaking('FIRES', "1  ", F), speaking('SILENT', "   ", S), dispatch([F, S]),
    banner("the LONGEST timeline sets end_tick for everybody"),
    speaking('SHORT', "1", Sh), speaking('LONG', "1      ", L), dispatch([Sh, L]),
    banner("a trigger that does not override is simply silent at the end"),
    speaking('SPEAKS', "1 ", Sp), mute('MUTE', "1 ", M), dispatch([Sp, M]).

%   THE PRODUCER: prepares one item per tick into its state cell
%   'state(Item, Finished)' -- shared with the consumer, changed in place.
producing(State, fire(Tick), Self) :-
    format(string(Item), "item@~d", [Tick]), nb_setarg(1, State, Item),
    dt_trigger_name(Self, N), format("  [t:~d] ~w prepared ~w~n", [Tick, N, Item]).
producing(State, on_termination(End), Self) :-
    nb_setarg(2, State, true),
    dt_trigger_name(Self, N), format("  [end:~d] ~w announced end-of-stream~n", [End, N]).

%   consume(+State, +Taken)
%   RETURN: takes each item as it appears, until the end is
%           announced -- yielding while there is none.
consume(State, Taken) :-
    (   arg(1, State, none)
    ->  (   arg(2, State, true)
        ->  format("  consumer saw end-of-stream after ~d item(s)~n", [Taken])
        ;   dt_yield, consume(State, Taken)
        )
    ;   arg(1, State, Item),
        format("        consumer took ~w~n", [Item]),
        nb_setarg(1, State, none),
        Taken1 is Taken + 1,
        consume(State, Taken1)
    ).

run_yielding :-
    banner("producer fires at every tick; consumer waits between them"),
    State = state(none, false),
    dt_trigger_new("111", 'PROD', producing(State), P), setup_line('PROD', "111", ""),
    dt_dispatcher_new([P], D),
    dt_run(dt_gather([dt_dispatcher_run(D), consume(State, 0)])),
    format("~nEach item was taken BEFORE the next tick prepared one: the run yields.~n").

%   THE STOPPING TRIGGER: a speaking one ('super') that asks the run to leave
%   -- the dispatcher it holds is bound once the dispatcher is made.
stopping(Dispatcher, fire(Tick), Self) :-
    speaking(fire(Tick), Self),
    format("  ... asks the dispatcher to stop~n"),
    dt_dispatcher_stop(Dispatcher).
stopping(_, on_termination(End), Self) :- speaking(on_termination(End), Self).

run_stop :-
    banner("stop() after the first tick -- ticks 1.. are not walked, the announcement still comes"),
    dt_trigger_new("1111", 'STOPPER', stopping(D), Stopper), setup_line('STOPPER', "1111", ""),
    speaking('OTHER', "1111", Other),
    dt_dispatcher_new([Stopper, Other], D),
    dt_run(dt_dispatcher_run(D)),
    format("~nend_tick is still the timeline's length, not the tick the run stopped at.~n").

%   cancelled_run
%   RETURN: starts a run, lets one tick pass, cancels it, awaits it.
cancelled_run :-
    speaking('A', "1111111111", A), dt_dispatcher_new([A], D),
    dt_task_new(dt_dispatcher_run(D), T0),
    dt_task_step(T0, T1),
    dt_task_cancel(T1, T2),
    catch(dt_task_await(T2), error(cancelled_error(_), _),
          format("  run() was cancelled~n")).

run_cancel :-
    banner("cancel() the task carrying run() -- no announcement follows"),
    dt_run(cancelled_run),
    format("~nNo '[end:..]' line above: the triggers were abandoned, not ended.~n").

run_edges :-
    banner("an EMPTY timeline -- end_tick 0"),
    speaking('EMPTY', "", E), dispatch([E]),
    banner("a timeline of BLANKS -- no digit, so nothing fires"),
    speaking('BLANK', "    ", B), dispatch([B]),
    banner("NO TRIGGERS at all -- nothing to announce, and no failure"),
    dispatch([]),
    format("  (dispatcher ran; nothing was scheduled)~n"),
    banner("a timeline of blanks beside one that fires"),
    speaking('BLANK', "   ", B2), speaking('FIRES', " 1 ", F), dispatch([B2, F]).

run_abstract :-
    banner("the BASE 'fire' is abstract -- it refuses"),
    dt_trigger_new("1", 'BARE', bare, Bare),
    catch(dispatch([Bare]), error(not_implemented_error(_), _),
          format("  NotImplementedError -- as owed: a trigger must say what it does~n")),
    banner("the BASE 'on_termination' is optional -- it is silent"),
    dt_trigger_new("", 'BARE', bare, Bare2),
    dt_on_termination(Bare2, 0),
    format("  returned quietly; nothing raised, nothing printed~n"),
    banner("a NAME given is the name kept"),
    dt_trigger_new("1", 'GIVEN', bare, Given), dt_trigger_name(Given, Name),
    format("  name: ~w~n", [Name]).

main :-
    hwut_runner_run("TriggerDispatcher: schedule, priority, and the end of time",
                    [ schedule-run_schedule,
                      priority-run_priority,
                      stable-run_stable,
                      termination-run_termination,
                      yielding-run_yielding,
                      stop-run_stop,
                      cancel-run_cancel,
                      edges-run_edges,
                      abstract-run_abstract ],
                    []).
