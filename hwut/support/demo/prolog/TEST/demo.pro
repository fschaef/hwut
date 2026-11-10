% @hwut {
%     title   = "Demo: what hwut tolerates, and where it is said"
%     choices {
%         plain       { features = ["demo-prolog", "demo-prolog+cover-exact-comparison"] }
%         tolerance   { features = ["demo-prolog", "demo-prolog+cover-equivalence-pattern", "demo-prolog+cover-numeric-ratio"]
%                       tolerance {
%                           eq_pattern    = ["(hello|bonjour|hallo|buongiorno|hola|ahoj)"]
%                           numeric_ratio = 0.01
%                       } }
%         constraints { features = ["demo-prolog", "demo-prolog+cover-constraints"]
%                       tolerance {
%                           constraints = ["load >= 0 and load <= 100",
%                                          "even % 2 == 0",
%                                          "twice == 2 * once"]
%                       } }
%         analogies   { features = ["demo-prolog", "demo-prolog+cover-analogies"] }
%         race        { features = ["demo-prolog", "demo-prolog+cover-order-free-block"] }
%         pool        { features = ["demo-prolog", "demo-prolog+cover-potpourri-subset-duplicates"] }
%         progress    { features = ["demo-prolog", "demo-prolog+cover-visible-nothing"]
%                       tolerance { nothing = ["[.]+"] } }
%         lisp        { features = ["demo-prolog", "demo-prolog+cover-analogy-markers"]
%                       tolerance { analogy = ["{", "}"] } }
%         clusters    { features = ["demo-prolog", "demo-prolog+cover-point-cloud-pair-distance"] }
%     }
% }
%
/*
______________________________________________________________________________
A TEST APPLICATION OF HWUT, FOR READING -- the template for every language.

    hwut.run                    runs every choice below, compares with GOOD/
    hwut.play demo.pro plain    runs one choice and records it in OUT/
    hwut.accept demo.pro plain  blesses that recording as GOOD; it runs
                                nothing. Where a GOOD stands, the change
                                is 'hwut.merge's -- or '--force' (also
                                '--as-is') replaces it whole.
    hwut.merge                  shows OUTPUT against GOOD, key by key
    hwut.config.show demo.pro   prints what hwut READ from the header above

The header above is the whole configuration: a title, and one scope per
choice. hwut calls 'swipl demo.pro <choice>' and compares what it prints on
stdout with 'GOOD/demo.pro--<choice>.txt' -- here a '.link' to the Python
demonstration's GOOD: the same choice prints the same text. '<hwut-end>'
closes the stream: a stream without it never COMPLETED and is not accepted.

Every run is seeded by the clock, so the output differs from run to run --
and every choice passes anyway. Each shows WHY:

plain        nothing varies; nothing is tolerated. The output must equal
             GOOD, line by line.

tolerance    'eq_pattern': a greeting drawn at random; any greeting the
             pattern names is EQUIVALENT to any other.
             'numeric_ratio': a value drawn from [19.91, 20.09]. The band
             belongs to the GOOD's number, |n| x ratio: GOOD 19.91 against
             20.09 differs by 0.18, inside 19.91 x 0.01 = 0.1991. Every pair
             from the interval passes; 20.30 would not.

constraints  '((name: value))' BINDS a value; the expressions under
             'constraints' judge it, not the GOOD's value. 'load' may be
             anything from 0 to 100; 'even' any even number; 'twice' must be
             twice 'once', whatever 'once' is. A law over two variables is
             checked once both are bound. A binding that breaks its law is
             red.

race         '##! potpourri' ... '####' opens a block whose lines may arrive
             in ANY order -- three workers (threads) print as they finish.
             The same lines must stand on both sides, each once; the order
             is free. The program prints the markers, and so does GOOD.

analogies    '((x))' is a placeholder: '((a7f3))' against GOOD's '((91c2))'
             is equivalent where the mapping holds throughout the stream --
             the same handle opened, read and closed. A handle that changes
             in mid-stream is red.

pool         '##! potpourri subset duplicates': four workers share twelve
             jobs from one message queue; who takes how many is the
             scheduler's. 'subset': a worker that got no job is no fault --
             every line of the run must stand in GOOD, not every line of
             GOOD in the run. 'duplicates': a worker named twice is one
             line. The GOOD was recorded from a run in which all four
             worked.

progress     'nothing': a line made only of what the pattern names counts
             as no line. A download prints dots while it waits -- none, or
             a few lines of them -- and the dots are no fact.

lisp         'analogy = ["{", "}"]': the output is Lisp, where '((' is
             syntax, so the placeholder is marked otherwise. An object is
             printed with its address, '{10044C1F33}'; the address differs
             per run, and must be the same object throughout.

clusters     '##! point-cloud limit=0.3 pair dist=Linf': three centroids of
             a clustering, in whatever order the run finds them. 'pair':
             each centroid pairs with ONE point of GOOD -- two centroids in
             one cluster are red. 'dist=Linf': within 0.3 in x AND in y.

PROLOG'S WAYS: a choice is a predicate; a thread is 'thread_create/3', a
lock 'with_mutex/2', a queue a message queue. '~|...~t~N+' lays a field out
in N columns, as Python's '%-Ns' and '%Nd' do.
______________________________________________________________________________
*/
:- encoding(utf8).
:- initialization(main, main).

