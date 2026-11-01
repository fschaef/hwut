// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// A TERMINAL FILE VIEWER -- the program 'screen.cpp' tests; no test itself.
// Built as 'viewer.exe' with 'screen.exe' (the Makefile).
//
//     viewer.exe <file>
//
// Full screen, on the terminal's alternate screen: a title bar (reverse
// video), as many lines of the file as fit, and a status line: the keys
// flush left, the lines shown flush right. Keys: 'j' or down one line
// further, 'k' or up one line back, 'q' quits.
// _____________________________________________________________________________
#include <algorithm>
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>
#include <sys/ioctl.h>
#include <termios.h>
#include <unistd.h>

static void write_out(const std::string& text)
/* RETURN: nothing. 'text' written to the terminal whole. */
{
    size_t done = 0;
    while( done < text.size() ) {
        ssize_t n = ::write(STDOUT_FILENO, text.data() + done, text.size() - done);
        if( n <= 0 ) return;
        done += (size_t)n;
    }
}

static void draw(const std::string& name, const std::vector<std::string>& line_list, int top, int row_n, int column_n)
/* RETURN: nothing. Draws the whole screen with the file's line 'top' first. */
{
    const int body_n = row_n - 2;
    const int shown  = std::max(0, std::min(body_n, (int)line_list.size() - top));
    std::string out = "\x1b[H\x1b[2J";
    std::string title = " " + name;
    title.resize((size_t)column_n, ' ');
    out += "\x1b[7m" + title + "\x1b[0m\r\n";
    for(int i = 0; i < shown; ++i) out += line_list[(size_t)(top + i)].substr(0, (size_t)column_n) + "\r\n";
    for(int i = shown; i < body_n; ++i) out += "\r\n";
    const std::string keys  = "j k q";
    const std::string where = "lines " + std::to_string(top + 1) + "-" + std::to_string(top + shown)
                            + " of " + std::to_string(line_list.size());
    const int width = column_n - 1 - (int)keys.size();
    out += "\x1b[" + std::to_string(row_n) + ";1H" + keys
         + std::string((size_t)std::max(0, width - (int)where.size()), ' ') + where;
    write_out(out);
}

int main(int argc, char** argv)
/* RETURN: 0, once 'q' was pressed;
 *         2, where no file is named or it cannot be read.               */
{
    if( argc != 2 ) { std::fprintf(stderr, "usage: viewer.exe <file>\n"); return 2; }
    std::ifstream in(argv[1]);
    if( ! in ) { std::fprintf(stderr, "viewer.exe: cannot read '%s'\n", argv[1]); return 2; }
    std::vector<std::string> line_list;
    for(std::string line; std::getline(in, line); ) line_list.push_back(line);
    std::string name = argv[1];
    name = name.substr(name.rfind('/') + 1);

    struct winsize size = {};
    ioctl(STDOUT_FILENO, TIOCGWINSZ, &size);
    const int row_n = size.ws_row, column_n = size.ws_col;
    struct termios saved, raw;
    tcgetattr(STDIN_FILENO, &saved);
    raw = saved;
    cfmakeraw(&raw);
    tcsetattr(STDIN_FILENO, TCSAFLUSH, &raw);
    write_out("\x1b[?1049h");
    int top = 0;
    const int last_top = std::max(0, (int)line_list.size() - (row_n - 2));
    for(;;) {
        draw(name, line_list, top, row_n, column_n);
        char buffer[8];
        ssize_t n = ::read(STDIN_FILENO, buffer, sizeof(buffer));
        if( n <= 0 ) break;
        const std::string key(buffer, (size_t)n);
        if     ( key == "q" )                       break;
        else if( key == "j" || key == "\x1b[B" )    top = std::min(top + 1, last_top);
        else if( key == "k" || key == "\x1b[A" )    top = std::max(top - 1, 0);
    }
    write_out("\x1b[?1049l");
    tcsetattr(STDIN_FILENO, TCSADRAIN, &saved);
    return 0;
}
