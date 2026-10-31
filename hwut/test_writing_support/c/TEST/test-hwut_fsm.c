/* @hwut {
 *     title      = "hwut_fsm: a state machine as the test's model of the system"
 *     build      { framework = "make", executable = "%.exe" }
 *     choices {
 *         syntax    { features = ["c-fsm"] }
 *         refused   { features = ["c-fsm"] }
 *         dfa       { features = ["c-fsm"] }
 *         nfa       { features = ["c-fsm"] }
 *         forbidden { features = ["c-fsm"] }
 *         model     { features = ["c-fsm"] }
 *         report    { features = ["c-fsm"] }
 *         masks     { features = ["c-fsm"] }
 *     }
 *     interactive = true
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The C port of 'python/TEST/test-hwut_fsm.py', choice for choice,
 *          held against its GOOD files by '.link'. What Python prints of its
 *          own values -- True, None, a tuple -- is printed so here, since the
 *          GOOD file is one. Where Python raises FsmError, the C call returns
 *          NULL or -1 and the error text is printed the same way.
 * _____________________________________________________________________________
 */
#include <stdio.h>
#include <string.h>
#include "hwut_runner.h"
#include "hwut_pytext.h"
#include "hwut_fsm.h"

static const char* PROTOCOL =
    "\n"
    "    initial:   idle\n"
    "    forbidden: crashed\n"
    "    final:     idle\n"
    "    idle    ---( request )---> waiting ---( grant )---> busy\n"
    "    busy    ---( release )---> idle\n"
    "    :       ---( fault )--->   crashed       # the state that began line 6\n"
    "    waiting ---( cancel )---> idle\n";

static char error[FSM_ERROR_MAX];

static void banner(const char* label) { printf("\n--- %s ---\n", label); }

static FsmMachine*
protocol(const char* name)
/* RETURN: FsmMachine, the PROTOCOL read -- it is a valid model.            */
{ return FsmMachine_from_string(PROTOCOL, 1, name, error, sizeof(error)); }

static const char*
join(char* buffer, size_t size, const char** list, size_t n)
/* RETURN: buffer, the texts of 'list' joined by ', '.                      */
{
    size_t i, k = 0; buffer[0] = '\0';
    for(i = 0; i < n; ++i) k += (size_t)snprintf(buffer + k, size - k, "%s%s", i ? ", " : "", list[i]);
    return buffer;
}

static const char*
allowed_text(FsmMachine* m, char* buffer, size_t size)
/* RETURN: buffer, the events allowed now, joined by ', '.                  */
{ const char* list[64]; return join(buffer, size, list, FsmMachine_allowed(m, list, 64)); }

static const char*
path_text(char* buffer, size_t size, FsmMachine* m, const char* state, const char* start, int masked_f)
/* RETURN: buffer, the path as Python prints the tuple 'path_to' returns --
 *         "('request', 'grant')", "('grant',)", "()" -- 'None' where none. */
{
    const char* path[64]; char quoted[256];
    int         n = FsmMachine_path_to(m, state, start, masked_f, path, 64), i;
    size_t      k;
    if( n < 0 ) { snprintf(buffer, size, "None"); return buffer; }
    k = (size_t)snprintf(buffer, size, "(");
    for(i = 0; i < n; ++i)
        k += (size_t)snprintf(buffer + k, size - k, "%s%s", i ? ", " : "", pytext_str_repr(quoted, sizeof(quoted), path[i]));
    snprintf(buffer + k, size - k, n == 1 ? ",)" : ")");
    return buffer;
}

/* ------------------------------------------------------------------ syntax */
static void
run_syntax(void)
{
    char        text[4096];
    FsmMachine* m = protocol("fsm");
    banner("the protocol, written back");
    printf("%s\n", FsmMachine_to_string(m, text, sizeof(text)));
    FsmMachine_free(m);
    banner("the author's form: 'state', a chain, ':', blanks around '-->'");
    m = FsmMachine_from_string("\n"
        "        state A ---( event )---> state B\n"
        "        :                ---(event2)---> state C ---(event) --> state D\n"
        "        state E          # no transition yet\n", 1, "fsm", error, sizeof(error));
    printf("%s\n", FsmMachine_to_string(m, text, sizeof(text)));
    FsmMachine_free(m);
}

