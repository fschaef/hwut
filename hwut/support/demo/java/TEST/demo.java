/* @hwut {
 *     title   = "Demo: what hwut tolerates, and where it is said"
 *     build   { framework = "make", target = "%.exe" }
 *     choices {
 *         plain       { features = ["demo-java", "demo-java+cover-exact-comparison"] }
 *         tolerance   { features = ["demo-java", "demo-java+cover-equivalence-pattern", "demo-java+cover-numeric-ratio"]
 *                       tolerance {
 *                           eq_pattern    = ["(hello|bonjour|hallo|buongiorno|hola|ahoj)"]
 *                           numeric_ratio = 0.01
 *                       } }
 *         constraints { features = ["demo-java", "demo-java+cover-constraints"]
 *                       tolerance {
 *                           constraints = ["load >= 0 and load <= 100",
 *                                          "even % 2 == 0",
 *                                          "twice == 2 * once"]
 *                       } }
 *         analogies   { features = ["demo-java", "demo-java+cover-analogies"] }
 *         race        { features = ["demo-java", "demo-java+cover-order-free-block"] }
 *         pool        { features = ["demo-java", "demo-java+cover-potpourri-subset-duplicates"] }
 *         progress    { features = ["demo-java", "demo-java+cover-visible-nothing"]
 *                       tolerance { nothing = ["[.]+"] } }
 *         lisp        { features = ["demo-java", "demo-java+cover-analogy-markers"]
 *                       tolerance { analogy = ["{", "}"] } }
 *         clusters    { features = ["demo-java", "demo-java+cover-point-cloud-pair-distance"] }
 *     }
 * }
 * ______________________________________________________________________________
 * A TEST APPLICATION OF HWUT, FOR READING -- the template for every language.
 *
 *     hwut.run                     runs every choice below, compares with GOOD/
 *     hwut.play demo.java plain    runs one choice and records it in OUT/
 *     hwut.accept demo.java plain  blesses that recording as GOOD; it runs
 *                                  nothing. Where a GOOD stands, the change
 *                                  is 'hwut.merge's -- or '--force' (also
 *                                  '--as-is') replaces it whole.
 *     hwut.merge                   shows OUTPUT against GOOD, key by key
 *     hwut.config.show demo.java   prints what hwut READ from the header above
 *
 * The header above is the whole configuration: a title, how the test is
 * built ('make demo.exe', by the Makefile beside it), and one scope per
 * choice. hwut calls 'demo.exe <choice>' and compares what it prints on
 * stdout with 'GOOD/demo.java--<choice>.txt' -- a link to the Python demo's
 * GOOD: the Java demo prints what the Python demo prints. '<hwut-end>'
 * closes the stream: a stream without it never COMPLETED and is not
 * accepted.
 *
 * Every run is seeded by the clock, so the output differs from run to run --
 * and every choice passes anyway. Each shows WHY:
 *
 * plain        nothing varies; nothing is tolerated. The output must equal
 *              GOOD, line by line.
 *
 * tolerance    'eq_pattern': a greeting drawn at random; any greeting the
 *              pattern names is EQUIVALENT to any other.
 *              'numeric_ratio': a value drawn from [19.91, 20.09]. The band
 *              belongs to the GOOD's number, |n| x ratio: GOOD 19.91 against
 *              20.09 differs by 0.18, inside 19.91 x 0.01 = 0.1991. Every pair
 *              from the interval passes; 20.30 would not.
 *
 * constraints  '((name: value))' BINDS a value; the expressions under
 *              'constraints' judge it, not the GOOD's value. 'load' may be
 *              anything from 0 to 100; 'even' any even number; 'twice' must be
 *              twice 'once', whatever 'once' is. A law over two variables is
 *              checked once both are bound. A binding that breaks its law is
 *              red.
 *
 * race         '##! potpourri' ... '####' opens a block whose lines may arrive
 *              in ANY order -- three workers print as they finish. The same
 *              lines must stand on both sides, each once; the order is free.
 *              The program prints the markers, and so does GOOD.
 *
 * analogies    '((x))' is a placeholder: '((a7f3))' against GOOD's '((91c2))'
 *              is equivalent where the mapping holds throughout the stream --
 *              the same handle opened, read and closed. A handle that changes
 *              in mid-stream is red.
 *
 * pool         '##! potpourri subset duplicates': four workers share twelve
 *              jobs; who takes how many is the scheduler's. 'subset': a
 *              worker that got no job is no fault -- every line of the run
 *              must stand in GOOD, not every line of GOOD in the run.
 *              'duplicates': a worker named twice is one line. The GOOD was
 *              recorded from a run in which all four worked.
 *
 * progress     'nothing': a line made only of what the pattern names counts
 *              as no line. A download prints dots while it waits -- none, or
 *              a few lines of them -- and the dots are no fact.
 *
 * lisp         'analogy = ["{", "}"]': the output is Lisp, where '((' is
 *              syntax, so the placeholder is marked otherwise. An object is
 *              printed with its address, '{10044C1F33}'; the address differs
 *              per run, and must be the same object throughout.
 *
 * clusters     '##! point-cloud limit=0.3 pair dist=Linf': three centroids of
 *              a clustering, in whatever order the run finds them. 'pair':
 *              each centroid pairs with ONE point of GOOD -- two centroids in
 *              one cluster are red. 'dist=Linf': within 0.3 in x AND in y.
 * ______________________________________________________________________________
 */
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Random;
import java.util.concurrent.ConcurrentLinkedQueue;

