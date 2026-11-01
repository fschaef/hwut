/* @hwut {
 *     title      = "HOCON parser: subset (A), annotated tree"
 *     build      { framework = "make", executable = "%.exe" }
 *     choices {
 *         comments  { features = ["c-hocon"] }
 *         faults    { features = ["c-hocon"] }
 *         fuzz      { features = ["c-hocon"] }
 *         numbers   { features = ["c-hocon"] }
 *         oneline   { features = ["c-hocon"] }
 *         positions { features = ["c-hocon"] }
 *         quoting   { features = ["c-hocon"] }
 *         refused   { features = ["c-hocon"] }
 *         scalars   { features = ["c-hocon"] }
 *         structure { features = ["c-hocon"] }
 *         triple    { features = ["c-hocon"] }
 *         unclosed  { features = ["c-hocon"] }
 *     }
 *     interactive = true
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The C port of 'python/TEST/test-hwut_hocon.py', choice for choice,
 *          held against its GOOD files by '.link'. A value prints as Python's
 *          '%r (type)' prints it; the fuzz draws the same edits from the same
 *          seed ('deterministic_random') and bounds every parse by a timer.
 * _____________________________________________________________________________
 */
#define _POSIX_C_SOURCE 200809L
#include <setjmp.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include "hwut_runner.h"
#include "hwut_hocon.h"
#include "deterministic_random.h"

static void banner(const char* label) { printf("\n--- %s ---\n", label); }

typedef struct { char* copy; HoconSourceLine* line; size_t n; } Lines;

static Lines
lines(const char* text, int line_offset, int column_offset)
/* RETURN: Lines, 'text' split at every newline (an ending one gives a last,
 *         empty line, as Python's 'split'), offsets applied uniformly.    */
{
    Lines  result;
    size_t i, n = 1;
    char*  p;
    for(i = 0; text[i]; ++i) n += text[i] == '\n';
    result.copy = strdup(text);
    result.line = malloc(n * sizeof(HoconSourceLine));
    result.n    = 0;
    for(p = result.copy; ; ) {
        char* end = strchr(p, '\n');
        result.line[result.n].text          = p;
        result.line[result.n].line          = (int)result.n + 1 + line_offset;
        result.line[result.n].column_offset = column_offset;
        result.n += 1;
        if( ! end ) break;
        *end = '\0'; p = end + 1;
    }
    return result;
}

static void Lines_free(Lines* self) { free(self->copy); free(self->line); }

static void
show(const HoconNode* node, int indent)
/* RETURN: nothing; the annotated tree is printed, positions included.     */
{
    char   pad[256], at[32], repr[4096];
    size_t i;
    snprintf(pad, sizeof(pad), "%*s", 4 * indent, "");
    switch( node->kind ) {
    case HOCON_OBJECT:
        printf("%s{ at %s\n", pad, HoconPosition_to_string(node->position, at, sizeof(at)));
        for(i = 0; i < node->entry_n; ++i) {
            printf("%s  key '%s' at %s ->\n", pad, node->entry[i].key,
                   HoconPosition_to_string(node->entry[i].key_position, at, sizeof(at)));
            show(node->entry[i].node, indent + 1);
        }
        printf("%s}\n", pad);
        break;
    case HOCON_LIST:
        printf("%s[ at %s\n", pad, HoconPosition_to_string(node->position, at, sizeof(at)));
        for(i = 0; i < node->item_n; ++i) show(node->item[i], indent + 1);
        printf("%s]\n", pad);
        break;
    default:
        printf("%s%s (%s) at %s\n", pad, HoconNode_value_repr(node, repr, sizeof(repr)),
               HoconNode_type_name(node), HoconPosition_to_string(node->position, at, sizeof(at)));
    }
}

static void
run_offset(const char* label, const char* text, int line_offset, int column_offset)
/* RETURN: nothing; 'text' is parsed, its tree and faults printed.         */
{
    Lines          l = lines(text, line_offset, column_offset);
    HoconFaultList fault;
    HoconNode*     document;
    char           buffer[2048];
    size_t         i;
    banner(label);
    HoconFaultList_init(&fault);
    document = Hocon_parse(l.line, l.n, "f.hocon", &fault);
    show(document, 0);
    for(i = 0; i < fault.n; ++i) printf("FAULT %s\n", HoconFault_to_string(&fault.fault[i], buffer, sizeof(buffer)));
    HoconNode_free(document); HoconFaultList_free(&fault); Lines_free(&l);
}

static void run(const char* label, const char* text) { run_offset(label, text, 0, 0); }

static void
run_scalars(void)
{
    run("scalars",
        "a = bare\n"
        "b = \"quoted \\\"x\\\" and \\n\"\n"
        "c = 42\n"
        "d = -3.14\n"
        "e = 1e-6\n"
        "f = true\n"
        "g = no\n"
        "h = make %.exe\n"
        "i: \"colon-bound\"\n"
        "j = null\n"
        "k = nihil\n"
        "l =\n");
}

