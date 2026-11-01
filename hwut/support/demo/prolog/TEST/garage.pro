% @hwut {
%     title    = "Demo: a garage's space counter -- a space, a stream and races, generated"
%     interactive = true
%     choices {
%         space       { features = ["space-from-hocon", "space-iterator", "hwut-runner"]
%                       tolerance { constraints = ["mismatches == 0"] } }
%         random      { features = ["deterministic-stream", "hwut-runner"]
%                       tolerance { constraints = ["mismatches == 0"] } }
%         race-naive  { features = ["deterministic-timeline", "space-iterator", "hwut-runner"]
%                       tolerance { constraints = ["overbooked > 0"] } }
%         race-atomic { features = ["deterministic-timeline", "space-iterator", "hwut-runner"]
%                       tolerance { constraints = ["overbooked == 0"] } }
%     }
% }
%
/*
______________________________________________________________________________
SUBJECT  the counter of free spaces at a garage's gates: which cars it
         admits, which it refuses, and how many stand inside.
REQUIREMENT  The garage admits a car only while a space is free, lets a car
             out only while one stands inside, and never holds more cars
             than it has spaces -- also when two gates admit at once.

No choice writes its cases out by hand. Each GENERATES them, with one of
hwut's modules for writing tests (hwut/support/test_writing/prolog, found
through 'support_path.pro'):

space        'garage-space.hocon' states the tested space -- capacities,
             cars arriving, cars leaving -- in hwut's HOCON, read by
             'hwut_hocon'. A reviewer edits the space without reading
             Prolog. 'space_point' walks every combination: 3 x 5 x 4 = 60
             cases, on backtracking. Each is printed as one cell of a
             matrix, and checked against the model: admitted =
             min(arriving, capacity), out = min(leaving, admitted).

random       'dr_stream_new(4711, S)' draws 1000 cars arriving and leaving
             at a garage of 5. The draw is the same on every machine and in
             every language hwut supports -- the stream is a linear
             congruential generator, not SWI's 'random' -- so the GOOD is
             exact (the Python demonstration's own), and a failing run can
             be replayed by its seed.

race-naive   two gates, one free space. A gate CHECKS whether a space is
             free, and later ADMITS its car. 'deterministic_timeline' runs
             the two gates as triggers on timelines drawn as strings --
             '1 1 ' fires at tick 0 and tick 2 -- so every interleaving is
             played exactly, not hoped for with sleeps. 'space_point'
             generates all six interleavings of two two-step gates in four
             ticks. Where both gates check before either admits, both
             admit: the garage is overbooked. The law is 'overbooked > 0':
             the GOOD is the accepted violation report.

race-atomic  the same six interleavings, the gate checking and admitting
             in ONE step under the counter's lock. 'overbooked == 0'.

THE FRONT END is hwut's runner, 'hwut_runner_run': the choice map below is
the whole command line, '--hwut-info' included. The header says
'interactive = true': hwut starts the application ONCE and asks for the
choices one after another in that one process -- an accelerator only: a
choice's output equals what it prints when run alone (the runner forks a
child per choice).

PROLOG'S WAYS: the garage is a term 'garage(Capacity, Occupied)' whose count
is changed IN PLACE ('nb_setarg') -- two gates must see one counter, not two
copies; a gate is a BEHAVIOUR, a closure the dispatcher sends 'fire(Tick)',
its step and what it saw a cell of its own.
______________________________________________________________________________
*/
:- encoding(utf8).
:- use_module('support_path.pro').
:- use_module(hwut('hwut_runner.pro')).
:- use_module(hwut('space_iterator.pro')).
:- use_module(hwut('hwut_hocon.pro')).
:- use_module(hwut('deterministic_random.pro')).
:- use_module(hwut('deterministic_timeline.pro')).
:- initialization(main, main).

:- prolog_load_context(directory, Here), asserta(here(Here)).

/* ______________________________________________________________________________
   The unit under test: a counter of the spaces a garage has.
*/
%   garage_new(+Capacity, -Garage)
%   RETURN: Garage, an empty garage of 'Capacity' spaces.
garage_new(Capacity, garage(Capacity, 0)).