final class Demo {
    static final String[] GREETING = { "hello", "bonjour", "hallo", "buongiorno", "hola", "ahoj" };
    static final Random   RANDOM   = new Random(System.nanoTime());

    /** RETURN: nothing; 'format' laid out with 'args', the decimal point a
     *          '.' whatever the locale, is printed as one line. */
    static void say(String format, Object... args) {
        System.out.println(String.format(Locale.ROOT, format, args));
    }

    /** RETURN: double, drawn uniformly from [low, high). */
    static double uniform(double low, double high) { return low + (high - low) * RANDOM.nextDouble(); }

    /** RETURN: int, drawn uniformly from [low, high], both included. */
    static int randint(int low, int high) { return low + RANDOM.nextInt(high - low + 1); }

    /** RETURN: nothing; the current thread slept 'seconds'. */
    static void sleep(double seconds) {
        try { Thread.sleep((long) (seconds * 1000.0)); }
        catch (InterruptedException error) { Thread.currentThread().interrupt(); }
    }

    /** RETURN: nothing; every thread of 'pool' was started, then joined. */
    static void startAndJoin(List<Thread> pool) {
        for (Thread thread : pool) thread.start();
        for (Thread thread : pool) {
            try { thread.join(); }
            catch (InterruptedException error) { Thread.currentThread().interrupt(); }
        }
    }

    /** RETURN: nothing; what never varies is printed. */
    static void plain() {
        System.out.println("the first line");
        System.out.println("the second line: 1 2 3");
    }

    /** RETURN: nothing; a greeting and a value, both drawn at random, are printed. */
    static void tolerance() {
        say("greeting: %s, world", GREETING[RANDOM.nextInt(GREETING.length)]);
        say("value:    %.2f", uniform(19.91, 20.09));
    }

    /** RETURN: nothing; bindings, each drawn at random, each lawful, are printed. */
    static void constraints() {
        say("load  ((load: %.1f)) %%", uniform(0.0, 100.0));
        say("even  ((even: %d))", 2 * randint(0, 500));
        int once = randint(1, 50);
        say("once  ((once: %d))", once);
        say("twice ((twice: %d))", 2 * once);
    }

    /** RETURN: List<Long>, 'n' distinct numbers drawn from [low, high). */
    static List<Long> sample(long low, long high, int n) {
        List<Long> result = new ArrayList<>();
        while (result.size() < n) {
            long x = low + (long) (RANDOM.nextDouble() * (high - low));
            if (!result.contains(x)) result.add(x);
        }
        return result;
    }

    /** RETURN: nothing; two handles, each drawn at random, each used
     *          consistently from opening to closing, are printed. */
    static void analogies() {
        List<Long> pair = sample(0x1000, 0x10000, 2);
        long first = pair.get(0), second = pair.get(1);
        say("open  ((%04x)) input.txt", first);
        say("open  ((%04x)) output.txt", second);
        say("read  ((%04x)) 17 lines", first);
        say("write ((%04x)) 17 lines", second);
        say("close ((%04x))", first);
        say("close ((%04x))", second);
    }

    /** RETURN: nothing; three workers printed as they finished; the order is
     *          the scheduler's, the facts are not. The program frames the
     *          unordered block itself: '##! potpourri' ... '####'. */
    static void race() {
        Object lock = new Object();
        List<Thread> pool = new ArrayList<>();
        String[] name = { "A", "B", "C" };
        int[]    jobs = { 3, 5, 2 };
        for (int i = 0; i < 3; ++i) {
            final int k = i;
            pool.add(new Thread(() -> {
                sleep(uniform(0.0, 0.02));
                synchronized (lock) { say("worker %s done: %d jobs", name[k], jobs[k]); }
            }));
        }
        System.out.println("start");
        System.out.println("##! potpourri");
        startAndJoin(pool);
        System.out.println("####");
        System.out.println("all joined");
    }

    /** RETURN: nothing; four workers took twelve jobs from one queue, each
     *          reported the job it finished. Who takes how many is the
     *          scheduler's. */
    static void pool() {
        ConcurrentLinkedQueue<Integer> jobQueue = new ConcurrentLinkedQueue<>();
        for (int job = 0; job < 12; ++job) jobQueue.add(job);
        List<String> doneList = Collections.synchronizedList(new ArrayList<>());
        List<Thread> pool = new ArrayList<>();
        for (String name : List.of("A", "B", "C", "D")) {
            pool.add(new Thread(() -> {
                while (jobQueue.poll() != null) {
                    sleep(uniform(0.0, 0.005));
                    doneList.add("job done by worker " + name);
                }
            }));
        }
        startAndJoin(pool);
        System.out.println("twelve jobs, four workers:");
        System.out.println("##! potpourri subset duplicates");
        for (String line : doneList) System.out.println(line);
        System.out.println("####");
        say("jobs done: %d", doneList.size());
    }

