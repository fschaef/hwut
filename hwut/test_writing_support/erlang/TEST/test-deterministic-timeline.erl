%% @hwut {
%%     title      = "TriggerDispatcher: schedule, priority, and the end of time"
%%     choices {
%%         abstract    { features = ["erlang-timeline"] }
%%         cancel      { features = ["erlang-timeline"] }
%%         edges       { features = ["erlang-timeline"] }
%%         priority    { features = ["erlang-timeline"] }
%%         schedule    { features = ["erlang-timeline"] }
%%         stable      { features = ["erlang-timeline"] }
%%         stop        { features = ["erlang-timeline"] }
%%         termination { features = ["erlang-timeline"] }
%%         yielding    { features = ["erlang-timeline"] }
%%     }
%%     interactive = true
%% }
%%
%% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%%_____________________________________________________________________________
%%
%% PURPOSE: The Erlang port of 'python/TEST/test-deterministic-timeline.py',
%%          choice for choice, held against its GOOD files by '.link'.
%%          Python's trigger classes are behaviours -- maps of funs -- run in
%%          trigger processes; its consumer coroutine is a task process the
%%          dispatcher hands turns to.
%%_____________________________________________________________________________
-mode(compile).
-include("../hwut_boot.hrl").

main(Argv) ->
    hwut_boot(),
    hwut_runner:run(Argv, "TriggerDispatcher: schedule, priority, and the end of time",
                    #{"schedule"    => fun run_schedule/0,
                      "priority"    => fun run_priority/0,
                      "stable"      => fun run_stable/0,
                      "termination" => fun run_termination/0,
                      "yielding"    => fun run_yielding/0,
                      "stop"        => fun run_stop/0,
                      "cancel"      => fun run_cancel/0,
                      "edges"       => fun run_edges/0,
                      "abstract"    => fun run_abstract/0}).

%% RETURN: ok; the section heading is printed.
banner(Label) -> io:format("~n--- ~ts ---~n", [Label]).

%% RETURN: ok; says that the trigger 'Name' fired at 'Tick'.
fires(Tick, Name) -> io:format("  [t:~b] ~ts fires~n", [Tick, Name]).

%% RETURN: trigger, one that says what it is asked to do, and when.
speaking(Name, Timeline) ->
    io:format("SETUP: ~ts |~ts|~n", [pytext:ljust(Name, 7), Timeline]),
    deterministic_timeline:trigger(
      #{fire           => fun(Tick, S) -> fires(Tick, Name), {ok, S} end,
        on_termination => fun(End, S) -> io:format("  [end:~b] ~ts notified~n", [End, Name]), S end},
      Timeline, Name, nostate).

%% RETURN: trigger, one that fires and has NO 'on_termination' -- the
%%         silence of the optional callback is what it shows.
mute(Name, Timeline) ->
    io:format("SETUP: ~ts |~ts|  (no on_termination override)~n", [pytext:ljust(Name, 7), Timeline]),
    deterministic_timeline:trigger(#{fire => fun(Tick, S) -> fires(Tick, Name), {ok, S} end},
                                   Timeline, Name, nostate).

%% RETURN: the run's result (ok); a dispatcher over 'Triggers' ran to its end.
dispatch(Triggers) -> deterministic_timeline:run(deterministic_timeline:dispatcher(Triggers)).

%% RETURN: ok; a digit's position is its tick.
run_schedule() ->
    banner("staggered: A at 0, B at 2, C at 4"),
    dispatch([speaking("A", "1    "), speaking("B", "  1  "), speaking("C", "    1")]),
    banner("a SHORT timeline stops contributing; the long one goes on"),
    dispatch([speaking("SHORT", "11"), speaking("LONG", "111111")]),
    banner("the SCHEDULE as built -- '[tick] (priority)name'"),
    D = deterministic_timeline:dispatcher([speaking("A", "12"), speaking("B", "21")]),
    io:format("~ts~n", [deterministic_timeline:format(D)]).

%% RETURN: ok; the lower digit first within one tick, registration order
%%         notwithstanding.
run_priority() ->
    banner("digits swap between ticks: B leads at 0, A leads at 1"),
    dispatch([speaking("A", "21"), speaking("B", "12")]),
    banner("0 is the strongest digit, 9 the weakest"),
    dispatch([speaking("WEAK", "9"), speaking("STRONG", "0")]).

%% RETURN: ok; equal digits fire in registration order.
run_stable() ->
    banner("three triggers, all digit 1 at tick 0"),
    dispatch([speaking("first", "1"), speaking("second", "1"), speaking("third", "1")]),
    banner("registered BACKWARDS -- the order follows registration, not the name"),
    dispatch([speaking("third", "1"), speaking("second", "1"), speaking("first", "1")]).

%% RETURN: ok; the end of the timeline is an event with a stated tick.
run_termination() ->
    banner("end_tick is the LENGTH -- 5 characters, last firing at tick 0"),
    dispatch([speaking("EARLY", "1    ")]),
    banner("a trigger that NEVER fires is notified all the same"),
    dispatch([speaking("FIRES", "1  "), speaking("SILENT", "   ")]),
    banner("the LONGEST timeline sets end_tick for everybody"),
    dispatch([speaking("SHORT", "1"), speaking("LONG", "1      ")]),
    banner("a trigger that does not override is simply silent at the end"),
    dispatch([speaking("SPEAKS", "1 "), mute("MUTE", "1 ")]).

