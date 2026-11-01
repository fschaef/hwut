/* @hwut {
 *     title   = "Demo: what hwut tolerates, and where it is said"
 *     build   { framework = "make", executable = "%.exe" }
 *     choices {
 *         plain       { features = ["demo-passes-on-every-run", "exact-comparison"] }
 *         tolerance   { features = ["demo-passes-on-every-run", "equivalence-pattern", "numeric-ratio"]
 *                       tolerance {
 *                           eq_pattern    = ["(hello|bonjour|hallo|buongiorno|hola|ahoj)"]
 *                           numeric_ratio = 0.01
 *                       } }
 *         constraints { features = ["demo-passes-on-every-run", "constraints"]
 *                       tolerance {
 *                           constraints = ["load >= 0 and load <= 100",
 *                                          "even % 2 == 0",
 *                                          "twice == 2 * once"]
 *                       } }
 *         analogies   { features = ["demo-passes-on-every-run", "analogies"] }
 *         race        { features = ["demo-passes-on-every-run", "order-free-block"] }
 *         pool        { features = ["demo-passes-on-every-run", "potpourri-subset-duplicates"] }
 *         progress    { features = ["demo-passes-on-every-run", "visible-nothing"]
 *                       tolerance { nothing = ["[.]+"] } }
 *         lisp        { features = ["demo-passes-on-every-run", "analogy-markers"]
 *                       tolerance { analogy = ["{", "}"] } }
 *         clusters    { features = ["demo-passes-on-every-run", "point-cloud-pair-distance"] }
 *     }
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * A TEST APPLICATION OF HWUT, FOR READING -- the template, in C.
 *
 *     hwut.run                   builds 'demo.exe' by the Makefile beside
 *                                this file ('build' above), runs every
 *                                choice below, compares with GOOD/
 *     hwut.play demo.c plain     runs one choice and records it in OUT/
 *     hwut.accept demo.c plain   blesses that recording as GOOD; it runs
 *                                nothing. Where a GOOD stands, the change
 *                                is 'hwut.merge's -- or '--force' (also
 *                                '--as-is') replaces it whole.
 *     hwut.merge                 shows OUTPUT against GOOD, key by key
 *     hwut.config.show demo.c    prints what hwut READ from the header above
 *
 * The header above is the whole configuration: a title, how the application
 * is built, and one scope per choice. hwut calls 'demo.exe <choice>' and
 * compares what it prints on stdout with 'GOOD/demo.c--<choice>.txt' -- a
 * '.link' to the Python demo's GOOD: the C program prints the same text.
 * '<hwut-end>' closes the stream: a stream without it never COMPLETED and is
 * not accepted.
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
 *              in ANY order -- three workers (threads) print as they finish.
 *              The same lines must stand on both sides, each once; the order
 *              is free. The program prints the markers, and so does GOOD.
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
 * _____________________________________________________________________________
 */
#define _POSIX_C_SOURCE 200809L
#define _DEFAULT_SOURCE
#include <math.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

static const char* const GREETING[] = { "hello", "bonjour", "hallo", "buongiorno", "hola", "ahoj" };

/* ONE RANDOM STREAM for the process, seeded by the clock; the workers of
 * 'race' and 'pool' draw from it under its lock.                             */
static uint64_t        random_state;
static pthread_mutex_t random_lock  = PTHREAD_MUTEX_INITIALIZER;
static pthread_mutex_t print_lock   = PTHREAD_MUTEX_INITIALIZER;

