/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * A TERMINAL FILE VIEWER -- the program 'screen.c' tests; no test itself.
 *
 *     viewer.exe <file>          (built with 'screen.exe' by the Makefile)
 *
 * Full screen, on the terminal's alternate screen: a title bar (reverse
 * video), as many lines of the file as fit, and a status line: the keys
 * flush left, the lines shown flush right. Keys: 'j' or down one line
 * further, 'k' or up one line back, 'q' quits.
 * _____________________________________________________________________________
 */
#define _DEFAULT_SOURCE
#include <libgen.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <termios.h>
#include <unistd.h>

#define LINE_MAX_N 1024

static void
draw(const char* name, char** line, int line_n, int top, int row_n, int column_n)
/* RETURN: nothing. Draws the whole screen with the file's line 'top' first. */
{
    int  body_n = row_n - 2, shown_n = line_n - top < body_n ? line_n - top : body_n, i;
    char where[64], title[512];
    const char* keys = "j k q";
    printf("\x1b[H\x1b[2J");
    snprintf(title, sizeof(title), " %-*s", column_n > 1 ? column_n - 1 : 1, name);
    if( column_n < (int)sizeof(title) ) title[column_n] = '\0';
    printf("\x1b[7m%s\x1b[0m\r\n", title);
    for(i = 0; i < shown_n; ++i) printf("%.*s\r\n", column_n, line[top + i]);
    for(i = shown_n; i < body_n; ++i) printf("\r\n");
    snprintf(where, sizeof(where), "lines %d-%d of %d", top + 1, top + shown_n, line_n);
    printf("\x1b[%d;1H%s%*s", row_n, keys, column_n - 1 - (int)strlen(keys), where);
    fflush(stdout);
}

int
main(int argc, char** argv)
/* RETURN: int, 0 once 'q' was pressed; 1, the file cannot be read. */
{
    static char    text[65536];
    char*          line[LINE_MAX_N];
    int            line_n = 0, top = 0, row_n = 24, column_n = 80, n;
    char           key[8];
    struct winsize size;
    struct termios saved, raw;
    FILE*          fh = argc > 1 ? fopen(argv[1], "r") : NULL;
    size_t         length;
    char*          at;
    if( ! fh ) { fprintf(stderr, "usage: viewer.exe <file>\n"); return 1; }
    length = fread(text, 1, sizeof(text) - 1, fh); text[length] = '\0'; fclose(fh);
    for(at = text; *at && line_n < LINE_MAX_N; ) {
        line[line_n++] = at;
        at += strcspn(at, "\n");
        if( *at ) *at++ = '\0';
    }
    if( ioctl(STDOUT_FILENO, TIOCGWINSZ, &size) == 0 ) { row_n = size.ws_row; column_n = size.ws_col; }
    tcgetattr(STDIN_FILENO, &saved);
    raw = saved; cfmakeraw(&raw);
    tcsetattr(STDIN_FILENO, TCSANOW, &raw);
    printf("\x1b[?1049h");
    for(;;) {
        draw(basename(argv[1]), line, line_n, top, row_n, column_n);
        n = (int)read(STDIN_FILENO, key, sizeof(key));
        if( n <= 0 || (n == 1 && key[0] == 'q') ) break;
        if( (n == 1 && key[0] == 'j') || (n == 3 && memcmp(key, "\x1b[B", 3) == 0) ) {
            top = top + 1 < line_n - (row_n - 2) ? top + 1 : line_n - (row_n - 2);
            if( top < 0 ) top = 0;
        }
        else if( (n == 1 && key[0] == 'k') || (n == 3 && memcmp(key, "\x1b[A", 3) == 0) )
            top = top > 0 ? top - 1 : 0;
    }
    printf("\x1b[?1049l");
    fflush(stdout);
    tcsetattr(STDIN_FILENO, TCSADRAIN, &saved);
    return 0;
}
