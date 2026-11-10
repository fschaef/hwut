%% @hwut {
%%     title   = "Demo: what hwut tolerates, and where it is said"
%%     choices {
%%         plain       { features = ["demo-erlang", "demo-erlang+cover-exact-comparison"] }
%%         tolerance   { features = ["demo-erlang", "demo-erlang+cover-equivalence-pattern", "demo-erlang+cover-numeric-ratio"]
%%                       tolerance {
%%                           eq_pattern    = ["(hello|bonjour|hallo|buongiorno|hola|ahoj)"]
%%                           numeric_ratio = 0.01
%%                       } }
%%         constraints { features = ["demo-erlang", "demo-erlang+cover-constraints"]
%%                       tolerance {
%%                           constraints = ["load >= 0 and load <= 100",
%%                                          "even % 2 == 0",
%%                                          "twice == 2 * once"]
%%                       } }
%%         analogies   { features = ["demo-erlang", "demo-erlang+cover-analogies"] }
%%         race        { features = ["demo-erlang", "demo-erlang+cover-order-free-block"] }
%%         pool        { features = ["demo-erlang", "demo-erlang+cover-potpourri-subset-duplicates"] }
%%         progress    { features = ["demo-erlang", "demo-erlang+cover-visible-nothing"]
%%                       tolerance { nothing = ["[.]+"] } }
%%         lisp        { features = ["demo-erlang", "demo-erlang+cover-analogy-markers"]
%%                       tolerance { analogy = ["{", "}"] } }
%%         clusters    { features = ["demo-erlang", "demo-erlang+cover-point-cloud-pair-distance"] }
%%     }
%% }
%%
%%_____________________________________________________________________________
%% A TEST APPLICATION OF HWUT, FOR READING -- 'demo.py' of the Python
%% demonstration, in Erlang.
%%
%%     hwut.run                    runs every choice below, compares with GOOD/
%%     hwut.play demo.erl plain    runs one choice and records it in OUT/
%%     hwut.accept demo.erl plain  blesses that recording as GOOD; it runs
%%                                 nothing. Where a GOOD stands, the change
%%                                 is 'hwut.merge's -- or '--force' (also
%%                                 '--as-is') replaces it whole.
%%     hwut.merge                  shows OUTPUT against GOOD, key by key
%%     hwut.config.show demo.erl   prints what hwut READ from the header above
%%
%% The header above is the whole configuration: a title, and one scope per
%% choice. hwut calls 'escript demo.erl <choice>' (the 'erlang' interpreter of
%% 'hwut-root.conf') and compares what it prints on stdout with
%% 'GOOD/demo.erl--<choice>.txt' -- a link to the Python demo's GOOD: the
%% same choice prints the same text. '<hwut-end>' closes the stream: a stream
%% without it never COMPLETED and is not accepted.
%%
%% Every run draws from 'rand', which seeds itself in every process from the
%% clock and the process, so the output differs from run to run -- and every
%% choice passes anyway. Each shows WHY:
%%
%% plain        nothing varies; nothing is tolerated. The output must equal
%%              GOOD, line by line.
%%
%% tolerance    'eq_pattern': a greeting drawn at random; any greeting the
%%              pattern names is EQUIVALENT to any other.
%%              'numeric_ratio': a value drawn from [19.91, 20.09]. The band
%%              belongs to the GOOD's number, |n| x ratio: GOOD 19.91 against
%%              20.09 differs by 0.18, inside 19.91 x 0.01 = 0.1991. Every pair
%%              from the interval passes; 20.30 would not.
%%
%% constraints  '((name: value))' BINDS a value; the expressions under
%%              'constraints' judge it, not the GOOD's value. 'load' may be
%%              anything from 0 to 100; 'even' any even number; 'twice' must be
%%              twice 'once', whatever 'once' is. A law over two variables is
%%              checked once both are bound. A binding that breaks its law is
%%              red.
%%
%% race         '##! potpourri' ... '####' opens a block whose lines may arrive
%%              in ANY order -- three worker processes print as they finish.
%%              The same lines must stand on both sides, each once; the order
%%              is free. The program prints the markers, and so does GOOD.
%%
%% analogies    '((x))' is a placeholder: '((a7f3))' against GOOD's '((91c2))'
%%              is equivalent where the mapping holds throughout the stream --
%%              the same handle opened, read and closed. A handle that changes
%%              in mid-stream is red.
%%
%% pool         '##! potpourri subset duplicates': four workers share twelve
%%              jobs; who takes how many is the scheduler's. 'subset': a
%%              worker that got no job is no fault -- every line of the run
%%              must stand in GOOD, not every line of GOOD in the run.
%%              'duplicates': a worker named twice is one line. The GOOD was
%%              recorded from a run in which all four worked.
%%
%% progress     'nothing': a line made only of what the pattern names counts
%%              as no line. A download prints dots while it waits -- none, or
%%              a few lines of them -- and the dots are no fact.
%%
%% lisp         'analogy = ["{", "}"]': the output is Lisp, where '((' is
%%              syntax, so the placeholder is marked otherwise. An object is
%%              printed with its address, '{10044C1F33}'; the address differs
%%              per run, and must be the same object throughout.
%%
%% clusters     '##! point-cloud limit=0.3 pair dist=Linf': three centroids of
%%              a clustering, in whatever order the run finds them. 'pair':
%%              each centroid pairs with ONE point of GOOD -- two centroids in
%%              one cluster are red. 'dist=Linf': within 0.3 in x AND in y.
%%_____________________________________________________________________________
-mode(compile).

