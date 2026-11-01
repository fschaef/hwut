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
 * A TEST APPLICATION OF HWUT, FOR READING -- 'demo.py' of the Python
 * demonstration, choice for choice, printing the same text.
 *
 *     hwut.run                    builds 'demo.exe' (the Makefile beside this
 *                                 file), runs every choice, compares with GOOD/
 *     hwut.play demo.cpp plain    runs one choice and records it in OUT/
 *     hwut.accept demo.cpp plain  blesses that recording as GOOD
 *     hwut.config.show demo.cpp   prints what hwut READ from the header above
 *
 * The header above is the whole configuration: a title, how the application
 * is BUILT -- 'make demo.exe', in this directory -- and one scope per choice.
 * hwut calls 'demo.exe <choice>' and compares what it prints on stdout with
 * 'GOOD/demo.cpp--<choice>.link' -- a link to the Python demonstration's
 * GOOD: the C++ application is held against what the Python one was
 * accepted for. '<hwut-end>' closes the stream.
 *
 * Every run is seeded by the clock, so the output differs from run to run --
 * and every choice passes anyway. Why, each choice's tolerance says; the
 * Python 'demo.py' explains each at length:
 *
 * plain        nothing varies; nothing is tolerated.
 * tolerance    'eq_pattern': any greeting the pattern names is equivalent;
 *              'numeric_ratio': a value from [19.91, 20.09] within 1 %.
 * constraints  '((name: value))' binds; the laws judge, not the GOOD's value.
 * analogies    '((x))' a placeholder, consistent throughout the stream.
 * race         '##! potpourri' ... '####': three threads, any order.
 * pool         '##! potpourri subset duplicates': four threads, twelve jobs.
 * progress     'nothing': lines of dots count as no line.
 * lisp         'analogy = ["{", "}"]': '{10044C1F33}' a placeholder.
 * clusters     '##! point-cloud limit=0.3 pair dist=Linf': three centroids.
 * _____________________________________________________________________________
 */
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <functional>
#include <map>
#include <mutex>
#include <random>
#include <string>
#include <thread>
#include <utility>
#include <vector>

static std::mt19937_64 rng;

static double uniform(double low, double high)
/* RETURN: double, drawn uniformly from [low, high). */
{ return std::uniform_real_distribution<double>(low, high)(rng); }

static long long randint(long long low, long long high)
/* RETURN: long long, drawn uniformly from [low, high], both included. */
{ return std::uniform_int_distribution<long long>(low, high)(rng); }

static double gauss(double mu, double sigma)
/* RETURN: double, drawn from the normal distribution (mu, sigma). */
{ return std::normal_distribution<double>(mu, sigma)(rng); }

static std::pair<long long, long long> two_distinct(long long low, long long high)
/* RETURN: two distinct values, each drawn uniformly from [low, high). */
{
    long long first = randint(low, high - 1), second;
    do second = randint(low, high - 1); while( second == first );
    return { first, second };
}

static void plain()
/* RETURN: nothing. Prints what never varies. */
{
    std::printf("the first line\n");
    std::printf("the second line: 1 2 3\n");
}

static void tolerance()
/* RETURN: nothing. Prints a greeting and a value, both drawn at random. */
{
    static const char* greeting[] = { "hello", "bonjour", "hallo", "buongiorno", "hola", "ahoj" };
    std::printf("greeting: %s, world\n", greeting[randint(0, 5)]);
    std::printf("value:    %.2f\n", uniform(19.91, 20.09));
}

static void constraints()
/* RETURN: nothing. Prints bindings, each drawn at random, each lawful. */
{
    std::printf("load  ((load: %.1f)) %%\n", uniform(0.0, 100.0));
    std::printf("even  ((even: %lld))\n", 2 * randint(0, 500));
    long long once = randint(1, 50);
    std::printf("once  ((once: %lld))\n", once);
    std::printf("twice ((twice: %lld))\n", 2 * once);
}

