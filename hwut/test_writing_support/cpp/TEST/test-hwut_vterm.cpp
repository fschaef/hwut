/* @hwut {
 *     title      = "A terminal's screen read by a test: libvterm, loaded at run time."
 *     build      { framework = "make", executable = "%.exe" }
 *     choices {
 *         attributes { features = ["cpp-vterm"] }
 *         colours    { features = ["cpp-vterm"] }
 *         events     { features = ["cpp-vterm"] }
 *         keys       { features = ["cpp-vterm"] }
 *         missing    { features = ["cpp-vterm"] }
 *         regions    { features = ["cpp-vterm"] }
 *         screen     { features = ["cpp-vterm"] }
 *         text       { features = ["cpp-vterm"] }
 *         unnoticed  { features = ["cpp-vterm"] }
 *     }
 *     interactive = true
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The C++ port of 'python/TEST/test-hwut_vterm.py', choice for
 *          choice, held against its GOOD files by '.link'. WANTS libvterm --
 *          found at run time, no header needed to build. The two
 *          APPLICATIONS a Terminal runs here are the Python test's,
 *          unchanged: they are the system under test, and what they print is
 *          in the shared GOOD files.
 * _____________________________________________________________________________
 */
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>
#include "hwut_runner.hpp"
#include "hwut_pytext.hpp"
#include "hwut_vterm.hpp"

namespace vterm = hwut::vterm;
using hwut::pytext::repr;

#define ESC "\x1b"

static std::string
padded(const std::string& text, int width)
/* RETURN: 'text' filled with blanks to 'width' CHARACTERS -- as Python's
 *         '%-6s' counts, not bytes.                                        */
{
    int n = 0;
    for(char c : text) n += (c & 0xC0) != 0x80;
    return text + std::string(width > n ? (size_t)(width - n) : 0, ' ');
}

static void
shown(vterm::Screen& screen)
/* RETURN: nothing; every row that holds something, framed, then the cursor. */
{
    for(int row = 0; row < screen.row_n(); ++row) {
        std::string line = screen.line(row);
        if( ! line.empty() ) std::printf("    %d |%s|\n", row, line.c_str());
    }
    auto [row, column] = screen.cursor();
    std::printf("    cursor (%d, %d)\n", row, column);
}

template <class Body>
static void
probed(Body body)
/* RETURN: nothing; 'body' ran -- or the one line said where the library was
 *         not found.                                                       */
{
    try                                         { body(); }
    catch( const vterm::LibraryMissing& error ) { std::printf("NOT PROBED: %s\n", error.what()); }
}

/* ----------------------------------------------------------------- Screen */
static void
run_text()
{
    {   vterm::Screen s(4, 12);
        std::printf("-- plain, then carriage return and line feed\n");
        s.feed("hello\r\nworld");
        shown(s); }
    {   vterm::Screen s(4, 12);
        std::printf("-- UTF-8: two bytes, one cell; a wide character, two\n");
        s.feed("\xc3\xa4\xe6\x97\xa5x");                         // 'ä日x'
        shown(s);
        for(int column = 0; column < 4; ++column) {
            vterm::Cell cell = s.cell(0, column);
            std::printf("    column %d: %s width %d\n", column, padded(repr(cell.text), 6).c_str(), cell.width);
        } }
    {   vterm::Screen s(3, 5);
        std::printf("-- seven characters on five columns: the line wraps\n");
        s.feed("abcdefg");
        shown(s); }
    {   vterm::Screen s(2, 4);
        std::printf("-- a str is sent as UTF-8; the bytes taken are counted\n");
        std::printf("    taken: %zu\n", s.feed("a\xc3\xa4"));
        std::printf("-- a place off the screen\n");
        try                                    { s.cell(2, 0); }
        catch( const std::out_of_range& error ) { std::printf("    IndexError: %s\n", error.what()); } }
}

static void
run_screen()
{
    vterm::Screen s(5, 20);
    std::printf("-- three lines, then '<esc>[2;4H' (it counts from 1) and 'X'\n");
    s.feed("first line\r\nsecond line\r\nthird line");
    s.feed(ESC "[2;4HX");
    shown(s);
    std::printf("-- erase to the end of that line\n");
    s.feed(ESC "[K");
    shown(s);
    std::printf("-- clear the screen, home, one word\n");
    s.feed(ESC "[2J" ESC "[Hclean");
    shown(s);
}

static std::string said_or_none(const vterm::Cell& cell)
{ std::string said = cell.attribute_text(); return said.empty() ? "(none)" : said; }

