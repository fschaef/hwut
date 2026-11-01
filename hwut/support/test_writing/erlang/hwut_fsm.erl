%% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%%_____________________________________________________________________________
%%
%% PURPOSE: A STATE MACHINE AS A TEST'S MODEL OF THE SYSTEM UNDER TEST -- the
%%          port of 'python/hwut_fsm.py' (its manual: '../python/README-
%%          hwut_fsm.txt'): the states the system may be in, the events that
%%          move it, the states it must never reach. Every event the model
%%          does not allow, and every forbidden state entered, is WRITTEN as
%%          a line -- so it lands in the GOOD file and the comparison judges
%%          it.
%%
%%     {ok, M0} = hwut_fsm:from_string(<<"
%%         initial: idle
%%         forbidden: crashed
%%         idle ---( request )---> waiting ---( grant )---> busy
%%         busy ---( release )---> idle
%%         :    ---( fault )--->   crashed">>),
%%     {true,  M1} = hwut_fsm:fire(<<"request">>, 1, M0),
%%     {false, M2} = hwut_fsm:fire(<<"release">>, 2, M1),
%%                   %  BREACH line 2: 'release' in 'waiting' -- allowed: grant
%%     hwut_fsm:report(M2)
%%
%% THE MACHINE IS A VALUE. 'fire' takes the machine and returns the verdict
%% with the machine that follows; the machine is the LAST argument, as in
%% OTP's data-structure modules ('maps:put(K, V, Map)'). A machine kept is a
%% place to fire from again. Python's keyword arguments are an options map
%% ('#{state => S, where => W}', '#{start => now, masked => false}').
%%
%% THE VOCABULARY IS gen_statem's: a STATE, an EVENT that moves the machine,
%% a TRANSITION; 'state(M)' is where it stands. The roles are reversed: a
%% gen_statem IS the system, its states code; this machine WATCHES one, its
%% states data -- the model a test fires the system's events into, which
%% may stand in several states at once ('dfa => false').
%%
%% STATES AND EVENTS ARE BINARIES; 'where' is none, an integer (a line) or a
%% binary. A model that cannot be meant -- and a question that cannot be
%% answered -- is {error, {fsm_error, Text}}, Text Python's FsmError's.
%%_____________________________________________________________________________
-module(hwut_fsm).
-export([new/3, from_string/1, from_string/2, to_string/1, reset/1, fire/2,
         fire/3, forbidden/1, disallow/3, allow/3, forbid/3, permit/3,
         disallowed/4, forbidding/4, state/1, current/1, in_state/2, can/2,
         allowed/1, trace/1, breach_n/1, path_to/2, path_to/3,
         state_reachable/3, unreachable/2, dead_ends/2,
         forbidden_reachable/2, check/1, check/2, report/1]).

-record(fsm, {name, dfa_f, write, edge_db, initial, model_forbidden, final,
              states, events,
              mask_db, forbid_db, permit_db, current, visit_db, taken_db,
              trace, breach_n}).

-define(ARROW_RE, "-+\\s*\\(\\s*([^()]*?)\\s*\\)\\s*-*>").
-define(NAME_RE,  "^(?:state\\s+)?([A-Za-z_][\\w.\\-]*)$").
-define(KEY_RE,   "^(initial|forbidden|final)\\s*:\\s*(.*)$").

%% RETURN: never; the model or question is refused: a throw that the API
%%         function the caller called turns into {error, {fsm_error, Text}}.
fsm_error(Format, Arguments) ->
    throw({fsm_error, iolist_to_binary(io_lib:format(Format, Arguments))}).

%% RETURN: what 'Fun()' returns, if success;
%%         {error, {fsm_error, Text}}, it refused.
answer(Fun) ->
    try Fun() catch throw:{fsm_error, _} = Reason -> {error, Reason} end.

%% ---------------------------------------------------------------- building
%% RETURN: {ok, Machine}, standing in 'Initial', the transitions the list of
%%         {State, Event, State} 'Transitions' names, if success;
%%         {error, {fsm_error, Text}}, else -- a DFA with two transitions
%%         for one (state, event); a forbidden or final state no transition
%%         names.
%%         Options: forbidden, final ([State]), states ([State] no
%%         transition touches yet), dfa (true), name (<<"fsm">>), write
%%         (fun(Line): every breach and report line goes through it; the
%%         default writes it on stdout).
new(Transitions, Initial, Options) -> answer(fun() -> make(Transitions, Initial, Options) end).

%% RETURN: {ok, Machine}; throws an fsm_error (see 'new').
make(Transitions, Initial, Options) ->
    DfaF = maps:get(dfa, Options, true),
    EdgeDb = lists:foldl(
               fun({Source, Event, Target}, Db) ->
                       Set = maps:get({Source, Event}, Db, []),
                       case DfaF andalso Set =/= [] andalso not lists:member(Target, Set) of
                           true  -> fsm_error("'~ts' --(~ts)--> '~ts' and '~ts': a DFA moves "
                                              "one way per event -- or 'DFA=False'",
                                              [Source, Event, hd(Set), Target]);
                           false -> Db#{{Source, Event} => ordsets:add_element(Target, Set)}
                       end
               end, #{}, Transitions),
    StateSet = ordsets:from_list([Initial | maps:get(states, Options, [])]
                                 ++ lists:append([[S, T] || {S, _, T} <- Transitions])),
    Forbidden = ordsets:from_list(maps:get(forbidden, Options, [])),
    Final     = ordsets:from_list(maps:get(final, Options, [])),
    _ = [case ordsets:subtract(Chosen, StateSet) of
             []      -> ok;
             Unknown -> fsm_error("~ts state(s) ~ts: named nowhere else in the model",
                                  [Label, lists:join(", ", [["'", U, "'"] || U <- Unknown])])
         end || {Label, Chosen} <- [{"forbidden", Forbidden}, {"final", Final}]],
    {ok, reset(#fsm{name            = iolist_to_binary(maps:get(name, Options, <<"fsm">>)),
                    dfa_f           = DfaF,
                    write           = maps:get(write, Options, fun(Line) -> io:put_chars([Line, $\n]) end),
                    edge_db         = EdgeDb,
                    initial         = Initial,
                    model_forbidden = Forbidden,
                    final           = Final,
                    states          = ordsets:union(StateSet, Forbidden),
                    events          = lists:usort([E || {_, E} <- maps:keys(EdgeDb)])})}.

%% RETURN: as 'from_string/2', with the defaults.
from_string(Text) -> from_string(Text, #{}).

%% RETURN: {ok, Machine}, the model the text states, if success;
%%         {error, {fsm_error, Text}} naming the line, else.
%%         One statement per line, '#' starts a comment:
%%             initial: A             where the machine starts (default: the
%%                                    first state the text names)
%%             forbidden: X, Y        states the system must never enter
%%             final: A, B            states it may end in
%%             state A                a state, transitions or not
%%             A ---( ev )---> B ---( ev2 )---> C     transitions, chained
%%             :  ---( ev )---> D     ':' -- the state that began the line
%%                                    above
%%         Options: dfa, name, write (see 'new').
from_string(Text, Options) -> answer(fun() -> read(Text, Options) end).

%% RETURN: {ok, Machine}; throws an fsm_error naming the line (see
%%         'from_string').
read(Text, Options) ->
    DfaF = maps:get(dfa, Options, true),
    Lines = re:split(Text, "\r\n|[\n\r\v\f\x1c\x1d\x1e]|\\x{85}|\\x{2028}|\\x{2029}",
                     [unicode, {return, binary}]),
    Numbered = lists:zip(lists:seq(1, length(Lines)), Lines),
    Read0 = #{triples => [], declared => #{}, line_of => #{}, first => none,
              previous => none},
    Read = lists:foldl(fun({N, Raw}, Acc) -> read_line(N, Raw, DfaF, Acc) end,
                       Read0, Numbered),
    #{triples := Triples0, declared := Declared, first := First} = Read,
    Triples = lists:reverse(Triples0),
    First == none andalso not is_map_key(initial, Declared)
        andalso fsm_error("the model names no state", []),
    Initial = case Declared of #{initial := [I | _]} -> I; _ -> First end,
    make([T || {_, E, _} = T <- Triples, E =/= none], Initial,
         Options#{forbidden => maps:get(forbidden, Declared, []),
                  final     => maps:get(final, Declared, []),
                  states    => lists:usort([S || {S, none, none} <- Triples])}).

%% RETURN: map, the reading 'Acc' with the line 'Raw' (number 'Number') read
%%         into it; throws an fsm_error for a line that cannot be meant.
read_line(Number, Raw, DfaF, Acc) ->
    [Code | _] = binary:split(Raw, <<"#">>),
    Line = string:trim(Code),
    case Line of
        <<>> -> Acc;
        _ ->
            case re:run(Line, ?KEY_RE, [unicode, ucp, {capture, all_but_first, binary}]) of
                {match, [Word, Rest]} -> read_key(Number, binary_to_atom(Word), Rest, Acc);
                nomatch               -> read_arrows(Number, Line, DfaF, Acc)
            end
    end.

%% RETURN: map, 'Acc' with the states of an 'initial:', 'forbidden:' or
%%         'final:' line declared.
read_key(Number, Word, Rest, #{declared := Declared} = Acc) ->
    Names = [name_of(Part, Number) || Part <- binary:split(Rest, <<",">>, [global]),
                                      string:trim(Part) =/= <<>>],
    Word == initial andalso length(Names) =/= 1
        andalso fsm_error("line ~b: 'initial:' names one state", [Number]),
    Acc#{declared := Declared#{Word => maps:get(Word, Declared, []) ++ Names}}.

%% RETURN: map, 'Acc' with a state line or a chain of transitions read.
read_arrows(Number, Line, DfaF, Acc) ->
    case re:split(Line, ?ARROW_RE, [unicode, ucp, {return, binary}]) of
        [_] ->
            Head = name_of(Line, Number),
            #{triples := Triples, first := First} = Acc,
            Acc#{triples := [{Head, none, none} | Triples],
                 first := first_of(First, Head), previous := Head};
        [HeadText | Parts] ->
            lists:any(fun(E) -> string:trim(E) == <<>> end, events_of(Parts))
                andalso fsm_error("line ~b: an arrow names no event -- '---( event )--->'", [Number]),
            Head = case string:trim(HeadText) of
                       <<":">> ->
                           maps:get(previous, Acc) == none
                               andalso fsm_error("line ~b: ':' stands for the state of the line "
                                                 "above, and none stands there", [Number]),
                           maps:get(previous, Acc);
                       Text -> name_of(Text, Number)
                   end,
            #{first := First} = Acc,
            chain(Number, Head, Parts, DfaF, Acc#{first := first_of(First, Head), previous := Head})
    end.

%% RETURN: [binary], the events of the parts [event, state, event, ...].
events_of([Event, _ | Rest]) -> [Event | events_of(Rest)];
events_of([])                -> [].

%% RETURN: the first state the text named -- 'Head' where none was yet.
first_of(none, Head) -> Head;
first_of(First, _)   -> First.

%% RETURN: map, 'Acc' with the transitions of a chain from 'Source' read.
chain(_, _, [], _, Acc) -> Acc;
chain(Number, Source, [EventText, TargetText | Rest], DfaF,
      #{triples := Triples, line_of := LineOf} = Acc) ->
    Target = name_of(TargetText, Number),
    Event  = string:trim(EventText),
    case LineOf of
        #{{Source, Event} := {Other, Line}} when DfaF, Other =/= Target ->
            %  THE DFA'S CONFLICT NAMED WHERE IT STANDS: both lines.
            fsm_error("line ~b: '~ts' --(~ts)--> '~ts', and line ~b: --> '~ts' -- a DFA "
                      "moves one way per event, or 'DFA=False'",
                      [Number, Source, Event, Target, Line, Other]);
        _ -> ok
    end,
    chain(Number, Target, Rest, DfaF,
          Acc#{triples := [{Source, Event, Target} | Triples],
               line_of := maps:merge(#{{Source, Event} => {Target, Number}}, LineOf)}).

%% RETURN: binary, the state 'Text' names -- 'A' or 'state A', if success;
%%         throws an fsm_error naming line 'Number', else.
name_of(Text, Number) ->
    Trimmed = string:trim(Text),
    case re:run(Trimmed, ?NAME_RE, [unicode, ucp, {capture, all_but_first, binary}]) of
        {match, [Name]} -> Name;
        nomatch         -> fsm_error("line ~b: '~ts' names no state -- a state is a word "
                                     "('A', 'state A')", [Number, Trimmed])
    end.

%% RETURN: binary, the model in the text 'from_string' reads, one transition
%%         per line, sorted.
to_string(#fsm{} = M) ->
    Head = [["initial: ", M#fsm.initial]]
        ++ [["forbidden: ", lists:join(", ", M#fsm.model_forbidden)] || M#fsm.model_forbidden =/= []]
        ++ [["final: ", lists:join(", ", M#fsm.final)] || M#fsm.final =/= []],
    Edges = all_edges(M),
    Named = ordsets:from_list([M#fsm.initial | lists:append([[S, T] || {S, _, T} <- Edges])]),
    Lines = Head ++ [[S, " ---( ", E, " )---> ", T] || {S, E, T} <- Edges]
        ++ [["state ", S] || S <- M#fsm.states, not lists:member(S, Named),
                             not lists:member(S, M#fsm.model_forbidden)],
    iolist_to_binary(lists:join($\n, Lines)).

%% RETURN: [{State, Event, State}], every transition of the model, sorted.
all_edges(#fsm{edge_db = Db}) ->
    lists:sort([{S, E, T} || {{S, E}, Targets} <- maps:to_list(Db), T <- Targets]).

%% ----------------------------------------------------------------- running
%% RETURN: machine, standing in its initial state again under the model as
%%         written: what was seen is forgotten, and every mask and every
%%         state forbidden or permitted since.
reset(#fsm{} = M) ->
    M#fsm{mask_db   = #{},
          forbid_db = maps:from_list([{S, none} || S <- M#fsm.model_forbidden]),
          permit_db = #{},
          current   = [M#fsm.initial],
          visit_db  = #{M#fsm.initial => 1},
          taken_db  = #{},
          trace     = [],
          breach_n  = 0}.

%% RETURN: what the machine's 'write' returns; the line was written.
write(#fsm{write = Write}, Format, Arguments) ->
    Write(iolist_to_binary(io_lib:format(Format, Arguments))).

%% RETURN: as 'fire/3', the breach line naming no place.
fire(Event, M) -> fire(Event, none, M).

%% RETURN: {true, Machine}, 'Event' moved the machine and it entered no
%%         forbidden state;
%%         {false, Machine}, it was not allowed where the machine stands --
%%         a BREACH line is written and the machine stays -- or it entered a
%%         forbidden state, which is written too.
%%         'Where' is the place the breach line names: an integer is a line
%%         ('line 3'), a binary stands as written, none names nothing.
fire(Event, Where, #fsm{current = Current, edge_db = Db} = M0) ->
    {Moved, Masked, M1} =
        lists:foldl(
          fun(State, {MovedAcc, MaskedAcc, Mi}) ->
                  case masked_f(State, Event, Mi) of
                      true ->
                          {MovedAcc, MaskedAcc ++ [State || is_map_key({State, Event}, Db)], Mi};
                      false ->
                          lists:foldl(
                            fun(Target, {Ma, Mk, Mj}) ->
                                    Key = {State, Event, Target},
                                    Taken = Mj#fsm.taken_db,
                                    {ordsets:add_element(Target, Ma), Mk,
                                     Mj#fsm{taken_db = Taken#{Key => maps:get(Key, Taken, 0) + 1},
                                            trace = [{Where, State, Event, Target} | Mj#fsm.trace]}}
                            end, {MovedAcc, MaskedAcc, Mi}, maps:get({State, Event}, Db, []))
                  end
          end, {[], [], M0}, Current),
    case Moved of
        [] ->
            Allowed = allowed(M1),
            KnownF  = lists:member(Event, M1#fsm.events),
            Hint = if
                       not KnownF ->
                           "an event the model never names";
                       Masked =/= [] ->
                           Since = case M1#fsm.mask_db of
                                       #{{hd(Masked), Event} := W} -> W;
                                       Db1 -> maps:get({none, Event}, Db1, none)
                                   end,
                           ["disallowed", since_text(Since)];
                       Allowed =/= [] -> ["allowed: ", lists:join(", ", Allowed)];
                       true -> "no event leaves it"
                   end,
            write(M1, "BREACH~ts: '~ts' in ~ts -- ~ts", [where_text(Where), Event, here(M1), Hint]),
            {false, M1#fsm{breach_n = M1#fsm.breach_n + 1}};
        _ ->
            Visit = lists:foldl(fun(S, V) -> V#{S => maps:get(S, V, 0) + 1} end,
                                M1#fsm.visit_db, Moved),
            M2 = M1#fsm{current = Moved, visit_db = Visit},
            Entered = ordsets:intersection(Moved, forbidden(M2)),
            _ = [write(M2, "BREACH~ts: '~ts' entered by '~ts' -- ~ts",
                       [where_text(Where), S, Event,
                        case {lists:member(S, M2#fsm.model_forbidden), maps:get(S, M2#fsm.forbid_db)} of
                            {true, none} -> "a forbidden state";
                            {_, Since}   -> ["forbidden", since_text(Since)]
                        end]) || S <- Entered],
            {Entered == [], M2#fsm{breach_n = M2#fsm.breach_n + length(Entered)}}
    end.

%% RETURN: iolist, ' line 3' for 3, ' <text>' for a text, '' for none.
where_text(none)                    -> "";
where_text(Where) when is_integer(Where) -> [" line ", integer_to_list(Where)];
where_text(Where)                   -> [" ", Where].

%% RETURN: iolist, ' since line 9', ' since <text>', or '' for none.
since_text(none)  -> "";
since_text(Where) -> [" since", where_text(Where)].

%% RETURN: iolist, where the machine stands: "'idle'", or "{'a', 'b'}".
here(#fsm{current = [One]}) -> ["'", One, "'"];
here(#fsm{current = Set})   -> ["{", lists:join(", ", [["'", S, "'"] || S <- Set]), "}"].

%% --------------------------------------------------- the law, changing
%% RETURN: [State], the states forbidden NOW, sorted -- the model's, less
%%         those permitted, with those forbidden since.
forbidden(#fsm{forbid_db = Db}) -> lists:sort(maps:keys(Db)).

%% RETURN: true, 'Event' is disallowed in 'State' now -- in every state, or
%%         in that one; false else.
masked_f(State, Event, #fsm{mask_db = Db}) ->
    is_map_key({none, Event}, Db) orelse is_map_key({State, Event}, Db).

%% RETURN: ok, 'Event' and 'State' are named by the model (none for not
%%         given); throws an fsm_error naming what is not, else.
known(Event, State, #fsm{events = Events, states = States}) ->
    Event =/= none andalso not lists:member(Event, Events)
        andalso fsm_error("'~ts': an event the model never names -- events: ~ts",
                          [Event, lists:join(", ", Events)]),
    State =/= none andalso not lists:member(State, States)
        andalso fsm_error("'~ts': a state the model never names -- states: ~ts",
                          [State, lists:join(", ", States)]),
    ok.

%% RETURN: {ok, Machine}: from now on 'Event' is a breach -- in the state
%%         'Options.state' alone, in every state where none is given --
%%         until 'allow' lifts it; the breach line says 'disallowed since
%%         <Options.where>';
%%         {error, {fsm_error, Text}}, the model names no such event or state.
disallow(Event, Options, M) ->
    answer(fun() ->
                   State = maps:get(state, Options, none),
                   known(Event, State, M),
                   Db = M#fsm.mask_db,
                   {ok, M#fsm{mask_db = maps:merge(#{{State, Event} => maps:get(where, Options, none)}, Db)}}
           end).

%% RETURN: {ok, Machine}: the mask 'disallow' set for 'Event' in that scope
%%         ('Options.state', or every state) is lifted, a mask of another
%%         scope stays;
%%         {error, {fsm_error, Text}}, the model names no such event or state.
allow(Event, Options, M) ->
    answer(fun() ->
                   State = maps:get(state, Options, none),
                   known(Event, State, M),
                   {ok, M#fsm{mask_db = maps:remove({State, Event}, M#fsm.mask_db)}}
           end).

%% RETURN: {ok, Machine}: from now on entering 'State' is a breach, until
%%         'permit'; where the machine STANDS in it, one BREACH line is
%%         written at once -- the test forbade the present;
%%         {error, {fsm_error, Text}}, the model names no such state.
forbid(State, Options, #fsm{forbid_db = Db} = M) ->
    answer(fun() ->
                   known(none, State, M),
                   case is_map_key(State, Db) of
                       true  -> {ok, M};
                       false ->
                           Where = maps:get(where, Options, none),
                           M1 = M#fsm{forbid_db = Db#{State => Where},
                                      permit_db = maps:remove(State, M#fsm.permit_db)},
                           case lists:member(State, M1#fsm.current) of
                               false -> {ok, M1};
                               true  ->
                                   write(M1, "BREACH~ts: stands in '~ts' -- forbidden~ts",
                                         [where_text(Where), State, since_text(Where)]),
                                   {ok, M1#fsm{breach_n = M1#fsm.breach_n + 1}}
                           end
                   end
           end).

%% RETURN: {ok, Machine}: 'State' is no longer forbidden -- a state of the
%%         model's own 'forbidden:' too, until 'forbid' again;
%%         {error, {fsm_error, Text}}, the model names no such state.
permit(State, Options, #fsm{forbid_db = Db} = M) ->
    answer(fun() ->
                   known(none, State, M),
                   M1 = M#fsm{forbid_db = maps:remove(State, Db)},
                   case is_map_key(State, Db) andalso lists:member(State, M#fsm.model_forbidden) of
                       true  -> {ok, M1#fsm{permit_db = (M1#fsm.permit_db)#{State => maps:get(where, Options, none)}}};
                       false -> {ok, M1}
                   end
           end).

%% RETURN: {ok, Machine}, 'Fun(Machine) -> Machine' run as a PHASE during
%%         which 'Event' is disallowed (see 'disallow'), allowed again after
%%         it; {error, {fsm_error, Text}}, as 'disallow'.
disallowed(Event, Options, Fun, M0) ->
    case disallow(Event, Options, M0) of
        {ok, M1} -> allow(Event, maps:with([state], Options), Fun(M1));
        Error    -> Error
    end.

%% RETURN: {ok, Machine}, 'Fun(Machine) -> Machine' run as a PHASE during
%%         which 'State' is forbidden (see 'forbid'), permitted again after
%%         it; {error, {fsm_error, Text}}, as 'forbid'.
forbidding(State, Options, Fun, M0) ->
    case forbid(State, Options, M0) of
        {ok, M1} -> permit(State, #{}, Fun(M1));
        Error    -> Error
    end.

%% -------------------------------------------------------------- questions
%% RETURN: {ok, State}, the one state the machine stands in;
%%         {error, {fsm_error, Text}}, a set of states stands (dfa false):
%%         ask 'current'.
state(#fsm{current = [One]}) -> {ok, One};
state(M) ->
    {error, {fsm_error, iolist_to_binary(["the machine stands in ", here(M), ": ask 'current()'"])}}.

%% RETURN: [State], every state the machine stands in, sorted.
current(#fsm{current = Current}) -> Current.

%% RETURN: true, the machine stands in 'State'; false else.
in_state(State, #fsm{current = Current}) -> lists:member(State, Current).

%% RETURN: true, 'Event' would move the machine now; false else.
can(Event, #fsm{current = Current, edge_db = Db} = M) ->
    lists:any(fun(S) -> is_map_key({S, Event}, Db) andalso not masked_f(S, Event, M) end, Current).

%% RETURN: [Event], the events that would move the machine now, sorted.
allowed(#fsm{current = Current, edge_db = Db} = M) ->
    lists:usort([E || {S, E} <- maps:keys(Db), lists:member(S, Current), not masked_f(S, E, M)]).

%% RETURN: [{Where, State, Event, State}], every transition fired, in order.
trace(#fsm{trace = Trace}) -> lists:reverse(Trace).

%% RETURN: integer, the breaches written so far.
breach_n(#fsm{breach_n = N}) -> N.

%% -------------------------------------------------------- the model alone
%% RETURN: map, State -> sorted [{Event, State}] leaving it -- under the
%%         masks where 'MaskedF', as written else.
successor_db(MaskedF, #fsm{edge_db = Db} = M) ->
    maps:map(fun(_, Pairs) -> lists:sort(Pairs) end,
             maps:groups_from_list(fun({S, _, _}) -> S end, fun({_, E, T}) -> {E, T} end,
                                   [{S, E, T} || {{S, E}, Targets} <- maps:to_list(Db),
                                                 not (MaskedF andalso masked_f(S, E, M)),
                                                 T <- Targets])).

%% RETURN: as 'path_to/3', from the initial state, under the masks.
path_to(State, M) -> path_to(State, #{}, M).

%% RETURN: [Event], the shortest event sequence from 'Options.start' -- the
%%         initial state where none, 'now' for where the machine stands, or
%%         a state -- into 'State' ([] where it starts there); among equally
%%         short ones the first in event order; under the masks unless
%%         'Options.masked' is false;
%%         none, 'State' cannot be reached from there.
path_to(State, Options, M) ->
    StartSet = case maps:get(start, Options, none) of
                   now   -> M#fsm.current;
                   none  -> [M#fsm.initial];
                   Start -> [Start]
               end,
    case lists:member(State, StartSet) of
        true  -> [];
        false ->
            Successors = successor_db(maps:get(masked, Options, true), M),
            bfs(State, queue:from_list([{S, []} || S <- StartSet]), sets:from_list(StartSet), Successors)
    end.

%% RETURN: [Event] | none, the breadth-first search for 'State' continued.
bfs(State, Queue0, Seen0, Successors) ->
    case queue:out(Queue0) of
        {empty, _} -> none;
        {{value, {Here, Path}}, Queue1} ->
            step(State, maps:get(Here, Successors, []), Path, Queue1, Seen0, Successors)
    end.

%% RETURN: [Event] | none, the successors of one state looked at, then the
%%         search continued.
step(State, [], _, Queue, Seen, Successors) -> bfs(State, Queue, Seen, Successors);
step(State, [{Event, Target} | Rest], Path, Queue, Seen, Successors) ->
    case sets:is_element(Target, Seen) of
        true                    -> step(State, Rest, Path, Queue, Seen, Successors);
        false when Target == State -> lists:reverse([Event | Path]);
        false -> step(State, Rest, Path, queue:in({Target, [Event | Path]}, Queue),
                      sets:add_element(Target, Seen), Successors)
    end.

%% RETURN: true, 'State' can be reached (see 'path_to'); false else.
state_reachable(State, Options, M) -> path_to(State, Options, M) =/= none.

%% RETURN: [State], the states forbidden now where masked, the model's else.
forbidden_of(true, M)  -> forbidden(M);
forbidden_of(false, M) -> M#fsm.model_forbidden.

%% RETURN: [State], the states no path from the initial state reaches,
%%         forbidden ones left out, sorted; under the masks unless
%%         'Options.masked' is false.
unreachable(Options, M) ->
    MaskedF = maps:get(masked, Options, true),
    Forbidden = forbidden_of(MaskedF, M),
    [S || S <- M#fsm.states, not lists:member(S, Forbidden),
          not state_reachable(S, #{masked => MaskedF}, M)].

%% RETURN: [State], the states no event leaves that are neither final nor
%%         forbidden -- where a system would hang -- sorted; under the masks
%%         unless 'Options.masked' is false.
dead_ends(Options, M) ->
    MaskedF = maps:get(masked, Options, true),
    Successors = successor_db(MaskedF, M),
    Forbidden = forbidden_of(MaskedF, M),
    [S || S <- M#fsm.states, not is_map_key(S, Successors),
          not lists:member(S, M#fsm.final), not lists:member(S, Forbidden)].

%% RETURN: [State], the forbidden states the model lets the system reach
%%         from the initial state, sorted; under the masks and the states
%%         forbidden now unless 'Options.masked' is false.
forbidden_reachable(Options, M) ->
    MaskedF = maps:get(masked, Options, true),
    [S || S <- forbidden_of(MaskedF, M), state_reachable(S, #{masked => MaskedF}, M)].

%% RETURN: as 'check/2', under the masks.
check(M) -> check(#{}, M).

%% RETURN: integer, how many findings the MODEL has, each written as one
%%         line 'MODEL: ...' -- unreachable states, dead ends, forbidden
%%         states reachable (with the shortest way there); 0 for none.
check(Options, M) ->
    MaskedF = maps:get(masked, Options, true),
    Lines = [io_lib:format("MODEL: '~ts' cannot be reached", [S]) || S <- unreachable(Options, M)]
        ++ [io_lib:format("MODEL: '~ts' is a dead end -- no event leaves it", [S]) || S <- dead_ends(Options, M)]
        ++ [io_lib:format("MODEL: forbidden '~ts' is reachable: ~ts",
                          [S, lists:join(" ", path_to(S, #{masked => MaskedF}, M))])
            || S <- forbidden_reachable(Options, M)],
    _ = [(M#fsm.write)(iolist_to_binary(L)) || L <- Lines],
    length(Lines).

%% ---------------------------------------------------------------- the end
%% RETURN: integer, the breaches seen, a non-final end counted; written
%%         before it, sorted, what the events covered of the model -- states
%%         counted without the forbidden ones:
%%             fsm: 3 of 3 states visited, 3 of 4 transitions taken, 1 breach
%%               taken      idle ---( request )---> waiting   x2
%%               not taken  busy ---( fault )---> crashed
%%               never in   ...
%%               ended in   'idle'
%%         then the masks and forbidden states still standing; a machine
%%         with final states that ends elsewhere adds a BREACH line.
report(#fsm{} = M) ->
    Edges = all_edges(M),
    EndF = M#fsm.final == [] orelse ordsets:intersection(M#fsm.current, M#fsm.final) =/= [],
    BreachN = M#fsm.breach_n + (if EndF -> 0; true -> 1 end),
    %  A FORBIDDEN STATE IS NO GOAL OF COVERAGE: counted out.
    Goal = [S || S <- M#fsm.states, not lists:member(S, M#fsm.model_forbidden)],
    Visited = [S || S <- Goal, is_map_key(S, M#fsm.visit_db)],
    write(M, "~ts: ~b of ~b states visited, ~b of ~b transitions taken, ~b breach~ts",
          [M#fsm.name, length(Visited), length(Goal), map_size(M#fsm.taken_db),
           length(Edges), BreachN, if BreachN == 1 -> ""; true -> "es" end]),
    _ = [begin
             N = maps:get(Edge, M#fsm.taken_db, 0),
             write(M, "  ~ts  ~ts ---( ~ts )---> ~ts~ts",
                   [if N > 0 -> "taken    "; true -> "not taken" end, S, E, T,
                    if N > 1 -> io_lib:format("   x~b", [N]); true -> "" end])
         end || {S, E, T} = Edge <- Edges],
    _ = [write(M, "  never in   '~ts'", [S]) || S <- M#fsm.states, not is_map_key(S, M#fsm.visit_db),
                                                not lists:member(S, M#fsm.model_forbidden)],
    write(M, "  ended in   ~ts", [here(M)]),
    %  A PHASE NEVER LIFTED IS SAID: what still stands at the end.
    Masks = lists:sort(fun({{S1, E1}, _}, {{S2, E2}, _}) -> {E1, none_last(S1)} =< {E2, none_last(S2)} end,
                       maps:to_list(M#fsm.mask_db)),
    _ = [write(M, "  disallowed '~ts' ~ts~ts",
               [E, case S of none -> "in every state"; _ -> ["in '", S, "'"] end, since_text(Since)])
         || {{S, E}, Since} <- Masks],
    _ = [write(M, "  forbidden  '~ts'~ts", [S, since_text(maps:get(S, M#fsm.forbid_db))])
         || S <- forbidden(M), not lists:member(S, M#fsm.model_forbidden)],
    _ = [write(M, "  permitted  '~ts'~ts", [S, since_text(Since)])
         || {S, Since} <- lists:sort(maps:to_list(M#fsm.permit_db))],
    EndF orelse write(M, "BREACH: ended in ~ts -- final: ~ts", [here(M), lists:join(", ", M#fsm.final)]),
    BreachN.

%% RETURN: binary, the state a mask's sort key carries -- '' for every state
%%         (Python's 'state or ""').
none_last(none) -> <<>>;
none_last(S)    -> S.