static uint64_t
random_next(void)
/* RETURN: uint64_t, the next number of the stream (splitmix64), any value. */
{
    uint64_t z;
    pthread_mutex_lock(&random_lock);
    z = (random_state += 0x9E3779B97F4A7C15ULL);
    pthread_mutex_unlock(&random_lock);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

static double
uniform(double low, double high)
/* RETURN: double, drawn evenly from [low, high). */
{ return low + (high - low) * (double)(random_next() >> 11) / 9007199254740992.0; }

static long long
randint(long long low, long long high)
/* RETURN: long long, drawn evenly from [low, high], both included. */
{ return low + (long long)(random_next() % (uint64_t)(high - low + 1)); }

static double
gauss(double mu, double sigma)
/* RETURN: double, drawn from the normal distribution (mu, sigma); Box-Muller. */
{
    double u = 1.0 - uniform(0.0, 1.0), v = uniform(0.0, 1.0);
    return mu + sigma * sqrt(-2.0 * log(u)) * cos(2.0 * M_PI * v);
}

static void
sleep_s(double seconds)
/* RETURN: nothing; the thread has slept 'seconds'. */
{
    struct timespec t;
    t.tv_sec  = (time_t)seconds;
    t.tv_nsec = (long)((seconds - (double)t.tv_sec) * 1e9);
    nanosleep(&t, NULL);
}

static void
plain(void)
/* RETURN: nothing. Prints what never varies. */
{
    printf("the first line\n");
    printf("the second line: 1 2 3\n");
}

static void
tolerance(void)
/* RETURN: nothing. Prints a greeting and a value, both drawn at random. */
{
    printf("greeting: %s, world\n", GREETING[randint(0, 5)]);
    printf("value:    %.2f\n", uniform(19.91, 20.09));
}

static void
constraints(void)
/* RETURN: nothing. Prints bindings, each drawn at random, each lawful. */
{
    long long once;
    printf("load  ((load: %.1f)) %%\n", uniform(0.0, 100.0));
    printf("even  ((even: %lld))\n", 2 * randint(0, 500));
    once = randint(1, 50);
    printf("once  ((once: %lld))\n", once);
    printf("twice ((twice: %lld))\n", 2 * once);
}

static void
analogies(void)
/* RETURN: nothing. Prints two handles, each drawn at random, each used
 *         consistently from opening to closing.                              */
{
    long long first = randint(0x1000, 0xFFFF), second;
    do second = randint(0x1000, 0xFFFF); while( second == first );
    printf("open  ((%04llx)) input.txt\n", first);
    printf("open  ((%04llx)) output.txt\n", second);
    printf("read  ((%04llx)) 17 lines\n", first);
    printf("write ((%04llx)) 17 lines\n", second);
    printf("close ((%04llx))\n", first);
    printf("close ((%04llx))\n", second);
}

typedef struct { const char* name; int jobs; } RaceWorker;

static void*
race_work(void* argument)
/* RETURN: NULL. The worker slept a little, then said it is done. */
{
    const RaceWorker* self = (const RaceWorker*)argument;
    sleep_s(uniform(0.0, 0.02));
    pthread_mutex_lock(&print_lock);
    printf("worker %s done: %i jobs\n", self->name, self->jobs);
    pthread_mutex_unlock(&print_lock);
    return NULL;
}

static void
race(void)
/* RETURN: nothing. Three workers print as they finish; the order is the
 *         scheduler's, the facts are not. The program frames the unordered
 *         block itself: '##! potpourri' ... '####'.                         */
{
    static const RaceWorker worker[3] = { { "A", 3 }, { "B", 5 }, { "C", 2 } };
    pthread_t thread[3];
    int       i;
    printf("start\n");
    printf("##! potpourri\n");
    fflush(stdout);
    for(i = 0; i < 3; ++i) pthread_create(&thread[i], NULL, race_work, (void*)&worker[i]);
    for(i = 0; i < 3; ++i) pthread_join(thread[i], NULL);
    printf("####\n");
    printf("all joined\n");
}

static int  pool_job_n;             /* jobs still in the queue           */
static char pool_done[12][32];      /* 'job done by worker X', in order  */
static int  pool_done_n;

static void*
pool_work(void* argument)
/* RETURN: NULL. The worker took jobs from the queue until it was empty. */
{
    const char* name = (const char*)argument;
    for(;;) {
        pthread_mutex_lock(&print_lock);
        if( pool_job_n == 0 ) { pthread_mutex_unlock(&print_lock); return NULL; }
        pool_job_n -= 1;
        pthread_mutex_unlock(&print_lock);
        sleep_s(uniform(0.0, 0.005));
        pthread_mutex_lock(&print_lock);
        snprintf(pool_done[pool_done_n++], sizeof(pool_done[0]), "job done by worker %s", name);
        pthread_mutex_unlock(&print_lock);
    }
}

static void
pool(void)
/* RETURN: nothing. Four workers take twelve jobs from one queue; each
 *         reports the job it finished. Who takes how many is the scheduler's. */
{
    static const char* const name[4] = { "A", "B", "C", "D" };
    pthread_t thread[4];
    int       i;
    pool_job_n = 12;
    for(i = 0; i < 4; ++i) pthread_create(&thread[i], NULL, pool_work, (void*)name[i]);
    for(i = 0; i < 4; ++i) pthread_join(thread[i], NULL);
    printf("twelve jobs, four workers:\n");
    printf("##! potpourri subset duplicates\n");
    for(i = 0; i < pool_done_n; ++i) printf("%s\n", pool_done[i]);
    printf("####\n");
    printf("jobs done: %i\n", pool_done_n);
}

static void
progress(void)
/* RETURN: nothing. A download that prints dots while it waits; how many is
 *         the network's.                                                    */
{
    long long line_n = randint(0, 3), i, dot_n;
    printf("connecting to mirror\n");
    for(i = 0; i < line_n; ++i) {
        for(dot_n = randint(1, 8); dot_n; --dot_n) putchar('.');
        putchar('\n');
    }
    printf("connected\n");
    printf("received 1024 bytes\n");
}

static void
lisp(void)
/* RETURN: nothing. A Lisp session at its prompt: two objects, each printed
 *         with its address '{...}', drawn anew per run, and each used again. */
{
    long long table = randint(0x1000000000LL, 0x10FFFFFFFFLL), thread;
    do thread = randint(0x1000000000LL, 0x10FFFFFFFFLL); while( thread == table );
    printf("* (defvar *cache* (make-hash-table))\n");
    printf("#<HASH-TABLE :TEST EQL :COUNT 0 {%llX}>\n", table);
    printf("* (defvar *worker* (make-thread (lambda () (loop (sleep 1))) :name \"worker\"))\n");
    printf("#<THREAD \"worker\" RUNNING {%llX}>\n", thread);
    printf("* (let ((key (list 1 2))) (setf (gethash key *cache*) *worker*))\n");
    printf("#<THREAD \"worker\" RUNNING {%llX}>\n", thread);
    printf("* *cache*\n");
    printf("#<HASH-TABLE :TEST EQL :COUNT 1 {%llX}>\n", table);
}

typedef struct { double x, y; } Point;

static double
distance2(Point p, Point c)
/* RETURN: double, the square of the distance between 'p' and 'c'. */
{ return (p.x - c.x) * (p.x - c.x) + (p.y - c.y) * (p.y - c.y); }

static void
clusters(void)
/* RETURN: nothing. Clusters 90 noisy points around three centres and prints
 *         the centroids in the order the run found them.                    */
{
    static const Point centre[3] = { { 1.0, 1.0 }, { 5.0, 4.0 }, { 9.0, 1.0 } };
    Point  point[90], centroid[3], swap, sum[3];
    int    member_n[3], i, k, round, nearest, best;
    double nearest_d, d, best_d;
    for(k = 0; k < 3; ++k)
        for(i = 0; i < 30; ++i) {
            point[30 * k + i].x = centre[k].x + gauss(0.0, 0.3);
            point[30 * k + i].y = centre[k].y + gauss(0.0, 0.3);
        }
    for(i = 89; i > 0; --i) {
        k = (int)randint(0, i);
        swap = point[i]; point[i] = point[k]; point[k] = swap;
    }
    /* The start: one point at random, then twice the point farthest from
     * every start chosen so far -- one start per cluster.                   */
    centroid[0] = point[randint(0, 89)];
    for(k = 1; k < 3; ++k) {
        best = 0; best_d = -1.0;
        for(i = 0; i < 90; ++i) {
            nearest_d = distance2(point[i], centroid[0]);
            for(round = 1; round < k; ++round) {
                d = distance2(point[i], centroid[round]);
                if( d < nearest_d ) nearest_d = d;
            }
            if( nearest_d > best_d ) { best_d = nearest_d; best = i; }
        }
        centroid[k] = point[best];
    }
    for(round = 0; round < 10; ++round) {
        memset(sum, 0, sizeof(sum)); memset(member_n, 0, sizeof(member_n));
        for(i = 0; i < 90; ++i) {
            nearest = 0;
            for(k = 1; k < 3; ++k)
                if( distance2(point[i], centroid[k]) < distance2(point[i], centroid[nearest]) ) nearest = k;
            sum[nearest].x += point[i].x; sum[nearest].y += point[i].y; member_n[nearest] += 1;
        }
        for(k = 0; k < 3; ++k) {
            centroid[k].x = sum[k].x / member_n[k];
            centroid[k].y = sum[k].y / member_n[k];
        }
    }
    printf("centroids (x y), in the order found:\n");
    printf("##! point-cloud limit=0.3 pair dist=Linf\n");
    for(k = 0; k < 3; ++k) printf("    %5.2f %5.2f\n", centroid[k].x, centroid[k].y);
    printf("####\n");
}

static const struct { const char* name; void (*function)(void); } CHOICE_DB[] = {
    { "plain",       plain },
    { "tolerance",   tolerance },
    { "constraints", constraints },
    { "analogies",   analogies },
    { "race",        race },
    { "pool",        pool },
    { "progress",    progress },
    { "lisp",        lisp },
    { "clusters",    clusters },
    { NULL,          NULL }
};

int
main(int argc, char** argv)
/* RETURN: int, 0 -- the choice ran and '<hwut-end>' closed its output;
 *         1, the choice is not one of CHOICE_DB (they are named).           */
{
    struct timespec now;
    const char*     choice = argc > 1 ? argv[1] : "";
    int             i;
    clock_gettime(CLOCK_REALTIME, &now);
    random_state = (uint64_t)now.tv_sec * 1000000000ULL + (uint64_t)now.tv_nsec;
    for(i = 0; CHOICE_DB[i].name; ++i) if( strcmp(choice, CHOICE_DB[i].name) == 0 ) break;
    if( ! CHOICE_DB[i].name ) {
        printf("choices: ");
        for(i = 0; CHOICE_DB[i].name; ++i) printf("%s%s", i ? ", " : "", CHOICE_DB[i].name);
        printf("\n");
        return 1;
    }
    CHOICE_DB[i].function();
    printf("<hwut-end>\n");
    return 0;
}