%% RETURN: ok; a producer prepares one item per tick, a consumer task takes
%%         each between the ticks -- the run yields after every firing.
run_yielding() ->
    banner("producer fires at every tick; consumer waits between them"),
    io:format("SETUP: ~ts |~ts|~n", [pytext:ljust("PROD", 7), "111"]),
    Producer = deterministic_timeline:trigger(
                 #{fire => fun(Tick, S) ->
                                   Item = io_lib:format("item@~b", [Tick]),
                                   io:format("  [t:~b] PROD prepared ~ts~n", [Tick, Item]),
                                   {ok, S#{item := Item}}
                           end,
                   on_termination => fun(End, S) ->
                                             io:format("  [end:~b] PROD announced end-of-stream~n", [End]),
                                             S#{finished := true}
                                     end},
                 "111", "PROD", #{item => none, finished => false}),
    Consumer = fun(Yield) -> consume(Producer, 0, Yield) end,
    ok = deterministic_timeline:run(deterministic_timeline:dispatcher([Producer]), [Consumer]),
    io:format("~nEach item was taken BEFORE the next tick prepared one: the run yields.~n").

%% RETURN: ok; every item taken as it appears, until the end is announced.
consume(Producer, Taken, Yield) ->
    Take = fun(#{item := none} = S) -> {S, S};
              (#{item := _} = S)    -> {S, S#{item := none}}
           end,
    case deterministic_timeline:call(Producer, Take) of
        #{item := none, finished := true} ->
            io:format("  consumer saw end-of-stream after ~b item(s)~n", [Taken]);
        #{item := none} ->
            Yield(),
            consume(Producer, Taken, Yield);
        #{item := Item} ->
            io:format("        consumer took ~ts~n", [Item]),
            consume(Producer, Taken + 1, Yield)
    end.

%% RETURN: ok; a stopped run is an ended run: it still announces.
run_stop() ->
    banner("stop() after the first tick -- ticks 1.. are not walked, the announcement still comes"),
    io:format("SETUP: ~ts |~ts|~n", [pytext:ljust("STOPPER", 7), "1111"]),
    Stopper = deterministic_timeline:trigger(
                #{fire => fun(Tick, S) ->
                                  fires(Tick, "STOPPER"),
                                  io:format("  ... asks the dispatcher to stop~n"),
                                  {stop, S}
                          end,
                  on_termination => fun(End, S) -> io:format("  [end:~b] STOPPER notified~n", [End]), S end},
                "1111", "STOPPER", nostate),
    dispatch([Stopper, speaking("OTHER", "1111")]),
    io:format("~nend_tick is still the timeline's length, not the tick the run stopped at.~n").

%% RETURN: ok; a cancellation is an abandonment: it announces nothing.
run_cancel() ->
    banner("cancel() the task carrying run() -- no announcement follows"),
    D = deterministic_timeline:dispatcher([speaking("A", "1111111111")]),
    %  THE CANCELLING TASK gets its first turn after the first firing --
    %  Python's 'await asyncio.sleep(0)' before 'task.cancel()'.
    {error, cancelled} = deterministic_timeline:run(D, [fun(_Yield) -> deterministic_timeline:cancel(D) end]),
    io:format("  run() was cancelled~n"),
    io:format("~nNo '[end:..]' line above: the triggers were abandoned, not ended.~n").

%% RETURN: ok; degenerate timelines announce and do not fail.
run_edges() ->
    banner("an EMPTY timeline -- end_tick 0"),
    dispatch([speaking("EMPTY", "")]),
    banner("a timeline of BLANKS -- no digit, so nothing fires"),
    dispatch([speaking("BLANK", "    ")]),
    banner("NO TRIGGERS at all -- nothing to announce, and no failure"),
    dispatch([]),
    io:format("  (dispatcher ran; nothing was scheduled)~n"),
    banner("a timeline of blanks beside one that fires"),
    dispatch([speaking("BLANK", "   "), speaking("FIRES", " 1 ")]).

%% RETURN: ok; 'fire' refuses, 'on_termination' is silent.
run_abstract() ->
    banner("the BASE 'fire' is abstract -- it refuses"),
    case dispatch([deterministic_timeline:trigger(#{}, "1", "BARE", nostate)]) of
        {error, not_implemented} ->
            io:format("  NotImplementedError -- as owed: a trigger must say what it does~n")
    end,
    banner("the BASE 'on_termination' is optional -- it is silent"),
    ok = deterministic_timeline:on_termination(deterministic_timeline:trigger(#{}, "", "BARE", nostate), 0),
    io:format("  returned quietly; nothing raised, nothing printed~n"),
    banner("a NAME given is the name kept"),
    io:format("  name: ~ts~n", [deterministic_timeline:name(deterministic_timeline:trigger(#{}, "1", "GIVEN", nostate))]).
