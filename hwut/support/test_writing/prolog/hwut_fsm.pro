/*  SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
    ___________________________________________________________________________

    PURPOSE: A STATE MACHINE AS A TEST'S MODEL OF THE SYSTEM UNDER TEST -- the
             port of 'python/hwut_fsm.py' (its README explains the model, the
             breach lines, the masks and the report; this module prints the
             same words).

        fsm_from_string("initial: idle
                         idle ---( request )---> waiting ---( grant )---> busy
                         busy ---( release )---> idle", M),
        fsm_fire(M, request, [where(1)]),       % succeeds: it moved
        \+ fsm_fire(M, release, [where(2)]),    % BREACH line 2: ... -- fails
        fsm_report(M, BreachN)

    THE MODEL IS RELATIONS. A machine is a handle 'fsm(Id)'; what the text
    states is ASSERTED as facts of this module -- 'edge(Id, State, Event,
    Target)' one per transition, 'model_state/2', 'model_event/2',
    'model_forbidden/2', 'final/2' -- and every question of the model is a
    query over them: 'fsm_path_to' is a breadth-first search over 'edge/4'
    (the shortest path, the first in event order among equally short ones),
    'fsm_unreachable' and 'fsm_dead_ends' are 'findall's over the states.
    What the machine SEES while it runs -- where it stands, what was visited
    and taken, the masks -- are facts too, retracted and asserted as events
    are fired; 'fsm_reset' retracts them.

    PYTHON'S VALUES, PROLOG'S WAYS:
        a bool                success or failure: 'fsm_fire', 'fsm_can',
                              'fsm_in_state', 'fsm_state_reachable'
        None                  failure: 'fsm_path_to' fails where no path is
        keyword arguments     an option list: where(W), state(S),
                              start(now | S), masked(false), dfa(false),
                              name(N), write(Closure)
        FsmError              error(fsm_error(Message), _) -- Message Python's
                              text, word for word
        'with disallowed()'   fsm_disallowed(M, Event, Options, Goal): the
                              mask stands while Goal runs, lifted however it
                              ends (setup_call_cleanup)

    'where': an integer names a line ('line 3'), any other text stands as
    written. 'write(Closure)': every breach, finding and report line goes
    through 'call(Closure, Line)'; the default writes it and a newline.
    ___________________________________________________________________________
*/
:- module(hwut_fsm,
          [ fsm_new/4,                  % +Transitions, +Initial, +Options, -M
            fsm_from_string/2,          % +Text, -M
            fsm_from_string/3,          % +Text, +Options, -M
            fsm_to_string/2,            % +M, -String
            fsm_free/1,                 % +M
            fsm_reset/1,                % +M
            fsm_fire/2,                 % +M, +Event
            fsm_fire/3,                 % +M, +Event, +Options
            fsm_state/2,                % +M, -State
            fsm_current/2,              % +M, -States
            fsm_in_state/2,             % +M, +State
            fsm_can/2,                  % +M, +Event
            fsm_allowed/2,              % +M, -Events
            fsm_trace/2,                % +M, -Trace
            fsm_breach_n/2,             % +M, -N
            fsm_forbidden/2,            % +M, -States
            fsm_disallow/3,             % +M, +Event, +Options
            fsm_allow/3,                % +M, +Event, +Options
            fsm_forbid/3,               % +M, +State, +Options
            fsm_permit/3,               % +M, +State, +Options
            fsm_disallowed/4,           % +M, +Event, +Options, :Goal
            fsm_forbidding/4,           % +M, +State, +Options, :Goal
            fsm_path_to/3,              % +M, +State, -Path
            fsm_path_to/4,              % +M, +State, +Options, -Path
            fsm_state_reachable/2,      % +M, +State
            fsm_state_reachable/3,      % +M, +State, +Options
            fsm_unreachable/3,          % +M, +Options, -States
            fsm_dead_ends/3,            % +M, +Options, -States
            fsm_forbidden_reachable/3,  % +M, +Options, -States
            fsm_check/2,                % +M, -FindingN
            fsm_check/3,                % +M, +Options, -FindingN
            fsm_report/2                % +M, -BreachN
          ]).
:- encoding(utf8).
:- use_module(library(option)).
:- use_module(library(apply)).
:- use_module(library(lists)).

:- meta_predicate
    fsm_new(+, +, :, -),
    fsm_from_string(+, :, -),
    fsm_disallowed(+, +, +, 0),
    fsm_forbidding(+, +, +, 0).

%  THE MODEL, as written                      THE RUN, as seen
:- dynamic info/5,              % Id, Name, Dfa, Initial, Write
           edge/4,              % Id, State, Event, Target
           model_state/2,       % Id, State       (the state tuple)
           model_event/2,       % Id, Event       (the event tuple)
           model_forbidden/2,   % Id, State
           final/2,             % Id, State
           current/2,           % Id, State
           visit/3,             % Id, State, N
           taken/5,             % Id, State, Event, Target, N
           trace/3,             % Id, Seq, t(Where, State, Event, Target)
           mask/4,              % Id, State | '$every', Event, Since
           forbid/3,            % Id, State, Since
           permit/3,            % Id, State, Since
           breach/2.            % Id, N