-define(GREETINGS, ["hello", "bonjour", "hallo", "buongiorno", "hola", "ahoj"]).

%% RETURN: never; the VM halts with 0 after the choice 'Argv' names was
%%         printed and '<hwut-end>' after it; with 1, naming the choices,
%%         where 'Argv' names none of them.
main(Argv) ->
    ChoiceMap = #{"plain"       => fun plain/0,
                  "tolerance"   => fun tolerance/0,
                  "constraints" => fun constraints/0,
                  "analogies"   => fun analogies/0,
                  "race"        => fun race/0,
                  "pool"        => fun pool/0,
                  "progress"    => fun progress/0,
                  "lisp"        => fun lisp/0,
                  "clusters"    => fun clusters/0},
    case Argv of
        [Choice | _] when is_map_key(Choice, ChoiceMap) ->
            (maps:get(Choice, ChoiceMap))(),
            io:format("<hwut-end>~n");
        _ ->
            io:format("choices: plain, tolerance, constraints, analogies, race, pool, "
                      "progress, lisp, clusters~n"),
            halt(1)
    end.

%% RETURN: float, drawn uniformly from [Low, High].
uniform(Low, High) -> Low + rand:uniform_real() * (High - Low).

%% RETURN: integer, drawn uniformly from [Low, High].
randint(Low, High) -> Low + rand:uniform(High - Low + 1) - 1.

%% RETURN: {integer, integer}, two different integers drawn from [Low, High].
two_of(Low, High) ->
    First = randint(Low, High),
    case randint(Low, High) of
        First  -> two_of(Low, High);
        Second -> {First, Second}
    end.

%% RETURN: ok, once every process of 'Pids' ended.
join(Pids) ->
    Refs = [monitor(process, Pid) || Pid <- Pids],
    [receive {'DOWN', Ref, process, _, _} -> ok end || Ref <- Refs],
    ok.

%% RETURN: ok; prints what never varies.
plain() ->
    io:format("the first line~n"),
    io:format("the second line: 1 2 3~n").

%% RETURN: ok; prints a greeting and a value, both drawn at random.
tolerance() ->
    io:format("greeting: ~s, world~n", [lists:nth(rand:uniform(length(?GREETINGS)), ?GREETINGS)]),
    io:format("value:    ~.2f~n", [uniform(19.91, 20.09)]).

%% RETURN: ok; prints bindings, each drawn at random, each lawful.
constraints() ->
    io:format("load  ((load: ~.1f)) %~n", [uniform(0.0, 100.0)]),
    io:format("even  ((even: ~b))~n", [2 * randint(0, 500)]),
    Once = randint(1, 50),
    io:format("once  ((once: ~b))~n", [Once]),
    io:format("twice ((twice: ~b))~n", [2 * Once]).

