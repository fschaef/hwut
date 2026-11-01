#! /usr/bin/env bash
#
# @hwut {
#     title      = "A terminal's screen read by a test: libvterm through the C port, a coprocess."
#     choices {
#         attributes { features = ["bash-vterm"] }
#         colours    { features = ["bash-vterm"] }
#         events     { features = ["bash-vterm"] }
#         keys       { features = ["bash-vterm"] }
#         missing    { features = ["bash-vterm"] }
#         regions    { features = ["bash-vterm"] }
#         screen     { features = ["bash-vterm"] }
#         text       { features = ["bash-vterm"] }
#         unnoticed  { features = ["bash-vterm"] }
#     }
#     interactive = true
# }
#
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: The bash port of 'python/TEST/test-hwut_vterm.py', choice for
#          choice, held against its GOOD files by '.link'. WANTS libvterm --
#          reached through the C port, by 'hwut_vterm_server', which
#          'hwut_vterm.sh' builds on first use (cc, make). The two
#          APPLICATIONS a terminal runs here are the Python test's,
#          unchanged: they are the system under test, and what they print
#          is in the shared GOOD files.
#______________________________________________________________________________
source "$(dirname "$0")/../hwut_runner.sh"
source "$(dirname "$0")/../hwut_vterm.sh"

ESC=$'\e'

