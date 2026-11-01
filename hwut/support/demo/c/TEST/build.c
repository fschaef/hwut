/* @hwut {
 *     title   = "Demo: a recursive build, serial and parallel -- one summary, by a pype system"
 *     build   { framework = "make", executable = "%.exe" }
 *     pype    = "build.pypes"
 *     same    = true
 *     choices = ["serial", "parallel"]
 *     features = ["pype-in-header", "pype-system", "same-nominal", "choices-as-list",
 *                 "pype-push-pop", "pype-entry-exit", "pype-import", "pype-repeat-group",
 *                 "pype-quantity", "pype-anchors-globs-flush"]
 *     tolerance { constraints = ["compile < 5 s", "breaches == 0"] }
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * SUBJECT  the log of a recursive build -- configure, then the directories
 *          'lib', 'app' and, inside 'app', 'app/plugins' -- and the summary
 *          a pype system makes of it.
 * REQUIREMENT  A parallel build builds what the serial build builds: the same
 *              sources, the same warnings, the same archives and the same
 *              program, linked from the same parts.
 *
 * The application only REPORTS the build as it happens, as 'make -w' would.
 * The header's 'pype = "build.pypes"' puts a SYSTEM of two pype scripts
 * between it and the comparison (hwut runs it; the application prints no
 * '<hwut-end>'):
 *
 *     build.pypes       --> normalise.pype         stdin to the first
 *                       normalise.pype --> build.pype
 *     normalise.pype    a parallel build tags each line with its job,
 *                       'job2: cc -c ...'; the tag goes, every other line
 *                       passes unchanged ('flush')
 *     build.pype        the summary, sorted -- see its own comments: modes
 *                       pushed on 'Entering directory' and popped on
 *                       'Leaving' (nested: 'app/plugins' inside 'app'),
 *                       '<entry>'/'<exit>' around each, a vocabulary
 *                       imported from 'compiler.pype', a repeat group over
 *                       the parts of a link, durations read as quantities
 *
 * 'same = true': BOTH CHOICES SHARE ONE GOOD, 'GOOD/build.c.txt' (a link to
 * the Python demo's). Serial or parallel, the summary must be the same --
 * that is the requirement, and the header says it once. 'choices' is a list:
 * no choice states anything of its own.
 *
 * The laws: the compile times sum to under 5 s ('((compile: ...))', in s,
 * whatever unit the log used), and nothing in the log broke the build's
 * grammar ('((breaches: 0))').
 *
 * A HEADER'S PYPE READS THE OUTPUT AFTER THE RUN: the whole stream at once.
 * Time as the pype sees it -- 'pype.time()', 'tick:' -- is no time of the
 * build here; a pype that judges time is fed live ('protocol.sh slow').
 * _____________________________________________________________________________
 */
#define _POSIX_C_SOURCE 200809L
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* What each directory does: its sources, warnings and products. */
typedef struct {
    const char* name;
    const char* source[4];          /* NULL-terminated                      */
    const char* warning_source;     /* the source that warns, or NULL       */
    const char* warning;
    const char* product;
} Directory;

static const Directory DIRECTORY_DB[] = {
    { "lib",         { "lib/str.c", "lib/num.c", "lib/map.c", NULL },
      "lib/num.c",   "lib/num.c:14:9: warning: unused variable 'n'",
      "ar rcs lib/libcore.a lib/str.o lib/num.o lib/map.o" },
    { "app/plugins", { "app/plugins/png.c", "app/plugins/svg.c", NULL },
      "app/plugins/svg.c", "app/plugins/svg.c:3:1: warning: implicit declaration of 'xml_open'",
      "ar rcs app/plugins/libplug.a app/plugins/png.o app/plugins/svg.o" },
    { "app",         { "app/main.c", "app/cli.c", NULL },
      NULL,          NULL,
      "ld -o app/demo app/main.o app/cli.o lib/libcore.a app/plugins/libplug.a" },
};

/* A BLOCK of lines, what one directory prints; grown as it is written. */
typedef struct { char** line; size_t n, capacity; } Block;

static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static uint64_t        random_state;

static double
uniform(double low, double high)
/* RETURN: double, drawn evenly from [low, high) (splitmix64, under 'lock'). */
{
    uint64_t z;
    pthread_mutex_lock(&lock);
    z = (random_state += 0x9E3779B97F4A7C15ULL);
    pthread_mutex_unlock(&lock);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return low + (high - low) * (double)((z ^ (z >> 31)) >> 11) / 9007199254740992.0;
}

static void
Block_add(Block* self, const char* text)
/* RETURN: nothing; a copy of 'text' is the block's last line. */
{
    if( self->n == self->capacity ) {
        self->capacity = self->capacity ? 2 * self->capacity : 16;
        self->line     = realloc(self->line, self->capacity * sizeof(char*));
    }
    self->line[self->n++] = strdup(text);
}

static void
Block_free(Block* self)
/* RETURN: nothing; the block's lines are released, the block is empty. */
{
    size_t i;
    for(i = 0; i < self->n; ++i) free(self->line[i]);
    free(self->line);
    self->line = NULL; self->n = self->capacity = 0;
}

