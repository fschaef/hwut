// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// A TERMINAL FILE VIEWER -- the program 'screen.sv' tests; no test itself.
//
//     viewer.exe <file>
//
// Full screen, on the terminal's alternate screen: a title bar (reverse
// video), as many lines of the file as fit, and a status line: the keys
// flush left, the lines shown flush right. Keys: 'j' or down one line
// further, 'k' or up one line back, 'q' quits.
//
// THE TERMINAL is reached through DPI-C into the C library itself -- no C of
// this directory: 'ioctl' for its size, 'tcgetattr'/'cfmakeraw'/'tcsetattr'
// for raw mode (a 'struct termios' and a 'struct winsize' held as bit vectors
// the size of the struct, or larger). Keys are read by '$fgetc' on stdin.
// _____________________________________________________________________________
import hwut_runner::*;

import "DPI-C" function int  ioctl(int fd, longint request, output longint window_size);
import "DPI-C" function int  tcgetattr(int fd, output bit [1023:0] termios);
import "DPI-C" function void cfmakeraw(inout bit [1023:0] termios);
import "DPI-C" function int  tcsetattr(int fd, int when, input bit [1023:0] termios);

localparam longint TIOCGWINSZ = 'h5413;   // Linux
localparam int     TCSADRAIN  = 1;
localparam int     STDIN      = 32'h8000_0000;
localparam string  ESC        = "\x1b";
localparam string  CRLF       = "\015\n";

class Viewer;
    string line_list[$];
    string name;
    int    row_n;
    int    column_n;

    function bit load(string path);
        // RETURN: 1, the lines of the file 'path' stand in 'line_list' and its
        //         base name in 'name'; 0, it cannot be read.
        int    fd;
        string line;
        line_list = {};
        fd = $fopen(path, "r");
        if (fd == 0) return 0;
        forever begin
            if ($fgets(line, fd) == 0) break;           // never a 'while' condition
            if (line.len() && line[line.len() - 1] == "\n") line = line.substr(0, line.len() - 2);
            line_list.push_back(line);
        end
        $fclose(fd);
        name = path;
        for (int i = path.len() - 1; i >= 0; i--)
            if (path[i] == "/") begin name = path.substr(i + 1, path.len() - 1); break; end
        return 1;
    endfunction

    function string cut(string text, int width);
        // RETURN: 'text' to at most 'width' characters.
        return text.len() <= width ? text : text.substr(0, width - 1);
    endfunction

    function string spaces(int n);
        // RETURN: 'n' blanks; none where 'n' <= 0.
        string text = "";
        for (int i = 0; i < n; i++) text = {text, " "};
        return text;
    endfunction

    function void draw(int top);
        // RETURN: nothing; the whole screen was drawn, the file's line 'top'
        //         first.
        int    body_n = row_n - 2;
        int    shown_n = 0;
        string title = cut({" ", name, spaces(column_n)}, column_n);
        string where, keys = "j k q";
        $write("%s[H%s[2J", ESC, ESC);
        $write("%s[7m%s%s[0m%s", ESC, title, ESC, CRLF);
        for (int i = top; i < line_list.size() && shown_n < body_n; i++) begin
            $write("%s%s", cut(line_list[i], column_n), CRLF);
            shown_n += 1;
        end
        for (int i = shown_n; i < body_n; i++) $write("%s", CRLF);
        where = $sformatf("lines %0d-%0d of %0d", top + 1, top + shown_n, line_list.size());
        $write("%s[%0d;1H%s%s%s", ESC, row_n, keys, spaces(column_n - 1 - keys.len() - where.len()), where);
        $fflush();
    endfunction

    function int key();
        // RETURN: the key pressed: its character, 'B' for down and 'A' for up
        //         (the escape sequence read whole); -1 at the end of input.
        int c = $fgetc(STDIN);
        if (c != 8'h1b) return c;
        c = $fgetc(STDIN);
        if (c != "[") return c;
        return $fgetc(STDIN);
    endfunction

    function int main(string path);
        // RETURN: 0 once 'q' was pressed (or the input ended); 1 where 'path'
        //         cannot be read or stdin is no terminal.
        bit [1023:0] saved, raw;
        longint      window_size;
        int          top = 0, c, last;
        if (!load(path)) begin
            $fdisplay(32'h8000_0002, "viewer: cannot read '%s'", path);
            return 1;
        end
        if (ioctl(1, TIOCGWINSZ, window_size) != 0 || tcgetattr(0, saved) != 0) begin
            $fdisplay(32'h8000_0002, "viewer: stdin and stdout must be a terminal");
            return 1;
        end
        row_n    = int'(window_size[15:0]);
        column_n = int'(window_size[31:16]);
        raw      = saved;
        cfmakeraw(raw);
        void'(tcsetattr(0, TCSADRAIN, raw));
        $write("%s[?1049h", ESC);
        last = line_list.size() - (row_n - 2);
        if (last < 0) last = 0;
        forever begin
            draw(top);
            c = key();
            if (c == "q" || c < 0)              break;
            else if (c == "j" || c == "B")    top = top + 1 < last ? top + 1 : last;
            else if (c == "k" || c == "A")    top = top > 0 ? top - 1 : 0;
        end
        $write("%s[?1049l", ESC);
        $fflush();
        void'(tcsetattr(0, TCSADRAIN, saved));
        return 0;
    endfunction
endclass

module viewer;
    initial begin
        Viewer v = new();
        if (hwut_sv_argc() != 2) begin
            $display("usage: viewer.exe <file>");
            exit_(1);
        end
        exit_(v.main(hwut_sv_argv(1)));
    end
endmodule
