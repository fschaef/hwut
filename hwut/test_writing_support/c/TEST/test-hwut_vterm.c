/* @hwut {
 *     title      = "A terminal's screen read by a test: libvterm through dlopen."
 *     build      { framework = "make", executable = "%.exe" }
 *     choices {
 *         attributes { features = ["c-vterm"] }
 *         colours    { features = ["c-vterm"] }
 *         events     { features = ["c-vterm"] }
 *         keys       { features = ["c-vterm"] }
 *         missing    { features = ["c-vterm"] }
 *         regions    { features = ["c-vterm"] }
 *         screen     { features = ["c-vterm"] }
 *         text       { features = ["c-vterm"] }
 *         unnoticed  { features = ["c-vterm"] }
 *     }
 *     interactive = true
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The C port of 'python/TEST/test-hwut_vterm.py', choice for choice,
 *          held against its GOOD files by '.link'. WANTS libvterm -- found at
 *          run time, no header needed to build. The two APPLICATIONS a
 *          Terminal runs here are the Python test's, unchanged: they are the
 *          system under test, and what they print is in the shared GOOD
 *          files.
 * _____________________________________________________________________________
 */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "hwut_runner.h"
#include "hwut_pytext.h"
#include "hwut_vterm.h"

#define ESC "\x1b"

static VtermError error;

static void
padded(const char* text, int width)
/* RETURN: nothing; 'text' is printed, filled with blanks to 'width'
 *         CHARACTERS -- as Python's '%-6s' counts, not bytes.            */
{
    int         n = 0;
    const char* p;
    for(p = text; *p; ++p) n += (*p & 0xC0) != 0x80;
    printf("%s%*s", text, width > n ? width - n : 0, "");
}

static void
shown(VtermScreen* screen)
/* RETURN: nothing; every row that holds something, framed, then the cursor. */
{
    char line[4096];
    int  row, column;
    for(row = 0; row < screen->row_n; ++row)
        if( *VtermScreen_line(screen, row, line, sizeof(line)) ) printf("    %d |%s|\n", row, line);
    VtermScreen_cursor(screen, &row, &column);
    printf("    cursor (%d, %d)\n", row, column);
}

static int
missing(void* object)
/* RETURN: 1, and the one line said, where the library was not found; 0. */
{
    if( object ) return 0;
    printf("NOT PROBED: %s\n", error.message);
    return 1;
}

static void
feed(VtermScreen* screen, const char* text)
{ VtermScreen_feed(screen, text, strlen(text)); }

static const char*
lines_repr(char* buffer, size_t size, char** line_list, size_t line_n)
/* RETURN: buffer, the lines as Python prints a list of str.               */
{
    char   quoted[1024];
    size_t i, k = (size_t)snprintf(buffer, size, "[");
    for(i = 0; i < line_n; ++i)
        k += (size_t)snprintf(buffer + k, size - k, "%s%s", i ? ", " : "", pytext_str_repr(quoted, sizeof(quoted), line_list[i]));
    snprintf(buffer + k, size - k, "]");
    return buffer;
}

/* ----------------------------------------------------------------- Screen */
static void
run_text(void)
{
    VtermScreen* s;
    VtermCell    cell;
    char         quoted[64];
    int          column;
    if( missing(s = VtermScreen_new(4, 12, &error)) ) return;
    printf("-- plain, then carriage return and line feed\n");
    feed(s, "hello\r\nworld");
    shown(s); VtermScreen_free(s);

    s = VtermScreen_new(4, 12, &error);
    printf("-- UTF-8: two bytes, one cell; a wide character, two\n");
    feed(s, "\xc3\xa4\xe6\x97\xa5x");                     /* 'ä日x' */
    shown(s);
    for(column = 0; column < 4; ++column) {
        VtermScreen_cell(s, 0, column, &cell);
        printf("    column %d: ", column);
        padded(pytext_str_repr(quoted, sizeof(quoted), cell.text), 6);
        printf(" width %d\n", cell.width);
    }
    VtermScreen_free(s);

    s = VtermScreen_new(3, 5, &error);
    printf("-- seven characters on five columns: the line wraps\n");
    feed(s, "abcdefg");
    shown(s); VtermScreen_free(s);

    s = VtermScreen_new(2, 4, &error);
    printf("-- a str is sent as UTF-8; the bytes taken are counted\n");
    printf("    taken: %zu\n", VtermScreen_feed(s, "a\xc3\xa4", 3));
    printf("-- a place off the screen\n");
    if( VtermScreen_cell(s, 2, 0, &cell) ) printf("    %s: %s\n", s->error.kind, s->error.message);
    VtermScreen_free(s);
}