static void
run_attributes()
{
    vterm::Screen s(3, 20);
    for(size_t i = 0; i < 7; ++i)
        s.feed(ESC "[" + std::string(vterm::ATTRIBUTE_SGR[i]) + "m" + vterm::ATTRIBUTE_NAME[i][0] + ESC "[0m");
    std::printf("-- one cell per attribute, set by its own code\n");
    for(size_t i = 0; i < 7; ++i) {
        vterm::Cell cell = s.cell(0, (int)i);
        /* 'conceal' IS NOT KNOWN TO EVERY LIBRARY: said, not pinned. */
        std::string said = std::string(vterm::ATTRIBUTE_NAME[i]) == "conceal" ? "conceal, or (none) on libvterm 0.1"
                                                                            : said_or_none(cell);
        std::printf("    %s  %s\n", repr(cell.text).c_str(), said.c_str());
    }
    std::printf("-- bold, underline and reverse at once; then reset\n");
    s.feed("\r\n" ESC "[1;4;7mA" ESC "[0mB");
    for(int i = 0; i < 2; ++i) {
        vterm::Cell cell = s.cell(1, i);
        std::printf("    %s  %s\n", repr(cell.text).c_str(), said_or_none(cell).c_str());
    }
    std::printf("-- double underline (SGR 21) is underlined\n");
    s.feed(ESC "[21mD");
    std::printf("    %s  %s\n", "'D'", s.cell(1, 2).attribute_text().c_str());
}

static std::string
colour_text(const std::optional<vterm::Rgb>& rgb)
/* RETURN: '(r, g, b)' as Python prints the tuple, or 'None'.              */
{ return rgb ? repr(std::make_tuple((int)(*rgb)[0], (int)(*rgb)[1], (int)(*rgb)[2])) : "None"; }

static void
run_colours()
{
    static const char* what[] = { "default", "indexed 31", "palette 196", "direct 10;20;30", "background 1;2;3" };
    vterm::Screen s(2, 20);
    s.feed("d" ESC "[31mr" ESC "[0m" ESC "[38;5;196mp" ESC "[0m" ESC "[38;2;10;20;30mt" ESC "[0m");
    s.feed(ESC "[48;2;1;2;3mb" ESC "[0m");
    for(int column = 0; column < 5; ++column) {
        vterm::Cell cell = s.cell(0, column);
        std::string said;
        /* THE EIGHT NAMED COLOURS ARE THE LIBRARY'S OWN PALETTE: mostly red
         * is the claim, not its shade.                                   */
        if( std::string(what[column]) == "indexed 31" ) {
            const vterm::Rgb& fg  = cell.foreground.value_or(vterm::Rgb{ { 0, 0, 0 } });
            int               max = fg[1] > fg[2] ? fg[1] : fg[2];
            said = "fg mostly red: " + repr(fg[0] > 2 * max);
        } else
            said = "fg " + colour_text(cell.foreground) + "  bg " + colour_text(cell.background);
        std::printf("    %-18s %s  %s\n", what[column], repr(cell.text).c_str(), said.c_str());
    }
}

/* THE APPLICATIONS UNDER OBSERVATION -- the Python test's own, word for word:
 * the system under test is the same, so the GOOD files can be.            */
static const char* SEEING_APP = R"PY(
import os, sys, tty, termios
print("streams are terminals: %s %s %s"
      % (sys.stdin.isatty(), sys.stdout.isatty(), sys.stderr.isatty()))
try:    os.close(os.open("/dev/tty", os.O_RDWR)); print("controlling terminal: yes")
except OSError: print("controlling terminal: no")
print("size: %d columns, %d rows" % tuple(os.get_terminal_size()))
print("TERM=%s COLUMNS=%s" % (os.environ.get("TERM"), os.environ.get("COLUMNS")))
old = termios.tcgetattr(0); tty.setraw(0)
sys.stdout.write("\x1b[6;9H\x1b[6n"); sys.stdout.flush()
reply = b""
while not reply.endswith(b"R"): reply += os.read(0, 1)
sys.stdout.write("\r\x1b[7;1Hthe terminal answered: %r" % reply); sys.stdout.flush()
while True:
    key = os.read(0, 32)
    sys.stdout.write("\x1b[9;1H\x1b[Kread: %r" % key); sys.stdout.flush()
    if key == b"q": break
termios.tcsetattr(0, termios.TCSADRAIN, old)
print("\r\nleaving"); sys.exit(3)
)PY";

static const char* DRAWING_APP = R"PY(
import os, sys, tty, termios
old = termios.tcgetattr(0); tty.setraw(0)
count, foot = 0, "q=quit"
def draw():
    out = "\x1b[2J\x1b[1;1H\x1b[7m the head \x1b[0m"
    out += "\x1b[3;1Hcount: %d\x1b[4;1H(press n)" % count
    out += "\x1b[8;1H%s" % foot
    sys.stdout.write(out); sys.stdout.flush()
draw()
while True:
    key = os.read(0, 1)
    if   key == b"n": count += 1
    elif key == b"f": foot = "q=quit  f=pressed"
    elif key == b"q": break
    draw()
termios.tcsetattr(0, termios.TCSADRAIN, old)
)PY";

/* --------------------------------------------------------------- Terminal */
static void
run_unnoticed()
{
    setenv("COLUMNS", "300", 1);
    vterm::Terminal t(10, 44);
    bool running = t.run({ "python3", "-c", SEEING_APP });
    std::printf("-- still running after its first screen: %s\n", repr(running).c_str());
    shown(t);
    t.send("q");
    std::printf("-- after 'q': exit status %d\n", t.wait().value_or(0));
    shown(t);
}