static const Directory*
directory(const char* name)
/* RETURN: const Directory*, the entry of DIRECTORY_DB named 'name'; NULL
 *         where none is.                                                    */
{
    size_t i;
    for(i = 0; i < sizeof(DIRECTORY_DB) / sizeof(DIRECTORY_DB[0]); ++i)
        if( strcmp(DIRECTORY_DB[i].name, name) == 0 ) return &DIRECTORY_DB[i];
    return NULL;
}

static void
compile_lines(Block* block, const Directory* spec)
/* RETURN: nothing; 'block' holds what compiling 'spec's sources prints, each
 *         compiled in the time it takes.                                    */
{
    char            line[256], spent[32], object[128];
    double          took;
    struct timespec nap;
    int             i;
    for(i = 0; spec->source[i]; ++i) {
        took = uniform(0.04, 0.12);
        nap.tv_sec = 0; nap.tv_nsec = (long)(took * 1e9);
        nanosleep(&nap, NULL);
        if( took < 0.1 ) snprintf(spent, sizeof(spent), "%d ms", (int)(took * 1000));
        else             snprintf(spent, sizeof(spent), "%.2f s", took);
        snprintf(object, sizeof(object), "%.*s.o", (int)strlen(spec->source[i]) - 2, spec->source[i]);
        snprintf(line, sizeof(line), "cc -c %s -o %s (took %s)", spec->source[i], object, spent);
        Block_add(block, line);
        if( spec->warning_source && strcmp(spec->warning_source, spec->source[i]) == 0 )
            Block_add(block, spec->warning);
    }
}

static void
directory_block(Block* block, const char* name, int level, const char* inner)
/* RETURN: nothing; 'block' got the lines 'make -w' prints for 'name' at
 *         'level', the block of 'inner' (or NULL) nested before the product. */
{
    const Directory* spec = directory(name);
    char             line[256];
    snprintf(line, sizeof(line), "make[%d]: Entering directory '%s'", level, name);
    Block_add(block, line);
    compile_lines(block, spec);
    if( inner ) directory_block(block, inner, level + 1, NULL);
    Block_add(block, spec->product);
    snprintf(line, sizeof(line), "make[%d]: Leaving directory '%s'", level, name);
    Block_add(block, line);
}

static void
configure(void)
/* RETURN: nothing. Prints what 'configure' prints, and that make enters the
 *         top directory.                                                    */
{
    printf("configure: checking for cc... cc\n");
    printf("configure: checking for ar... ar\n");
    printf("make: Entering directory 'demo'\n");
    fflush(stdout);
}

static void
serial(void)
/* RETURN: nothing. Builds one directory after the other. */
{
    Block  block = { NULL, 0, 0 };
    size_t i;
    configure();
    directory_block(&block, "lib", 1, NULL);
    directory_block(&block, "app", 1, "app/plugins");
    for(i = 0; i < block.n; ++i) { printf("%s\n", block.line[i]); fflush(stdout); }
    Block_free(&block);
    printf("make: Leaving directory 'demo'\n");
}

typedef struct { int slot; const char* name; const char* inner; } Job;

static void*
job(void* argument)
/* RETURN: NULL. The job built its directory and printed its block whole,
 *         every line tagged 'job<slot>: ' ('make -O').                      */
{
    const Job* self  = (const Job*)argument;
    Block      block = { NULL, 0, 0 };
    size_t     i;
    directory_block(&block, self->name, 1, self->inner);
    pthread_mutex_lock(&lock);
    for(i = 0; i < block.n; ++i) { printf("job%d: %s\n", self->slot, block.line[i]); fflush(stdout); }
    pthread_mutex_unlock(&lock);
    Block_free(&block);
    return NULL;
}

static void
parallel(void)
/* RETURN: nothing. Builds 'lib' and 'app' at once; which job finishes first
 *         is the scheduler's.                                               */
{
    static const Job job_list[2] = { { 1, "lib", NULL }, { 2, "app", "app/plugins" } };
    pthread_t        thread[2];
    int              i;
    configure();
    for(i = 0; i < 2; ++i) pthread_create(&thread[i], NULL, job, (void*)&job_list[i]);
    for(i = 0; i < 2; ++i) pthread_join(thread[i], NULL);
    printf("make: Leaving directory 'demo'\n");
}

int
main(int argc, char** argv)
/* RETURN: int, 0 -- the build's log printed (no '<hwut-end>': the pype's);
 *         1, the choice is neither 'serial' nor 'parallel' (both named).    */
{
    struct timespec now;
    const char*     choice = argc > 1 ? argv[1] : "";
    clock_gettime(CLOCK_REALTIME, &now);
    random_state = (uint64_t)now.tv_sec * 1000000000ULL + (uint64_t)now.tv_nsec;
    if     ( strcmp(choice, "serial")   == 0 ) serial();
    else if( strcmp(choice, "parallel") == 0 ) parallel();
    else { printf("choices: serial, parallel\n"); return 1; }
    return 0;
}
