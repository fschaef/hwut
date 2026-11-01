#! /usr/bin/env python3
#
# @hwut {
#     title     = "Demo: a terminal program's screen, as a person sees it"
#     tolerance { regions    = false
#                 comment    = false
#                 whitespace = false }
#     choices {
#         open   { features = ["terminal-screen", "screen-as-seen"] }
#         scroll { features = ["terminal-screen", "screen-as-seen"] }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  the screen of 'viewer.py', a full-screen file viewer, run in a
         terminal of 9 rows and 40 columns and driven by its keys.
REQUIREMENT  The viewer shows a title bar in reverse video, the file's lines
             as they fit, and a status line -- the keys flush left, the lines
             shown flush right; 'j' and the down key go one line further,
             'k' one back.

hwut_vterm's 'Terminal' runs the viewer on a pseudo-terminal: the viewer
cannot tell it from a real one. The test PRESSES KEYS and is told what
CHANGED: three regions are declared -- title, body, status -- and after
every key, once the viewer has gone quiet, each region whose text changed
is printed. A redraw that changes nothing is not told: the title is told
once.

THE SCREEN IS COMPARED AS A PERSON SEES IT -- three tolerances switched
off, in the header:

    regions = false     the file shown is a GOOD file of hwut, with a
                        '##! potpourri' ... '####' block. On this screen
                        those are characters, not a region to open.
    comment = false     '## ...' lines are characters too, not notes.
    whitespace = false  the status line's two halves stand flush left and
                        flush right: every blank between them counts. A
                        half moved by one column is red. (A line's leading
                        and trailing blanks are stripped all the same.)

libvterm must be installed ('apt install libvterm0'); where it is not, the
test prints why and probes nothing -- its output differs from GOOD and the
reason stands in the difference.

CHOICES  open    the viewer opened, then quit.
         scroll  down, down, 'j', then 'k': three lines on, one back.
______________________________________________________________________________
"""
import os
import sys

from hwut.test_writing_support.python.hwut_vterm import Terminal, LibraryMissing

HERE   = os.path.dirname(os.path.abspath(__file__))
SAMPLE = """\
## demo.py race -- three workers
start
##! potpourri
worker B done: 5 jobs
worker A done: 3 jobs
worker C done: 2 jobs
####
all joined
## the order between the markers is
## free; the lines are not.
"""


def show(name, line_list):
    """RETURN: None. Prints one region that changed, its rows as they
    stand on the screen, from the first column."""
    print("-- %s" % name)
    for line in line_list:
        print(line)


def view(key_list):
    """RETURN: None. Runs the viewer on the sample, presses 'key_list',
    quits, and prints what changed after each step."""
    path = os.path.join(HERE, "TMP", "race.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(SAMPLE)
    with Terminal(row_n=9, column_n=40) as terminal:
        terminal.region("title",  row=0)
        terminal.region("body",   row=1, row_n=7)
        terminal.region("status", row=-1)
        terminal.on_change(show)
        print("> viewer.py race.txt")
        terminal.run([sys.executable, os.path.join(HERE, "viewer.py"), path])
        cell = terminal.cell(0, 1)
        print("title bar: %s" % (cell.attribute_text() or "plain"))
        for key in key_list:
            print("> %s" % key)
            if len(key) == 1: terminal.send(key)
            else:             terminal.press(key)
        terminal.send("q")
        print("> q -- exit status %d" % terminal.wait())


CHOICE_DB = {"open":   [],
             "scroll": ["down", "down", "j", "k"]}

choice = sys.argv[1] if len(sys.argv) > 1 else ""
if choice not in CHOICE_DB:
    print("choices: %s" % ", ".join(CHOICE_DB))
    sys.exit(1)
try:
    view(CHOICE_DB[choice])
except LibraryMissing as error:
    print(error)
    sys.exit(1)
print("<hwut-end>")