%% RETURN: ok; prints two handles, each drawn at random, each used
%%         consistently from opening to closing.
analogies() ->
    {First, Second} = two_of(16#1000, 16#FFFF),
    [A, B] = [string:lowercase(integer_to_list(N, 16)) || N <- [First, Second]],
    io:format("open  ((~s)) input.txt~n", [A]),
    io:format("open  ((~s)) output.txt~n", [B]),
    io:format("read  ((~s)) 17 lines~n", [A]),
    io:format("write ((~s)) 17 lines~n", [B]),
    io:format("close ((~s))~n", [A]),
    io:format("close ((~s))~n", [B]).

%% RETURN: ok; three worker processes print as they finish; the order is the
%%         scheduler's, the facts are not. The program frames the unordered
%%         block itself: '##! potpourri' ... '####'. No lock: one 'io:format'
%%         is one request to the output, never torn by another process's.
race() ->
    Work = fun(Name, Jobs) ->
                   fun() -> timer:sleep(randint(0, 20)),
                            io:format("worker ~s done: ~b jobs~n", [Name, Jobs])
                   end
           end,
    io:format("start~n"),
    io:format("##! potpourri~n"),
    join([spawn(Work(Name, Jobs)) || {Name, Jobs} <- [{"A", 3}, {"B", 5}, {"C", 2}]]),
    io:format("####~n"),
    io:format("all joined~n").

%% RETURN: ok; four worker processes take twelve jobs from one queue (an
%%         atomic counter); each reports the job it finished, as a message.
%%         Who takes how many is the scheduler's.
pool() ->
    Queue = atomics:new(1, []),
    atomics:put(Queue, 1, 12),
    Self  = self(),
    Work  = fun Work(Name) ->
                    case atomics:sub_get(Queue, 1, 1) of
                        Left when Left < 0 -> ok;
                        _ -> timer:sleep(randint(0, 5)),
                             Self ! {done, Name},
                             Work(Name)
                    end
            end,
    join([spawn(fun() -> Work(Name) end) || Name <- ["A", "B", "C", "D"]]),
    Done = done_list([]),
    io:format("twelve jobs, four workers:~n"),
    io:format("##! potpourri subset duplicates~n"),
    [io:format("job done by worker ~s~n", [Name]) || Name <- Done],
    io:format("####~n"),
    io:format("jobs done: ~b~n", [length(Done)]).

%% RETURN: [string], the workers' names of every 'done' message in the
%%         mailbox, in the order they arrived.
done_list(Done) ->
    receive {done, Name} -> done_list([Name | Done])
    after 0              -> lists:reverse(Done)
    end.

%% RETURN: ok; a download that prints dots while it waits; how many is the
%%         network's.
progress() ->
    io:format("connecting to mirror~n"),
    [io:format("~s~n", [lists:duplicate(randint(1, 8), $.)]) || _ <- lists:seq(1, randint(0, 3))],
    io:format("connected~n"),
    io:format("received 1024 bytes~n").

%% RETURN: ok; a Lisp session at its prompt: two objects, each printed with
%%         its address '{...}', drawn anew per run, and each used again.
lisp() ->
    {Table, Thread} = two_of(16#1000000000, 16#10FFFFFFFF),
    [T, W] = [integer_to_list(N, 16) || N <- [Table, Thread]],
    io:format("* (defvar *cache* (make-hash-table))~n"),
    io:format("#<HASH-TABLE :TEST EQL :COUNT 0 {~s}>~n", [T]),
    io:format("* (defvar *worker* (make-thread (lambda () (loop (sleep 1))) :name \"worker\"))~n"),
    io:format("#<THREAD \"worker\" RUNNING {~s}>~n", [W]),
    io:format("* (let ((key (list 1 2))) (setf (gethash key *cache*) *worker*))~n"),
    io:format("#<THREAD \"worker\" RUNNING {~s}>~n", [W]),
    io:format("* *cache*~n"),
    io:format("#<HASH-TABLE :TEST EQL :COUNT 1 {~s}>~n", [T]).

%% RETURN: float, the squared distance between the points 'P' and 'Q'.
distance2({X1, Y1}, {X2, Y2}) -> (X1 - X2) * (X1 - X2) + (Y1 - Y2) * (Y1 - Y2).

%% RETURN: ok; clusters 90 noisy points around three centres and prints the
%%         centroids in the order the run found them.
clusters() ->
    Points0 = [{X + 0.3 * rand:normal(), Y + 0.3 * rand:normal()}
               || {X, Y} <- [{1.0, 1.0}, {5.0, 4.0}, {9.0, 1.0}], _ <- lists:seq(1, 30)],
    Points  = [P || {_, P} <- lists:sort([{rand:uniform(), P} || P <- Points0])],
    %% The start: one point at random, then twice the point farthest from
    %% every start chosen so far -- one start per cluster.
    Nearest = fun(P, Cs) -> lists:min([distance2(P, C) || C <- Cs]) end,
    Farthest = fun(Cs) -> element(2, lists:max([{Nearest(P, Cs), P} || P <- Points])) end,
    Start1  = [lists:nth(rand:uniform(length(Points)), Points)],
    Start2  = Start1 ++ [Farthest(Start1)],
    Start3  = Start2 ++ [Farthest(Start2)],
    Centroids = lists:foldl(fun(_, Cs) -> step(Points, Cs) end, Start3, lists:seq(1, 10)),
    io:format("centroids (x y), in the order found:~n"),
    io:format("##! point-cloud limit=0.3 pair dist=Linf~n"),
    [io:format("    ~5.2f ~5.2f~n", [X, Y]) || {X, Y} <- Centroids],
    io:format("####~n").

%% RETURN: [{X, Y}], the centroids after one step of k-means: each the mean
%%         of the points nearer to it than to any other of 'Centroids'.
step(Points, Centroids) ->
    Indexed = lists:zip(lists:seq(1, length(Centroids)), Centroids),
    Member  = fun(P) -> element(2, lists:min([{distance2(P, C), I} || {I, C} <- Indexed])) end,
    Groups  = maps:groups_from_list(Member, Points),
    [begin
         M = maps:get(I, Groups),
         {lists:sum([X || {X, _} <- M]) / length(M), lists:sum([Y || {_, Y} <- M]) / length(M)}
     end || I <- lists:seq(1, length(Centroids))].
