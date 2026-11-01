% @hwut {
%     title      = "hwut_fsm: a state machine as the test's model of the system"
%     choices {
%         syntax    { features = ["prolog-fsm"] }
%         refused   { features = ["prolog-fsm"] }
%         dfa       { features = ["prolog-fsm"] }
%         nfa       { features = ["prolog-fsm"] }
%         forbidden { features = ["prolog-fsm"] }
%         model     { features = ["prolog-fsm"] }
%         report    { features = ["prolog-fsm"] }
%         masks     { features = ["prolog-fsm"] }
%     }
%     interactive = true
% }
%
% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%______________________________________________________________________________
%
% PURPOSE: The Prolog port of 'python/TEST/test-hwut_fsm.py', choice for
%          choice, held against its GOOD files by '.link'. What Python prints
%          of its own values -- True, None, a tuple -- is printed so here
%          ('hwut_pytext'): a bool is a goal's success, None a failure. Where
%          Python raises FsmError, error(fsm_error(Message), _) is caught and
%          printed the same way.
%______________________________________________________________________________
:- encoding(utf8).
:- use_module('../hwut_runner.pro').
:- use_module('../hwut_pytext.pro').
:- use_module('../hwut_fsm.pro').
:- initialization(main, main).

%  THE PROTOCOL OF EVERY CHOICE: a request is waited on, granted, released; a
%  fault while busy crashes it -- which must never happen.
protocol("
    initial:   idle
    forbidden: crashed
    final:     idle
    idle    ---( request )---> waiting ---( grant )---> busy
    busy    ---( release )---> idle
    :       ---( fault )--->   crashed       # the state that began line 6
    waiting ---( cancel )---> idle
").

banner(Label) :- format("~n--- ~w ---~n", [Label]).

protocol_machine(M) :- protocol(T), fsm_from_string(T, M).

%   fsm_error_said(:Goal)
%   RETURN: Goal, or the FsmError it raises printed.
:- meta_predicate fsm_error_said(0).
fsm_error_said(Goal) :-
    catch(Goal, error(fsm_error(Message), _), format("FsmError: ~w~n", [Message])).

%   path_text(+M, +State, +Options, -Text)
%   RETURN: what Python prints of 'path_to':
%           a tuple of the events, or None.
path_text(M, State, Options, Text) :-
    (   fsm_path_to(M, State, Options, Path) -> py_repr(tuple(Path), Text)
    ;   Text = "None"
    ).

joined(Items, Sep, Text) :- atomic_list_concat(Items, Sep, A), atom_string(A, Text).

run_syntax :-
    banner("the protocol, written back"),
    protocol_machine(M), fsm_to_string(M, T), format("~w~n", [T]),
    banner("the author's form: 'state', a chain, ':', blanks around '-->'"),
    fsm_from_string("
        state A ---( event )---> state B
        :                ---(event2)---> state C ---(event) --> state D
        state E          # no transition yet
    ", M2),
    fsm_to_string(M2, T2), format("~w~n", [T2]).

run_refused :-
    forall(member(Text, ["A ---( x )---> B\n: ---( x )---> C",
                         "A ---(  )---> B",
                         ": ---( x )---> B",
                         "A B ---( x )---> C",
                         "initial: A, B\nA ---( x )---> B",
                         "forbidden: Q\nA ---( x )---> B",
                         "# nothing but a comment"]),
           (   split_string(Text, "\n", "", Parts), joined(Parts, " | ", Label),
               banner(Label),
               fsm_error_said(( fsm_from_string(Text, _), format("accepted~n") ))
           )).

run_dfa :-
    protocol_machine(M),
    forall(nth1(N, [request, release, grant, release, jump, request], Event),
           (   py_bool(fsm_fire(M, Event, [where(N)]), Moved),
               fsm_state(M, State), fsm_allowed(M, Allowed), joined(Allowed, ", ", A),
               py_ljust(Event, 8, E), py_ljust(Moved, 5, Mv), py_ljust(State, 8, S),
               format("    ~w -> ~w now ~w allowed: ~w~n", [E, Mv, S, A])
           )),
    banner("questions where it stands"),
    py_bool(fsm_can(M, grant), G), format("can('grant')   ~w~n", [G]),
    py_bool(fsm_can(M, release), R), format("can('release') ~w~n", [R]),
    py_bool(fsm_in_state(M, waiting), W), format("in_state('waiting') ~w~n", [W]),
    fsm_trace(M, Trace),
    findall(T, ( member(t(Wh, _, Ev, To), Trace), format(string(T), "~w:~w>~w", [Wh, Ev, To]) ), Ts),
    joined(Ts, " ", TT),
    format("trace: ~w~n", [TT]).

run_nfa :-
    fsm_from_string("
        A ---( x )---> B ---( y )---> D
        : ---( x )---> C ---( y )---> E
        C ---( z )---> F
    ", [dfa(false)], M),
    forall(member(Event, [x, z, y]),
           (   format(atom(Where), "t=~w", [Event]),
               ignore(fsm_fire(M, Event, [where(Where)])),
               fsm_current(M, States), joined(States, ", ", S),
               format("    after ~w: ~w~n", [Event, S])
           )),
    banner("'state' asked of a set"),
    fsm_reset(M), ignore(fsm_fire(M, x)),
    fsm_error_said(( fsm_state(M, State), format("~w~n", [State]) )).

run_forbidden :-
    protocol_machine(M),
    forall(nth1(N, [request, grant, fault], Event),
           (   py_bool(fsm_fire(M, Event, [where(N)]), Moved),
               py_ljust(Event, 8, E), format("    ~w -> ~w~n", [E, Moved])
           )),
    fsm_state(M, State), fsm_breach_n(M, B),
    format("now in ~w -- breaches: ~d~n", [State, B]).

run_model :-
    protocol(P), string_concat(P, "\n    state limbo\n    limbo ---( kick )---> idle\n", Text),
    fsm_from_string(Text, M),
    fsm_check(M, N), format("check: ~d~n", [N]),
    banner("path_to"),
    forall(member(State, [busy, crashed, limbo, idle]),
           (   path_text(M, State, [], T), py_ljust(State, 8, S),
               format("    ~w ~w~n", [S, T])
           )),
    ignore(fsm_fire(M, request)),
    path_text(M, busy, [start(now)], T2), format("    busy from now: ~w~n", [T2]),
    py_bool(fsm_state_reachable(M, idle, [start(now)]), R),
    format("    state_reachable('idle', start='now'): ~w~n", [R]).

run_report :-
    protocol(P), fsm_from_string(P, [name(protocol)], M),
    forall(member(Event, [request, grant, release, request, grant]), ignore(fsm_fire(M, Event))),
    fsm_report(M, N), format("report returns ~d~n", [N]).

run_masks :-
    protocol_machine(M),
    banner("'grant' disallowed in every state, since line 2"),
    fsm_disallow(M, grant, [where(2)]),
    ignore(fsm_fire(M, request, [where(3)])),
    fsm_allowed(M, Allowed), joined(Allowed, ", ", A), py_bool(fsm_can(M, grant), Can),
    format("    allowed now: ~w -- can('grant'): ~w~n", [A, Can]),
    ignore(fsm_fire(M, grant, [where(4)])),
    path_text(M, busy, [], P1), format("    path_to('busy'):               ~w~n", [P1]),
    path_text(M, busy, [masked(false)], P2), format("    path_to('busy', masked=False): ~w~n", [P2]),
    fsm_check(M, C1), format("    check(): ~d~n", [C1]),
    fsm_check(M, [masked(false)], C2), format("    check(masked=False): ~d~n", [C2]),
    banner("allowed again; 'busy' forbidden while standing in it"),
    fsm_allow(M, grant, [where(5)]),
    ignore(fsm_fire(M, grant, [where(6)])),
    fsm_forbid(M, busy, [where(7)]),
    ignore(fsm_fire(M, release, [where(8)])),
    ignore(fsm_fire(M, request, [where(9)])),
    ignore(fsm_fire(M, grant, [where(10)])),
    banner("permitted: 'busy', and the model's own 'crashed'"),
    fsm_permit(M, busy, [where(11)]),
    fsm_permit(M, crashed, [where(12)]),
    py_bool(fsm_fire(M, fault, [where(13)]), F), fsm_state(M, S),
    format("    fault -> ~w -- now in ~w~n", [F, S]),
    banner("a phase: 'release' disallowed in 'busy' for a block"),
    fsm_reset(M),
    ignore(fsm_fire(M, request)), ignore(fsm_fire(M, grant)),
    fsm_disallowed(M, release, [state(busy), where(phase)],
                   ignore(fsm_fire(M, release, [where(20)]))),
    ignore(fsm_fire(M, release, [where(21)])),
    fsm_disallow(M, cancel, [where(22)]),
    fsm_report(M, _),
    banner("refused: a word the model never names"),
    forall(member(Call, [fsm_disallow(M, jump, []), fsm_forbid(M, limbo, []),
                         fsm_allow(M, grant, [state(nowhere)])]),
           fsm_error_said(Call)).

main :-
    hwut_runner_run("hwut_fsm: a state machine as the test's model of the system",
                    [ syntax-run_syntax,
                      refused-run_refused,
                      dfa-run_dfa,
                      nfa-run_nfa,
                      forbidden-run_forbidden,
                      model-run_model,
                      report-run_report,
                      masks-run_masks ],
                    []).