static void
run_numbers(void)
{
    run("decimal, with sign and exponent",
        "a = 42\n" "b = -0.12\n" "c = +7e212\n" "d = 6.02e23\n" "e = .5\n");
    run("the visual helper enters no value",
        "a = 1_000\n" "b = 7_000.5_5\n");
    run("hexadecimal, binary, octal",
        "a = 0xDEAD_BEEF\n" "b = 0b0111_11_01\n" "c = 0o3124\n" "d = 0XFF\n" "e = -0b1010\n");
    run("roman",
        "a = 0rIV\n" "b = 0rMCMLXXXIV\n" "c = -0rX\n");
    run("a sign standing apart from its digits",
        "a = - 0.12\n" "b = + 7\n" "c = - 0xFF\n" "d = - -1.5e3\n");
    run("what spells no number is a string, and carries quotes",
        "a = 1.2.3\n" "b = 0x\n" "c = 0b012\n" "d = 1__0\n" "e = 0rIIII\n" "f = 0rVX\n");
    run("no arithmetic: this language computes nothing",
        "a = 5 - 1\n");
}

static void
run_quoting(void)
{
    run("quoted: blanks, comment markers and binders are content",
        "a = \"make %.exe\"\n" "b = \"not # a comment\"\n" "c = \"x = y\"\n" "d = \"yes\"\n");
    run("unquoted: refused, and shown in the quotes it wants",
        "a = make\n" "b = strip.pype\n" "c = [one, two]\n" "d = 1\n");
}

static void
run_structure(void)
{
    run("nesting and key-brace",
        "outer {\n" "    inner = { deep = 1 }\n" "    braced { x = 2 }\n" "}\n");
    run("lists",
        "commas   = [one, two, three]\n"
        "newlines = [\n" "    1\n" "    2\n" "]\n"
        "objects  = [ { a = 1 }, { a = 2 } ]\n"
        "empty    = []\n");
}

static void
run_oneline(void)
{
    run("two entries, one line, no comma", "caps { timeout_sec = 30  network = false }\n");
    run("a quoted value with blanks, beside a following key", "a { build = \"make %.exe\"  timeout_sec = 5 }\n");
    run("three entries, one line", "x { a = 1  b = \"two\"  c = { d = 3 } }\n");
}

static void
run_comments(void)
{
    run("comments",
        "# whole line\n" "a = 1   # trailing\n" "// slashes too\n" "b = 2   // trailing slashes\n"
        "c = bare value # comment cut\n");
}

static void
run_refused(void)
{
    run("refused, each by name",
        "include \"other.conf\"\n" "a = ${outside.value}\n" "b += appended\n" "d = survives\n");
}

static void
run_triple(void)
{
    run("several lines: indentation and blank ends go",
        "doc = \"\"\"\n" "    First line.\n" "\n" "      indented more\n" "    last line\n" "    \"\"\"\n" "after = 1\n");
    run("on one line; beside another entry; in a list",
        "a = \"\"\"one line\"\"\"  b = 2\n" "c = [\"\"\"x\"\"\", \"y\"]\n");
    run("as written: a quote, a backslash-n, a comment marker",
        "a = \"\"\"says \"no\" \\n # not a comment\"\"\"\n");
    run("never closed: a fault, at its beginning",
        "a = 1\n" "b = \"\"\"open\n" "c = 2\n");
}

static void
run_faults(void)
{
    run("faults accumulate",
        "a = 1\n" "a = 2\n" "b = \"unterminated\n" "}\n" "c {\n" "    d = 3\n");
}

static void
run_unclosed(void)
{
    run("a list closed by the object's brace", "@hwut { title = \"B\" choices = [ }\n" "after = 1\n");
    run("a stray character in a list", "a = [1, ; 2]\n");
}

static void
run_positions(void)
{
    const char* text = "@hwut {\n" "    title = \"T\"\n" "}";
    run("plain: as its own file", text);
    run_offset("offset: same text, region begins at line 40, 3 columns stripped", text, 39, 3);
}

/* ------------------------------------------------------------------- fuzz */
static const char* FUZZ_SEED[] = {
    "@hwut {\n"
    "    title    = \"T\"\n"
    "    choices  = [\"a\", \"b\"]\n"
    "    tolerance { eq_pattern = [\"x.*\"] }\n"
    "    n        = -1.5e3\n"
    "    f        = true\n"
    "}\n",
    "hwut {\n"
    "    target     { clean = \"./c.sh\" }\n"
    "    dependency { \"a.py\" = [\"b.py one\"] }\n"
    "    ignore     = [\"x\"]   // comment\n"
    "    # comment\n"
    "}\n"
};
/* WHAT A TYPO IS MADE OF: the characters HOCON gives meaning to, a few that
 * it refuses by name, and some ordinary ones.                             */