static void
run_screen(void)
{
    VtermScreen* s;
    if( missing(s = VtermScreen_new(5, 20, &error)) ) return;
    printf("-- three lines, then '<esc>[2;4H' (it counts from 1) and 'X'\n");
    feed(s, "first line\r\nsecond line\r\nthird line");
    feed(s, ESC "[2;4HX");
    shown(s);
    printf("-- erase to the end of that line\n");
    feed(s, ESC "[K");
    shown(s);
    printf("-- clear the screen, home, one word\n");
    feed(s, ESC "[2J" ESC "[Hclean");
    shown(s);
    VtermScreen_free(s);
}

static void
run_attributes(void)
{
    VtermScreen* s;
    VtermCell    cell;
    char         text[64], said[256], quoted[64];
    int          i;
    if( missing(s = VtermScreen_new(3, 20, &error)) ) return;
    for(i = 0; i < 7; ++i) {
        snprintf(text, sizeof(text), ESC "[%sm%c" ESC "[0m", VTERM_ATTRIBUTE_SGR[i], VTERM_ATTRIBUTE_NAME[i][0]);
        feed(s, text);
    }
    printf("-- one cell per attribute, set by its own code\n");
    for(i = 0; i < 7; ++i) {
        VtermScreen_cell(s, 0, i, &cell);
        /* 'conceal' IS NOT KNOWN TO EVERY LIBRARY: said, not pinned. */
        if( ! *VtermCell_attribute_text(&cell, said, sizeof(said)) ) snprintf(said, sizeof(said), "(none)");
        if( ! strcmp(VTERM_ATTRIBUTE_NAME[i], "conceal") ) snprintf(said, sizeof(said), "conceal, or (none) on libvterm 0.1");
        printf("    %s  %s\n", pytext_str_repr(quoted, sizeof(quoted), cell.text), said);
    }
    printf("-- bold, underline and reverse at once; then reset\n");
    feed(s, "\r\n" ESC "[1;4;7mA" ESC "[0mB");
    for(i = 0; i < 2; ++i) {
        VtermScreen_cell(s, 1, i, &cell);
        if( ! *VtermCell_attribute_text(&cell, said, sizeof(said)) ) snprintf(said, sizeof(said), "(none)");
        printf("    %s  %s\n", pytext_str_repr(quoted, sizeof(quoted), cell.text), said);
    }
    printf("-- double underline (SGR 21) is underlined\n");
    feed(s, ESC "[21mD");
    VtermScreen_cell(s, 1, 2, &cell);
    printf("    %s  %s\n", "'D'", VtermCell_attribute_text(&cell, said, sizeof(said)));
    VtermScreen_free(s);
}

static const char*
colour_text(char* buffer, size_t size, int set_f, const unsigned char* rgb)
/* RETURN: buffer, '(r, g, b)' as Python prints the tuple, or 'None'.      */
{
    if( set_f ) snprintf(buffer, size, "(%d, %d, %d)", rgb[0], rgb[1], rgb[2]);
    else        snprintf(buffer, size, "None");
    return buffer;
}

