/* @hwut {
 *     title     = "Demo: a terminal program's screen, as a person sees it"
 *     build     { framework = "make", executable = "%.exe" }
 *     tolerance { regions    = false
 *                 comment    = false
 *                 whitespace = false }
 *     choices {
 *         open   { features = ["terminal-screen", "screen-as-seen"] }
 *         scroll { features = ["terminal-screen", "screen-as-seen"] }
 *     }
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * SUBJECT  the screen of 'viewer.exe' (from 'viewer.cpp'), a full-screen file
 *          viewer, run in a terminal of 9 rows and 40 columns and driven by
 *          its keys.
 * REQUIREMENT  The viewer shows a title bar in reverse video, the file's lines
 *              as they fit, and a status line -- the keys flush left, the
 *              lines shown flush right; 'j' and the down key go one line
 *              further, 'k' one back.
 *
 * 'hwut::vterm::Terminal' runs the viewer on a pseudo-terminal: the viewer
 * cannot tell it from a real one. The test PRESSES KEYS and is told what
 * CHANGED: three regions are declared -- title, body, status -- and after
 * every key, once the viewer has gone quiet, each region whose text changed
 * is printed.
 *
 * THE SCREEN IS COMPARED AS A PERSON SEES IT -- three tolerances switched
 * off, in the header: 'regions = false' (the file shown is a GOOD file of
 * hwut, its '##! potpourri' characters, no region), 'comment = false' ('##'
 * lines are characters too), 'whitespace = false' (every blank of the status
 * line counts).
 *
 * The GOOD is this test's own, not a link: its first line names the program
 * started, 'viewer.exe' where Python's names 'viewer.py' (RATIONALE
 * DEMO-CPP-4). Every other line is the Python demonstration's.
 *
 * libvterm must be installed ('apt install libvterm0'); where it is not, the
 * test prints why and probes nothing.
 *
 * CHOICES  open    the viewer opened, then quit.
 *          scroll  down, down, 'j', then 'k': three lines on, one back.
 * _____________________________________________________________________________
 */
#include <cstdio>
#include <fstream>
#include <string>
#include <sys/stat.h>
#include <unistd.h>
#include <limits.h>

#include "hwut_vterm.hpp"

static const char* SAMPLE =
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

static std::string here()
/* RETURN: std::string, the directory this executable stands in. */
{
    char path[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", path, sizeof(path) - 1);
    std::string self = n > 0 ? std::string(path, (size_t)n) : std::string(".");
    size_t slash = self.rfind('/');
    return slash == std::string::npos ? "." : self.substr(0, slash);
}

static void show(const std::string& name, const std::vector<std::string>& line_list)
/* RETURN: nothing. Prints one region that changed, its rows as they stand
 *         on the screen, from the first column.                         */
{
    std::printf("-- %s\n", name.c_str());
    for(const std::string& line : line_list) std::printf("%s\n", line.c_str());
}

static int view(const std::vector<std::string>& key_list)
/* RETURN: 0, the viewer run on the sample, 'key_list' pressed, quit, and
 *         what changed after each step printed.                          */
{
    const std::string path = here() + "/TMP/race.txt";
    mkdir((here() + "/TMP").c_str(), 0777);
    std::ofstream(path) << SAMPLE;
    hwut::vterm::Terminal terminal(9, 40);
    terminal.region("title",  0);
    terminal.region("body",   1, 7);
    terminal.region("status", -1);
    terminal.on_change(show);
    std::printf("> viewer.exe race.txt\n");
    terminal.run({ here() + "/viewer.exe", path });
    const std::string attribute = terminal.cell(0, 1).attribute_text();
    std::printf("title bar: %s\n", attribute.empty() ? "plain" : attribute.c_str());
    for(const std::string& key : key_list) {
        std::printf("> %s\n", key.c_str());
        if( key.size() == 1 ) terminal.send(key);
        else                  terminal.press(key);
    }
    terminal.send("q");
    std::printf("> q -- exit status %d\n", terminal.wait().value_or(-1));
    return 0;
}

int main(int argc, char** argv)
/* RETURN: 0, the choice named by 'argv[1]' printed, '<hwut-end>' after it;
 *         1, where no known choice is named, or libvterm is missing.     */
{
    const std::string choice = argc > 1 ? argv[1] : "";
    std::vector<std::string> key_list;
    if     ( choice == "open" )   key_list = {};
    else if( choice == "scroll" ) key_list = { "down", "down", "j", "k" };
    else { std::printf("choices: open, scroll\n"); return 1; }
    try {
        view(key_list);
    } catch( const hwut::vterm::LibraryMissing& error ) {
        std::printf("%s\n", error.what());
        return 1;
    }
    std::printf("<hwut-end>\n");
    return 0;
}