%   garage_free(+Garage, -N)
%   RETURN: N, the number of spaces free now -- negative where the garage is
%           overbooked.
garage_free(garage(Capacity, Occupied), N) :- N is Capacity - Occupied.

%   garage_arrive(+Garage)
%   RETURN: success, a car was admitted, if a space was free;
%           failure, else (the car is refused).
garage_arrive(G) :-
    garage_free(G, N), N > 0,
    arg(2, G, O), O1 is O + 1, nb_setarg(2, G, O1).

%   garage_leave(+Garage)
%   RETURN: success, a car drove out, if one stood inside;
%           failure, else.
garage_leave(G) :-
    arg(2, G, O), O > 0,
    O1 is O - 1, nb_setarg(2, G, O1).

bool(Goal, B) :- ( call(Goal) -> B = true ; B = false ).

/* ______________________________________________________________________________
   space -- the tested space from HOCON, walked by space_point
*/
%   read_space(+Path, -Dimensions)
%   RETURN: Dimensions, the dimensions of the space in 'Path', in the order
%           written: Name-Values. Every fault the HOCON reader found is
%           printed with '!!' first.
read_space(Path, Dimensions) :-
    read_file_to_string(Path, Text0, [encoding(utf8)]),
    ( string_concat(Text, "\n", Text0) -> true ; Text = Text0 ),
    hocon_lines(Text, 0, 0, Lines),
    file_base_name(Path, Name),
    hocon_parse(Lines, Name, Document, Faults),
    forall(member(F, Faults), ( hocon_fault_text(F, T), format("!! ~s~n", [T]) )),
    hocon_get(Document, "space", entry(_, _, object_node(_, Entries))),
    findall(Key-Values,
            ( member(entry(Key, _, list_node(Items, _)), Entries),
              findall(V, member(scalar_node(V, _), Items), Values) ),
            Dimensions).

%   python_list(+Values, -Text)
%   RETURN: Text, the list as Python prints it: '[1, 2, 3]'.
python_list(Values, Text) :-
    atomic_list_concat(Values, ', ', Inner), format(string(Text), "[~w]", [Inner]).

%   space
%   RETURN: true. Prints every case of the space as a matrix cell.
space :-
    here(Here), directory_file_path(Here, 'garage-space.hocon', Path),
    read_space(Path, Dimensions),
    pairs_values(Dimensions, Basis),
    Basis = [Capacities, Arrivings, Leavings],
    findall(D, ( member(N-V, Dimensions), python_list(V, L), format(string(D), "~s ~s", [N, L]) ), Ds),
    atomic_list_concat(Ds, '  x  ', SpaceText),
    format("space: ~w~n", [SpaceText]),
    format("cell: cars inside / cars refused at the gate ('!!' differs from the model)~n"),
    findall(key(C, A)-Cell-Mismatch,
            ( space_point(Basis, [C, A, L]), space_case(C, A, L, Cell, Mismatch) ),
            Cases),
    aggregate_all(sum(M), member(_-_-M, Cases), MismatchN),
    findall(Head, ( member(L, Leavings), format(string(Head), "leave ~|~d~t~3+", [L]) ), Heads),
    atomic_list_concat(Heads, '  ', HeadText0), rstrip(HeadText0, HeadText),
    forall(member(C, Capacities),
           ( format("capacity ~d   ~s~n", [C, HeadText]),
             forall(member(A, Arrivings),
                    ( findall(P, ( member(key(C, A)-Cell-_, Cases),
                                   format(string(P), "~|~s~t~9+", [Cell]) ), Ps),
                      atomic_list_concat(Ps, '  ', Row0),
                      format(string(Line0), "  arrive ~d   ~w", [A, Row0]),
                      rstrip(Line0, Line),
                      format("~s~n", [Line]) )) )),
    length(Cases, CaseN),
    format("cases ~d, differing from the model ((mismatches: ~d))~n", [CaseN, MismatchN]).