static void
run_colours(void)
{
    static const char* what[] = { "default", "indexed 31", "palette 196", "direct 10;20;30", "background 1;2;3" };
    VtermScreen* s;
    VtermCell    cell;
    char         said[256], fg[32], bg[32], quoted[64];
    int          column;
    if( missing(s = VtermScreen_new(2, 20, &error)) ) return;
    feed(s, "d" ESC "[31mr" ESC "[0m" ESC "[38;5;196mp" ESC "[0m" ESC "[38;2;10;20;30mt" ESC "[0m");
    feed(s, ESC "[48;2;1;2;3mb" ESC "[0m");
    for(column = 0; column < 5; ++column) {
        VtermScreen_cell(s, 0, column, &cell);
        /* THE EIGHT NAMED COLOURS ARE THE LIBRARY'S OWN PALETTE: mostly red
         * is the claim, not its shade.                                   */
        if( ! strcmp(what[column], "indexed 31") ) {
            int max = cell.foreground[1] > cell.foreground[2] ? cell.foreground[1] : cell.foreground[2];
            snprintf(said, sizeof(said), "fg mostly red: %s", pytext_bool(cell.foreground[0] > 2 * max));
        } else
            snprintf(said, sizeof(said), "fg %s  bg %s", colour_text(fg, sizeof(fg), cell.foreground_f, cell.foreground),
                     colour_text(bg, sizeof(bg), cell.background_f, cell.background));
        printf("    %-18s %s  %s\n", what[column], pytext_str_repr(quoted, sizeof(quoted), cell.text), said);
    }
    VtermScreen_free(s);
}

/* THE APPLICATIONS UNDER OBSERVATION -- the Python test's own, word for word:
 * the system under test is the same, so the GOOD files can be.            */
static const char* SEEING_APP =
    "\n"
    "import os, sys, tty, termios\n"
    "print(\"streams are terminals: %s %s %s\"\n"
    "      % (sys.stdin.isatty(), sys.stdout.isatty(), sys.stderr.isatty()))\n"
    "try:    os.close(os.open(\"/dev/tty\", os.O_RDWR)); print(\"controlling terminal: yes\")\n"
    "except OSError: print(\"controlling terminal: no\")\n"
    "print(\"size: %d columns, %d rows\" % tuple(os.get_terminal_size()))\n"
    "print(\"TERM=%s COLUMNS=%s\" % (os.environ.get(\"TERM\"), os.environ.get(\"COLUMNS\")))\n"
    "old = termios.tcgetattr(0); tty.setraw(0)\n"
    "sys.stdout.write(\"\\x1b[6;9H\\x1b[6n\"); sys.stdout.flush()\n"
    "reply = b\"\"\n"
    "while not reply.endswith(b\"R\"): reply += os.read(0, 1)\n"
    "sys.stdout.write(\"\\r\\x1b[7;1Hthe terminal answered: %r\" % reply); sys.stdout.flush()\n"
    "while True:\n"
    "    key = os.read(0, 32)\n"
    "    sys.stdout.write(\"\\x1b[9;1H\\x1b[Kread: %r\" % key); sys.stdout.flush()\n"
    "    if key == b\"q\": break\n"
    "termios.tcsetattr(0, termios.TCSADRAIN, old)\n"
    "print(\"\\r\\nleaving\"); sys.exit(3)\n"
    "";

static const char* DRAWING_APP =
    "\n"
    "import os, sys, tty, termios\n"
    "old = termios.tcgetattr(0); tty.setraw(0)\n"
    "count, foot = 0, \"q=quit\"\n"
    "def draw():\n"
    "    out = \"\\x1b[2J\\x1b[1;1H\\x1b[7m the head \\x1b[0m\"\n"
    "    out += \"\\x1b[3;1Hcount: %d\\x1b[4;1H(press n)\" % count\n"
    "    out += \"\\x1b[8;1H%s\" % foot\n"
    "    sys.stdout.write(out); sys.stdout.flush()\n"
    "draw()\n"
    "while True:\n"
    "    key = os.read(0, 1)\n"
    "    if   key == b\"n\": count += 1\n"
    "    elif key == b\"f\": foot = \"q=quit  f=pressed\"\n"
    "    elif key == b\"q\": break\n"
    "    draw()\n"
    "termios.tcsetattr(0, termios.TCSADRAIN, old)\n"
    "";


