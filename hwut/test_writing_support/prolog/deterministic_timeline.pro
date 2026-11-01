/*  SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
    ___________________________________________________________________________

    PURPOSE: Races drawn as strings -- the port of
             'python/deterministic_timeline.py'. A trigger's timeline is a
             string: a digit's POSITION is its tick, its VALUE its priority
             within the tick (0 first, 9 last; equal digits in registration
             order). The end of the timeline is an event: every trigger is
             told 'on_termination(EndTick)', EndTick the longest timeline's
             length.

    A TRIGGER is 'trigger(Timeline, Name, Behaviour)'. The BEHAVIOUR is a
    closure that is sent MESSAGES -- 'call(Behaviour, Message, Trigger)':

        fire(Tick)              the trigger's tick has come
        on_termination(End)     the timeline has passed

    A behaviour understands a message where it has a clause for it; one it
    has no clause for FAILS. That failure is the base class: 'fire' not
    understood is refused -- 'error(not_implemented_error(''), _)', Python's
    NotImplementedError: a trigger that does nothing has no reason to stand in
    the timeline -- and 'on_termination' not understood is silence. A
    'subclass' is a behaviour whose clause calls another's ('super').

        speaking(fire(T), Self)          :- dt_trigger_name(Self, N),
                                            format("[t:~d] ~w fires~n", [T, N]).
        speaking(on_termination(E), Self) :- ...

        dt_trigger_new("1 1", 'A', speaking, A),
        dt_dispatcher_new([A, B], D),
        dt_run(dt_dispatcher_run(D))

    A TASK IS A SUSPENDED GOAL -- SWI's delimited continuations. 'dt_yield'
    is 'shift(yield)': the goal stops there, and what is left of it is a
    continuation, a term, run on by the next step. 'dt_task_step' runs a
    task to its next yield (Python's one turn of the event loop),
    'dt_gather' steps tasks in turn in the order given -- asyncio.gather's
    order -- until all are done, 'dt_run' is asyncio.run. 'dt_task_cancel'
    abandons the continuation: nothing of the goal runs again, so a
    cancelled run announces nothing; 'dt_task_await' of it raises
    'error(cancelled_error(''), _)', as awaiting a cancelled task does.

    'dt_dispatcher_stop' leaves the timeline at the next firing; the
    announcement still follows. The dispatcher's one mutable cell -- running
    or not -- is changed in place ('nb_setarg'): a trigger that stops the run
    holds the dispatcher, and the run must see the change, not a copy.
    ___________________________________________________________________________
*/
:- module(deterministic_timeline,
          [ dt_trigger_new/4,           % +Timeline, +Name, :Behaviour, -Trigger
            dt_trigger_name/2,          % +Trigger, -Name
            dt_trigger_timeline/2,      % +Trigger, -Timeline
            dt_fire/2,                  % +Trigger, +Tick
            dt_on_termination/2,        % +Trigger, +EndTick
            dt_dispatcher_new/2,        % +Triggers, -Dispatcher
            dt_dispatcher_run/1,        % +Dispatcher           (yields)
            dt_dispatcher_stop/1,       % +Dispatcher
            dt_dispatcher_end_tick/2,   % +Dispatcher, -EndTick
            dt_dispatcher_text/2,       % +Dispatcher, -String  (repr)
            dt_yield/0,                 %                       (asyncio.sleep(0))
            dt_task_new/2,              % :Goal, -Task
            dt_task_step/2,             % +Task0, -Task
            dt_task_cancel/2,           % +Task0, -Task
            dt_task_await/1,            % +Task
            dt_gather/1,                % :Goals
            dt_run/1                    % :Goal
          ]).
:- encoding(utf8).

:- meta_predicate
    dt_trigger_new(+, +, 2, -),
    dt_task_new(0, -),
    dt_gather(:),
    dt_run(0).

/* ------------------------------------------------------------- triggers */

%!  dt_trigger_new(+Timeline, +Name, :Behaviour, -Trigger) is det.
%
%   RETURN: Trigger, 'trigger(Timeline, Name, Behaviour)' -- 'Timeline' as a
%           string; where 'Name' is '' a name of its own, 'trigger-<n>'.
dt_trigger_new(Timeline, Name0, Behaviour, trigger(T, Name, Behaviour)) :-
    text_to_string(Timeline, T),
    (   Name0 == '' -> gensym('trigger-', Name)
    ;   Name0 == "" -> gensym('trigger-', Name)
    ;   Name = Name0
    ).