static void analogies()
/* RETURN: nothing. Prints two handles, each drawn at random, each used
 *         consistently from opening to closing.                          */
{
    auto [first, second] = two_distinct(0x1000, 0x10000);
    std::printf("open  ((%04llx)) input.txt\n", first);
    std::printf("open  ((%04llx)) output.txt\n", second);
    std::printf("read  ((%04llx)) 17 lines\n", first);
    std::printf("write ((%04llx)) 17 lines\n", second);
    std::printf("close ((%04llx))\n", first);
    std::printf("close ((%04llx))\n", second);
}

static void race()
/* RETURN: nothing. Three threads print as they finish; the order is the
 *         scheduler's, the facts are not. The program frames the unordered
 *         block itself: '##! potpourri' ... '####'.                      */
{
    std::mutex lock;
    std::vector<std::pair<const char*, int>> job_list = { { "A", 3 }, { "B", 5 }, { "C", 2 } };
    std::vector<int> sleep_us;
    for(size_t i = 0; i < job_list.size(); ++i) sleep_us.push_back((int)randint(0, 20000));
    std::printf("start\n");
    std::printf("##! potpourri\n");
    std::fflush(stdout);
    std::vector<std::thread> pool;
    for(size_t i = 0; i < job_list.size(); ++i) {
        pool.emplace_back([&, i] {
            std::this_thread::sleep_for(std::chrono::microseconds(sleep_us[i]));
            std::lock_guard<std::mutex> guard(lock);
            std::printf("worker %s done: %i jobs\n", job_list[i].first, job_list[i].second);
            std::fflush(stdout);
        });
    }
    for(auto& thread : pool) thread.join();
    std::printf("####\n");
    std::printf("all joined\n");
}

static void pool()
/* RETURN: nothing. Four threads take twelve jobs from one queue; each
 *         reports the job it finished. Who takes how many is the
 *         scheduler's.                                                   */
{
    std::mutex lock;
    int job_n = 12;
    std::vector<std::string> done_list;
    std::vector<std::thread> pool;
    for(const char* name : { "A", "B", "C", "D" }) {
        int sleep_us = (int)randint(0, 5000);
        pool.emplace_back([&, name, sleep_us] {
            for(;;) {
                {
                    std::lock_guard<std::mutex> guard(lock);
                    if( job_n == 0 ) return;
                    --job_n;
                }
                std::this_thread::sleep_for(std::chrono::microseconds(sleep_us));
                std::lock_guard<std::mutex> guard(lock);
                done_list.push_back(std::string("job done by worker ") + name);
            }
        });
    }
    for(auto& thread : pool) thread.join();
    std::printf("twelve jobs, four workers:\n");
    std::printf("##! potpourri subset duplicates\n");
    for(const auto& line : done_list) std::printf("%s\n", line.c_str());
    std::printf("####\n");
    std::printf("jobs done: %zu\n", done_list.size());
}

static void progress()
/* RETURN: nothing. A download that prints dots while it waits; how many is
 *         the network's.                                                 */
{
    std::printf("connecting to mirror\n");
    for(long long i = randint(0, 3); i > 0; --i)
        std::printf("%s\n", std::string((size_t)randint(1, 8), '.').c_str());
    std::printf("connected\n");
    std::printf("received 1024 bytes\n");
}

static void lisp()
/* RETURN: nothing. A Lisp session at its prompt: two objects, each printed
 *         with its address '{...}', drawn anew per run, and each used again. */
{
    auto [table, thread] = two_distinct(0x1000000000LL, 0x1100000000LL);
    std::printf("* (defvar *cache* (make-hash-table))\n");
    std::printf("#<HASH-TABLE :TEST EQL :COUNT 0 {%llX}>\n", table);
    std::printf("* (defvar *worker* (make-thread (lambda () (loop (sleep 1))) :name \"worker\"))\n");
    std::printf("#<THREAD \"worker\" RUNNING {%llX}>\n", thread);
    std::printf("* (let ((key (list 1 2))) (setf (gethash key *cache*) *worker*))\n");
    std::printf("#<THREAD \"worker\" RUNNING {%llX}>\n", thread);
    std::printf("* *cache*\n");
    std::printf("#<HASH-TABLE :TEST EQL :COUNT 1 {%llX}>\n", table);
}

