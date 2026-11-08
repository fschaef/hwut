/* @hwut {
 *     title    = "Demo: a garage's space counter -- a space, a stream and races, generated"
 *     build    { framework = "make", target = "%.exe" }
 *     interactive = true
 *     choices {
 *         space       { features = ["space-from-hocon", "space-iterator", "hwut-runner"]
 *                       tolerance { constraints = ["mismatches == 0"] } }
 *         random      { features = ["deterministic-stream", "hwut-runner"]
 *                       tolerance { constraints = ["mismatches == 0"] } }
 *         race-naive  { features = ["deterministic-timeline", "space-iterator", "hwut-runner"]
 *                       tolerance { constraints = ["overbooked > 0"] } }
 *         race-atomic { features = ["deterministic-timeline", "space-iterator", "hwut-runner"]
 *                       tolerance { constraints = ["overbooked == 0"] } }
 *     }
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * SUBJECT  the counter of free spaces at a garage's gates: which cars it
 *          admits, which it refuses, and how many stand inside.
 * REQUIREMENT  The garage admits a car only while a space is free, lets a car
 *              out only while one stands inside, and never holds more cars
 *              than it has spaces -- also when two gates admit at once.
 *
 * No choice writes its cases out by hand. Each GENERATES them, with one of
 * hwut's helpers for writing tests -- the C++ port, 'hwut::' (README.txt,
 * MAKE IT IMPORTABLE; the Makefile names where it stands):
 *
 * space        'garage-space.hocon' states the tested space, read by
 *              'hwut::hocon::parse'; 'hwut::space_iterator::do_' walks every
 *              combination: 3 x 5 x 4 = 60 cases, checked against the model:
 *              admitted = min(arriving, capacity), out = min(leaving, admitted).
 *
 * random       'hwut::DeterministicStream(4711)' draws 1000 cars arriving and
 *              leaving at a garage of 5. The draw is the same on every machine
 *              and in every language hwut supports -- the GOOD is the Python
 *              demonstration's, exact.
 *
 * race-naive   two gates, one free space. A gate CHECKS whether a space is
 *              free, and later ADMITS its car. 'hwut::TriggerDispatcher' runs
 *              the gates as Triggers on timelines drawn as strings -- '1 1 '
 *              fires at tick 0 and tick 2 -- so every interleaving is played
 *              exactly. 'space_iterator' generates all six interleavings of
 *              two two-step gates in four ticks. The law is 'overbooked > 0':
 *              the GOOD is the accepted violation report.
 *
 * race-atomic  the same six interleavings, the gate checking and admitting in
 *              ONE step. 'overbooked == 0'.
 *
 * THE FRONT END is 'hwut::HwutRunner': the choice list below is the whole
 * command line, '--hwut-info' included. 'interactive = true': hwut starts the
 * application ONCE and asks for the choices one after another.
 * _____________________________________________________________________________
 */
#include <cstdio>
#include <fstream>
#include <functional>
#include <map>
#include <set>
#include <string>
#include <utility>
#include <vector>
#include <unistd.h>
#include <limits.h>

#include "hwut_runner.hpp"
#include "hwut_hocon.hpp"
#include "hwut_pytext.hpp"
#include "deterministic_random.hpp"
#include "deterministic_timeline.hpp"
#include "space_iterator.hpp"