static const char* FUZZ_ALPHABET[] = {
    "{", "}", "[", "]", "\"", ",", "=", ":", "#", "/", "\\", "$", " ", "\n", "\t", "-", "+", ".", "e", "E",
    "0", "a", "\"\"\"", "${", "//", "+="
};
#define FUZZ_ALPHABET_N (sizeof(FUZZ_ALPHABET) / sizeof(FUZZ_ALPHABET[0]))
#define FUZZ_INPUT_N    3000
#define FUZZ_BOUND_US   500000                  /* one parse takes well under a millisecond */

static char*
mutated(DeterministicStream* stream, const char* original)
/* RETURN: a new text, 'original' edited by one to four random insertions,
 *         deletions and duplications of a short stretch.                  */
{
    char*   text = strdup(original);
    int64_t edit, edit_n = DeterministicStream_next_int(stream, 1, 4);
    for(edit = 0; edit < edit_n; ++edit) {
        size_t n = strlen(text);
        size_t i = (size_t)DeterministicStream_next_int(stream, 0, (int64_t)n);
        char*  piece;  size_t piece_n;
        char*  next;
        switch( DeterministicStream_next_int(stream, 0, 2) ) {
        case 0:
            piece = (char*)FUZZ_ALPHABET[DeterministicStream_select(stream, FUZZ_ALPHABET_N)];
            piece_n = strlen(piece);
            break;
        case 1:
            if( i < n ) memmove(text + i, text + i + 1, n - i);
            continue;
        default: {
            size_t j = (size_t)DeterministicStream_next_int(stream, 0, (int64_t)n);
            piece   = text + j;
            piece_n = n - j < 5 ? n - j : 5;
        }
        }
        next = malloc(n + piece_n + 1);
        memcpy(next, text, i);
        memcpy(next + i, piece, piece_n);
        memcpy(next + i + piece_n, text + i, n - i + 1);
        free(text);
        text = next;
    }
    return text;
}

static sigjmp_buf hang_jump;
static void alarmed(int signal_id) { (void)signal_id; siglongjmp(hang_jump, 1); }

static void
set_timer(long microseconds)
{
    struct itimerval t;
    memset(&t, 0, sizeof(t));
    t.it_value.tv_sec  = microseconds / 1000000;
    t.it_value.tv_usec = microseconds % 1000000;
    setitimer(ITIMER_REAL, &t, NULL);
}

static void
run_fuzz(void)
{
    DeterministicStream stream;
    /* static: what the jump out of a hung parse must still see */
    static int          clean, with_faults, hang, exception;
    static char*        first_hang;
    static char*        text;
    int                 k;
    char                label[64];
    signal(SIGALRM, alarmed);
    DeterministicStream_init(&stream, 4711);
    for(k = 0; k < FUZZ_INPUT_N; ++k) {
        text = mutated(&stream, FUZZ_SEED[DeterministicStream_select(&stream, 2)]);
        Lines* volatile          l = malloc(sizeof(Lines));
        HoconFaultList* volatile fault = malloc(sizeof(HoconFaultList));
        *l = lines(text, 0, 0);
        HoconFaultList_init(fault);
        if( ! sigsetjmp(hang_jump, 1) ) {
            HoconNode* document;
            set_timer(FUZZ_BOUND_US);
            document = Hocon_parse(l->line, l->n, "f.hocon", fault);
            set_timer(0);
            if( fault->n ) ++with_faults; else ++clean;
            HoconNode_free(document);
        } else {                                  /* the tree of a hung parse is lost */
            ++hang;
            if( ! first_hang ) first_hang = strdup(text);
        }
        HoconFaultList_free(fault); Lines_free(l); free(fault); free(l); free(text);
    }
    snprintf(label, sizeof(label), "%d mutated headers", FUZZ_INPUT_N);
    banner(label);
    printf("    %-12s %d\n", "clean", clean);
    printf("    %-12s %d\n", "with faults", with_faults);
    printf("    %-12s %d\n", "hang", hang);
    printf("    %-12s %d\n", "exception", exception);       /* C raises nothing: always 0 */
    if( first_hang ) { printf("FIRST HANG:\n%s\n", first_hang); free(first_hang); }
}

int
main(int argc, char** argv)
{
    static const HwutRunner_Choice choice_list[] = {
        { "scalars", run_scalars }, { "numbers", run_numbers }, { "quoting", run_quoting },
        { "structure", run_structure }, { "oneline", run_oneline }, { "comments", run_comments },
        { "refused", run_refused }, { "triple", run_triple }, { "unclosed", run_unclosed },
        { "fuzz", run_fuzz }, { "faults", run_faults }, { "positions", run_positions },
        { NULL, NULL }
    };
    HwutRunner runner;
    HwutRunner_init(&runner, argc, argv, "HOCON parser: subset (A), annotated tree;", choice_list);
    return HwutRunner_run(&runner);
}
