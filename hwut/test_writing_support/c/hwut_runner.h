/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: FRONT END OF A HWUT TEST APPLICATION IN C -- the port of
 *          'python/hwut_runner.py': the same modes, the same words.
 *
 *     app --hwut-info      the info block; exit 0.
 *     app <choice>         one choice; test output on stdout and stderr,
 *                          '<hwut-end>' after it. '-' runs a choice-less test.
 *     app --interactive    choices started over stdin, output into two named
 *                          sink files per choice, 'done' on the original stdout.
 *     app                  the choice-less test; where the application has
 *                          choices, refused, naming them.
 *
 * USAGE:
 *
 *     static void run_plain(void)  { ... }
 *     static void run_tricky(void) { ... }
 *
 *     int main(int argc, char** argv)
 *     {
 *         static const HwutRunner_Choice choice_list[] = {
 *             { "plain", run_plain }, { "tricky", run_tricky }, { NULL, NULL }
 *         };
 *         HwutRunner runner;
 *         HwutRunner_init(&runner, argc, argv, "What this tests", choice_list);
 *         return HwutRunner_run(&runner);
 *     }
 *
 * A choice-less test names its one function "-". After 'HwutRunner_init' and
 * before 'HwutRunner_run' a test may set 'happy' (NULL-terminated patterns),
 * 'same_f' and 'parallel_f' (interactive: choices run concurrently).
 *
 * THE INTERACTIVE PROTOCOL is Python's, line for line:
 *     DOWN  run <choice> <sink-out> <sink-err> | info | quit | q | exit
 *     UP    done <choice> <status> | fail <choice> <reason> | info: <line> | bye
 * EVERY CHOICE RUNS IN A CHILD PROCESS of its own: a choice that calls
 * 'exit' or crashes ends that choice, not the session -- what Python gets by
 * catching SystemExit -- and no choice inherits another's state.
 *
 * NAMING (all C ports): a class is a struct; its methods are functions
 * '<Class>_<method>(<Class>* self, ...)'.
 * _____________________________________________________________________________
 */
#ifndef HWUT_RUNNER_H
#define HWUT_RUNNER_H

typedef void (*HwutRunner_Function)(void);

typedef struct {
    const char*          name;        /* "-" for the choice-less test */
    HwutRunner_Function  function;
} HwutRunner_Choice;

#define HWUT_RUNNER_CHOICE_MAX  256

typedef struct {
    int                       argc;
    char**                    argv;
    const char*               title;
    const HwutRunner_Choice*  choice_list;
    int                       choice_n;
    const char*               sorted[HWUT_RUNNER_CHOICE_MAX];
    const char* const*        happy;      /* NULL-terminated, or NULL */
    int                       same_f;
    int                       parallel_f;
    /* interactive mode */
    int                       control_fd;
    int                       pending_pid[HWUT_RUNNER_CHOICE_MAX];
    char                      pending_token[HWUT_RUNNER_CHOICE_MAX][64];
    int                       pending_n;
} HwutRunner;

void HwutRunner_init(HwutRunner* self, int argc, char** argv, const char* title,
                     const HwutRunner_Choice* choice_list);
int  HwutRunner_run(HwutRunner* self);

int         HwutRunner_levenshtein_distance(const char* a, const char* b);
const char* HwutRunner_levenshtein_best_match(const char* needle, const char* const* haystack, int n);

#endif