static void
run_refused(void)
{
    static const char* text_list[] = {
        "A ---( x )---> B\n: ---( x )---> C",
        "A ---(  )---> B",
        ": ---( x )---> B",
        "A B ---( x )---> C",
        "initial: A, B\nA ---( x )---> B",
        "forbidden: Q\nA ---( x )---> B",
        "# nothing but a comment",
        NULL
    };
    const char* const* text;
    for(text = text_list; *text; ++text) {
        char        label[256]; size_t i, k = 0;
        FsmMachine* m;
        for(i = 0; (*text)[i]; ++i) {
            if( (*text)[i] == '\n' ) k += (size_t)snprintf(label + k, sizeof(label) - k, " | ");
            else                     label[k++] = (*text)[i];
        }
        label[k] = '\0';
        banner(label);
        if( (m = FsmMachine_from_string(*text, 1, "fsm", error, sizeof(error))) ) { printf("accepted\n"); FsmMachine_free(m); }
        else                                                                       printf("FsmError: %s\n", error);
    }
}

/* ------------------------------------------------------------------- runs */
static void
run_dfa(void)
{
    static const char* event[] = { "request", "release", "grant", "release", "jump", "request" };
    FsmMachine*          m = protocol("fsm");
    const FsmTraceEntry* trace;
    char                 number[16], text[1024];
    size_t               i, n;
    for(i = 0; i < 6; ++i) {
        int moved;
        snprintf(number, sizeof(number), "%zu", i + 1);
        moved = FsmMachine_fire(m, event[i], number);
        printf("    %-8s -> %-5s now %-8s allowed: %s\n", event[i], pytext_bool(moved),
               FsmMachine_state(m), allowed_text(m, text, sizeof(text)));
    }
    banner("questions where it stands");
    printf("can('grant')   %s\n", pytext_bool(FsmMachine_can(m, "grant")));
    printf("can('release') %s\n", pytext_bool(FsmMachine_can(m, "release")));
    printf("in_state('waiting') %s\n", pytext_bool(FsmMachine_in_state(m, "waiting")));
    printf("trace:");
    for(i = 0, n = FsmMachine_trace(m, &trace); i < n; ++i)
        printf(" %s:%s>%s", trace[i].where, trace[i].event, trace[i].target);
    printf("\n");
    FsmMachine_free(m);
}

static void
run_nfa(void)
{
    static const char* event[] = { "x", "z", "y" };
    FsmMachine* m = FsmMachine_from_string("\n"
        "        A ---( x )---> B ---( y )---> D\n"
        "        : ---( x )---> C ---( y )---> E\n"
        "        C ---( z )---> F\n", 0, "fsm", error, sizeof(error));
    const char* list[64]; const char* state;
    char        where[16], text[1024];
    size_t      i;
    for(i = 0; i < 3; ++i) {
        snprintf(where, sizeof(where), "t=%s", event[i]);
        FsmMachine_fire(m, event[i], where);
        printf("    after %s: %s\n", event[i], join(text, sizeof(text), list, FsmMachine_current(m, list, 64)));
    }
    banner("'state' asked of a set");
    FsmMachine_reset(m);
    FsmMachine_fire(m, "x", NULL);
    if( (state = FsmMachine_state(m)) ) printf("%s\n", state);
    else                               printf("FsmError: %s\n", m->error);
    FsmMachine_free(m);
}

static void
run_forbidden(void)
{
    static const char* event[] = { "request", "grant", "fault" };
    FsmMachine* m = protocol("fsm");
    char        number[16];
    size_t      i;
    for(i = 0; i < 3; ++i) {
        int moved;
        snprintf(number, sizeof(number), "%zu", i + 1);
        moved = FsmMachine_fire(m, event[i], number);
        printf("    %-8s -> %s\n", event[i], pytext_bool(moved));
    }
    printf("now in %s -- breaches: %d\n", FsmMachine_state(m), FsmMachine_breach_n(m));
    FsmMachine_free(m);
}