%   space_case(+Capacity, +Arriving, +Leaving, -Cell, -Mismatch)
%   RETURN: Cell, 'inside/refused' with '!!' where it differs from the model,
%           else two blanks; Mismatch 1 where it differs, else 0.
space_case(Capacity, Arriving, Leaving, Cell, Mismatch) :-
    garage_new(Capacity, G),
    aggregate_all(count, ( between(1, Arriving, _), \+ garage_arrive(G) ), Refused),
    forall(between(1, Leaving, _), ignore(garage_leave(G))),
    Admitted is min(Arriving, Capacity),
    ExpectedIn is Admitted - min(Leaving, Admitted),
    ExpectedRefused is Arriving - Admitted,
    arg(2, G, Inside),
    (   Inside =:= ExpectedIn, Refused =:= ExpectedRefused
    ->  Mark = "  ", Mismatch = 0
    ;   Mark = "!!", Mismatch = 1
    ),
    format(string(Cell), "~d/~d~s", [Inside, Refused, Mark]).

%   rstrip(+Text, -Stripped)
%   RETURN: Stripped, 'Text' without its trailing blanks.
rstrip(Text, Stripped) :-
    string_codes(Text, Codes), reverse(Codes, R0),
    drop_blanks(R0, R), reverse(R, Codes1), string_codes(Stripped, Codes1).

