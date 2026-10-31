/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The front end of a HWUT test application -- see 'hwut_runner.h'.
 * _____________________________________________________________________________
 */
#define _POSIX_C_SOURCE 200809L
#include "hwut_runner.h"

#include <ctype.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

static const char* NONE = "-";

static int
_compare_text(const void* a, const void* b)
{ return strcmp(*(const char* const*)a, *(const char* const*)b); }

void
HwutRunner_init(HwutRunner* self, int argc, char** argv, const char* title,
                const HwutRunner_Choice* choice_list)
/* RETURN: nothing; 'self' is ready for 'HwutRunner_run'.                   */
{
    int i;
    memset(self, 0, sizeof(*self));
    self->argc        = argc;
    self->argv        = argv;
    self->title       = title;
    self->choice_list = choice_list;
    for(i = 0; choice_list[i].name != NULL && i < HWUT_RUNNER_CHOICE_MAX; ++i)
        self->sorted[i] = choice_list[i].name;
    self->choice_n = i;
    qsort(self->sorted, (size_t)self->choice_n, sizeof(self->sorted[0]), _compare_text);
    self->control_fd = -1;
}

static int
_none_f(HwutRunner* self)
/* RETURN: 1 where the application is choice-less ('-' its one choice).     */
{ return self->choice_n == 1 && strcmp(self->choice_list[0].name, NONE) == 0; }

static HwutRunner_Function
_function_of(HwutRunner* self, const char* name)
/* RETURN: the function of the choice 'name'; NULL where none is.           */
{
    int i;
    for(i = 0; i < self->choice_n; ++i)
        if( strcmp(self->choice_list[i].name, name) == 0 ) return self->choice_list[i].function;
    return NULL;
}

static void
_info_lines(HwutRunner* self, void (*put)(HwutRunner*, const char*))
/* RETURN: nothing; every line of the info block went through 'put'.        */
{
    char line[4096];
    int  i, k;
    size_t n = strlen(self->title);
    snprintf(line, sizeof(line), "%s%s", self->title, (n && self->title[n - 1] == ';') ? "" : ";");
    put(self, line);
    if( ! _none_f(self) ) {
        k = snprintf(line, sizeof(line), "CHOICES: ");
        for(i = 0; i < self->choice_n; ++i)
            k += snprintf(line + k, sizeof(line) - (size_t)k, "%s%s", i ? ", " : "", self->sorted[i]);
        snprintf(line + k, sizeof(line) - (size_t)k, ";");
        put(self, line);
    }
    for(i = 0; self->happy && self->happy[i]; ++i) {
        snprintf(line, sizeof(line), "HAPPY: %s;", self->happy[i]);
        put(self, line);
    }
    if( self->same_f ) put(self, "SAME;");
    put(self, "INTERACTIVE;");
}

static void _put_stdout(HwutRunner* self, const char* line) { (void)self; printf("%s\n", line); }

static void
_choice_list_text(HwutRunner* self, char* out, size_t size)
{
    int i, k = 0;
    out[0] = '\0';
    for(i = 0; i < self->choice_n; ++i)
        k += snprintf(out + k, size - (size_t)k, "%s%s", i ? ", " : "", self->sorted[i]);
}

static int
_run_one(HwutRunner* self, HwutRunner_Function function)
/* RETURN: 0; the choice ran, then '<hwut-end>' (R-70).                     */
{
    (void)self;
    function();
    printf("<hwut-end>\n");
    fflush(stdout);
    return 0;
}

/* -------------------------------------------------------- interactive mode */
static void
_up(HwutRunner* self, const char* message)
/* RETURN: nothing; 'message' and a newline are written on the UP channel.  */
{
    size_t n = strlen(message);
    if( write(self->control_fd, message, n) < 0 || write(self->control_fd, "\n", 1) < 0 ) {}
}

static void _put_up_info(HwutRunner* self, const char* line)
{ char text[4200]; snprintf(text, sizeof(text), "info: %s", line); _up(self, text); }

static int
_exit_code_of(int status)
/* RETURN: the exit status a child ended with; minus the signal that ended it. */
{
    if( WIFEXITED(status) )   return WEXITSTATUS(status);
    if( WIFSIGNALED(status) ) return -WTERMSIG(status);
    return 1;
}

