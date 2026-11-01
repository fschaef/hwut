%% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%%_____________________________________________________________________________
%%
%% PURPOSE: RACES DRAWN AS STRINGS -- the port of
%%          'python/deterministic_timeline.py' (its docstring is the
%%          manual): a digit's POSITION in a timeline is its tick, the digit
%%          its priority within the tick (0 first, equal digits in
%%          registration order), and the end of the timeline is an EVENT
%%          every trigger is told ('on_termination(EndTick)', EndTick the
%%          longest timeline's length).
%%
%%     Say = #{fire => fun(Tick, S) -> io:format("[~p] A~n", [Tick]), {ok, S} end},
%%     A   = deterministic_timeline:trigger(Say, "1 1 3", "A", nostate),
%%     B   = deterministic_timeline:trigger(Say, "21  1", "B", nostate),
%%     ok  = deterministic_timeline:run(deterministic_timeline:dispatcher([A, B]))
%%
%% THE DRAWN ORDER IS A MESSAGE ORDER. A trigger is a PROCESS holding its
%% state; the dispatcher is the PROCESS that walks the timeline and decides
%% who runs next: it sends 'fire' to one trigger and waits for its answer
%% before it sends anything else. Nothing runs that the dispatcher did not
%% start, so the interleaving is the drawn one whatever the scheduler does.
%%
%% TASKS -- Python's coroutines beside the run ('asyncio.gather') -- are
%% processes too ('run(D, [TaskFun])'). Python's 'await asyncio.sleep(0)'
%% after each firing is the dispatcher handing every task a TURN and
%% waiting until the task gives it back: 'TaskFun(Yield)' runs on its first
%% turn, 'Yield()' gives the turn back and returns at the next one. Once
%% the timeline and its announcement are done, the tasks get turns until
%% they all returned -- gather's end.
%%
%% A TRIGGER'S BEHAVIOUR is a module with the callbacks below, or a map of
%% the same funs (#{fire => F, on_termination => G}) -- an escript test
%% defines no module. 'fire' is ABSTRACT: a behaviour without it makes the
%% run return {error, not_implemented}; 'on_termination' is optional and
%% silent. 'fire' returns {stop, State} for Python's 'dispatcher.stop()'.
%% A task reads or changes a trigger's state by 'call(Trigger, Fun)'.
%%
%% THE END: 'stop' (or {stop, S} from 'fire') leaves the timeline at the
%% next firing and STILL announces termination; 'cancel' kills the process
%% carrying the run -- an exit signal, an abandonment -- and announces
%% nothing: 'run' returns {error, cancelled}.
%%
%% ERRORS ARE VALUES: 'run' returns ok or {error, Reason}; a trigger whose
%% 'fire' raises makes the run return {error, {Class, Reason, Stack}}.
%%_____________________________________________________________________________
-module(deterministic_timeline).
-export([trigger/4, name/1, timeline/1, on_termination/2, call/2,
         dispatcher/1, run/1, run/2, stop/1, cancel/1, format/1]).

-callback fire(Tick :: non_neg_integer(), State :: term()) ->
    {ok, NewState :: term()} | {stop, NewState :: term()}.
-callback on_termination(EndTick :: non_neg_integer(), State :: term()) ->
    NewState :: term().
-optional_callbacks([on_termination/2]).

-record(trigger, {pid, name :: binary(), timeline :: [char()]}).

%% ---------------------------------------------------------------- trigger
%% RETURN: trigger, a process holding 'State', firing by 'Behaviour' (a
%%         module or a map of funs, see the head) at the ticks 'Timeline'
%%         marks; named 'Name' -- 'trigger-<pid>' where it is empty. The
%%         process ends with the process that made it.
trigger(Behaviour, Timeline, Name, State) ->
    Owner = self(),
    Pid   = spawn(fun() -> monitor(process, Owner), trigger_loop(Behaviour, State, Owner) end),
    Text  = unicode:characters_to_list(Timeline),
    #trigger{pid      = Pid,
             name     = case iolist_to_binary(Name) of
                            <<>> -> list_to_binary("trigger-" ++ pid_to_list(Pid));
                            N    -> N
                        end,
             timeline = Text}.

%% RETURN: binary, the trigger's name.
name(#trigger{name = Name}) -> Name.

%% RETURN: string, the trigger's timeline.
timeline(#trigger{timeline = Timeline}) -> Timeline.

%% RETURN: ok, once the trigger's 'on_termination(EndTick, State)' ran --
%%         at once where its behaviour has none (it is optional: silent).
on_termination(Trigger, EndTick) -> request(Trigger, {terminate, EndTick}).

%% RETURN: term, the 'Reply' of '{Reply, NewState} = Fun(State)', run in the
%%         trigger's process; its state is 'NewState' from now on.
call(Trigger, Fun) -> request(Trigger, {call, Fun}).

%% RETURN: term, the trigger process's reply to 'Message'.
request(#trigger{pid = Pid}, Message) ->
    Ref = monitor(process, Pid),
    Pid ! {Message, self(), Ref},
    receive
        {Ref, Reply}                   -> demonitor(Ref, [flush]), Reply;
        {'DOWN', Ref, process, _, Why} -> {error, {trigger_down, Why}}
    end.

%% RETURN: ok, once the owner ended; serves 'fire', 'terminate' and 'call'
%%         one at a time, in the order they arrive, until then.
trigger_loop(Behaviour, State, Owner) ->
    receive
        {{fire, Tick}, From, Ref} ->
            case callback(Behaviour, fire) of
                none ->
                    From ! {Ref, {error, not_implemented}},
                    trigger_loop(Behaviour, State, Owner);
                Fire ->
                    {Reply, State1} = try Fire(Tick, State) of
                                          {ok, S}   -> {ok, S};
                                          {stop, S} -> {stop, S}
                                      catch Class:Reason:Stack ->
                                          {{error, {Class, Reason, Stack}}, State}
                                      end,
                    From ! {Ref, Reply},
                    trigger_loop(Behaviour, State1, Owner)
            end;
        {{terminate, EndTick}, From, Ref} ->
            State1 = case callback(Behaviour, on_termination) of
                         none -> State;
                         Done -> Done(EndTick, State)
                     end,
            From ! {Ref, ok},
            trigger_loop(Behaviour, State1, Owner);
        {{call, Fun}, From, Ref} ->
            {Reply, State1} = Fun(State),
            From ! {Ref, Reply},
            trigger_loop(Behaviour, State1, Owner);
        {'DOWN', _, process, Owner, _} ->
            ok
    end.

%% RETURN: fun/2, the behaviour's callback 'Name'; none where it has none.
callback(Map, Name) when is_map(Map) -> maps:get(Name, Map, none);
callback(Module, Name) when is_atom(Module) ->
    _ = code:ensure_loaded(Module),
    case erlang:function_exported(Module, Name, 2) of
        true  -> fun Module:Name/2;
        false -> none
    end.

%% ------------------------------------------------------------- dispatcher
%% RETURN: pid, the dispatcher of 'Triggers': its schedule built -- one
%%         entry per tick up to the longest timeline, each holding the
%%         triggers due then, by priority and, priorities equal, in
%%         registration order. It ends with the process that made it.
dispatcher(Triggers) ->
    Owner    = self(),
    EndTick  = lists:max([0 | [length(T#trigger.timeline) || T <- Triggers]]),
    Schedule = [{Tick, due(Tick, Triggers)} || Tick <- lists:seq(0, EndTick - 1)],
    spawn(fun() -> monitor(process, Owner),
                   dispatcher_loop(Triggers, Schedule, EndTick, Owner) end).

%% RETURN: [{Priority, Trigger}], the triggers whose timeline carries a digit
%%         at 'Tick', sorted by the digit -- stable: registration order
%%         among equals.
due(Tick, Triggers) ->
    Marked = [{Char - $0, T} || T <- Triggers,
                                Tick < length(T#trigger.timeline),
                                Char <- [lists:nth(Tick + 1, T#trigger.timeline)],
                                Char >= $0, Char =< $9],
    lists:keysort(1, Marked).

%% RETURN: as 'run/2', with no task beside the run.
run(Dispatcher) -> run(Dispatcher, []).

%% RETURN: ok, the timeline was walked -- to its end, or to a 'stop' -- and
%%         every trigger was told 'on_termination(EndTick)', and every task
%%         of 'TaskFuns' returned;
%%         {error, cancelled}, the run was cancelled ('cancel'): nothing
%%         announced;
%%         {error, not_implemented}, a trigger due had no 'fire';
%%         {error, {Class, Reason, Stack}}, a trigger's 'fire' raised.
run(Dispatcher, TaskFuns) ->
    Ref = monitor(process, Dispatcher),
    Dispatcher ! {run, self(), Ref, TaskFuns},
    receive
        {Ref, Result}                         -> demonitor(Ref, [flush]), Result;
        {'DOWN', Ref, process, _, cancelled}  -> {error, cancelled};
        {'DOWN', Ref, process, _, Why}        -> {error, {dispatcher_down, Why}}
    end.

%% RETURN: ok; the run leaves the timeline before its next firing and still
%%         announces termination.
stop(Dispatcher) -> Dispatcher ! stop, ok.

%% RETURN: ok; the process carrying the run is killed: the run announces
%%         nothing, its tasks end with it, 'run' returns {error, cancelled}.
cancel(Dispatcher) -> exit(Dispatcher, cancelled), ok.

%% RETURN: binary, the built timeline -- 'TriggerDispatcher', then one line
%%         per scheduled firing '[tick] (priority)name', ticks ascending
%%         and, within a tick, in firing order; Python's 'repr'.
format(Dispatcher) ->
    Ref = monitor(process, Dispatcher),
    Dispatcher ! {format, self(), Ref},
    receive {Ref, Text} -> demonitor(Ref, [flush]), Text end.

%% RETURN: ok, once the owner ended; serves 'run' and 'format' until then.
dispatcher_loop(Triggers, Schedule, EndTick, Owner) ->
    receive
        {run, From, Ref, TaskFuns} ->
            Self  = self(),
            Tasks = [spawn_link(fun() -> task(Self, F) end) || F <- TaskFuns],
            From ! {Ref, walk(Schedule, Triggers, EndTick, Tasks)},
            dispatcher_loop(Triggers, Schedule, EndTick, Owner);
        {format, From, Ref} ->
            Lines = [io_lib:format("[~b] (~b)~ts", [Tick, P, T#trigger.name])
                     || {Tick, Due} <- Schedule, {P, T} <- Due],
            From ! {Ref, iolist_to_binary(lists:join($\n, ["TriggerDispatcher" | Lines]))},
            dispatcher_loop(Triggers, Schedule, EndTick, Owner);
        {'DOWN', _, process, Owner, _} ->
            ok
    end.

%% RETURN: the result of the run (see 'run'), the ticks from 'Tick' on
%%         walked.
walk([], Triggers, EndTick, Tasks) ->
    announce(Triggers, EndTick, Tasks);
walk([{Tick, Due} | Rest], Triggers, EndTick, Tasks) ->
    case stopped_f() orelse fire_due(Tick, Due, Tasks) of
        true               -> announce(Triggers, EndTick, Tasks);
        {continue, Tasks1} -> walk(Rest, Triggers, EndTick, Tasks1);
        {stopped, Tasks1}  -> announce(Triggers, EndTick, Tasks1);
        {error, _} = Error -> Error
    end.

%% RETURN: {continue, Tasks}, every trigger 'Due' at 'Tick' fired, each
%%         followed by one turn of every task; {stopped, Tasks}, a stop came
%%         first; {error, Reason}, a firing failed. 'Tasks' are those that
%%         have not returned yet.
fire_due(_, [], Tasks) -> {continue, Tasks};
fire_due(Tick, [{_, Trigger} | Rest], Tasks) ->
    case stopped_f() of
        true  -> {stopped, Tasks};
        false ->
            case request(Trigger, {fire, Tick}) of
                ok             -> fire_due(Tick, Rest, turns(Tasks));
                stop           -> self() ! stop, fire_due(Tick, Rest, turns(Tasks));
                {error, _} = E -> E
            end
    end.

%% RETURN: true, a 'stop' was asked (it stays asked), false else.
stopped_f() -> receive stop -> self() ! stop, true after 0 -> false end.

%% RETURN: ok, every trigger told 'on_termination(EndTick)' in registration
%%         order, then every task turned until it returned.
announce(Triggers, EndTick, Tasks) ->
    _ = [on_termination(T, EndTick) || T <- Triggers],
    finish(Tasks).

%% RETURN: ok, once every task of 'Tasks' returned; a stop still asked is
%%         forgotten, so the next run starts afresh.
finish([])    -> receive stop -> ok after 0 -> ok end;
finish(Tasks) -> finish(turns(Tasks)).

%% RETURN: [pid], the tasks still running after each of 'Tasks' had one turn,
%%         in order -- asyncio's ready queue, FIFO.
turns(Tasks) -> [T || T <- Tasks, turn(T) == yielded].

%% RETURN: yielded, 'Task' gave its turn back and wants another;
%%         returned, it ended.
turn(Task) ->
    Task ! {turn, self()},
    receive
        {yielded, Task}  -> yielded;
        {returned, Task} -> returned
    end.

%% RETURN: the task's end message sent; 'Fun(Yield)' ran from the task's
%%         first turn on, 'Yield()' giving each turn back.
task(Dispatcher, Fun) ->
    receive {turn, Dispatcher} -> ok end,
    Yield = fun() -> Dispatcher ! {yielded, self()},
                     receive {turn, Dispatcher} -> ok end
            end,
    Fun(Yield),
    Dispatcher ! {returned, self()}.