shown() {
    #  RETURN: 0; every row of screen '$1' that holds something printed,
    #          framed, then the cursor.
    local row
    vterm_line_list "$1"
    for (( row = 0; row < ${#REPLY_LIST[@]}; ++row )); do
        [[ -n ${REPLY_LIST[row]} ]] && echo "    $row |${REPLY_LIST[row]}|"
    done
    vterm_cursor "$1"
    echo "    cursor $REPLY"
}

missing() {
    #  RETURN: 0, and the one line said, where the library was not found;
    #          1, it was.
    [[ $VTERM_ERROR_KIND == LibraryMissing ]] || return 1
    echo "NOT PROBED: $VTERM_ERROR"
}

# ------------------------------------------------------------------- Screen
run_text() {
    local column quoted
    vterm_screen_new screen 4 12 || { missing; return; }
    echo "-- plain, then carriage return and line feed"
    vterm_feed screen $'hello\r\nworld'
    shown screen; vterm_close screen

    vterm_screen_new screen 4 12
    echo "-- UTF-8: two bytes, one cell; a wide character, two"
    vterm_feed screen "ä日x"
    shown screen
    for (( column = 0; column < 4; ++column )); do
        vterm_cell screen 0 $column cell
        pytext_str_repr "${cell[text]}"; pytext_ljust "$REPLY" 6
        echo "    column $column: $REPLY width ${cell[width]}"
    done
    vterm_close screen

    vterm_screen_new screen 3 5
    echo "-- seven characters on five columns: the line wraps"
    vterm_feed screen "abcdefg"
    shown screen; vterm_close screen

    vterm_screen_new screen 2 4
    echo "-- a str is sent as UTF-8; the bytes taken are counted"
    vterm_feed screen "aä"; echo "    taken: $REPLY"
    echo "-- a place off the screen"
    vterm_cell screen 2 0 cell || echo "    $VTERM_ERROR_KIND: $VTERM_ERROR"
    vterm_close screen
}

run_screen() {
    vterm_screen_new screen 5 20 || { missing; return; }
    echo "-- three lines, then '<esc>[2;4H' (it counts from 1) and 'X'"
    vterm_feed screen $'first line\r\nsecond line\r\nthird line'
    vterm_feed screen "$ESC[2;4HX"
    shown screen
    echo "-- erase to the end of that line"
    vterm_feed screen "$ESC[K"
    shown screen
    echo "-- clear the screen, home, one word"
    vterm_feed screen "$ESC[2J$ESC[Hclean"
    shown screen
    vterm_close screen
}

run_attributes() {
    local name column said
    vterm_screen_new screen 3 20 || { missing; return; }
    for name in "${VTERM_ATTRIBUTE_NAMES[@]}"; do
        vterm_feed screen "$ESC[${VTERM_ATTRIBUTE_SGR[$name]}m${name:0:1}$ESC[0m"
    done
    echo "-- one cell per attribute, set by its own code"
    column=0
    for name in "${VTERM_ATTRIBUTE_NAMES[@]}"; do
        vterm_cell screen 0 $column cell; (( ++column ))
        #  'conceal' IS NOT KNOWN TO EVERY LIBRARY: said, not pinned.
        vterm_cell_attribute_text cell; said=${REPLY:-(none)}
        [[ $name == conceal ]] && said="conceal, or (none) on libvterm 0.1"
        pytext_str_repr "${cell[text]}"
        echo "    $REPLY  $said"
    done
    echo "-- bold, underline and reverse at once; then reset"
    vterm_feed screen $'\r\n'"$ESC[1;4;7mA$ESC[0mB"
    for column in 0 1; do
        vterm_cell screen 1 $column cell
        vterm_cell_attribute_text cell; said=${REPLY:-(none)}
        pytext_str_repr "${cell[text]}"
        echo "    $REPLY  $said"
    done
    echo "-- double underline (SGR 21) is underlined"
    vterm_feed screen "$ESC[21mD"
    vterm_cell screen 1 2 cell; vterm_cell_attribute_text cell
    echo "    'D'  $REPLY"
    vterm_close screen
}

run_colours() {
    local column what said fg bg
    local -a what_list=("default" "indexed 31" "palette 196" "direct 10;20;30" "background 1;2;3")
    vterm_screen_new screen 2 20 || { missing; return; }
    vterm_feed screen "d$ESC[31mr$ESC[0m$ESC[38;5;196mp$ESC[0m$ESC[38;2;10;20;30mt$ESC[0m"
    vterm_feed screen "$ESC[48;2;1;2;3mb$ESC[0m"
    for (( column = 0; column < 5; ++column )); do
        what=${what_list[column]}
        vterm_cell screen 0 $column cell
        #  THE EIGHT NAMED COLOURS ARE THE LIBRARY'S OWN PALETTE: that one
        #  is a colour and mostly red is the claim, not its shade.
        if [[ $what == "indexed 31" ]]; then
            local -a rgb=(${cell[foreground]})
            local max=$(( rgb[1] > rgb[2] ? rgb[1] : rgb[2] ))
            pytext_bool $(( rgb[0] > 2 * max )); said="fg mostly red: $REPLY"
        else
            vterm_cell_colour_text cell foreground; fg=$REPLY
            vterm_cell_colour_text cell background; bg=$REPLY
            said="fg $fg  bg $bg"
        fi
        pytext_str_repr "${cell[text]}"
        printf '    %-18s %s  %s\n' "$what" "$REPLY" "$said"
    done
    vterm_close screen
}

#  THE APPLICATION UNDER OBSERVATION: it says what it sees, asks the
#  terminal where the cursor is, then names every key until 'q'.
SEEING_APP='
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
'

#  AN APPLICATION WITH A HEAD, A BODY AND A FOOT: 'n' counts in the body,
#  'f' rewrites the foot, 'r' redraws everything unchanged, 'q' leaves.
DRAWING_APP='
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
'

# ----------------------------------------------------------------- Terminal
run_unnoticed() {
    export COLUMNS=300
    vterm_terminal_new terminal 10 44 || { missing; return; }
    if vterm_run terminal -- python3 -c "$SEEING_APP"; then pytext_bool 1; else pytext_bool 0; fi
    echo "-- still running after its first screen: $REPLY"
    shown terminal
    vterm_send terminal q
    vterm_wait terminal
    echo "-- after 'q': exit status $REPLY"
    shown terminal
    vterm_close terminal
}

said_read() {
    #  RETURN: 0; the key last pressed, and what the application read.
    pytext_ljust "$pressed" 22                    # 'ä': characters, not bytes
    echo "    $REPLY $2"
}

run_keys() {
    local key
    vterm_terminal_new terminal 10 44 || { missing; return; }
    vterm_region terminal read 8
    vterm_on_change terminal said_read
    pressed="(start)"
    vterm_run terminal -- python3 -c "$SEEING_APP"
    for key in up enter tab escape f5 delete "c ctrl" "x alt" "up shift"; do
        local -a word=($key)
        pressed="${word[*]:1} ${word[0]}"; pressed=${pressed# }
        vterm_press terminal "${word[@]}"
    done
    pressed="send 'ä'"
    vterm_send terminal "ä"
    pressed="send 'q'"
    vterm_send terminal q
    vterm_wait terminal
    vterm_close terminal
}

said_change() {
    #  RETURN: 0; the region that changed, and its lines.
    local name=$1; shift
    pytext_list_repr str "$@"
    printf '    changed  %-5s %s\n' "$name" "$REPLY"
}

run_regions() {
    local said typed
    #  A LONGER PAUSE THAN THE DEFAULT: three redraws typed at once must be
    #  ONE report on a loaded machine too.
    vterm_terminal_new terminal 8 30 0.3 || { missing; return; }
    vterm_region terminal head 0
    vterm_region terminal body 2 2
    vterm_region terminal foot -1
    vterm_on_change terminal said_change
    echo "-- run"
    vterm_run terminal -- python3 -c "$DRAWING_APP"
    for said in "'n'=n" "'n'=n" "'r': a redraw, nothing new=r" "'f'=f" "'nnn', typed at once=nnn" "'q'=q"; do
        typed=${said##*=} said=${said%=*}
        echo "-- $said"
        vterm_send terminal "$typed"
    done
    vterm_wait terminal; local status=$REPLY
    vterm_region_text terminal body; pytext_list_repr str "${REPLY_LIST[@]}"
    echo "-- exit status $status; a region asked by name: $REPLY"
    vterm_region_text terminal nosuch || echo "-- no such region: $VTERM_ERROR_KIND $VTERM_ERROR"
    vterm_close terminal
}

said_event() { echo "    $1"; }

run_events() {
    local said
    vterm_terminal_new terminal 4 20 || { missing; return; }
    vterm_on_event terminal said_event
    local -a fed=("'ab'" "ab"
                  "a line feed and 'c'" $'\r\nc'
                  "the cursor to row 4, hidden" "$ESC[4;1H$ESC[?25l"
                  "the alternate screen" "$ESC[?1049h"
                  "the bell" $'\a'
                  "nothing that draws: a reset of attributes" "$ESC[0m")
    local k
    for (( k = 0; k < ${#fed[@]}; k += 2 )); do
        echo "-- fed: ${fed[k]}"
        vterm_feed terminal "${fed[k+1]}"
    done
    echo "-- asked where the cursor is, nobody running: the answer waits"
    vterm_feed terminal "$ESC[2;5H$ESC[6n"
    vterm_answer terminal; pytext_bytes_repr "$REPLY"
    echo "    answer() = $REPLY"
    echo "-- a key pressed with nobody running"
    vterm_press terminal f1 react_s=0
    vterm_answer terminal; pytext_bytes_repr "$REPLY"
    echo "    answer() = $REPLY"
    vterm_close terminal
}

run_missing() {
    export HWUT_LIBVTERM=/nowhere/libvterm.so
    vterm_reset_library
    if vterm_screen_new screen; then
        echo "a Screen stands on a library that is not there"
        vterm_close screen
        return
    fi
    #  THE SYSTEM'S OWN WORDS for the failed load are left out; what this
    #  module says -- the line, and the way to install -- stands.
    local -a line_list
    mapfile -t line_list <<< "$VTERM_ERROR"
    echo "$VTERM_ERROR_KIND: ${line_list[0]%% -- *}"
    printf '%s\n' "${line_list[@]:1}"
}

declare -A choice_map=(
    [text]=run_text [screen]=run_screen [attributes]=run_attributes [colours]=run_colours
    [unnoticed]=run_unnoticed [keys]=run_keys [regions]=run_regions [events]=run_events
    [missing]=run_missing
)
hwut_runner_new runner "A terminal's screen read by a test: libvterm through the C port, a coprocess." choice_map
hwut_runner_run runner "$@"
