#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# THE SCREENSHOTS OF THE LANDING PAGE, made from real runs.
#
#     adm/screenshots/make.sh [OUTDIR]          default: vut/doc/img
#
# Works on a COPY of the tree. It breaks one line of the demo, builds
# two small scenes beside it (an invoice whose behaviour changed;
# three programs that fail for reasons other than a difference), runs
# the commands in a terminal of fixed size under tmux, and renders what
# the terminal showed as PNG. Needs: tmux, python3 with the packages the
# tree imports plus 'playwright' and a chromium (PW_CHROMIUM names one).
HERE=$(cd "$(dirname "$0")" && pwd)
VUT=$(cd "$HERE/../.." && pwd)
OUT=$(mkdir -p "${1:-$VUT/doc/img}" && cd "${1:-$VUT/doc/img}" && pwd)
WORK=$(mktemp -d)
trap 'tmux kill-session -t hwut-shot 2>/dev/null; rm -rf "$WORK"' EXIT
cp -r "$VUT" "$WORK/vut"
rm -rf "$WORK/vut/.git" "$WORK"/vut/demo/*/TEST/OUT
export PYTHONPATH="$WORK${PYTHONPATH:+:$PYTHONPATH}" COLUMNS=100 TERM=xterm-256color
BIN="$WORK/vut/bin"
DEMO="$WORK/vut/demo/python/TEST"

scene() {           # scene DIR FILE TITLE BODY -- one program, one choice, accepted
    mkdir -p "$1/GOOD"
    printf '#! /bin/bash\n# @hwut {\n#     title   = "%s"\n#     choices { %s { } }\n# }\n%s\n' \
        "$3" "$5" "$4" > "$1/$2"
    chmod +x "$1/$2"
    (cd "$1" && "$BIN/hwut.accept" --whole "$2" "$5" > /dev/null 2>&1)
}

#  the demo, one line broken
sed -i 's/1 2 3/1 2 4/' "$DEMO/demo.py"

#  scene: an invoice whose behaviour changed
INV="$WORK/vut/demo/acceptscene/TEST"
scene "$INV" invoice.sh "Scene: a report whose behaviour changed" \
'echo "invoice 4711"; echo "  3 x widget        30.00"; echo "  2 x gadget        25.00"
echo "  1 x gizmo         12.50"; echo "net               67.50"; echo "tax 19%           12.83"
echo "total             80.33"; echo "<hwut-end>"' totals
sed -i 's/3 x widget        30.00/4 x widget        40.00/; s/67.50/77.50/; s/12.83/14.73/; s/80.33/92.23/' "$INV/invoice.sh"
(cd "$INV" && "$BIN/hwut.run" --plain invoice.sh totals > /dev/null 2>&1)

#  scene: failures that are not a plain difference
HLP="$WORK/vut/demo/helpscene/TEST"
scene "$HLP" forgot.sh "Scene: stops before it is done" 'echo "step one"; echo "step two"; echo "<hwut-end>"' go
scene "$HLP" crash.sh  "Scene: dies"                   'echo "step one"; echo "<hwut-end>"' go
scene "$HLP" build.sh  "Scene: does not build"         'echo "building"; echo "<hwut-end>"' go
sed -i 's/; echo "<hwut-end>"//' "$HLP/forgot.sh"
sed -i 's/echo "step one"; echo "<hwut-end>"/echo "step one"; echo "boom" >\&2; exit 3/' "$HLP/crash.sh"
sed -i 's/echo "building"; echo "<hwut-end>"/echo "building"; nosuchcommand_xyz; echo "<hwut-end>"/' "$HLP/build.sh"
(cd "$HLP" && "$BIN/hwut.run" --plain > /dev/null 2>&1)

snap() {            # snap NAME DIR ROWS TITLE COMMAND [KEY...]
    local name=$1 dir=$2 rows=$3 title=$4 cmd=$5; shift 5
    tmux kill-session -t hwut-shot 2>/dev/null
    tmux new-session -d -s hwut-shot -x 100 -y "$rows" \
        "cd $dir && export PS1='\$ ' PATH=$BIN:\$PATH && bash --norc -i"
    sleep 0.5; tmux send-keys -t hwut-shot "$cmd" Enter; sleep 4
    for k in "$@"; do tmux send-keys -t hwut-shot "$k"; sleep 1; done
    tmux capture-pane -t hwut-shot -e -p > "$WORK/$name.ans"
    python3 "$HERE/render.py" "$WORK/$name.ans" "$OUT/$name.png" "$title"
}

snap hwut-run                "$DEMO" 24 'demo/python/TEST $ hwut'                          'hwut'
snap hwut-run-diff           "$DEMO"  8 'hwut.run.diff -y demo.py plain'                   'hwut.run.diff -y demo.py plain'
snap hwut-accept-interactive "$INV"  13 'hwut.accept.interactive invoice.sh totals (two takes made)' \
     'hwut.accept.interactive invoice.sh totals' j Enter j j j Enter
snap hwut-report             "$DEMO" 30 'hwut.report'                                      'hwut.report'
snap hwut-help               "$HLP"  42 'hwut.help'                                        'hwut.help'
echo "screenshots in $OUT"