static void clusters()
/* RETURN: nothing. Clusters 90 noisy points around three centres and prints
 *         the centroids in the order the run found them.                 */
{
    using Point = std::pair<double, double>;
    const std::vector<Point> centre_list = { { 1.0, 1.0 }, { 5.0, 4.0 }, { 9.0, 1.0 } };
    std::vector<Point> point_list;
    for(const Point& c : centre_list)
        for(int i = 0; i < 30; ++i) point_list.push_back({ c.first + gauss(0.0, 0.3), c.second + gauss(0.0, 0.3) });
    std::shuffle(point_list.begin(), point_list.end(), rng);
    auto distance2 = [](const Point& p, const Point& c) {
        return (p.first - c.first) * (p.first - c.first) + (p.second - c.second) * (p.second - c.second);
    };
    //  The start: one point at random, then twice the point farthest from
    //  every start chosen so far -- one start per cluster.
    std::vector<Point> centroid_list = { point_list[(size_t)randint(0, (long long)point_list.size() - 1)] };
    while( centroid_list.size() < 3 ) {
        auto nearest = [&](const Point& p) {
            double d = distance2(p, centroid_list[0]);
            for(const Point& c : centroid_list) d = std::min(d, distance2(p, c));
            return d;
        };
        centroid_list.push_back(*std::max_element(point_list.begin(), point_list.end(),
                                [&](const Point& a, const Point& b) { return nearest(a) < nearest(b); }));
    }
    for(int round = 0; round < 10; ++round) {
        std::vector<std::vector<Point>> member_list(3);
        for(const Point& p : point_list) {
            size_t nearest = 0;
            for(size_t i = 1; i < 3; ++i)
                if( distance2(p, centroid_list[i]) < distance2(p, centroid_list[nearest]) ) nearest = i;
            member_list[nearest].push_back(p);
        }
        for(size_t i = 0; i < 3; ++i) {
            double x = 0.0, y = 0.0;
            for(const Point& p : member_list[i]) { x += p.first; y += p.second; }
            centroid_list[i] = { x / member_list[i].size(), y / member_list[i].size() };
        }
    }
    std::printf("centroids (x y), in the order found:\n");
    std::printf("##! point-cloud limit=0.3 pair dist=Linf\n");
    for(const Point& c : centroid_list) std::printf("    %5.2f %5.2f\n", c.first, c.second);
    std::printf("####\n");
}

int main(int argc, char** argv)
/* RETURN: 0, the choice named by 'argv[1]' printed, '<hwut-end>' after it;
 *         1, where no known choice is named (the choices are printed).   */
{
    const std::vector<std::pair<std::string, std::function<void()>>> choice_list = {
        { "plain",       plain },       { "tolerance", tolerance }, { "constraints", constraints },
        { "analogies",   analogies },   { "race",      race },      { "pool",        pool },
        { "progress",    progress },    { "lisp",      lisp },      { "clusters",    clusters },
    };
    rng.seed((uint64_t)std::chrono::system_clock::now().time_since_epoch().count());
    const std::string choice = argc > 1 ? argv[1] : "";
    for(const auto& [name, function] : choice_list) {
        if( name != choice ) continue;
        function();
        std::printf("<hwut-end>\n");
        return 0;
    }
    std::string names;
    for(const auto& entry : choice_list) names += (names.empty() ? "" : ", ") + entry.first;
    std::printf("choices: %s\n", names.c_str());
    return 1;
}