/* --------------------------------------------------------------- Terminal */
static void
run_unnoticed(void)
{
    char* const    argv[] = { "python3", "-c", (char*)SEEING_APP, NULL };
    VtermTerminal* t;
    int            status = 0, running;
    setenv("COLUMNS", "300", 1);
    if( missing(t = VtermTerminal_new(10, 44, 0.1, &error)) ) return;
    running = VtermTerminal_run(t, argv, NULL, 10.0);
    printf("-- still running after its first screen: %s\n", pytext_bool(running == 1));
    shown(&t->base);
    VtermTerminal_send(t, "q", 1.0);
    VtermTerminal_wait(t, 10.0, &status);
    printf("-- after 'q': exit status %d\n", status);
    shown(&t->base);
    VtermTerminal_free(t);
}

static const char* pressed;

static void
said_read(void* context, const char* name, char** line_list, size_t line_n)
{
    (void)context; (void)name; (void)line_n;
    printf("    "); padded(pressed, 22); printf(" %s\n", line_list[0]);        /* 'ä': characters, not bytes */
}

static void
run_keys(void)
{
    static const struct { const char* key; const char* modifier; const char* said; } press[] = {
        { "up", NULL, "up" }, { "enter", NULL, "enter" }, { "tab", NULL, "tab" }, { "escape", NULL, "escape" },
        { "f5", NULL, "f5" }, { "delete", NULL, "delete" }, { "c", "ctrl", "ctrl c" }, { "x", "alt", "alt x" },
        { "up", "shift", "shift up" }, { NULL, NULL, NULL }
    };
    char* const    argv[] = { "python3", "-c", (char*)SEEING_APP, NULL };
    VtermTerminal* t;
    int            i, status;
    if( missing(t = VtermTerminal_new(10, 44, 0.1, &error)) ) return;
    VtermTerminal_region(t, "read", 8, 1, 0, -1);
    VtermTerminal_on_change(t, said_read, NULL);
    pressed = "(start)";
    VtermTerminal_run(t, argv, NULL, 10.0);
    for(i = 0; press[i].key; ++i) {
        pressed = press[i].said;
        VtermTerminal_press(t, press[i].key, press[i].modifier, 1.0);
    }
    pressed = "send '\xc3\xa4'";
    VtermTerminal_send(t, "\xc3\xa4", 1.0);
    pressed = "send 'q'";
    VtermTerminal_send(t, "q", 1.0);
    VtermTerminal_wait(t, 10.0, &status);
    VtermTerminal_free(t);
}

static void
said_change(void* context, const char* name, char** line_list, size_t line_n)
{
    char text[4096];
    (void)context;
    printf("    changed  %-5s %s\n", name, lines_repr(text, sizeof(text), line_list, line_n));
}

static void
run_regions(void)
{
    char* const    argv[] = { "python3", "-c", (char*)DRAWING_APP, NULL };
    static const struct { const char* said; const char* typed; } act[] = {
        { "'n'", "n" }, { "'n'", "n" }, { "'r': a redraw, nothing new", "r" }, { "'f'", "f" },
        { "'nnn', typed at once", "nnn" }, { "'q'", "q" }, { NULL, NULL }
    };
    VtermTerminal* t;
    char**         line;
    size_t         line_n;
    char           text[4096];
    int            i, status = 0;
    /* A LONGER PAUSE THAN THE DEFAULT: three redraws typed at once must be
     * ONE report on a loaded machine too.                                */
    if( missing(t = VtermTerminal_new(8, 30, 0.3, &error)) ) return;
    VtermTerminal_region(t, "head", 0, 1, 0, -1);
    VtermTerminal_region(t, "body", 2, 2, 0, -1);
    VtermTerminal_region(t, "foot", -1, 1, 0, -1);
    VtermTerminal_on_change(t, said_change, NULL);
    printf("-- run\n");
    VtermTerminal_run(t, argv, NULL, 10.0);
    for(i = 0; act[i].said; ++i) {
        printf("-- %s\n", act[i].said);
        VtermTerminal_send(t, act[i].typed, 1.0);
    }
    VtermTerminal_wait(t, 10.0, &status);
    line = VtermTerminal_region_text(t, "body", &line_n);
    printf("-- exit status %d; a region asked by name: %s\n", status, lines_repr(text, sizeof(text), line, line_n));
    VtermTerminal_lines_free(line, line_n);
    if( ! VtermTerminal_region_text(t, "nosuch", &line_n) )
        printf("-- no such region: %s %s\n", t->base.error.kind, t->base.error.message);
    VtermTerminal_free(t);
}