greeting_list([hello, bonjour, hallo, buongiorno, hola, ahoj]).

%   uniform(+Low, +High, -X)
%   RETURN: X, a float drawn uniformly from [Low, High].
uniform(Low, High, X) :- random(U), X is Low + (High - Low) * U.

%   gauss(+Mu, +Sigma, -X)
%   RETURN: X, a float drawn from the normal distribution (Mu, Sigma)
%           -- Box-Muller.
gauss(Mu, Sigma, X) :-
    random(U1), random(U2),
    X is Mu + Sigma * sqrt(-2.0 * log(1.0 - U1)) * cos(2.0 * pi * U2).

%   plain
%   RETURN: true. Prints what never varies.
plain :-
    format("the first line~n"),
    format("the second line: 1 2 3~n").

%   tolerance
%   RETURN: true. Prints a greeting and a value, both drawn at random.
tolerance :-
    greeting_list(L), random_member(G, L),
    format("greeting: ~w, world~n", [G]),
    uniform(19.91, 20.09, V),
    format("value:    ~2f~n", [V]).

%   constraints
%   RETURN: true. Prints bindings, each drawn at random, each lawful.
constraints :-
    uniform(0.0, 100.0, Load),
    format("load  ((load: ~1f)) %~n", [Load]),
    random_between(0, 500, E), Even is 2 * E,
    format("even  ((even: ~d))~n", [Even]),
    random_between(1, 50, Once), Twice is 2 * Once,
    format("once  ((once: ~d))~n", [Once]),
    format("twice ((twice: ~d))~n", [Twice]).

%   analogies
%   RETURN: true. Prints two handles, each drawn at random, each used
%           consistently from opening to closing.
analogies :-
    numlist(0x1000, 0xFFFF, All), random_select(First, All, Rest),
    random_member(Second, Rest),
    format("open  ((~16r)) input.txt~n",  [First]),
    format("open  ((~16r)) output.txt~n", [Second]),
    format("read  ((~16r)) 17 lines~n",   [First]),
    format("write ((~16r)) 17 lines~n",   [Second]),
    format("close ((~16r))~n",            [First]),
    format("close ((~16r))~n",            [Second]).

%   race
%   RETURN: true. Three workers print as they finish; the order is the
%           scheduler's, the facts are not. The program frames the unordered
%           block itself: '##! potpourri' ... '####'.
race :-
    format("start~n"),
    format("##! potpourri~n"),
    findall(Id, ( member(Name-Jobs, ['A'-3, 'B'-5, 'C'-2]),
                  thread_create(race_work(Name, Jobs), Id, []) ), IdList),
    maplist(thread_join, IdList),
    format("####~n"),
    format("all joined~n").

race_work(Name, Jobs) :-
    uniform(0.0, 0.02, S), sleep(S),
    with_mutex(demo_print, format("worker ~w done: ~d jobs~n", [Name, Jobs])).

:- dynamic done/1.

%   pool
%   RETURN: true. Four workers take twelve jobs from one queue; each reports
%           the job it finished. Who takes how many is the scheduler's.
pool :-
    message_queue_create(Queue),
    forall(between(0, 11, Job), thread_send_message(Queue, Job)),
    findall(Id, ( member(Name, ['A', 'B', 'C', 'D']),
                  thread_create(pool_work(Queue, Name), Id, []) ), IdList),
    maplist(thread_join, IdList),
    findall(Line, done(Line), DoneList),
    format("twelve jobs, four workers:~n"),
    format("##! potpourri subset duplicates~n"),
    forall(member(Line, DoneList), format("~s~n", [Line])),
    format("####~n"),
    length(DoneList, N),
    format("jobs done: ~d~n", [N]).

pool_work(Queue, Name) :-
    (   thread_get_message(Queue, _Job, [timeout(0)])
    ->  uniform(0.0, 0.005, S), sleep(S),
        format(string(Line), "job done by worker ~w", [Name]),
        with_mutex(demo_print, assertz(done(Line))),
        pool_work(Queue, Name)
    ;   true
    ).