drop_blanks([0' |Codes0], Codes) :- !, drop_blanks(Codes0, Codes).
drop_blanks(Codes, Codes).

/* ______________________________________________________________________________
   random -- a deterministic stream of arrivals and departures
*/
%   random_stream
%   RETURN: true. Prints the summary of 1000 drawn cars, model-checked.
random_stream :-
    dr_stream_new(4711, S0),
    garage_new(5, G),
    numlist(1, 1000, Steps),
    foldl(random_step(G), Steps,
          state(S0, 0, counts(0, 0, 0, 0), [0, 0, 0, 0, 0, 0], 0, []),
          state(_, _, counts(Arrive, Refused, Leave, Empty), Histogram, MismatchN, StripR)),
    reverse(StripR, Strip),
    length(First, 60), append(First, _, Strip),
    format("seed 4711, garage of 5, 1000 cars drawn: '+' arrives, '-' leaves~n"),
    format("first 60: ~s~n", [First]),
    format("arrivals ~d, refused ~d; departures ~d, from an empty garage ~d~n",
           [Arrive, Refused, Leave, Empty]),
    format("cars inside after each event:~n"),
    forall(nth0(N, Histogram, Count),
           ( Bars is Count // 10, length(Bar, Bars), maplist(=(0'#), Bar),
             format("    ~d  ~|~t~d~4+  ~s~n", [N, Count, Bar]) )),
    format("steps differing from the model ((mismatches: ~d))~n", [MismatchN]).

random_step(G, _, state(S0, Model0, counts(A0, R0, L0, E0), H0, M0, Strip0),
                  state(S,  Model,  counts(A,  R,  L,  E),  H,  M,  [Sign|Strip0])) :-
    dr_coin(0.55, Coin, S0, S),
    (   Coin == true
    ->  A is A0 + 1, L = L0, E = E0,
        ( garage_arrive(G) -> R = R0 ; R is R0 + 1 ),
        Model is min(5, Model0 + 1), Sign = 0'+
    ;   L is L0 + 1, A = A0, R = R0,
        ( garage_leave(G) -> E = E0 ; E is E0 + 1 ),
        Model is max(0, Model0 - 1), Sign = 0'-
    ),
    arg(2, G, Inside),
    ( Inside =:= Model -> M = M0 ; M is M0 + 1 ),
    nth0(Inside, H0, C0, Rest), C is C0 + 1, nth0(Inside, H, C, Rest).

/* ______________________________________________________________________________
   race -- two gates on drawn timelines
*/
%   gate(+Cell, +Message, +Trigger)
%   RETURN: success, once the gate did its next step at the tick of
%           'fire(Tick)': its first tick checks, its second admits. 'Cell'
%           is gate(Garage, Atomic, Log, Step, SawFree), Step and SawFree
%           changed in place; Log a cell 'log(Events)', the events in
%           reverse order.
gate(Cell, fire(_Tick), Trigger) :-
    Cell = gate(G, Atomic, Log, Step, SawFree),
    dt_trigger_name(Trigger, Name),
    (   Step == 0, Atomic == true
    ->  bool(garage_arrive(G), Saw),
        ( Saw == true -> format(string(E), "~w checks+admits", [Name])
        ;                format(string(E), "~w refuses", [Name]) )
    ;   Step == 0
    ->  garage_free(G, Free), ( Free > 0 -> Saw = true ; Saw = false ),
        format(string(E), "~w sees ~d free", [Name, Free])
    ;   Atomic == true
    ->  Saw = SawFree,
        ( SawFree == true -> format(string(E), "~w opens", [Name])
        ;                    format(string(E), "~w stays shut", [Name]) )
    ;   SawFree == true
    ->  Saw = SawFree,
        arg(2, G, O), O1 is O + 1, nb_setarg(2, G, O1),      % the naive admit
        format(string(E), "~w admits", [Name])
    ;   Saw = SawFree,
        format(string(E), "~w refuses", [Name])
    ),
    arg(1, Log, Events), nb_setarg(1, Log, [E|Events]),
    Step1 is Step + 1, nb_setarg(4, Cell, Step1), nb_setarg(5, Cell, Saw).

%   interleaving_list(-Pairs)
%   RETURN: Pairs, every TimelineA-TimelineB in four ticks in which each of
%           two gates fires twice, never at the same tick: gate A's and gate
%           B's.
interleaving_list(Pairs) :-
    numlist(0, 3, Ticks),
    findall(LA-LB, ( space_point([Ticks, Ticks, Ticks, Ticks], [A1, A2, B1, B2]),
                     A1 < A2, B1 < B2, sort([A1, A2, B1, B2], S), length(S, 4),
                     timeline(A1, A2, LA), timeline(B1, B2, LB) ), Pairs).

timeline(X, Y, Line) :-
    findall(C, ( between(0, 3, T), ( memberchk(T, [X, Y]) -> C = 0'1 ; C = 0'  ) ), Codes),
    string_codes(Line, Codes).

%   race(+Atomic)
%   RETURN: true. Plays every interleaving of two gates at one space.
race(Atomic) :-
    format("one free space, two gates, one car at each; timelines: a digit fires~n"),
    format("    gate A  gate B  what happens                                    inside~n"),
    interleaving_list(Pairs),
    foldl(race_case(Atomic), Pairs, 0, OverbookedN),
    length(Pairs, N),
    format("interleavings overbooking the garage ((overbooked: ~d)) of ~d~n", [OverbookedN, N]).

race_case(Atomic, TimelineA-TimelineB, N0, N) :-
    garage_new(1, G),
    Log = log([]),
    dt_trigger_new(TimelineA, 'A', gate(gate(G, Atomic, Log, 0, false)), A),
    dt_trigger_new(TimelineB, 'B', gate(gate(G, Atomic, Log, 0, false)), B),
    dt_dispatcher_new([A, B], D),
    dt_run(dt_dispatcher_run(D)),
    arg(1, Log, Events0), reverse(Events0, Events),
    atomic_list_concat(Events, ', ', What),
    G = garage(Capacity, Inside),
    ( Inside > Capacity -> Mark = "!!", N is N0 + 1 ; Mark = "  ", N = N0 ),
    format(string(Line0), "    \"~s\"  \"~s\"  ~|~w~t~46+  ~d ~s", [TimelineA, TimelineB, What, Inside, Mark]),
    rstrip(Line0, Line),
    format("~s~n", [Line]).

%   race_naive
%   RETURN: true. The gates check, then admit, in two steps.
race_naive :- race(false).

%   race_atomic
%   RETURN: true. The gates check and admit in one step.
race_atomic :- race(true).

main :-
    hwut_runner_run("Demo: a garage's space counter -- a space, a stream and races, generated;",
                    [space-space, random-random_stream,
                     'race-naive'-race_naive, 'race-atomic'-race_atomic], []).