static void
said_event(void* context, const VtermEvent* event)
{ char text[256]; (void)context; printf("    %s\n", VtermEvent_to_string(event, text, sizeof(text))); }

static void
run_events(void)
{
    static const struct { const char* said; const char* data; } fed[] = {
        { "'ab'", "ab" }, { "a line feed and 'c'", "\r\nc" },
        { "the cursor to row 4, hidden", ESC "[4;1H" ESC "[?25l" },
        { "the alternate screen", ESC "[?1049h" }, { "the bell", "\x07" },
        { "nothing that draws: a reset of attributes", ESC "[0m" }, { NULL, NULL }
    };
    VtermTerminal* t;
    char*          answer;
    char           repr[256];
    size_t         length;
    int            i;
    if( missing(t = VtermTerminal_new(4, 20, 0.1, &error)) ) return;
    VtermTerminal_on_event(t, said_event, NULL);
    for(i = 0; fed[i].said; ++i) {
        printf("-- fed: %s\n", fed[i].said);
        VtermTerminal_feed(t, fed[i].data, strlen(fed[i].data));
    }
    printf("-- asked where the cursor is, nobody running: the answer waits\n");
    VtermTerminal_feed(t, ESC "[2;5H" ESC "[6n", 10);
    answer = VtermTerminal_answer(t, &length);
    printf("    answer() = %s\n", pytext_bytes_repr(repr, sizeof(repr), answer, length));
    free(answer);
    printf("-- a key pressed with nobody running\n");
    VtermTerminal_press(t, "f1", NULL, 0);
    answer = VtermTerminal_answer(t, &length);
    printf("    answer() = %s\n", pytext_bytes_repr(repr, sizeof(repr), answer, length));
    free(answer);
    VtermTerminal_free(t);
}

static void
run_missing(void)
{
    VtermScreen* s;
    char*        line;
    char*        cut;
    setenv(VTERM_LIBRARY_VARIABLE, "/nowhere/libvterm.so", 1);
    Vterm_reset_library();
    if( (s = VtermScreen_new(24, 80, &error)) ) {
        printf("a Screen stands on a library that is not there\n");
        VtermScreen_free(s);
        return;
    }
    /* THE SYSTEM'S OWN WORDS for the failed load are left out; what this
     * module says -- the line, and the way to install -- stands.          */
    line = error.message;
    cut  = strchr(line, '\n');
    if( cut ) *cut = '\0';
    {   char* words = strstr(line, " -- ");
        printf("%s: %.*s\n", error.kind, words ? (int)(words - line) : (int)strlen(line), line); }
    if( cut ) printf("%s\n", cut + 1);
}

int
main(int argc, char** argv)
{
    static const HwutRunner_Choice choice_list[] = {
        { "text", run_text }, { "screen", run_screen }, { "attributes", run_attributes },
        { "colours", run_colours }, { "unnoticed", run_unnoticed }, { "keys", run_keys },
        { "regions", run_regions }, { "events", run_events }, { "missing", run_missing },
        { NULL, NULL }
    };
    HwutRunner runner;
    HwutRunner_init(&runner, argc, argv, "A terminal's screen read by a test: libvterm through dlopen.",
                    choice_list);
    return HwutRunner_run(&runner);
}