%   progress
%   RETURN: true. A download that prints dots while it waits; how many is
%           the network's.
progress :-
    format("connecting to mirror~n"),
    random_between(0, 3, N),
    forall(between(1, N, _),
           ( random_between(1, 8, M), length(Dots, M), maplist(=(0'.), Dots),
             format("~s~n", [Dots]) )),
    format("connected~n"),
    format("received 1024 bytes~n").

%   lisp
%   RETURN: true. A Lisp session at its prompt: two objects, each printed
%           with its address '{...}', drawn anew per run, and each used again.
lisp :-
    random_between(0x1000000000, 0x10FFFFFFFF, Table),
    repeat, random_between(0x1000000000, 0x10FFFFFFFF, Thread), Thread =\= Table, !,
    format("* (defvar *cache* (make-hash-table))~n"),
    format("#<HASH-TABLE :TEST EQL :COUNT 0 {~16R}>~n", [Table]),
    format("* (defvar *worker* (make-thread (lambda () (loop (sleep 1))) :name \"worker\"))~n"),
    format("#<THREAD \"worker\" RUNNING {~16R}>~n", [Thread]),
    format("* (let ((key (list 1 2))) (setf (gethash key *cache*) *worker*))~n"),
    format("#<THREAD \"worker\" RUNNING {~16R}>~n", [Thread]),
    format("* *cache*~n"),
    format("#<HASH-TABLE :TEST EQL :COUNT 1 {~16R}>~n", [Table]).

%   clusters
%   RETURN: true. Clusters 90 noisy points around three centres and prints
%           the centroids in the order the run found them.
clusters :-
    findall(X-Y, ( member(CX-CY, [1.0-1.0, 5.0-4.0, 9.0-1.0]), between(1, 30, _),
                   gauss(CX, 0.3, X), gauss(CY, 0.3, Y) ), Points0),
    random_permutation(Points0, Points),
    %  The start: one point at random, then twice the point farthest from
    %  every start chosen so far -- one start per cluster.
    random_member(Start, Points),
    farthest_starts(Points, [Start], Starts),
    k_means(10, Points, Starts, Centroids),
    format("centroids (x y), in the order found:~n"),
    format("##! point-cloud limit=0.3 pair dist=Linf~n"),
    forall(member(X-Y, Centroids), format("    ~|~t~2f~5+ ~|~t~2f~5+~n", [X, Y])),
    format("####~n").

distance2(X-Y, CX-CY, D) :- D is (X - CX) ** 2 + (Y - CY) ** 2.

nearest_distance2(P, Centroids, D) :-
    aggregate_all(min(D0), ( member(C, Centroids), distance2(P, C, D0) ), D).

farthest_starts(_, Starts, Starts) :- length(Starts, 3), !.
farthest_starts(Points, Starts0, Starts) :-
    aggregate_all(max(D, P), ( member(P, Points), nearest_distance2(P, Starts0, D) ), max(_, Far)),
    append(Starts0, [Far], Starts1),
    farthest_starts(Points, Starts1, Starts).

k_means(0, _, Centroids, Centroids) :- !.
k_means(N, Points, Centroids0, Centroids) :-
    findall(C, ( nth0(I, Centroids0, _),
                 findall(P, ( member(P, Points), nearest_index(P, Centroids0, I) ), Members),
                 mean(Members, C) ), Centroids1),
    N1 is N - 1,
    k_means(N1, Points, Centroids1, Centroids).

%   nearest_index(+P, +Centroids, -I)
%   RETURN: I, the index of the first of 'Centroids' nearest to 'P'.
nearest_index(P, Centroids, I) :-
    findall(D-J, ( nth0(J, Centroids, C), distance2(P, C, D) ), Pairs),
    aggregate_all(min(D), member(D-_, Pairs), Min),
    once(member(Min-I, Pairs)).

mean(Points, X-Y) :-
    length(Points, N),
    aggregate_all(sum(PX), member(PX-_, Points), SX),
    aggregate_all(sum(PY), member(_-PY, Points), SY),
    X is SX / N, Y is SY / N.

choice_db([plain-plain, tolerance-tolerance, constraints-constraints,
           analogies-analogies, race-race, pool-pool, progress-progress,
           lisp-lisp, clusters-clusters]).

main :-
    set_stream(user_output, encoding(utf8)),
    get_time(T), Seed is truncate(T * 1.0e9), set_random(seed(Seed)),
    current_prolog_flag(argv, Argv),
    choice_db(Db),
    (   Argv = [Word|_], atom_string(Choice, Word), memberchk(Choice-Goal, Db)
    ->  call(Goal),
        format("<hwut-end>~n")
    ;   findall(N, member(N-_, Db), Names), atomic_list_concat(Names, ', ', Text),
        format("choices: ~w~n", [Text]),
        halt(1)
    ).