static void
_reap(HwutRunner* self, int block_f)
/* RETURN: nothing; every child that has ended is reported 'done'; with
 *         'block_f' it waits until none is left.                           */
{
    char text[128];
    int  status, i, pid;
    while( self->pending_n > 0 ) {
        pid = waitpid(-1, &status, block_f ? 0 : WNOHANG);
        if( pid <= 0 ) return;
        for(i = 0; i < self->pending_n; ++i) {
            if( self->pending_pid[i] != pid ) continue;
            snprintf(text, sizeof(text), "done %s %d", self->pending_token[i], _exit_code_of(status));
            _up(self, text);
            self->pending_pid[i] = self->pending_pid[self->pending_n - 1];
            memcpy(self->pending_token[i], self->pending_token[self->pending_n - 1], 64);
            self->pending_n -= 1;
            break;
        }
    }
}

static int
_run_into_sinks(HwutRunner* self, HwutRunner_Function function, const char* sink_out,
                const char* sink_err, const char* token)
/* RETURN: the child's exit status where the choice ran to its end in this
 *         call (sequential); 0 where it runs on (parallel, reported later);
 *         1 where no child could be made.                                  */
{
    int pid, status;
    fflush(stdout); fflush(stderr);
    pid = fork();
    if( pid < 0 ) return 1;
    if( pid == 0 ) {
        int out = open(sink_out, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        int err = open(sink_err, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if( out < 0 || err < 0 ) _exit(1);
        dup2(out, 1); dup2(err, 2); close(out); close(err);
        close(self->control_fd);
        function();
        if( ! getenv("HWUT_NO_TERMINAL") ) printf("<hwut-end>\n");
        fflush(stdout); fflush(stderr);
        _exit(0);
    }
    if( self->parallel_f && self->pending_n < HWUT_RUNNER_CHOICE_MAX ) {
        self->pending_pid[self->pending_n] = pid;
        snprintf(self->pending_token[self->pending_n], 64, "%s", token);
        self->pending_n += 1;
        return -1000;                           /* reported when reaped */
    }
    while( waitpid(pid, &status, 0) < 0 ) {}
    return _exit_code_of(status);
}

static int
_find_choice(HwutRunner* self, const char* token, HwutRunner_Function* function)
/* RETURN: 1, the token names a choice -- by name, by its index into the
 *         sorted list, or '-' for the choice-less test; 0, else.           */
{
    const char* p;
    if( (*function = _function_of(self, token)) != NULL ) return 1;
    for(p = token; *p && isdigit((unsigned char)*p); ++p) {}
    if( *token && ! *p ) {
        int i = atoi(token);
        if( i < self->choice_n ) { *function = _function_of(self, self->sorted[i]); return 1; }
    }
    return 0;
}

static int
_interprete(HwutRunner* self, char* line)
/* RETURN: 1, the session goes on; 0, it ends.                              */
{
    char  text[512];
    char* field[5];
    int   n = 0;
    char* save = NULL;
    char* word = strtok_r(line, " \t", &save);
    while( word && n < 5 ) { field[n++] = word; word = strtok_r(NULL, " \t", &save); }
    if( word ) n = 5;                                   /* too many: bad */
    if( n == 1 && (! strcmp(field[0], "quit") || ! strcmp(field[0], "q") || ! strcmp(field[0], "exit")) )
        return 0;
    if( n == 1 && ! strcmp(field[0], "info") ) {
        _info_lines(self, _put_up_info);
        _up(self, "done - 0");
        return 1;
    }
    if( n == 4 && ! strcmp(field[0], "run") ) {
        HwutRunner_Function function;
        if( ! _find_choice(self, field[1], &function) ) {
            snprintf(text, sizeof(text), "fail %s unknown-choice", field[1]);
            _up(self, text);
        } else {
            int status = _run_into_sinks(self, function, field[2], field[3], field[1]);
            if( status != -1000 ) {
                snprintf(text, sizeof(text), "done %s %d", field[1], status);
                _up(self, text);
            }
        }
        return 1;
    }
    _up(self, "fail - bad-command");
    return 1;
}

static int
_mode_interactive(HwutRunner* self)
/* RETURN: 0, once the session ended ('quit' or end of input). The original
 *         stdout is the UP channel; fd 1 and fd 2 point at a stray sink.   */
{
    char  path[] = "/tmp/hwut_stray_XXXXXX";
    char* line   = NULL;
    size_t capacity = 0;
    int   stray;
    fflush(stdout); fflush(stderr);
    self->control_fd = dup(1);
    stray = mkstemp(path);
    if( stray >= 0 ) { dup2(stray, 1); dup2(stray, 2); close(stray); }
    while( 1 ) {
        ssize_t got;
        _reap(self, 0);
        got = getline(&line, &capacity, stdin);
        if( got < 0 ) break;
        while( got > 0 && isspace((unsigned char)line[got - 1]) ) line[--got] = '\0';
        if( got == 0 ) continue;
        if( ! _interprete(self, line) ) break;
    }
    free(line);
    _reap(self, 1);
    _up(self, "bye");
    return 0;
}

/* ------------------------------------------------------------ the dispatch */
int
HwutRunner_run(HwutRunner* self)
/* RETURN: the exit status of the mode the command line selects (see the
 *         header); a refusal exits 1.                                      */
{
    const char* word = self->argc > 1 ? self->argv[1] : NULL;
    char        list[4096];
    HwutRunner_Function function;

    if( word && (! strcmp(word, "-h") || ! strcmp(word, "--hi") || ! strcmp(word, "--hwut-info")
                 || ! strcmp(word, "--sos") || ! strcmp(word, "--wtf")) ) {
        _info_lines(self, _put_stdout);
        return 0;
    }
    if( word && ! strcmp(word, "--interactive") ) return _mode_interactive(self);
    _choice_list_text(self, list, sizeof(list));
    if( ! word ) {
        if( _none_f(self) ) return _run_one(self, self->choice_list[0].function);
        printf("error: a choice is required: %s -- name one, or let 'hwut.play' ask.\n", list);
        return 1;
    }
    if( (function = _function_of(self, word)) != NULL ) return _run_one(self, function);
    if( _none_f(self) ) {
        printf("error: '%s': this application has no choices -- call it without one.\n", word);
        return 1;
    }
    printf("error: choice '%s' not available.\n", word);
    printf("error: available: %s.\n", list);
    {
        const char* best = HwutRunner_levenshtein_best_match(word, self->sorted, self->choice_n);
        if( best ) printf("error: did you mean '%s'?\n", best);
    }
    return 1;
}

int
HwutRunner_levenshtein_distance(const char* a, const char* b)
/* RETURN: the Levenshtein distance between 'a' and 'b', >= 0.              */
{
    int  la = (int)strlen(a), lb = (int)strlen(b), i, j, result;
    int* prev; int* cur;
    if( ! strcmp(a, b) ) return 0;
    if( ! la ) return lb;
    if( ! lb ) return la;
    if( la < lb ) { const char* t = a; a = b; b = t; i = la; la = lb; lb = i; }
    prev = malloc(sizeof(int) * (size_t)(lb + 1));
    cur  = malloc(sizeof(int) * (size_t)(lb + 1));
    for(j = 0; j <= lb; ++j) prev[j] = j;
    for(i = 1; i <= la; ++i) {
        cur[0] = i;
        for(j = 1; j <= lb; ++j) {
            int ins = cur[j - 1] + 1, del = prev[j] + 1, sub = prev[j - 1] + (a[i - 1] != b[j - 1]);
            int m = ins < del ? ins : del;
            cur[j] = m < sub ? m : sub;
        }
        memcpy(prev, cur, sizeof(int) * (size_t)(lb + 1));
    }
    result = prev[lb];
    free(prev); free(cur);
    return result;
}

const char*
HwutRunner_levenshtein_best_match(const char* needle, const char* const* haystack, int n)
/* RETURN: the element of 'haystack' least distant from 'needle'; NULL where
 *         'needle' is NULL or 'haystack' is empty.                         */
{
    const char* best = NULL;
    int         best_d = -1, i;
    if( ! needle || n == 0 ) return NULL;
    for(i = 0; i < n; ++i) if( ! strcmp(haystack[i], needle) ) return needle;
    for(i = 0; i < n; ++i) {
        int d = HwutRunner_levenshtein_distance(needle, haystack[i]);
        if( best_d < 0 || d < best_d ) { best_d = d; best = haystack[i]; }
    }
    return best;
}