fsm_error(Format, Args) :-
    format(string(Message), Format, Args),
    throw(error(fsm_error(Message), _)).

:- multifile prolog:error_message//1.
prolog:error_message(fsm_error(Message)) --> [ 'FsmError: ~w'-[Message] ].

/* ------------------------------------------------------------- reading */

%!  fsm_new(+Transitions, +Initial, :Options, -M) is det.
%
%   RETURN: M, 'fsm(Id)', a machine standing in 'Initial' over the list of
%           'State-Event-Target' triples, if success; raises
%           error(fsm_error(Message), _), else -- a DFA with two transitions
%           for one (state, event); a forbidden or final state no
%           transition names.
%           Options: forbidden(States), final(States), dfa(false),
%           name(Name) ('fsm'), write(Closure), states(States) -- states no
%           transition touches.
fsm_new(Triples, Initial, Module:Options, fsm(Id)) :-
    flag(hwut_fsm_id, Id, Id + 1),
    option(dfa(Dfa0), Options, true), ( Dfa0 == false -> Dfa = false ; Dfa = true ),
    option(name(Name), Options, fsm),
    (   option(write(W0), Options) -> W = Module:W0 ; W = hwut_fsm:write_line ),
    option(states(Extra), Options, []),
    option(forbidden(Forbidden0), Options, []),
    option(final(Final0), Options, []),
    catch(model(Id, Triples, Initial, Extra, Forbidden0, Final0, Dfa),
          E, ( fsm_free(fsm(Id)), throw(E) )),
    assertz(info(Id, Name, Dfa, Initial, W)),
    fsm_reset(fsm(Id)).

model(Id, Triples, Initial, Extra, Forbidden0, Final0, Dfa) :-
    forall(member(S-E-T, Triples), add_edge(Id, Dfa, S, E, T)),
    findall(S, ( member(S, [Initial|Extra]) ; edge(Id, S, _, _) ; edge(Id, _, _, S) ), States0),
    sort(States0, StateSet),
    sort(Forbidden0, Forbidden), sort(Final0, Final),
    unknown_check(forbidden, Forbidden, StateSet),
    unknown_check(final, Final, StateSet),
    forall(member(S, StateSet), assertz(model_state(Id, S))),
    forall(member(S, Forbidden), assertz(model_forbidden(Id, S))),
    forall(member(S, Final), assertz(final(Id, S))),
    findall(E, edge(Id, _, E, _), Events0), sort(Events0, Events),
    forall(member(E, Events), assertz(model_event(Id, E))).

add_edge(Id, Dfa, S, E, T) :-
    (   edge(Id, S, E, T) -> true
    ;   Dfa == true, findall(X, edge(Id, S, E, X), Xs), Xs = [_|_]
    ->  sort(Xs, [First|_]),
        fsm_error("'~w' --(~w)--> '~w' and '~w': a DFA moves one way per event -- or 'DFA=False'",
                  [S, E, First, T])
    ;   assertz(edge(Id, S, E, T))
    ).

unknown_check(Label, Chosen, StateSet) :-
    exclude([S]>>memberchk(S, StateSet), Chosen, Unknown),
    (   Unknown == [] -> true
    ;   maplist([S, Q]>>format(string(Q), "'~w'", [S]), Unknown, Qs),
        atomic_list_concat(Qs, ', ', Text),
        fsm_error("~w state(s) ~w: named nowhere else in the model", [Label, Text])
    ).

write_line(Line) :- format("~w~n", [Line]).

%!  fsm_free(+M) is det.
%
%   RETURN: true; every fact of machine M is retracted -- the handle names
%           nothing from now on.
fsm_free(fsm(Id)) :-
    forall(member(P, [info/5, edge/4, model_state/2, model_event/2, model_forbidden/2,
                      final/2, current/2, visit/3, taken/5, trace/3, mask/4,
                      forbid/3, permit/3, breach/2]),
           ( P = N/A, functor(H, N, A), arg(1, H, Id), retractall(H) )).

%!  fsm_from_string(+Text, -M) is det.
%!  fsm_from_string(+Text, :Options, -M) is det.
%
%   RETURN: M, the machine the model text states, if success; raises
%           error(fsm_error(Message), _) naming the line, else. One statement
%           per line, '#' starts a comment:
%               initial: A          forbidden: X, Y        final: A, B
%               state A             (a state, transitions or not)
%               A ---( ev )---> B ---( ev2 )---> C          a chain
%               :  ---( ev )---> D  ':' the state that began the line above
%           Options as 'fsm_new': dfa(false), name(Name), write(Closure).
fsm_from_string(Text, M) :- fsm_from_string(Text, [], M).
fsm_from_string(Text, Module:Options, M) :-
    option(dfa(Dfa0), Options, true), ( Dfa0 == false -> Dfa = false ; Dfa = true ),
    split_string(Text, "\n", "", Raw),
    read_lines(Raw, 1, Dfa, s([], [], none, none), s(Items, Declared, First, _)),
    (   First == none, \+ memberchk(initial-_, Declared)
    ->  fsm_error("the model names no state", [])
    ;   true
    ),
    reverse(Items, Ordered),
    (   memberchk(initial-[I|_], Declared) -> Initial = I ; Initial = First ),
    findall(S-E-T, member(t(S, E, T, _), Ordered), Triples),
    findall(S, member(state(S), Ordered), States),
    declared(forbidden, Declared, Forbidden),
    declared(final, Declared, Final),
    fsm_new(Triples, Initial,
            Module:[forbidden(Forbidden), final(Final), states(States)|Options], M).