%!  dt_trigger_name(+Trigger, -Name) is det.
%
%   RETURN: Name, the name the trigger was given (or made).
dt_trigger_name(trigger(_, N, _), N).

%!  dt_trigger_timeline(+Trigger, -Timeline) is det.
%
%   RETURN: Timeline, the trigger's timeline string.
dt_trigger_timeline(trigger(T, _, _), T).

%!  dt_fire(+Trigger, +Tick) is det.
%
%   RETURN: true, once the behaviour did what it does at 'Tick' -- it may
%           yield on the way; raises error(not_implemented_error(''), _)
%           where the behaviour has no clause for 'fire' (THE BASE IS
%           ABSTRACT).
dt_fire(Trigger, Tick) :-
    Trigger = trigger(_, _, B),
    (   call(B, fire(Tick), Trigger) -> true
    ;   throw(error(not_implemented_error(''), context(dt_fire/2, _)))
    ).

%!  dt_on_termination(+Trigger, +EndTick) is det.
%
%   RETURN: true, once the behaviour wound down -- where it has no clause for
%           'on_termination', at once and silently (overriding is optional).
dt_on_termination(Trigger, End) :-
    Trigger = trigger(_, _, B),
    ( call(B, on_termination(End), Trigger) -> true ; true ).

/* ----------------------------------------------------------- dispatcher */

%!  dt_dispatcher_new(+Triggers, -Dispatcher) is det.
%
%   RETURN: Dispatcher, 'dispatcher(Triggers, Schedule, EndTick, Cell)': the
%           Schedule one 'Tick-Priority-Trigger' per digit of every timeline,
%           ascending by tick, then priority, then registration -- the order
%           the run fires them; EndTick the longest timeline's length (0
%           where there is none); Cell 'running(true)'.
dt_dispatcher_new(Triggers, dispatcher(Triggers, Schedule, End, running(true))) :-
    foldl(longest, Triggers, 0, End),
    keyed(Triggers, 0, Keyed),
    msort(Keyed, Sorted),
    pairs_values(Sorted, Schedule).

longest(trigger(T, _, _), N0, N) :- string_length(T, L), N is max(N0, L).

%   keyed(+Triggers, +I, -Keyed)
%   RETURN: 'key(Tick, Priority, I)-(Tick-Priority-
%           Trigger)' per digit. WRITTEN WITHOUT 'findall', which would COPY the
%           triggers: a behaviour's state -- a cell shared with a consumer, a
%           dispatcher bound after the trigger was made -- must be the trigger's
%           own in the schedule too, not a copy's.
keyed([], _, []).
keyed([Trigger|Ts], I, Keyed) :-
    Trigger = trigger(T, _, _),
    string_codes(T, Cs),
    digits(Cs, 0, I, Trigger, Keyed, Rest),
    I1 is I + 1,
    keyed(Ts, I1, Rest).

digits([], _, _, _, K, K).
digits([C|Cs], Tick, I, Trigger, K0, K) :-
    (   code_type(C, digit(P))
    ->  K0 = [key(Tick, P, I)-(Tick-P-Trigger)|K1]
    ;   K0 = K1
    ),
    Tick1 is Tick + 1,
    digits(Cs, Tick1, I, Trigger, K1, K).

%!  dt_dispatcher_stop(+Dispatcher) is det.
%
%   RETURN: true; the run leaves the timeline before its next firing, and
%           still announces termination.
dt_dispatcher_stop(dispatcher(_, _, _, Cell)) :- nb_setarg(1, Cell, false).

%!  dt_dispatcher_end_tick(+Dispatcher, -EndTick) is det.
%
%   RETURN: EndTick, the length of the longest timeline.
dt_dispatcher_end_tick(dispatcher(_, _, End, _), End).