static std::string here()
/* RETURN: std::string, the directory this executable stands in. */
{
    char path[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", path, sizeof(path) - 1);
    std::string self = n > 0 ? std::string(path, (size_t)n) : std::string(".");
    size_t slash = self.rfind('/');
    return slash == std::string::npos ? "." : self.substr(0, slash);
}

/* The unit under test: a counter of the spaces a garage has. */
struct Garage {
    int capacity;
    int occupied = 0;
    explicit Garage(int capacity_) : capacity(capacity_) {}

    int free() const
    /* RETURN: int, the number of spaces free now -- negative where the
     *         garage is overbooked.                                       */
    { return capacity - occupied; }

    bool arrive()
    /* RETURN: true, a car was admitted, if a space was free;
     *         false, else (the car is refused).                           */
    { if( free() <= 0 ) return false; ++occupied; return true; }

    bool leave()
    /* RETURN: true, a car drove out, if one stood inside;
     *         false, else.                                                */
    { if( occupied == 0 ) return false; --occupied; return true; }
};

// _____________________________________________________________________________
// space -- the tested space from HOCON, walked by space_iterator
//
static std::vector<std::pair<std::string, std::vector<int>>> read_space(const std::string& path)
/* RETURN: the dimensions of the space in 'path', in the order written:
 *         (name, values). Every fault the HOCON reader found is printed
 *         with '!!' first.                                               */
{
    std::ifstream in(path);
    std::vector<hwut::hocon::SourceLine> line_list;
    std::string text;
    for(int i = 1; std::getline(in, text); ++i) line_list.push_back({ text, i, 0 });
    auto [document, fault_list] = hwut::hocon::parse(line_list, path.substr(path.rfind('/') + 1));
    for(const auto& fault : fault_list) std::printf("!! %s\n", fault.to_string().c_str());
    std::vector<std::pair<std::string, std::vector<int>>> dimension_list;
    for(const auto& entry : document.get("space")->node.entry_list()) {
        std::vector<int> value_list;
        for(const auto& item : entry.node.item_list()) value_list.push_back((int)item.as_int());
        dimension_list.push_back({ entry.key, value_list });
    }
    return dimension_list;
}

static std::string rstrip(std::string text)
/* RETURN: std::string, 'text' without its trailing blanks. */
{ text.erase(text.find_last_not_of(' ') + 1); return text; }

static void space()
/* RETURN: nothing. Prints every case of the space as a matrix cell. */
{
    auto dimension_list = read_space(here() + "/garage-space.hocon");
    std::vector<std::vector<int>> value_list;
    std::string head;
    for(const auto& [name, values] : dimension_list) {
        value_list.push_back(values);
        head += (head.empty() ? "" : "  x  ") + name + " " + hwut::pytext::repr(values);
    }
    std::printf("space: %s\n", head.c_str());
    std::printf("cell: cars inside / cars refused at the gate ('!!' differs from the model)\n");
    int mismatch_n = 0;
    std::map<std::pair<int, int>, std::vector<std::string>> row_db;
    for(const std::vector<int>& point : hwut::space_iterator::do_(value_list)) {
        int capacity = point[0], arriving = point[1], leaving = point[2];
        Garage garage(capacity);
        int refused = 0;
        for(int i = 0; i < arriving; ++i) refused += ! garage.arrive();
        for(int i = 0; i < leaving; ++i)  garage.leave();
        int admitted = std::min(arriving, capacity);
        std::pair<int, int> expected = { admitted - std::min(leaving, admitted), arriving - admitted };
        std::pair<int, int> got      = { garage.occupied, refused };
        mismatch_n += got != expected;
        char cell[32];
        std::snprintf(cell, sizeof(cell), "%d/%d%s", got.first, got.second, got == expected ? "  " : "!!");
        row_db[{ capacity, arriving }].push_back(cell);
    }
    for(int capacity : value_list[0]) {
        std::string leave_head;
        for(int leaving : value_list[2]) {
            char word[32];
            std::snprintf(word, sizeof(word), "leave %-3d", leaving);
            leave_head += (leave_head.empty() ? "" : "  ") + std::string(word);
        }
        std::printf("capacity %d   %s\n", capacity, rstrip(leave_head).c_str());
        for(int arriving : value_list[1]) {
            std::string row;
            for(const std::string& c : row_db[{ capacity, arriving }]) {
                char word[32];
                std::snprintf(word, sizeof(word), "%-9s", c.c_str());
                row += (row.empty() ? "" : "  ") + std::string(word);
            }
            std::printf("%s\n", rstrip("  arrive " + std::to_string(arriving) + "   " + row).c_str());
        }
    }
    std::printf("cases %zu, differing from the model ((mismatches: %d))\n",
                row_db.size() * value_list[2].size(), mismatch_n);
}

// _____________________________________________________________________________
// random -- a deterministic stream of arrivals and departures
//
static void random_stream()
/* RETURN: nothing. Prints the summary of 1000 drawn cars, model-checked. */
{
    hwut::DeterministicStream stream(4711);
    Garage garage(5);
    int model = 0, arrive_n = 0, refused_n = 0, leave_n = 0, empty_n = 0, mismatch_n = 0;
    std::vector<int> histogram(6, 0);
    std::string strip;
    for(int i = 0; i < 1000; ++i) {
        if( stream.coin(0.55) ) {
            ++arrive_n;
            if( ! garage.arrive() ) ++refused_n;
            model = std::min(5, model + 1);
            strip += "+";
        } else {
            ++leave_n;
            if( ! garage.leave() ) ++empty_n;
            model = std::max(0, model - 1);
            strip += "-";
        }
        mismatch_n += garage.occupied != model;
        histogram[(size_t)garage.occupied] += 1;
    }
    std::printf("seed 4711, garage of 5, 1000 cars drawn: '+' arrives, '-' leaves\n");
    std::printf("first 60: %s\n", strip.substr(0, 60).c_str());
    std::printf("arrivals %d, refused %d; departures %d, from an empty garage %d\n",
                arrive_n, refused_n, leave_n, empty_n);
    std::printf("cars inside after each event:\n");
    for(size_t n = 0; n < histogram.size(); ++n)
        std::printf("    %zu  %4d  %s\n", n, histogram[n], std::string((size_t)histogram[n] / 10, '#').c_str());
    std::printf("steps differing from the model ((mismatches: %d))\n", mismatch_n);
}

// _____________________________________________________________________________
// race -- two gates on drawn timelines
//
/* A gate on a timeline: its first tick checks, its second admits. */
struct Gate : hwut::Trigger {
    Garage&                                 garage;
    bool                                    atomic;
    std::function<void(const std::string&)> log;
    int                                     step = 0;
    bool                                    saw_free = false;

    Gate(const std::string& name, const std::string& timeline, Garage& garage_, bool atomic_,
         std::function<void(const std::string&)> log_)
    /* RETURN: Gate 'name' on 'timeline', at 'garage', not yet fired. */
        : hwut::Trigger(timeline, name), garage(garage_), atomic(atomic_), log(std::move(log_)) {}

    void fire(int pseudo_time) override
    /* RETURN: nothing. Performs the gate's next step at 'pseudo_time'. */
    {
        const std::string me = name();
        if( step == 0 && atomic ) {
            saw_free = garage.arrive();
            log(me + (saw_free ? " checks+admits" : " refuses"));
        } else if( step == 0 ) {
            saw_free = garage.free() > 0;
            log(me + " sees " + std::to_string(garage.free()) + " free");
        } else if( atomic ) {
            log(me + (saw_free ? " opens" : " stays shut"));
        } else if( saw_free ) {
            garage.occupied += 1;                                // the naive admit
            log(me + " admits");
        } else {
            log(me + " refuses");
        }
        ++step;
    }
};

static std::vector<std::pair<std::string, std::string>> interleaving_list()
/* RETURN: every pair of timelines in four ticks in which each of two gates
 *         fires twice, never at the same tick: gate A's and gate B's.    */
{
    std::vector<std::pair<std::string, std::string>> result;
    std::vector<std::vector<int>> basis(4, std::vector<int>{ 0, 1, 2, 3 });
    auto line = [](int x, int y) {
        std::string text;
        for(int t = 0; t < 4; ++t) text += (t == x || t == y) ? "1" : " ";
        return text;
    };
    for(const std::vector<int>& p : hwut::space_iterator::do_(basis)) {
        int a1 = p[0], a2 = p[1], b1 = p[2], b2 = p[3];
        if( a1 < a2 && b1 < b2 && std::set<int>{ a1, a2, b1, b2 }.size() == 4 )
            result.push_back({ line(a1, a2), line(b1, b2) });
    }
    return result;
}

static void race(bool atomic)
/* RETURN: nothing. Plays every interleaving of two gates at one space. */
{
    std::printf("one free space, two gates, one car at each; timelines: a digit fires\n");
    std::printf("    gate A  gate B  what happens                                    inside\n");
    int overbooked_n = 0;
    const auto pair_list = interleaving_list();
    for(const auto& [timeline_a, timeline_b] : pair_list) {
        Garage garage(1);
        std::string events;
        auto log = [&events](const std::string& e) { events += (events.empty() ? "" : ", ") + e; };
        Gate a("A", timeline_a, garage, atomic, log), b("B", timeline_b, garage, atomic, log);
        hwut::TriggerDispatcher({ &a, &b }).run();
        bool over = garage.occupied > garage.capacity;
        overbooked_n += over;
        char line[256];
        std::snprintf(line, sizeof(line), "    \"%s\"  \"%s\"  %-46s  %d %s", timeline_a.c_str(), timeline_b.c_str(),
                      events.c_str(), garage.occupied, over ? "!!" : "  ");
        std::printf("%s\n", rstrip(line).c_str());
    }
    std::printf("interleavings overbooking the garage ((overbooked: %d)) of %zu\n", overbooked_n, pair_list.size());
}

int main(int argc, char** argv)
/* RETURN: int, the exit status of the HwutRunner: 0 where the choice ran. */
{
    hwut::HwutRunner runner(argc, argv, "Demo: a garage's space counter -- a space, a stream and races, generated;", {
        { "space",       space },
        { "random",      random_stream },
        { "race-naive",  [] { race(false); } },
        { "race-atomic", [] { race(true); } },
    });
    return runner.run();
}