declared(Word, Declared, Names) :-
    findall(N, ( member(Word-Ns, Declared), member(N, Ns) ), Names).

%   read_lines(+Lines, +Number, +Dfa, +State0, -State)
%   RETURN: State is
%           s(Items, Declared, First, PreviousHead) -- Items 't(S, E, T, Line)' and
%           'state(S)' newest first, Declared 'Word-Names' in written order.
read_lines([], _, _, S, S).
read_lines([Raw|Rest], N, Dfa, S0, S) :-
    string_codes(Raw, Cs0),
    ( append(Before, [0'#|_], Cs0) -> true ; Before = Cs0 ),
    strip(Before, Line),
    (   Line == [] -> S1 = S0
    ;   read_line(Line, N, Dfa, S0, S1)
    ),
    N1 is N + 1,
    read_lines(Rest, N1, Dfa, S1, S).

read_line(Line, N, _, s(Is, D0, F, P), s(Is, D, F, P)) :-
    phrase(key(Word, RestCs), Line), !,
    split_codes(RestCs, 0',, Parts),
    findall(Name, ( member(Part, Parts), strip(Part, P1), P1 \== [], name_of(P1, N, Name) ), Names),
    (   Word == initial, Names \= [_]
    ->  fsm_error("line ~d: 'initial:' names one state", [N])
    ;   true
    ),
    append(D0, [Word-Names], D).
read_line(Line, N, Dfa, s(Is0, D, F0, P0), s(Is, D, F, P)) :-
    split_arrows(Line, Parts),
    (   Parts = [_]
    ->  name_of(Line, N, Head), first(F0, Head, F), P = Head,
        Is = [state(Head)|Is0]
    ;   Parts = [HeadText0|Chain],
        (   arrow_events(Chain, Events), member(E, Events), strip(E, [])
        ->  fsm_error("line ~d: an arrow names no event -- '---( event )--->'", [N])
        ;   true
        ),
        strip(HeadText0, HeadText),
        (   HeadText == `:`
        ->  (   P0 == none
            ->  fsm_error("line ~d: ':' stands for the state of the line above, and none stands there", [N])
            ;   Head = P0
            )
        ;   name_of(HeadText, N, Head)
        ),
        first(F0, Head, F), P = Head,
        chain(Chain, Head, N, Dfa, Is0, Is)
    ).

first(none, H, H) :- !.
first(F, _, F).

arrow_events([], []).
arrow_events([E, _|Rest], [E|Es]) :- arrow_events(Rest, Es).

%   chain(+EventTargetParts, +Source, +N, +Dfa, +Items0, -Items)
%   RETURN: the
%           transitions of one chain; a DFA's conflict named where both stand.
chain([], _, _, _, Is, Is).
chain([EventCs, TargetCs|Rest], Source, N, Dfa, Is0, Is) :-
    name_of(TargetCs, N, Target),
    strip(EventCs, ECs), atom_codes(Event, ECs),
    (   Dfa == true, line_of(Source, Event, Is0, Other, OtherN), Other \== Target
    ->  fsm_error("line ~d: '~w' --(~w)--> '~w', and line ~d: --> '~w' -- a DFA moves one way per event, or 'DFA=False'",
                  [N, Source, Event, Target, OtherN, Other])
    ;   true
    ),
    chain(Rest, Target, N, Dfa, [t(Source, Event, Target, N)|Is0], Is).

%   line_of(+S, +E, +Items, -Target, -Line)
%   RETURN: the FIRST transition (S, E)
%           written -- the items stand newest first.
line_of(S, E, Is, T, N) :- reverse(Is, Ordered), memberchk(t(S, E, T, N), Ordered).

%   name_of(+Codes, +Line, -Name)
%   RETURN: the state 'A' or 'state A' names, as an
%           atom; raises naming the line, else.
name_of(Cs0, N, Name) :-
    strip(Cs0, Cs),
    (   phrase(state_name(NameCs), Cs) -> atom_codes(Name, NameCs)
    ;   fsm_error("line ~d: '~s' names no state -- a state is a word ('A', 'state A')", [N, Cs])
    ).

/* THE TEXT'S FORMS, as grammars over codes -- the Python's regular
   expressions, each the same language:
       arrow       -+\s*\(\s*([^()]*?)\s*\)\s*-*>
       state_name  ^(?:state\s+)?([A-Za-z_][\w.\-]*)$
       key         ^(initial|forbidden|final)\s*:\s*(.*)$                  */

key(Word, Rest) --> key_word(Word), blanks, ":", blanks, remainder(Rest).
key_word(initial)   --> "initial".
key_word(forbidden) --> "forbidden".
key_word(final)     --> "final".

state_name(Name) --> "state", blank, blanks, word(Name).
state_name(Name) --> word(Name).

word([C|Cs]) --> [C], { code_type(C, csymf), C < 128 }, word_rest(Cs).
word_rest([C|Cs]) --> [C], { code_type(C, csym) ; C == 0'. ; C == 0'- }, !, word_rest(Cs).
word_rest([]) --> [].

arrow(Event) -->
    dash, dashes, blanks, "(", blanks, inner(Inner), ")", blanks, dashes, ">",
    { reverse(Inner, R), strip_leading_blanks(R, R1), reverse(R1, Event) }.

dash --> "-".
dashes --> "-", !, dashes.
dashes --> [].

inner([C|Cs]) --> [C], { C \== 0'(, C \== 0') }, !, inner(Cs).
inner([]) --> [].

blank --> [C], { code_type(C, space) }.
blanks --> blank, !, blanks.
blanks --> [].

remainder(Cs, Cs, []).

%   split_arrows(+Codes, -Parts)
%   RETURN: 're.split' by the arrow -- the text
%           between arrows and each arrow's event, alternating; the LEFTMOST arrow
%           first, as the regular expression finds it.
split_arrows(Cs, Parts) :-
    (   append(Before, After, Cs), phrase(arrow(Event), After, Remain)
    ->  Parts = [Before, Event|Rest], split_arrows(Remain, Rest)
    ;   Parts = [Cs]
    ).

split_codes(Cs, Sep, Parts) :-
    (   append(Before, [Sep|After], Cs) -> Parts = [Before|Rest], split_codes(After, Sep, Rest)
    ;   Parts = [Cs]
    ).

strip(Cs, Stripped) :-
    strip_leading_blanks(Cs, C1), reverse(C1, R), strip_leading_blanks(R, R1), reverse(R1, Stripped).

strip_leading_blanks([C|Cs], R) :- code_type(C, space), !, strip_leading_blanks(Cs, R).
strip_leading_blanks(Cs, Cs).

%!  fsm_to_string(+M, -String) is det.
%
%   RETURN: String, the model in the text 'fsm_from_string' reads, one
%           transition per line, sorted -- what a book page or a GOOD file
%           can show of it.
fsm_to_string(fsm(Id), String) :-
    info(Id, _, _, Initial, _),
    format(string(L0), "initial: ~w", [Initial]),
    findall(S, model_forbidden(Id, S), Fs),
    findall(S, final(Id, S), Finals),
    ( Fs == [] -> L1 = [] ; joined(Fs, ", ", FT), format(string(F), "forbidden: ~w", [FT]), L1 = [F] ),
    ( Finals == [] -> L2 = [] ; joined(Finals, ", ", NT), format(string(Fi), "final: ~w", [NT]), L2 = [Fi] ),
    all_edges(Id, Edges),
    findall(L, ( member(e(S, E, T), Edges), format(string(L), "~w ---( ~w )---> ~w", [S, E, T]) ), L3),
    findall(L, ( model_state(Id, S), S \== Initial, \+ edge(Id, S, _, _), \+ edge(Id, _, _, S),
                 \+ model_forbidden(Id, S), format(string(L), "state ~w", [S]) ), L4),
    append([[L0], L1, L2, L3, L4], Lines),
    joined(Lines, "\n", String).

joined(Items, Sep, String) :- atomic_list_concat(Items, Sep, A), atom_string(A, String).

all_edges(Id, Edges) :- findall(e(S, E, T), edge(Id, S, E, T), Es), sort(Es, Edges).

/* ------------------------------------------------------------- running */

%!  fsm_reset(+M) is det.
%
%   RETURN: true; the machine stands in its initial state again, under the
%           model as written: what was seen is forgotten, and so is every
%           mask and every state forbidden or permitted since.
fsm_reset(fsm(Id)) :-
    info(Id, _, _, Initial, _),
    forall(member(H, [current(Id, _), visit(Id, _, _), taken(Id, _, _, _, _), trace(Id, _, _),
                      mask(Id, _, _, _), forbid(Id, _, _), permit(Id, _, _), breach(Id, _)]),
           retractall(H)),
    forall(model_forbidden(Id, S), assertz(forbid(Id, S, '$nowhere'))),
    assertz(current(Id, Initial)),
    assertz(visit(Id, Initial, 1)),
    assertz(breach(Id, 0)).

where_text('$nowhere', "") :- !.
where_text(W, T) :- integer(W), !, format(string(T), " line ~d", [W]).
where_text(W, T) :- format(string(T), " ~w", [W]).

since_text('$nowhere', "") :- !.
since_text(W, T) :- where_text(W, WT), string_concat(" since", WT, T).

where_of(Options, W) :- option(where(W), Options, '$nowhere').

say(Id, Format, Args) :-
    info(Id, _, _, _, W), format(string(Line), Format, Args), call(W, Line).

breach_add(Id) :- retract(breach(Id, N)), N1 is N + 1, assertz(breach(Id, N1)).

current_list(Id, States) :- findall(S, current(Id, S), Ss), sort(Ss, States).

masked(Id, S, E) :- ( mask(Id, '$every', E, _) -> true ; mask(Id, S, E, _) ).

%!  fsm_fire(+M, +Event) is semidet.
%!  fsm_fire(+M, +Event, +Options) is semidet.
%
%   RETURN: true,  'Event' moved the machine and entered no forbidden state;
%           fails, it was not allowed where the machine stands -- a BREACH
%                  line is written and the machine stays -- or it entered a
%                  forbidden state, which is written too.
%           Options: where(W), the place a breach line names.
fsm_fire(M, E) :- fsm_fire(M, E, []).
fsm_fire(fsm(Id), Event, Options) :-
    where_of(Options, Where),
    current_list(Id, Here),
    findall(S, ( member(S, Here), masked(Id, S, Event), edge(Id, S, Event, _) ), MaskedL0),
    list_to_set(MaskedL0, Masked),
    findall(S-T, ( member(S, Here), \+ masked(Id, S, Event),
                   findall(X, edge(Id, S, Event, X), Xs), sort(Xs, Ts), member(T, Ts) ), Moves),
    (   Moves == []
    ->  breach_add(Id),
        breach_hint(Id, Event, Masked, Hint),
        here_text(Id, HereT), where_text(Where, WT),
        say(Id, "BREACH~w: '~w' in ~w -- ~w", [WT, Event, HereT, Hint]),
        fail
    ;   forall(member(S-T, Moves), take(Id, Where, S, Event, T)),
        findall(T, member(_-T, Moves), Targets0), sort(Targets0, Targets),
        retractall(current(Id, _)),
        forall(member(T, Targets), ( assertz(current(Id, T)), count_visit(Id, T) )),
        findall(T, ( member(T, Targets), forbid(Id, T, _) ), Entered),
        forall(member(T, Entered), entered(Id, Where, T, Event)),
        Entered == []
    ).

take(Id, Where, S, E, T) :-
    (   retract(taken(Id, S, E, T, N)) -> N1 is N + 1 ; N1 = 1 ),
    assertz(taken(Id, S, E, T, N1)),
    aggregate_all(count, trace(Id, _, _), Seq),
    assertz(trace(Id, Seq, t(Where, S, E, T))).

count_visit(Id, S) :-
    (   retract(visit(Id, S, N)) -> N1 is N + 1 ; N1 = 1 ),
    assertz(visit(Id, S, N1)).

entered(Id, Where, T, Event) :-
    breach_add(Id),
    forbid(Id, T, Since),
    (   model_forbidden(Id, T), Since == '$nowhere' -> Why = "a forbidden state"
    ;   since_text(Since, ST), string_concat("forbidden", ST, Why)
    ),
    where_text(Where, WT),
    say(Id, "BREACH~w: '~w' entered by '~w' -- ~w", [WT, T, Event, Why]).

breach_hint(Id, Event, _, "an event the model never names") :- \+ model_event(Id, Event), !.
breach_hint(Id, Event, [S|_], Hint) :- !,
    (   mask(Id, S, Event, Since) -> true
    ;   mask(Id, '$every', Event, Since) -> true
    ;   Since = '$nowhere'
    ),
    since_text(Since, ST), string_concat("disallowed", ST, Hint).
breach_hint(Id, _, [], Hint) :-
    fsm_allowed(fsm(Id), Allowed),
    (   Allowed == [] -> Hint = "no event leaves it"
    ;   joined(Allowed, ", ", A), string_concat("allowed: ", A, Hint)
    ).

%   here_text(+Id, -Text)
%   RETURN: "'idle'", or "{'a', 'b'}" for a set.
here_text(Id, Text) :-
    current_list(Id, Here),
    (   Here = [S] -> format(string(Text), "'~w'", [S])
    ;   maplist([S, Q]>>format(string(Q), "'~w'", [S]), Here, Qs),
        joined(Qs, ", ", J), format(string(Text), "{~w}", [J])
    ).

/* --------------------------------------------------- the law, changing */

%!  fsm_forbidden(+M, -States) is det.
%
%   RETURN: States, sorted, forbidden NOW -- the model's, less those
%           permitted, with those forbidden since.
fsm_forbidden(fsm(Id), States) :- findall(S, forbid(Id, S, _), Ss), sort(Ss, States).

known(Id, Event, State) :-
    (   Event \== '$none', \+ model_event(Id, Event)
    ->  findall(E, model_event(Id, E), Es), joined(Es, ", ", ET),
        fsm_error("'~w': an event the model never names -- events: ~w", [Event, ET])
    ;   true
    ),
    (   State \== '$every', State \== '$none', \+ model_state(Id, State)
    ->  findall(S, model_state(Id, S), Ss), joined(Ss, ", ", ST),
        fsm_error("'~w': a state the model never names -- states: ~w", [State, ST])
    ;   true
    ).

%!  fsm_disallow(+M, +Event, +Options) is det.
%
%   RETURN: true; from now on 'Event' is a breach -- in state(S) alone, or
%           in every state where no state(S) is given -- until 'fsm_allow'
%           lifts it; the breach line says 'disallowed since <where>'.
%           Raises error(fsm_error(_), _) where the model names no such event
%           or state.
fsm_disallow(fsm(Id), Event, Options) :-
    option(state(State), Options, '$every'), where_of(Options, Where),
    known(Id, Event, State),
    (   mask(Id, State, Event, _) -> true ; assertz(mask(Id, State, Event, Where)) ).

%!  fsm_allow(+M, +Event, +Options) is det.
%
%   RETURN: true; the mask 'fsm_disallow(M, Event, Options)' set is lifted --
%           a mask of another scope stays. Raises as 'fsm_disallow'.
fsm_allow(fsm(Id), Event, Options) :-
    option(state(State), Options, '$every'),
    known(Id, Event, State),
    retractall(mask(Id, State, Event, _)).

%!  fsm_forbid(+M, +State, +Options) is det.
%
%   RETURN: true; from now on entering 'State' is a breach, until
%           'fsm_permit'. Where the machine STANDS in it, one BREACH line is
%           written at once: the test forbade the present. Raises where the
%           model names no such state.
fsm_forbid(fsm(Id), State, Options) :-
    where_of(Options, Where),
    known(Id, '$none', State),
    (   forbid(Id, State, _) -> true
    ;   assertz(forbid(Id, State, Where)),
        retractall(permit(Id, State, _)),
        (   current(Id, State)
        ->  breach_add(Id), where_text(Where, WT), since_text(Where, ST),
            say(Id, "BREACH~w: stands in '~w' -- forbidden~w", [WT, State, ST])
        ;   true
        )
    ).

%!  fsm_permit(+M, +State, +Options) is det.
%
%   RETURN: true; 'State' is no longer forbidden -- a state of the model's
%           own 'forbidden:' too, until 'fsm_forbid' again. Raises where the
%           model names no such state.
fsm_permit(fsm(Id), State, Options) :-
    where_of(Options, Where),
    known(Id, '$none', State),
    (   retract(forbid(Id, State, _)), model_forbidden(Id, State)
    ->  retractall(permit(Id, State, _)), assertz(permit(Id, State, Where))
    ;   true
    ).

%!  fsm_disallowed(+M, +Event, +Options, :Goal) is semidet.
%
%   RETURN: what 'Goal' returns, run once with 'Event' disallowed (see
%           'fsm_disallow'); the mask is lifted on leaving, whatever way --
%           Python's 'with m.disallowed(...)'.
fsm_disallowed(M, Event, Options, Goal) :-
    setup_call_cleanup(fsm_disallow(M, Event, Options), once(Goal),
                       fsm_allow(M, Event, Options)).

%!  fsm_forbidding(+M, +State, +Options, :Goal) is semidet.
%
%   RETURN: what 'Goal' returns, run once with 'State' forbidden (see
%           'fsm_forbid'); permitted again on leaving, whatever way.
fsm_forbidding(M, State, Options, Goal) :-
    setup_call_cleanup(fsm_forbid(M, State, Options), once(Goal),
                       fsm_permit(M, State, [])).

/* ------------------------------------------------------------ questions */

%!  fsm_state(+M, -State) is det.
%
%   RETURN: State, the one state the machine stands in, if success; raises
%           error(fsm_error(_), _), else -- a set of states stands
%           (dfa(false)): ask 'fsm_current'.
fsm_state(fsm(Id), State) :-
    current_list(Id, Here),
    (   Here = [State] -> true
    ;   here_text(Id, T), fsm_error("the machine stands in ~w: ask 'current()'", [T])
    ).

%!  fsm_current(+M, -States) is det.
%
%   RETURN: States, sorted, every state the machine stands in.
fsm_current(fsm(Id), States) :- current_list(Id, States).

%!  fsm_in_state(+M, +State) is semidet.
%
%   RETURN: true, if the machine stands in 'State'; fails, else.
fsm_in_state(fsm(Id), State) :- current(Id, State), !.

%!  fsm_can(+M, +Event) is semidet.
%
%   RETURN: true, if 'Event' would move the machine now; fails, else.
fsm_can(fsm(Id), Event) :- current(Id, S), edge(Id, S, Event, _), \+ masked(Id, S, Event), !.

%!  fsm_allowed(+M, -Events) is det.
%
%   RETURN: Events, sorted, every event that would move the machine now.
fsm_allowed(fsm(Id), Events) :-
    findall(E, ( current(Id, S), edge(Id, S, E, _), \+ masked(Id, S, E) ), Es),
    sort(Es, Events).

%!  fsm_trace(+M, -Trace) is det.
%
%   RETURN: Trace, every transition fired, in order: 't(Where, State, Event,
%           Target)', Where '$nowhere' where the fire named none.
fsm_trace(fsm(Id), Trace) :-
    findall(Seq-T, trace(Id, Seq, T), Pairs), keysort(Pairs, Sorted), pairs_values(Sorted, Trace).

%!  fsm_breach_n(+M, -N) is det.
%
%   RETURN: N, the breaches seen since the last reset.
fsm_breach_n(fsm(Id), N) :- breach(Id, N).

/* ------------------------------------------------------ the model alone */

%   successor(+Id, +Masked, ?Source, -Pairs)
%   RETURN: the sorted 'Event-Target'
%           pairs leaving Source -- under the masks where Masked is true.
successor(Id, Masked, Source, Pairs) :-
    findall(E-T, ( edge(Id, Source, E, T), \+ ( Masked == true, masked(Id, Source, E) ) ), Ps),
    sort(Ps, Pairs).

masked_option(Options, M) :- ( option(masked(false), Options) -> M = false ; M = true ).

%!  fsm_path_to(+M, +State, -Path) is semidet.
%!  fsm_path_to(+M, +State, +Options, -Path) is semidet.
%
%   RETURN: Path, the list of events -- the shortest sequence from the start
%           into 'State', the first in event order among equally short ones
%           ('[]' where the start is 'State'), if one exists; fails, else
%           (Python's None). Options: start(S) -- the initial state where
%           not given, 'now' for where the machine stands; masked(false) --
%           the model as written, not under the masks standing now.
fsm_path_to(M, State, Path) :- fsm_path_to(M, State, [], Path).
fsm_path_to(fsm(Id), State, Options, Path) :-
    masked_option(Options, Masked),
    (   option(start(now), Options) -> current_list(Id, Start)
    ;   option(start(S), Options) -> Start = [S]
    ;   info(Id, _, _, Initial, _), Start = [Initial]
    ),
    (   memberchk(State, Start) -> Path = []
    ;   findall(S-[], member(S, Start), Queue),
        bfs(Queue, Id, Masked, State, Start, Reversed),
        reverse(Reversed, Path)
    ).

%   bfs(+Queue, +Id, +Masked, +Goal, +Seen, -ReversedPath)
%   RETURN: breadth-first --
%           the queue a list of 'State-ReversedEvents', the oldest first; the goal
%           is taken where it is first SEEN as a successor, as the Python does.
bfs([Here-Path|Queue], Id, Masked, Goal, Seen, Result) :-
    successor(Id, Masked, Here, Pairs),
    expand(Pairs, Path, Goal, Seen, Seen1, New, Found),
    (   nonvar(Found) -> Result = Found
    ;   append(Queue, New, Queue1),
        bfs(Queue1, Id, Masked, Goal, Seen1, Result)
    ).

expand([], _, _, Seen, Seen, [], _).
expand([E-T|Pairs], Path, Goal, Seen0, Seen, New, Found) :-
    (   memberchk(T, Seen0) -> expand(Pairs, Path, Goal, Seen0, Seen, New, Found)
    ;   T == Goal -> Found = [E|Path], Seen = Seen0, New = []
    ;   New = [T-[E|Path]|New1],
        expand(Pairs, Path, Goal, [T|Seen0], Seen, New1, Found)
    ).

%!  fsm_state_reachable(+M, +State) is semidet.
%!  fsm_state_reachable(+M, +State, +Options) is semidet.
%
%   RETURN: true, if 'State' can be reached (see 'fsm_path_to', its options
%           the same); fails, else.
fsm_state_reachable(M, State) :- fsm_state_reachable(M, State, []).
fsm_state_reachable(M, State, Options) :- fsm_path_to(M, State, Options, _), !.

forbidden_of(Id, true, Fs) :- !, fsm_forbidden(fsm(Id), Fs).
forbidden_of(Id, false, Fs) :- findall(S, model_forbidden(Id, S), Fs).

%!  fsm_unreachable(+M, +Options, -States) is det.
%
%   RETURN: States, sorted, no path from the initial state reaches --
%           forbidden ones left out; under the masks unless masked(false).
fsm_unreachable(fsm(Id), Options, States) :-
    masked_option(Options, Masked), forbidden_of(Id, Masked, Fs),
    findall(S, ( model_state(Id, S), \+ memberchk(S, Fs),
                 \+ fsm_state_reachable(fsm(Id), S, [masked(Masked)]) ), States).

%!  fsm_dead_ends(+M, +Options, -States) is det.
%
%   RETURN: States, sorted, no event leaves that are neither final nor
%           forbidden -- where a system would hang; under the masks unless
%           masked(false) (a mask can make one).
fsm_dead_ends(fsm(Id), Options, States) :-
    masked_option(Options, Masked), forbidden_of(Id, Masked, Fs),
    findall(S, ( model_state(Id, S), successor(Id, Masked, S, []),
                 \+ final(Id, S), \+ memberchk(S, Fs) ), States).

%!  fsm_forbidden_reachable(+M, +Options, -States) is det.
%
%   RETURN: States, sorted, the forbidden states the model lets the system
%           reach from the initial state; under the masks and the states
%           forbidden now unless masked(false).
fsm_forbidden_reachable(fsm(Id), Options, States) :-
    masked_option(Options, Masked), forbidden_of(Id, Masked, Fs),
    include([S]>>fsm_state_reachable(fsm(Id), S, [masked(Masked)]), Fs, States).

%!  fsm_check(+M, -FindingN) is det.
%!  fsm_check(+M, +Options, -FindingN) is det.
%
%   RETURN: FindingN, how many findings the MODEL has, each written as one
%           line 'MODEL: ...' -- unreachable states, dead ends, forbidden
%           states reachable (with the shortest way there); 0 where it has
%           none. Under the masks standing now unless masked(false).
fsm_check(M, N) :- fsm_check(M, [], N).
fsm_check(fsm(Id), Options, N) :-
    masked_option(Options, Masked), O = [masked(Masked)],
    fsm_unreachable(fsm(Id), O, Un),
    fsm_dead_ends(fsm(Id), O, Dead),
    fsm_forbidden_reachable(fsm(Id), O, FR),
    findall(L, ( member(S, Un), format(string(L), "MODEL: '~w' cannot be reached", [S]) ), L1),
    findall(L, ( member(S, Dead), format(string(L), "MODEL: '~w' is a dead end -- no event leaves it", [S]) ), L2),
    findall(L, ( member(S, FR), fsm_path_to(fsm(Id), S, O, P), joined(P, " ", PT),
                 format(string(L), "MODEL: forbidden '~w' is reachable: ~w", [S, PT]) ), L3),
    append([L1, L2, L3], Lines),
    info(Id, _, _, _, W),
    forall(member(L, Lines), call(W, L)),
    length(Lines, N).

/* -------------------------------------------------------------- the end */

%!  fsm_report(+M, -BreachN) is det.
%
%   RETURN: BreachN, the breaches seen, counting a non-final end; written
%           before it, sorted, what the events covered of the model --
%           states counted without the forbidden ones:
%               fsm: 3 of 3 states visited, 3 of 4 transitions taken, 1 breach
%                 taken      idle ---( request )---> waiting   x2
%                 not taken  busy ---( fault )---> crashed
%                 never in   ...
%                 ended in   'idle'
%           A machine with final states that ends elsewhere adds a BREACH
%           line.
fsm_report(fsm(Id), BreachN) :-
    info(Id, Name, _, _, _),
    all_edges(Id, Edges), length(Edges, EdgeN),
    breach(Id, B0),
    (   \+ final(Id, _) -> End = true
    ;   \+ \+ ( current(Id, X), final(Id, X) ) -> End = true
    ;   End = false
    ),
    ( End == true -> BreachN = B0 ; BreachN is B0 + 1 ),
    findall(S, ( model_state(Id, S), \+ model_forbidden(Id, S) ), Goal), length(Goal, GoalN),
    include([S]>>visit(Id, S, _), Goal, Visited), length(Visited, VisitedN),
    aggregate_all(count, taken(Id, _, _, _, _), TakenN),
    ( BreachN =:= 1 -> Es = "" ; Es = "es" ),
    say(Id, "~w: ~d of ~d states visited, ~d of ~d transitions taken, ~d breach~w",
        [Name, VisitedN, GoalN, TakenN, EdgeN, BreachN, Es]),
    forall(member(e(S, E, T), Edges),
           (   taken(Id, S, E, T, N)
           ->  ( N > 1 -> format(string(X), "   x~d", [N]) ; X = "" ),
               say(Id, "  taken      ~w ---( ~w )---> ~w~w", [S, E, T, X])
           ;   say(Id, "  not taken  ~w ---( ~w )---> ~w", [S, E, T])
           )),
    forall(( model_state(Id, S), \+ visit(Id, S, _), \+ model_forbidden(Id, S) ),
           say(Id, "  never in   '~w'", [S])),
    here_text(Id, Here),
    say(Id, "  ended in   ~w", [Here]),
    findall(k(E, SK)-m(S, E, Since),
            ( mask(Id, S, E, Since), ( S == '$every' -> SK = '' ; SK = S ) ), Masks0),
    keysort(Masks0, Masks1), pairs_values(Masks1, Masks),
    forall(member(m(S, E, Since), Masks),
           (   ( S == '$every' -> In = "in every state" ; format(string(In), "in '~w'", [S]) ),
               since_text(Since, ST),
               say(Id, "  disallowed '~w' ~w~w", [E, In, ST])
           )),
    findall(S-Since, ( forbid(Id, S, Since), \+ model_forbidden(Id, S) ), Fs0), keysort(Fs0, Fs),
    forall(member(S-Since, Fs), ( since_text(Since, ST), say(Id, "  forbidden  '~w'~w", [S, ST]) )),
    findall(S-Since, permit(Id, S, Since), Ps0), keysort(Ps0, Ps),
    forall(member(S-Since, Ps), ( since_text(Since, ST), say(Id, "  permitted  '~w'~w", [S, ST]) )),
    (   End == true -> true
    ;   findall(S, final(Id, S), Finals), joined(Finals, ", ", FT),
        say(Id, "BREACH: ended in ~w -- final: ~w", [Here, FT])
    ).