    /** RETURN: nothing; a download printed dots while it waited; how many is
     *          the network's. */
    static void progress() {
        System.out.println("connecting to mirror");
        for (int i = randint(0, 3); i > 0; --i) System.out.println(".".repeat(randint(1, 8)));
        System.out.println("connected");
        System.out.println("received 1024 bytes");
    }

    /** RETURN: nothing; a Lisp session at its prompt is printed: two objects,
     *          each with its address '{...}', drawn anew per run, and each
     *          used again. */
    static void lisp() {
        List<Long> pair = sample(0x1000000000L, 0x1100000000L, 2);
        long table = pair.get(0), thread = pair.get(1);
        System.out.println("* (defvar *cache* (make-hash-table))");
        say("#<HASH-TABLE :TEST EQL :COUNT 0 {%X}>", table);
        System.out.println("* (defvar *worker* (make-thread (lambda () (loop (sleep 1))) :name \"worker\"))");
        say("#<THREAD \"worker\" RUNNING {%X}>", thread);
        System.out.println("* (let ((key (list 1 2))) (setf (gethash key *cache*) *worker*))");
        say("#<THREAD \"worker\" RUNNING {%X}>", thread);
        System.out.println("* *cache*");
        say("#<HASH-TABLE :TEST EQL :COUNT 1 {%X}>", table);
    }

    /** RETURN: double, the squared distance between 'p' and 'c'. */
    static double distance2(double[] p, double[] c) {
        return (p[0] - c[0]) * (p[0] - c[0]) + (p[1] - c[1]) * (p[1] - c[1]);
    }

    /** RETURN: nothing; 90 noisy points around three centres were clustered,
     *          the centroids printed in the order the run found them. */
    static void clusters() {
        double[][] centreList = { { 1.0, 1.0 }, { 5.0, 4.0 }, { 9.0, 1.0 } };
        List<double[]> pointList = new ArrayList<>();
        for (double[] c : centreList)
            for (int i = 0; i < 30; ++i)
                pointList.add(new double[] { c[0] + 0.3 * RANDOM.nextGaussian(), c[1] + 0.3 * RANDOM.nextGaussian() });
        Collections.shuffle(pointList, RANDOM);
        //  The start: one point at random, then twice the point farthest from
        //  every start chosen so far -- one start per cluster.
        List<double[]> centroidList = new ArrayList<>();
        centroidList.add(pointList.get(RANDOM.nextInt(pointList.size())));
        while (centroidList.size() < 3) {
            double[] best = null; double bestD = -1.0;
            for (double[] p : pointList) {
                double d = Double.MAX_VALUE;
                for (double[] c : centroidList) d = Math.min(d, distance2(p, c));
                if (d > bestD) { bestD = d; best = p; }
            }
            centroidList.add(best);
        }
        for (int round = 0; round < 10; ++round) {
            Map<Integer, List<double[]>> memberDb = new LinkedHashMap<>();
            for (int i = 0; i < 3; ++i) memberDb.put(i, new ArrayList<>());
            for (double[] p : pointList) {
                int nearest = 0;
                for (int i = 1; i < 3; ++i)
                    if (distance2(p, centroidList.get(i)) < distance2(p, centroidList.get(nearest))) nearest = i;
                memberDb.get(nearest).add(p);
            }
            List<double[]> next = new ArrayList<>();
            for (List<double[]> m : memberDb.values()) {
                double x = 0.0, y = 0.0;
                for (double[] p : m) { x += p[0]; y += p[1]; }
                next.add(new double[] { x / m.size(), y / m.size() });
            }
            centroidList = next;
        }
        System.out.println("centroids (x y), in the order found:");
        System.out.println("##! point-cloud limit=0.3 pair dist=Linf");
        for (double[] c : centroidList) say("    %5.2f %5.2f", c[0], c[1]);
        System.out.println("####");
    }

    public static void main(String[] args) {
        Map<String, Runnable> choiceDb = new LinkedHashMap<>();
        choiceDb.put("plain",       Demo::plain);
        choiceDb.put("tolerance",   Demo::tolerance);
        choiceDb.put("constraints", Demo::constraints);
        choiceDb.put("analogies",   Demo::analogies);
        choiceDb.put("race",        Demo::race);
        choiceDb.put("pool",        Demo::pool);
        choiceDb.put("progress",    Demo::progress);
        choiceDb.put("lisp",        Demo::lisp);
        choiceDb.put("clusters",    Demo::clusters);
        String choice = args.length > 0 ? args[0] : "";
        if (!choiceDb.containsKey(choice)) {
            System.out.println("choices: " + String.join(", ", choiceDb.keySet()));
            System.exit(1);
        }
        choiceDb.get(choice).run();
        System.out.println("<hwut-end>");
    }
}
