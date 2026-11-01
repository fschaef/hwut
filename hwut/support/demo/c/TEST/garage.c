/* @hwut {
 *     title    = "Demo: a garage's space counter -- a space, a stream and races, generated"
 *     build    { framework = "make", executable = "%.exe" }
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
 * hwut's helpers for writing tests, in C (hwut/support/test_writing/c):
 *
 * space        'garage-space.hocon' states the tested space -- capacities,
 *              cars arriving, cars leaving -- in hwut's HOCON, read by
 *              'hwut_hocon' ('Hocon_parse'). A reviewer edits the space
 *              without reading C. 'SpaceIterator' walks every combination:
 *              3 x 5 x 4 = 60 cases, yielded as indices into the dimensions'
 *              values. Each is printed as one cell of a matrix, and checked
 *              against the model: admitted = min(arriving, capacity), out =
 *              min(leaving, admitted).
 *
 * random       'DeterministicStream' seeded 4711 draws 1000 cars arriving and
 *              leaving at a garage of 5. The draw is the same on every
 *              machine and in every language hwut supports -- the stream is a
 *              linear congruential generator, not libc's 'rand' -- so the
 *              GOOD is exact (the Python demo's), and a failing run can be
 *              replayed by its seed.
 *
 * race-naive   two gates, one free space. A gate CHECKS whether a space is
 *              free, and later ADMITS its car. 'deterministic_timeline' runs
 *              the two gates as Triggers on timelines drawn as strings --
 *              '1 1 ' fires at tick 0 and tick 2 -- so every interleaving is
 *              played exactly, not hoped for with sleeps. 'SpaceIterator'
 *              generates all six interleavings of two two-step gates in four
 *              ticks. Where both gates check before either admits, both
 *              admit: the garage is overbooked. The law is 'overbooked > 0':
 *              the GOOD is the accepted violation report.
 *
 * race-atomic  the same six interleavings, the gate checking and admitting
 *              in ONE step under the counter's lock. 'overbooked == 0'.
 *
 * THE FRONT END is hwut's HwutRunner: the choice list in 'main' is the whole
 * command line, '--hwut-info' included. The header says 'interactive =
 * true': hwut starts the application ONCE and asks for the choices one after
 * another in that one process -- an accelerator only: a choice's output
 * equals what it prints when run alone (the C runner runs each choice in a
 * child of its own).
 * _____________________________________________________________________________
 */
#define _POSIX_C_SOURCE 200809L
#include <libgen.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "hwut_runner.h"
#include "hwut_hocon.h"
#include "space_iterator.h"
#include "deterministic_random.h"
#include "deterministic_timeline.h"

/* The unit under test: a counter of the spaces a garage has. */
typedef struct { int capacity, occupied; } Garage;

static void
Garage_init(Garage* self, int capacity)
/* RETURN: nothing; an empty garage of 'capacity' spaces. */
{ self->capacity = capacity; self->occupied = 0; }

static int
Garage_free(const Garage* self)
/* RETURN: int, the number of spaces free now -- negative where the garage
 *         is overbooked.                                                    */
{ return self->capacity - self->occupied; }

static int
Garage_arrive(Garage* self)
/* RETURN: 1, a car was admitted, if a space was free;
 *         0, else (the car is refused).                                     */
{
    if( Garage_free(self) <= 0 ) return 0;
    self->occupied += 1;
    return 1;
}

static int
Garage_leave(Garage* self)
/* RETURN: 1, a car drove out, if one stood inside;
 *         0, else.                                                          */
{
    if( self->occupied == 0 ) return 0;
    self->occupied -= 1;
    return 1;
}

/* _____________________________________________________________________________
 * space -- the tested space from HOCON, walked by SpaceIterator
 */
#define DIMENSION_MAX 3
#define VALUE_MAX     16

typedef struct {
    char      name[32];
    long long value[VALUE_MAX];
    size_t    value_n;
} Dimension;

