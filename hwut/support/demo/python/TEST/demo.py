#! /usr/bin/env python3
#
# @hwut {
#     title   = "Demo: what hwut tolerates, and where it is said"
#     choices {
#         plain       { features = ["demo-passes-on-every-run", "exact-comparison"] }
#         tolerance   { features = ["demo-passes-on-every-run", "equivalence-pattern", "numeric-ratio"]
#                       tolerance {
#                           eq_pattern    = ["(hello|bonjour|hallo|buongiorno|hola|ahoj)"]
#                           numeric_ratio = 0.01
#                       } }
#         constraints { features = ["demo-passes-on-every-run", "constraints"]
#                       tolerance {
#                           constraints = ["load >= 0 and load <= 100",
#                                          "even % 2 == 0",
#                                          "twice == 2 * once"]
#                       } }
#         analogies   { features = ["demo-passes-on-every-run", "analogies"] }
#         race        { features = ["demo-passes-on-every-run", "order-free-block"] }
#         pool        { features = ["demo-passes-on-every-run", "potpourri-subset-duplicates"] }
#         progress    { features = ["demo-passes-on-every-run", "visible-nothing"]
#                       tolerance { nothing = ["[.]+"] } }
#         lisp        { features = ["demo-passes-on-every-run", "analogy-markers"]
#                       tolerance { analogy = ["{", "}"] } }
#         clusters    { features = ["demo-passes-on-every-run", "point-cloud-pair-distance"] }
#     }
# }
#
"""
______________________________________________________________________________
A TEST APPLICATION OF HWUT, FOR READING -- the template for every language.

    hwut.run                   runs every choice below, compares with GOOD/
    hwut.play demo.py plain    runs one choice and records it in OUT/
    hwut.accept demo.py plain  blesses that recording as GOOD; it runs
                               nothing. Where a GOOD stands, the change
                               is 'hwut.merge's -- or '--force' (also
                               '--as-is') replaces it whole.
    hwut.merge                 shows OUTPUT against GOOD, key by key
    hwut.config.show demo.py   prints what hwut READ from the header above

The header above is the whole configuration: a title, and one scope per
choice. hwut calls 'demo.py <choice>' and compares what it prints on stdout
with 'GOOD/demo.py--<choice>.txt'. '<hwut-end>' closes the stream: a stream
without it never COMPLETED and is not accepted.

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
             in ANY order -- three workers print as they finish. The same
             lines must stand on both sides, each once; the order is free.
             The program prints the markers, and so does GOOD.

analogies    '((x))' is a placeholder: '((a7f3))' against GOOD's '((91c2))'
             is equivalent where the mapping holds throughout the stream --
             the same handle opened, read and closed. A handle that changes
             in mid-stream is red.

pool         '##! potpourri subset duplicates': four workers share twelve
             jobs; who takes how many is the scheduler's. 'subset': a
             worker that got no job is no fault -- every line of the run
             must stand in GOOD, not every line of GOOD in the run.
             'duplicates': a worker named twice is one line. The GOOD was
             recorded from a run in which all four worked.

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
______________________________________________________________________________
"""
import random
import sys
import threading
import time

GREETING_TUPLE = ("hello", "bonjour", "hallo", "buongiorno", "hola", "ahoj")


def plain():
    """RETURN: None. Prints what never varies."""
    print("the first line")
    print("the second line: 1 2 3")


def tolerance():
    """RETURN: None. Prints a greeting and a value, both drawn at random."""
    print("greeting: %s, world" % random.choice(GREETING_TUPLE))
    print("value:    %.2f" % random.uniform(19.91, 20.09))


def constraints():
    """RETURN: None. Prints bindings, each drawn at random, each lawful."""
    print("load  ((load: %.1f)) %%" % random.uniform(0.0, 100.0))
    print("even  ((even: %i))" % (2 * random.randint(0, 500)))
    once = random.randint(1, 50)
    print("once  ((once: %i))" % once)
    print("twice ((twice: %i))" % (2 * once))


def analogies():
    """RETURN: None. Prints two handles, each drawn at random, each used
    consistently from opening to closing."""
    first, second = random.sample(range(0x1000, 0x10000), 2)
    print("open  ((%04x)) input.txt" % first)
    print("open  ((%04x)) output.txt" % second)
    print("read  ((%04x)) 17 lines" % first)
    print("write ((%04x)) 17 lines" % second)
    print("close ((%04x))" % first)
    print("close ((%04x))" % second)