static void
run_keys()
{
    struct Press { const char* key; const char* modifier; const char* said; };
    static const Press press[] = {
        { "up", "", "up" }, { "enter", "", "enter" }, { "tab", "", "tab" }, { "escape", "", "escape" },
        { "f5", "", "f5" }, { "delete", "", "delete" }, { "c", "ctrl", "ctrl c" }, { "x", "alt", "alt x" },
        { "up", "shift", "shift up" },
    };
    vterm::Terminal t(10, 44);
    std::string     pressed = "(start)";
    t.region("read", 8);
    t.on_change([&](const std::string&, const std::vector<std::string>& line_list) {
        std::printf("    %s %s\n", padded(pressed, 22).c_str(), line_list[0].c_str());   // 'ä': characters, not bytes
    });
    t.run({ "python3", "-c", SEEING_APP });
    for(const Press& p : press) { pressed = p.said; t.press(p.key, p.modifier); }
    pressed = "send '\xc3\xa4'";
    t.send("\xc3\xa4");
    pressed = "send 'q'";
    t.send("q");
    t.wait();
}

static void
run_regions()
{
    struct Act { const char* said; const char* typed; };
    static const Act act[] = {
        { "'n'", "n" }, { "'n'", "n" }, { "'r': a redraw, nothing new", "r" }, { "'f'", "f" },
        { "'nnn', typed at once", "nnn" }, { "'q'", "q" },
    };
    /* A LONGER PAUSE THAN THE DEFAULT: three redraws typed at once must be
     * ONE report on a loaded machine too.                                */
    vterm::Terminal t(8, 30, 0.3);
    t.region("head", 0);
    t.region("body", 2, 2);
    t.region("foot", -1);
    t.on_change([](const std::string& name, const std::vector<std::string>& line_list) {
        std::printf("    changed  %-5s %s\n", name.c_str(), repr(line_list).c_str());
    });
    std::printf("-- run\n");
    t.run({ "python3", "-c", DRAWING_APP });
    for(const Act& a : act) {
        std::printf("-- %s\n", a.said);
        t.send(a.typed);
    }
    int status = t.wait().value_or(0);
    std::printf("-- exit status %d; a region asked by name: %s\n", status, repr(t.region_text("body")).c_str());
    try                                   { t.region_text("nosuch"); }
    catch( const vterm::KeyError& error ) { std::printf("-- no such region: KeyError %s\n", error.what()); }
}

static void
run_events()
{
    struct Fed { const char* said; const char* data; };
    static const Fed fed[] = {
        { "'ab'", "ab" }, { "a line feed and 'c'", "\r\nc" },
        { "the cursor to row 4, hidden", ESC "[4;1H" ESC "[?25l" },
        { "the alternate screen", ESC "[?1049h" }, { "the bell", "\x07" },
        { "nothing that draws: a reset of attributes", ESC "[0m" },
    };
    vterm::Terminal t(4, 20);
    t.on_event([](const vterm::Event& event) { std::printf("    %s\n", event.to_string().c_str()); });
    for(const Fed& f : fed) {
        std::printf("-- fed: %s\n", f.said);
        t.feed(f.data);
    }
    std::printf("-- asked where the cursor is, nobody running: the answer waits\n");
    t.feed(ESC "[2;5H" ESC "[6n");
    std::printf("    answer() = %s\n", hwut::pytext::bytes_repr(t.answer()).c_str());
    std::printf("-- a key pressed with nobody running\n");
    t.press("f1", "", 0);
    std::printf("    answer() = %s\n", hwut::pytext::bytes_repr(t.answer()).c_str());
}

static void
run_missing()
{
    setenv(vterm::LIBRARY_VARIABLE, "/nowhere/libvterm.so", 1);
    vterm::reset_library();
    try {
        vterm::Screen s(24, 80);
        std::printf("a Screen stands on a library that is not there\n");
    } catch( const vterm::LibraryMissing& error ) {
        /* THE SYSTEM'S OWN WORDS for the failed load are left out; what this
         * module says -- the line, and the way to install -- stands.      */
        std::string message = error.what();
        size_t      cut     = message.find('\n');
        std::string line    = message.substr(0, cut);
        std::printf("%s: %s\n", error.kind().c_str(), line.substr(0, line.find(" -- ")).c_str());
        if( cut != std::string::npos ) std::printf("%s\n", message.substr(cut + 1).c_str());
    }
}

int
main(int argc, char** argv)
{
    hwut::HwutRunner runner(argc, argv, "A terminal's screen read by a test: libvterm, loaded at run time.", {
        { "text",      [] { probed(run_text); } },      { "screen",  [] { probed(run_screen); } },
        { "attributes", [] { probed(run_attributes); } }, { "colours", [] { probed(run_colours); } },
        { "unnoticed", [] { probed(run_unnoticed); } }, { "keys",    [] { probed(run_keys); } },
        { "regions",   [] { probed(run_regions); } },   { "events",  [] { probed(run_events); } },
        { "missing",   run_missing },
    });
    return runner.run();
}