static const char*
here(char* buffer, size_t size)
/* RETURN: const char*, 'buffer' holding the directory this executable stands
 *         in -- the test directory, where its data file stands too.        */
{
    char    path[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", path, sizeof(path) - 1);
    if( n < 0 ) { snprintf(buffer, size, "."); return buffer; }
    path[n] = '\0';
    snprintf(buffer, size, "%s", dirname(path));
    return buffer;
}

static size_t
read_space(const char* path, Dimension* dimension)
/* RETURN: size_t, the number of dimensions of the space in 'path', written
 *         into 'dimension' in the order written: name, values.
 *         Every fault the HOCON reader found is printed with '!!' first.   */
{
    static char     text[64][256];
    HoconSourceLine line[64];
    HoconFaultList  fault;
    HoconNode*      document;
    HoconEntry*     space;
    FILE*           fh = fopen(path, "r");
    size_t          line_n = 0, i, k, dimension_n = 0;
    char            said[1024];
    while( fh && line_n < 64 && fgets(text[line_n], sizeof(text[0]), fh) ) {
        text[line_n][strcspn(text[line_n], "\n")] = '\0';
        line[line_n].text = text[line_n]; line[line_n].line = (int)line_n + 1; line[line_n].column_offset = 0;
        ++line_n;
    }
    if( fh ) fclose(fh);
    HoconFaultList_init(&fault);
    document = Hocon_parse(line, line_n, "garage-space.hocon", &fault);
    for(i = 0; i < fault.n; ++i) printf("!! %s\n", HoconFault_to_string(&fault.fault[i], said, sizeof(said)));
    space = HoconNode_get(document, "space");
    for(i = 0; space && i < space->node->entry_n && dimension_n < DIMENSION_MAX; ++i, ++dimension_n) {
        const HoconEntry* entry = &space->node->entry[i];
        snprintf(dimension[i].name, sizeof(dimension[i].name), "%s", entry->key);
        dimension[i].value_n = 0;
        for(k = 0; k < entry->node->item_n && k < VALUE_MAX; ++k)
            dimension[i].value[dimension[i].value_n++] = entry->node->item[k]->value.i;
    }
    HoconNode_free(document);
    HoconFaultList_free(&fault);
    return dimension_n;
}

static void
space(void)
/* RETURN: nothing. Prints every case of the space as a matrix cell. */
{
    Dimension     d[DIMENSION_MAX];
    char          path[PATH_MAX], cell[VALUE_MAX][VALUE_MAX][VALUE_MAX][16], line[1024];
    size_t        size[DIMENSION_MAX], at[DIMENSION_MAX], i, k, l, n;
    SpaceIterator it;
    int           mismatch_n = 0, capacity, arriving, leaving, refused, admitted, inside, refused_x;
    Garage        garage;
    here(path, sizeof(path));
    strncat(path, "/garage-space.hocon", sizeof(path) - strlen(path) - 1);
    if( read_space(path, d) != 3 ) { printf("!! the space has no three dimensions\n"); return; }
    printf("space: ");
    for(i = 0; i < 3; ++i) {
        printf("%s%s [", i ? "  x  " : "", d[i].name);
        for(k = 0; k < d[i].value_n; ++k) printf("%s%lld", k ? ", " : "", d[i].value[k]);
        printf("]");
        size[i] = d[i].value_n;
    }
    printf("\ncell: cars inside / cars refused at the gate ('!!' differs from the model)\n");
    SpaceIterator_init(&it, size, 3);
    while( SpaceIterator_next(&it, at) ) {
        capacity = (int)d[0].value[at[0]]; arriving = (int)d[1].value[at[1]]; leaving = (int)d[2].value[at[2]];
        Garage_init(&garage, capacity);
        for(refused = 0, n = 0; n < (size_t)arriving; ++n) refused += ! Garage_arrive(&garage);
        for(n = 0; n < (size_t)leaving; ++n) Garage_leave(&garage);
        admitted  = arriving < capacity ? arriving : capacity;
        inside    = admitted - (leaving < admitted ? leaving : admitted);
        refused_x = arriving - admitted;
        mismatch_n += garage.occupied != inside || refused != refused_x;
        snprintf(cell[at[0]][at[1]][at[2]], sizeof(cell[0][0][0]), "%d/%d%s", garage.occupied, refused,
                 garage.occupied == inside && refused == refused_x ? "  " : "!!");
    }
    for(i = 0; i < size[0]; ++i) {
        n = (size_t)snprintf(line, sizeof(line), "capacity %lld   ", d[0].value[i]);
        for(l = 0; l < size[2]; ++l)
            n += (size_t)snprintf(line + n, sizeof(line) - n, "%sleave %-3lld", l ? "  " : "", d[2].value[l]);
        while( n && line[n - 1] == ' ' ) line[--n] = '\0';
        printf("%s\n", line);
        for(k = 0; k < size[1]; ++k) {
            n = (size_t)snprintf(line, sizeof(line), "  arrive %lld   ", d[1].value[k]);
            for(l = 0; l < size[2]; ++l)
                n += (size_t)snprintf(line + n, sizeof(line) - n, "%s%-9s", l ? "  " : "", cell[i][k][l]);
            while( n && line[n - 1] == ' ' ) line[--n] = '\0';
            printf("%s\n", line);
        }
    }
    printf("cases %d, differing from the model ((mismatches: %d))\n",
           (int)(size[0] * size[1] * size[2]), mismatch_n);
}

/* _____________________________________________________________________________
 * random -- a deterministic stream of arrivals and departures
 */
static void
random_stream(void)
/* RETURN: nothing. Prints the summary of 1000 drawn cars, model-checked. */
{
    DeterministicStream stream;
    Garage              garage;
    int                 model = 0, arrive_n = 0, refused_n = 0, leave_n = 0, empty_n = 0;
    int                 histogram[6] = { 0 }, mismatch_n = 0, i, n;
    char                strip[1001];
    DeterministicStream_init(&stream, 4711);
    Garage_init(&garage, 5);
    for(i = 0; i < 1000; ++i) {
        if( DeterministicStream_coin(&stream, 0.55) ) {
            arrive_n += 1;
            if( ! Garage_arrive(&garage) ) refused_n += 1;
            model = model + 1 < 5 ? model + 1 : 5;
            strip[i] = '+';
        } else {
            leave_n += 1;
            if( ! Garage_leave(&garage) ) empty_n += 1;
            model = model - 1 > 0 ? model - 1 : 0;
            strip[i] = '-';
        }
        mismatch_n += garage.occupied != model;
        histogram[garage.occupied] += 1;
    }
    strip[1000] = '\0';
    printf("seed 4711, garage of 5, 1000 cars drawn: '+' arrives, '-' leaves\n");
    printf("first 60: %.60s\n", strip);
    printf("arrivals %d, refused %d; departures %d, from an empty garage %d\n",
           arrive_n, refused_n, leave_n, empty_n);
    printf("cars inside after each event:\n");
    for(n = 0; n < 6; ++n) {
        printf("    %d  %4d  ", n, histogram[n]);
        for(i = 0; i < histogram[n] / 10; ++i) putchar('#');
        putchar('\n');
    }
    printf("steps differing from the model ((mismatches: %d))\n", mismatch_n);
}

/* _____________________________________________________________________________
 * race -- two gates on drawn timelines
 */
typedef struct { char text[512]; } EventLog;

static void
EventLog_add(EventLog* self, const char* name, const char* what)
/* RETURN: nothing; '<name> <what>' is the log's last event. */
{
    size_t n = strlen(self->text);
    snprintf(self->text + n, sizeof(self->text) - n, "%s%s %s", n ? ", " : "", name, what);
}

/* A gate on a timeline: its first tick checks, its second admits. */
typedef struct {
    Trigger   base;
    Garage*   garage;
    int       atomic_f;
    EventLog* log;
    int       step;
    int       saw_free_f;
} Gate;

static int
Gate_fire(Trigger* trigger, int pseudo_time)
/* RETURN: int, TIMELINE_OK -- the gate's next step performed at
 *         'pseudo_time'.                                                    */
{
    Gate* self = (Gate*)trigger;
    char  what[32];
    if( self->step == 0 && self->atomic_f ) {
        self->saw_free_f = Garage_arrive(self->garage);
        EventLog_add(self->log, trigger->name, self->saw_free_f ? "checks+admits" : "refuses");
    } else if( self->step == 0 ) {
        self->saw_free_f = Garage_free(self->garage) > 0;
        snprintf(what, sizeof(what), "sees %d free", Garage_free(self->garage));
        EventLog_add(self->log, trigger->name, what);
    } else if( self->atomic_f ) {
        EventLog_add(self->log, trigger->name, self->saw_free_f ? "opens" : "stays shut");
    } else if( self->saw_free_f ) {
        self->garage->occupied += 1;                        /* the naive admit */
        EventLog_add(self->log, trigger->name, "admits");
    } else {
        EventLog_add(self->log, trigger->name, "refuses");
    }
    self->step += 1;
    return TIMELINE_OK;
}

static const Trigger_Vtable Gate_vtable = { Gate_fire, NULL };

static void
Gate_init(Gate* self, const char* name, const char* timeline, Garage* garage, int atomic_f, EventLog* log)
/* RETURN: nothing; a gate before its first step. */
{
    Trigger_init(&self->base, &Gate_vtable, timeline, name);
    self->garage = garage; self->atomic_f = atomic_f; self->log = log;
    self->step = 0; self->saw_free_f = 0;
}

typedef struct { char a[5], b[5]; } Interleaving;

static size_t
interleaving_list(Interleaving* result)
/* RETURN: size_t, the number of pairs of timelines written into 'result':
 *         every pair in four ticks in which each of two gates fires twice,
 *         never at the same tick -- gate A's and gate B's.                  */
{
    static const size_t size[4] = { 4, 4, 4, 4 };
    SpaceIterator it;
    size_t        t[4], n = 0, k;
    SpaceIterator_init(&it, size, 4);
    while( SpaceIterator_next(&it, t) ) {
        if( ! (t[0] < t[1] && t[2] < t[3]) ) continue;
        if( t[0] == t[2] || t[0] == t[3] || t[1] == t[2] || t[1] == t[3] ) continue;
        for(k = 0; k < 4; ++k) {
            result[n].a[k] = (k == t[0] || k == t[1]) ? '1' : ' ';
            result[n].b[k] = (k == t[2] || k == t[3]) ? '1' : ' ';
        }
        result[n].a[4] = result[n].b[4] = '\0';
        ++n;
    }
    return n;
}

static void
race(int atomic_f)
/* RETURN: nothing. Plays every interleaving of two gates at one space. */
{
    Interleaving      pair[256];
    size_t            pair_n = interleaving_list(pair), i, n;
    int               overbooked_n = 0, overbooked_f;
    Garage            garage;
    EventLog          log;
    Gate              gate[2];
    Trigger*          trigger_list[2];
    TriggerDispatcher dispatcher;
    char              line[1024];
    printf("one free space, two gates, one car at each; timelines: a digit fires\n");
    printf("    gate A  gate B  what happens                                    inside\n");
    for(i = 0; i < pair_n; ++i) {
        Garage_init(&garage, 1);
        log.text[0] = '\0';
        Gate_init(&gate[0], "A", pair[i].a, &garage, atomic_f, &log);
        Gate_init(&gate[1], "B", pair[i].b, &garage, atomic_f, &log);
        trigger_list[0] = &gate[0].base; trigger_list[1] = &gate[1].base;
        TriggerDispatcher_init(&dispatcher, trigger_list, 2);
        TriggerDispatcher_run(&dispatcher);
        TriggerDispatcher_free(&dispatcher);
        overbooked_f  = garage.occupied > garage.capacity;
        overbooked_n += overbooked_f;
        n = (size_t)snprintf(line, sizeof(line), "    \"%s\"  \"%s\"  %-46s  %d %s",
                             pair[i].a, pair[i].b, log.text, garage.occupied, overbooked_f ? "!!" : "  ");
        while( n && line[n - 1] == ' ' ) line[--n] = '\0';
        printf("%s\n", line);
    }
    printf("interleavings overbooking the garage ((overbooked: %d)) of %d\n", overbooked_n, (int)pair_n);
}

static void
race_naive(void)
/* RETURN: nothing. The gates check, then admit, in two steps. */
{ race(0); }

static void
race_atomic(void)
/* RETURN: nothing. The gates check and admit in one step. */
{ race(1); }

int
main(int argc, char** argv)
/* RETURN: int, the exit status HwutRunner gives: 0 where the choice (or the
 *         interactive session) ran; else what the runner says it refused.  */
{
    static const HwutRunner_Choice choice_list[] = {
        { "space",       space },
        { "random",      random_stream },
        { "race-naive",  race_naive },
        { "race-atomic", race_atomic },
        { NULL,          NULL }
    };
    HwutRunner runner;
    HwutRunner_init(&runner, argc, argv,
                    "Demo: a garage's space counter -- a space, a stream and races, generated;",
                    choice_list);
    return HwutRunner_run(&runner);
}