/* ------------------------------------------------------- the model alone */
static void
run_model(void)
{
    static const char* goal[] = { "busy", "crashed", "limbo", "idle" };
    char        text[4096], path[1024];
    FsmMachine* m;
    size_t      i;
    snprintf(text, sizeof(text), "%s\n    state limbo\n    limbo ---( kick )---> idle\n", PROTOCOL);
    m = FsmMachine_from_string(text, 1, "fsm", error, sizeof(error));
    printf("check: %d\n", FsmMachine_check(m, 1));
    banner("path_to");
    for(i = 0; i < 4; ++i) printf("    %-8s %s\n", goal[i], path_text(path, sizeof(path), m, goal[i], NULL, 1));
    FsmMachine_fire(m, "request", NULL);
    printf("    busy from now: %s\n", path_text(path, sizeof(path), m, "busy", "now", 1));
    printf("    state_reachable('idle', start='now'): %s\n", pytext_bool(FsmMachine_state_reachable(m, "idle", "now", 1)));
    FsmMachine_free(m);
}

static void
run_report(void)
{
    static const char* event[] = { "request", "grant", "release", "request", "grant" };
    FsmMachine* m = protocol("protocol");
    size_t      i;
    for(i = 0; i < 5; ++i) FsmMachine_fire(m, event[i], NULL);
    {   int breach_n = FsmMachine_report(m);
        printf("report returns %d\n", breach_n); }
    FsmMachine_free(m);
}

/* ------------------------------------------------------------------ masks */
static void
release_in_phase(void* context)
{ FsmMachine_fire((FsmMachine*)context, "release", "20"); }

static void
run_masks(void)
{
    FsmMachine* m = protocol("fsm");
    char        text[1024];
    int         fault;

    banner("'grant' disallowed in every state, since line 2");
    FsmMachine_disallow(m, "grant", NULL, "2");
    FsmMachine_fire(m, "request", "3");
    printf("    allowed now: %s -- can('grant'): ", allowed_text(m, text, sizeof(text)));
    printf("%s\n", pytext_bool(FsmMachine_can(m, "grant")));
    FsmMachine_fire(m, "grant", "4");
    printf("    path_to('busy'):               %s\n", path_text(text, sizeof(text), m, "busy", NULL, 1));
    printf("    path_to('busy', masked=False): %s\n", path_text(text, sizeof(text), m, "busy", NULL, 0));
    {   int n = FsmMachine_check(m, 1); printf("    check(): %d\n", n); }
    {   int n = FsmMachine_check(m, 0); printf("    check(masked=False): %d\n", n); }

    banner("allowed again; 'busy' forbidden while standing in it");
    FsmMachine_allow(m, "grant", NULL);
    FsmMachine_fire(m, "grant", "6");
    FsmMachine_forbid(m, "busy", "7");
    FsmMachine_fire(m, "release", "8");
    FsmMachine_fire(m, "request", "9");
    FsmMachine_fire(m, "grant", "10");

    banner("permitted: 'busy', and the model's own 'crashed'");
    FsmMachine_permit(m, "busy", "11");
    FsmMachine_permit(m, "crashed", "12");
    fault = FsmMachine_fire(m, "fault", "13");
    printf("    fault -> %s -- now in %s\n", pytext_bool(fault), FsmMachine_state(m));

    banner("a phase: 'release' disallowed in 'busy' for a block");
    FsmMachine_reset(m);
    FsmMachine_fire(m, "request", NULL); FsmMachine_fire(m, "grant", NULL);
    FsmMachine_disallowed(m, "release", "busy", "phase", release_in_phase, m);
    FsmMachine_fire(m, "release", "21");
    FsmMachine_disallow(m, "cancel", NULL, "22");
    FsmMachine_report(m);

    banner("refused: a word the model never names");
    if( FsmMachine_disallow(m, "jump", NULL, NULL) )     printf("FsmError: %s\n", m->error);
    if( FsmMachine_forbid(m, "limbo", NULL) )            printf("FsmError: %s\n", m->error);
    if( FsmMachine_allow(m, "grant", "nowhere") )        printf("FsmError: %s\n", m->error);
    FsmMachine_free(m);
}

int
main(int argc, char** argv)
{
    static const HwutRunner_Choice choice_list[] = {
        { "syntax", run_syntax }, { "refused", run_refused }, { "dfa", run_dfa }, { "nfa", run_nfa },
        { "forbidden", run_forbidden }, { "model", run_model }, { "report", run_report },
        { "masks", run_masks }, { NULL, NULL }
    };
    HwutRunner runner;
    HwutRunner_init(&runner, argc, argv, "hwut_fsm: a state machine as the test's model of the system",
                    choice_list);
    return HwutRunner_run(&runner);
}