%!  dt_dispatcher_run(+Dispatcher) is det.
%
%   RETURN: true, once every firing of the schedule was done in its order --
%           each followed by a yield, so that a consumer of what the trigger
%           produced may progress -- or 'dt_dispatcher_stop' cut it short;
%           then EVERY trigger was told 'on_termination(EndTick)'. Run it as a
%           task ('dt_run', 'dt_gather'): it yields. A cancelled task carrying
%           it announces nothing.
dt_dispatcher_run(D) :-
    D = dispatcher(Triggers, Schedule, End, Cell),
    firings(Schedule, Cell),
    announce(Triggers, End).

firings([], _).
firings([Tick-_-Trigger|Rest], Cell) :-
    (   arg(1, Cell, true)
    ->  dt_fire(Trigger, Tick), dt_yield, firings(Rest, Cell)
    ;   true
    ).

announce([], _).
announce([T|Ts], End) :- dt_on_termination(T, End), announce(Ts, End).

%!  dt_dispatcher_text(+Dispatcher, -String) is det.
%
%   RETURN: String, the built timeline -- 'TriggerDispatcher', then one line
%           '[tick] (priority)name' per scheduled firing, in firing order,
%           joined by newlines (Python's '__repr__').
dt_dispatcher_text(dispatcher(_, Schedule, _, _), S) :-
    findall(L, ( member(Tick-P-trigger(_, N, _), Schedule),
                 format(string(L), "[~d] (~d)~w", [Tick, P, N]) ), Ls),
    atomic_list_concat(["TriggerDispatcher"|Ls], '\n', A),
    atom_string(A, S).

/* ---------------------------------------------------------------- tasks */

%!  dt_yield is det.
%
%   RETURN: true, once the task was stepped again -- 'asyncio.sleep(0)': the
%           goal is suspended here (shift/1) and given to the stepping loop.
dt_yield :- shift(yield).

%!  dt_task_new(:Goal, -Task) is det.
%
%   RETURN: Task, 'task(Goal)': not started; nothing of 'Goal' has run.
dt_task_new(G, task(G)).

%!  dt_task_step(+Task0, -Task) is det.
%
%   RETURN: Task, after 'Task0' ran to its next yield -- 'suspended(Cont)',
%           Cont what is left of the goal; or 'done', the goal succeeded;
%           'done' and 'cancelled' step to themselves. A goal that fails or
%           raises ends the step the same (failure as an error).
dt_task_step(done, done) :- !.
dt_task_step(cancelled, cancelled) :- !.
dt_task_step(task(G), T) :- !, step(G, T).
dt_task_step(suspended(C), T) :- step(C, T).

step(G, T) :-
    (   reset(G, Ball, Cont) -> true
    ;   throw(error(goal_failed(G), context(dt_task_step/2, _)))
    ),
    (   Cont == 0 -> T = done
    ;   Ball == yield -> T = suspended(Cont)
    ;   shift(Ball)                     % not ours: passed outward
    ).

%!  dt_task_cancel(+Task0, -Task) is det.
%
%   RETURN: Task, 'cancelled' -- the continuation is abandoned: nothing of
%           the goal runs again, no 'on_termination' is announced; a task
%           already done stays 'done'.
dt_task_cancel(done, done) :- !.
dt_task_cancel(_, cancelled).

%!  dt_task_await(+Task) is det.
%
%   RETURN: true, once 'Task' ran to its end (stepped alone);
%           raises error(cancelled_error(''), _) where it was cancelled.
dt_task_await(cancelled) :- !, throw(error(cancelled_error(''), context(dt_task_await/1, _))).
dt_task_await(done) :- !.
dt_task_await(T0) :- dt_task_step(T0, T), dt_task_await(T).

%!  dt_gather(:Goals) is det.
%
%   RETURN: true, once every goal of the list ran to its end -- each a task,
%           stepped in turn, in the order given, until all are done
%           (asyncio.gather's order).
dt_gather(M:Goals) :-
    maplist([G, task(M:G)]>>true, Goals, Tasks),
    round(Tasks).

round(Tasks) :-
    (   maplist(==(done), Tasks) -> true
    ;   maplist(dt_task_step, Tasks, Next), round(Next)
    ).

%!  dt_run(:Goal) is det.
%
%   RETURN: true, once 'Goal' ran to its end as one task -- asyncio.run;
%           what it raises passes on.
dt_run(G) :- dt_task_await(task(G)).
