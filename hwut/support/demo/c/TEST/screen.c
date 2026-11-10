/* @hwut {
 *     title     = "Demo: a terminal program's screen, as a person sees it"
 *     build     { framework = "make", target = "%.exe" }
 *     tolerance { regions    = false
 *                 comment    = false
 *                 whitespace = false }
 *     choices {
 *         open   { features = ["demo-c+cover-terminal-screen", "demo-c+cover-screen-as-seen"] }
 *         scroll { features = ["demo-c+cover-terminal-screen", "demo-c+cover-screen-as-seen"] }
 *     }
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * SUBJECT  the screen of 'viewer.exe' ('viewer.c'), a full-screen file
 *          viewer, run in a terminal of 9 rows and 40 columns and driven by
 *          its keys.
 * REQUIREMENT  The viewer shows a title bar in reverse video, the file's lines
 *              as they fit, and a status line -- the keys flush left, the lines
 *              shown flush right; 'j' and the down key go one line further,
 *              'k' one back.
 *
 * hwut_vterm's 'VtermTerminal' runs the viewer on a pseudo-terminal: the
 * viewer cannot tell it from a real one. The test PRESSES KEYS and is told
 * what CHANGED: three regions are declared -- title, body, status -- and after
 * every key, once the viewer has gone quiet, each region whose text changed
 * is printed. A redraw that changes nothing is not told: the title is told
 * once.
 *
 * THE SCREEN IS COMPARED AS A PERSON SEES IT -- three tolerances switched
 * off, in the header:
 *
 *     regions = false     the file shown is a GOOD file of hwut, with a
 *                         '##! potpourri' ... '####' block. On this screen
 *                         those are characters, not a region to open.
 *     comment = false     '## ...' lines are characters too, not notes.
 *     whitespace = false  the status line's two halves stand flush left and
 *                         flush right: every blank between them counts. A
 *                         half moved by one column is red. (A line's leading
 *                         and trailing blanks are stripped all the same.)
 *
 * libvterm must be installed ('apt install libvterm0') -- at run time only:
 * the C support loads it by 'dlopen' and needs no header. Where it is not,
 * the test prints why and probes nothing -- its output differs from GOOD and
 * the reason stands in the difference.
 *
 * CHOICES  open    the viewer opened, then quit.
 *          scroll  down, down, 'j', then 'k': three lines on, one back.
 * _____________________________________________________________________________
 */
#define _POSIX_C_SOURCE 200809L
#include <libgen.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include "hwut_vterm.h"

static const char* const SAMPLE =
    "## demo.py race -- three workers\n"
    "start\n"
    "##! potpourri\n"
    "worker B done: 5 jobs\n"
    "worker A done: 3 jobs\n"
    "worker C done: 2 jobs\n"
    "####\n"
    "all joined\n"
    "## the order between the markers is\n"
    "## free; the lines are not.\n";

static void
show(void* context, const char* name, char** line_list, size_t line_n)
/* RETURN: nothing. Prints one region that changed, its rows as they stand
 *         on the screen, from the first column.                             */
{
    size_t i;
    (void)context;
    printf("-- %s\n", name);
    for(i = 0; i < line_n; ++i) printf("%s\n", line_list[i]);
}

static int
view(const char* const* key_list)
/* RETURN: int, 0 -- the viewer ran on the sample, 'key_list' was pressed,
 *         the viewer quit, and what changed after each step was printed;
 *         1, the terminal could not be had (libvterm missing): why, printed. */
{
    char           here[PATH_MAX], path[PATH_MAX + 16], viewer[PATH_MAX + 16], attribute[128];
    ssize_t        n = readlink("/proc/self/exe", here, sizeof(here) - 1);
    VtermError     error;
    VtermTerminal* terminal;
    VtermCell      cell;
    FILE*          fh;
    int            status = -1;
    if( n < 0 ) n = (ssize_t)strlen(strcpy(here, "./x"));
    here[n] = '\0';
    dirname(here);
    snprintf(path,   sizeof(path),   "%s/TMP", here);
    mkdir(path, 0777);
    snprintf(path,   sizeof(path),   "%s/TMP/race.txt", here);
    snprintf(viewer, sizeof(viewer), "%s/viewer.exe", here);
    if( (fh = fopen(path, "w")) ) { fputs(SAMPLE, fh); fclose(fh); }
    {
        char* const argv[] = { viewer, path, NULL };
        if( ! (terminal = VtermTerminal_new(9, 40, 0.1, &error)) ) {
            printf("%s\n", error.message);
            return 1;
        }
        VtermTerminal_region(terminal, "title",  0, 1, 0, -1);
        VtermTerminal_region(terminal, "body",   1, 7, 0, -1);
        VtermTerminal_region(terminal, "status", -1, 1, 0, -1);
        VtermTerminal_on_change(terminal, show, NULL);
        printf("> viewer.exe race.txt\n");
        fflush(stdout);
        VtermTerminal_run(terminal, argv, NULL, 10.0);
        VtermScreen_cell(&terminal->base, 0, 1, &cell);
        VtermCell_attribute_text(&cell, attribute, sizeof(attribute));
        printf("title bar: %s\n", attribute[0] ? attribute : "plain");
        for(; *key_list; ++key_list) {
            printf("> %s\n", *key_list);
            if( strlen(*key_list) == 1 ) VtermTerminal_send(terminal, *key_list, 1.0);
            else                         VtermTerminal_press(terminal, *key_list, NULL, 1.0);
        }
        VtermTerminal_send(terminal, "q", 1.0);
        VtermTerminal_wait(terminal, 10.0, &status);
        printf("> q -- exit status %d\n", status);
        VtermTerminal_free(terminal);
    }
    return 0;
}

int
main(int argc, char** argv)
/* RETURN: int, 0 -- the choice ran and '<hwut-end>' closed its output;
 *         1, the choice is neither 'open' nor 'scroll' (both named), or the
 *         terminal could not be had.                                       */
{
    static const char* const OPEN[]   = { NULL };
    static const char* const SCROLL[] = { "down", "down", "j", "k", NULL };
    const char*              choice   = argc > 1 ? argv[1] : "";
    const char* const*       key_list;
    if     ( strcmp(choice, "open")   == 0 ) key_list = OPEN;
    else if( strcmp(choice, "scroll") == 0 ) key_list = SCROLL;
    else { printf("choices: open, scroll\n"); return 1; }
    fflush(stdout);
    if( view(key_list) != 0 ) return 1;
    printf("<hwut-end>\n");
    return 0;
}