def race():
    """RETURN: None. Three workers print as they finish; the order is the
    scheduler's, the facts are not. The program frames the unordered block
    itself: '##! potpourri' ... '####'."""
    lock = threading.Lock()

    def work(name, jobs):
        time.sleep(random.uniform(0.0, 0.02))
        with lock:
            print("worker %s done: %i jobs" % (name, jobs))

    pool = [threading.Thread(target=work, args=args)
            for args in (("A", 3), ("B", 5), ("C", 2))]
    print("start")
    print("##! potpourri")
    for thread in pool:
        thread.start()
    for thread in pool:
        thread.join()
    print("####")
    print("all joined")


def pool():
    """RETURN: None. Four workers take twelve jobs from one queue; each
    reports the job it finished. Who takes how many is the scheduler's."""
    import queue
    job_queue = queue.Queue()
    for job in range(12):
        job_queue.put(job)
    lock = threading.Lock()
    done_list = []

    def work(name):
        while True:
            try:               job_queue.get_nowait()
            except queue.Empty: return
            time.sleep(random.uniform(0.0, 0.005))
            with lock:
                done_list.append("job done by worker %s" % name)

    pool = [threading.Thread(target=work, args=(name,)) for name in "ABCD"]
    for thread in pool:
        thread.start()
    for thread in pool:
        thread.join()
    print("twelve jobs, four workers:")
    print("##! potpourri subset duplicates")
    for line in done_list:
        print(line)
    print("####")
    print("jobs done: %i" % len(done_list))


def progress():
    """RETURN: None. A download that prints dots while it waits; how many
    is the network's."""
    print("connecting to mirror")
    for _ in range(random.randint(0, 3)):
        print("." * random.randint(1, 8))
    print("connected")
    print("received 1024 bytes")


def lisp():
    """RETURN: None. A Lisp session at its prompt: two objects, each printed
    with its address '{...}', drawn anew per run, and each used again."""
    table, thread = random.sample(range(0x1000000000, 0x1100000000), 2)
    print("* (defvar *cache* (make-hash-table))")
    print("#<HASH-TABLE :TEST EQL :COUNT 0 {%X}>" % table)
    print("* (defvar *worker* (make-thread (lambda () (loop (sleep 1))) :name \"worker\"))")
    print("#<THREAD \"worker\" RUNNING {%X}>" % thread)
    print("* (let ((key (list 1 2))) (setf (gethash key *cache*) *worker*))")
    print("#<THREAD \"worker\" RUNNING {%X}>" % thread)
    print("* *cache*")
    print("#<HASH-TABLE :TEST EQL :COUNT 1 {%X}>" % table)


def clusters():
    """RETURN: None. Clusters 90 noisy points around three centres and
    prints the centroids in the order the run found them."""
    centre_list = [(1.0, 1.0), (5.0, 4.0), (9.0, 1.0)]
    point_list = [(x + random.gauss(0.0, 0.3), y + random.gauss(0.0, 0.3))
                  for x, y in centre_list for _ in range(30)]
    random.shuffle(point_list)
    #  The start: one point at random, then twice the point farthest from
    #  every start chosen so far -- one start per cluster.
    centroid_list = [random.choice(point_list)]
    while len(centroid_list) < 3:
        centroid_list.append(max(point_list, key=lambda p: min(
            (p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 for c in centroid_list)))
    for _ in range(10):
        member_db = {i: [] for i in range(3)}
        for p in point_list:
            nearest = min(range(3), key=lambda i: (p[0] - centroid_list[i][0]) ** 2
                                                  + (p[1] - centroid_list[i][1]) ** 2)
            member_db[nearest].append(p)
        centroid_list = [(sum(p[0] for p in m) / len(m), sum(p[1] for p in m) / len(m))
                         for m in member_db.values()]
    print("centroids (x y), in the order found:")
    print("##! point-cloud limit=0.3 pair dist=Linf")
    for x, y in centroid_list:
        print("    %5.2f %5.2f" % (x, y))
    print("####")


CHOICE_DB = {"plain":       plain,
             "tolerance":   tolerance,
             "constraints": constraints,
             "analogies":   analogies,
             "race":        race,
             "pool":        pool,
             "progress":    progress,
             "lisp":        lisp,
             "clusters":    clusters}

random.seed(time.time_ns())
choice = sys.argv[1] if len(sys.argv) > 1 else ""
if choice not in CHOICE_DB:
    print("choices: %s" % ", ".join(CHOICE_DB))
    sys.exit(1)
CHOICE_DB[choice]()
print("<hwut-end>")
