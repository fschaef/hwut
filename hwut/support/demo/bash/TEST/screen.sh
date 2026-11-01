#! /usr/bin/env bash
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
#______________________________________________________________________________
# SUBJECT  the screen of 'viewer.sh', a full-screen file viewer, run in a
#          terminal of 9 rows and 40 columns and driven by its keys.
# REQUIREMENT  The viewer shows a title bar in reverse video, the file's lines
#              as they fit, and a status line -- the keys flush left, the
#              lines shown flush right; 'j' and the down key go one line
#              further, 'k' one back.
#
# 'screen.py' of the Python demonstration, in bash: 'hwut_vterm.sh' runs the
# viewer on a pseudo-terminal, the test PRESSES KEYS and is told what
# CHANGED in three regions -- title, body, status. The screen is compared
# as a person sees it: 'regions', 'comment' and 'whitespace' off (why: see
# 'screen.py').
#
# libvterm must be installed ('apt install libvterm0'), and cc and make:
# 'hwut_vterm.sh' builds its server on first use. Where the library is
# missing, the test prints why and probes nothing.
#
# CHOICES  open    the viewer opened, then quit.
#          scroll  down, down, 'j', then 'k': three lines on, one back.
#______________________________________________________________________________
source "$(dirname "${BASH_SOURCE[0]}")/support.sh"
source hwut_vterm.sh

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SAMPLE='## demo.sh race -- three workers
start
##! potpourri
worker B done: 5 jobs
worker A done: 3 jobs
worker C done: 2 jobs
####
all joined
## the order between the markers is
## free; the lines are not.'

show() {
    #  RETURN: 0; one region that changed printed: '-- <name>', then its
    #          rows '$2...' as they stand on the screen.
    echo "-- $1"
    shift
    (( $# )) && printf '%s\n' "$@"
    return 0
}

view() {
    #  RETURN: 0; the viewer ran on the sample, the keys '$@' pressed, 'q'
    #          sent, and what changed after each step printed;
    #          1, the library is missing (its text printed).
    local path=$HERE/TMP/race.txt key
    mkdir -p "${path%/*}"
    echo "$SAMPLE" > "$path"
    vterm_terminal_new terminal 9 40 || { echo "$VTERM_ERROR"; return 1; }
    vterm_region terminal title 0
    vterm_region terminal body 1 7
    vterm_region terminal status -1
    vterm_on_change terminal show
    echo "> viewer.sh race.txt"
    vterm_run terminal -- bash "$HERE/viewer.sh" "$path"
    vterm_cell terminal 0 1 cell
    vterm_cell_attribute_text cell
    echo "title bar: ${REPLY:-plain}"
    for key; do
        echo "> $key"
        if (( ${#key} == 1 )); then vterm_send terminal "$key"
        else                        vterm_press terminal "$key"
        fi
    done
    vterm_send terminal q
    vterm_wait terminal
    echo "> q -- exit status $REPLY"
    vterm_close terminal
}

case ${1-} in
    open)   view || exit 1 ;;
    scroll) view down down j k || exit 1 ;;
    *)      echo "choices: open, scroll"; exit 1 ;;
esac
echo "<hwut-end>"
