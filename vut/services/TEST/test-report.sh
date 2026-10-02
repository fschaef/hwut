#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "The hwut.report face: the databases, rendered."
#     choices    = ["color", "json", "junit", "never_run", "not_in_book",
#                   "refused", "stain", "tap", "traditional", "width",
#                   "run_agrees", "run_width"]
# }
#
# ---------------------------------------------------------------------------
#
# THE 'hwut.report' FACE -- what the result databases hold, rendered
# for somebody else.
#
# NOTE: these fixtures state no 'title' in their 'hwut.conf', so the
# directory TITLE is absent and the page omits it -- itself pinned.
# The 'color' choice states one (X-INFO-DAT: the title is a conf
# key; 'hwut-info.dat' is a relic and unread).
#
# traditional  the HWUT page at a stated width: the per-directory
#              blocks, the summary with its prefix-elided directory
#              column, the failures listed once more, the total.
# width        the page fills what it is given: the same report at two
#              widths, the verdicts right-aligned in both.
# junit        the XML, well-formed, and PARSED to prove it.
# tap          version 13, the plan first.
# json         the document, its verdicts true/false/null.
# stain        A STAIN IS A FAILURE IN EVERY FORMAT, never a 'skipped':
#              JUnit goes red and the message names it.
# never_run    a case with no GOOD file, which the books never saw:
#              'no GOOD file [FAIL]', a failure in every format (display
#              D-32), and the page counts it.
# not_in_book  a GOOD file stands and 'GOOD/book.csv' has no row for the
#              case: 'not in book [FAIL]' (display D-37), with the
#              pointer to 'hwut.help'; after a run the row stands and
#              the case reads '[OK]'.
# refused      an unknown format, a bad width, an unknown option, a
#              directory that is not there.
# run_width    THE REPORT IS AS WIDE AS THE RUN (display D-33): the widest
#              line of each, piped, piped under 'COLUMNS=100', and on a
#              terminal of 60, 100 and 200 columns (a pty).
# run_agrees   EVERY FAILURE THE RUN COUNTS, THE REPORT SHOWS (E-128):
#              a header that does not parse, a test and a choice the book
#              records and the tree no longer declares, a case whose
#              dependency cannot be met, a case with no GOOD file, a
#              plain difference. The run's
#              failing cases and the report's, side by side, and equal;
#              then the page, each failure but the plain difference
#              carrying its reason word before '[FAIL]' (display D-31).
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
FACE="python3 -m vut.services.report"
RUN="python3 -m vut.services.run"
STABILITY="python3 -m vut.services.lib.run.stability"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "The hwut.report face: the databases, rendered.;"
        echo "CHOICES: traditional, width, junit, tap, json, stain, never_run, not_in_book, refused, color, run_agrees, run_width;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

#  THE TREE'S BOUNDARY. Every face ASCENDS collecting 'hwut.conf'
#  until it meets this file; a tree without one is refused, so a
#  fixture states its own. Empty says only 'the tree ends here'.
printf 'hwut {\n}\n' > hwut-root.conf

face() {
    $FACE "$@" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"; sed 's/^/    /' < out.txt; echo "}"
    if [ -s err.txt ]; then
        echo "STDERR {"; sed 's/^/    /' < err.txt; echo "}"
    fi
}

mask() {    # the recorded instant is the machine's
    sed -E 's/[0-9]{4}y[0-9]{2}m[0-9]{2}d [0-9]{2}h[0-9]{2}/YYYYyMMmDDd hhhmm/g
            s/"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]+Z"/"<instant>"/g'
}

masked() {
    $FACE "$@" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"; mask < out.txt | sed 's/^/    /'; echo "}"
}

fixture() {         # <body...> -- one directory, one app, run
    mkdir -p tree/suite/TEST/GOOD
    printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n}\n' \
        > tree/suite/TEST/hwut.conf
    { echo '#!/bin/bash'; printf '%s\n' "$@"; } > tree/suite/TEST/test-app.sh
    chmod +x tree/suite/TEST/test-app.sh
}

good_app() { fixture '# @hwut { title = "The steady one" }' \
                     'echo "steady line"' 'echo "<hwut-end>"'; }

mixed() {           # one standing, one differing
    good_app
    printf 'steady line\n<hwut-end>\n' > tree/suite/TEST/GOOD/test-app.sh.txt
    printf '#!/bin/bash\n# @hwut { title = "The differing one" }\necho "what the run says"\necho "<hwut-end>"\n' \
        > tree/suite/TEST/test-diff.sh
    chmod +x tree/suite/TEST/test-diff.sh
    printf 'what the GOOD expects\n<hwut-end>\n' \
        > tree/suite/TEST/GOOD/test-diff.sh.txt
    $RUN --directory=tree --silent > /dev/null 2>&1
}

flipping() {
    fixture '# @hwut { title = "The flip" }' \
            'n=0' '[ -f count.txt ] && n=$(cat count.txt)' \
            'echo $((n + 1)) > count.txt' \
            'if [ $((n % 2)) -eq 0 ]; then echo "steady line";' \
            'else echo "other"; fi' 'echo "<hwut-end>"'
    printf 'steady line\n<hwut-end>\n' > tree/suite/TEST/GOOD/test-app.sh.txt
}

# ---------------------------------------------------------------------------
case "$1" in

traditional)
    mixed
    masked --directory=tree --width=78
    ;;

width)
    #  The page fills what it is given; the verdicts stay in a line.
    mixed
    echo "--- 60 columns"
    masked --directory=tree --width=60
    echo "--- 100 columns"
    masked --directory=tree --width=100
    ;;

junit)
    mixed
    masked --directory=tree --format=junit
    echo "--- and it parses:"
    $FACE --directory=tree --format=junit --out=r.xml > /dev/null 2>&1
    python3 -c "
import xml.dom.minidom as m
d = m.parse('r.xml')
s = d.getElementsByTagName('testsuites')[0]
print('    testsuites tests=%s failures=%s'
      % (s.getAttribute('tests'), s.getAttribute('failures')))"
    ;;

tap)
    mixed
    masked --directory=tree --format=tap
    ;;

json)
    mixed
    masked --directory=tree --format=json
    ;;

stain)
    #  A STAIN IS A FAILURE IN EVERY FORMAT -- never a 'skipped'.
    flipping
    $STABILITY --directory=tree --repeat=4 > /dev/null 2>&1
    echo "--- traditional"
    masked --directory=tree --width=70
    echo "--- junit"
    masked --directory=tree --format=junit
    echo "--- tap"
    masked --directory=tree --format=tap
    ;;

never_run)
    #  No GOOD file, and the books never saw it: 'no GOOD file [FAIL]'.
    good_app
    echo "--- traditional"
    masked --directory=tree --width=70
    echo "--- json"
    masked --directory=tree --format=json
    ;;

not_in_book)
    #  A GOOD FILE THE BOOK NEVER SAW (D-37).
    good_app
    printf 'steady line\n<hwut-end>\n' > tree/suite/TEST/GOOD/test-app.sh.txt
    echo "--- before any run"
    masked --directory=tree --width=70
    $RUN --directory=tree --silent > /dev/null 2>&1
    echo "--- after a run"
    masked --directory=tree --width=70
    ;;

refused)
    mixed
    face --directory=tree --format=yaml
    face --directory=tree --width=0
    face --directory=tree --sideways
    face --directory=nowhere
    ;;

color)
    #  THE PAGE'S COLOURS (E-69): the title block on orange, '[OK]' on
    #  green, '[FAIL]' on red. The suite drives every face through a
    #  PIPE, where the page is plain by design, so '--color' is what
    #  lets a recorded GOOD see the escapes at all. They are spelled
    #  'ESC' here: a raw escape byte in a nominal is unreadable in a
    #  diff and a hazard to whatever prints it.
    mixed
    #  X-INFO-DAT: the title is a key of 'hwut.conf'; the relic is no
    #  longer read, and the fixture states it where the page looks.
    printf 'hwut {\n    title = "A fixture title"\n}\n' \
        > tree/suite/TEST/hwut.conf
    $FACE --directory=tree --width=70 --color \
        | sed -e 's/\x1b/ESC/g' | mask | sed 's/^/    /'
    echo "--- and the same page, piped, is plain"
    $FACE --directory=tree --width=70 | grep -c ESC | sed 's/^/    ESC count: /'
    ;;

run_width)
    mixed
    widest() { awk '{ n = length($0); if (n > m) m = n } END { print m }'; }
    echo "piped:              run $($RUN --directory=tree --plain | widest)" \
         " report $($FACE --directory=tree --plain | widest)"
    echo "piped, COLUMNS=100: run $(COLUMNS=100 $RUN --directory=tree --plain | widest)" \
         " report $(COLUMNS=100 $FACE --directory=tree --plain | widest)"
    for cols in 60 100 200; do
        printf 'terminal of %3d:   ' $cols
        for face in run report; do
            python3 - "$face" "$cols" <<'PYEOF'
import fcntl, os, pty, re, struct, sys, termios
face, cols = sys.argv[1], int(sys.argv[2])
pid, fd = pty.fork()
if pid == 0:
    fcntl.ioctl(1, termios.TIOCSWINSZ, struct.pack("HHHH", 50, cols, 0, 0))
    env = dict(os.environ); env.pop("COLUMNS", None)
    os.execvpe(sys.executable, [sys.executable, "-m", "vut.services." + face,
                                "--directory=tree", "--plain"], env)
out = b""
while True:
    try:    chunk = os.read(fd, 4096)
    except OSError: break
    if not chunk: break
    out += chunk
os.waitpid(pid, 0)
text = re.sub(rb"\x1b\[[0-9;?]*[A-Za-z]", b"", out).decode(errors="replace")
print(" %s %d" % (face, max(len(l) for l in re.split(r"[\r\n]", text))), end="")
PYEOF
        done
        echo
    done
    ;;

run_agrees)
    T=tree/suite/TEST
    mkdir -p $T/GOOD
    app() {     # <file> <header words> -- prints its first argument
        printf '#!/bin/bash\n# @hwut { title = "%s" %s }\necho "$1"\necho "<hwut-end>"\n' \
            "$1" "$2" > $T/$1
        chmod +x $T/$1
    }
    printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n}\n' > $T/hwut.conf
    app test-ok.sh   ''
    app test-ch.sh   'choices = ["one", "two"]'
    app test-gone.sh ''
    app test-dep.sh  ''
    app test-diff.sh ''
    app test-new.sh  ''                                   # no GOOD file
    ( cd $T && for t in test-ok.sh test-ch.sh test-gone.sh test-dep.sh test-diff.sh; do
          python3 -m vut.services.accept $t --whole --dont-ask > /dev/null 2>&1
      done )
    $RUN --directory=tree --silent > /dev/null 2>&1
    #  THE DAMAGE, each kind once.
    sed -i 's/"one", "two"/"one"/' $T/test-ch.sh          # a choice vanished
    rm $T/GOOD/test-ch.sh--two.txt
    rm $T/test-gone.sh                                    # a test vanished
    printf '#!/bin/bash\n# @hwut { title = "B" frobnicate = 1 }\necho b\n' \
        > $T/test-broken.sh                               # a broken header
    chmod +x $T/test-broken.sh
    printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n    dependency { "test-dep.sh" = ["test-ghost.sh"] }\n}\n' \
        > $T/hwut.conf                                    # a dependency lost
    printf 'other\n<hwut-end>\n' > $T/GOOD/test-diff.sh.txt # a difference
    $RUN --directory=tree --plain > run.txt 2>&1
    echo "RUN STATUS: $?"
    $FACE --directory=tree --format=tap > report.txt 2>&1
    echo "REPORT STATUS: $?"
    grep -E '^[A-Z ]{5} ' run.txt | grep '\[FAIL\]' \
        | sed -E 's/^.{6}//; s/ *\.{3,}.*//; s/  +/ /g' | sort > run-fail.txt
    grep '^not ok' report.txt | sed -E 's/^not ok [0-9]+ - suite\/TEST: //' \
        | sort > report-fail.txt
    echo "RUN FAILS {";    sed 's/^/    /' run-fail.txt;    echo "}"
    echo "REPORT FAILS {"; sed 's/^/    /' report-fail.txt; echo "}"
    echo "the same: $(cmp -s run-fail.txt report-fail.txt && echo yes || echo NO)"
    #  THE REASON WORD BEFORE '[FAIL]' (display D-31): each kind but
    #  the plain difference carries its word.
    echo "PAGE {"
    $FACE --directory=tree --width=70 | grep '\[FAIL\]$' | grep -v '^ *[0-9]' \
        | sed 's/^/    /'
    echo "}"
    ;;

*)
    echo "no such choice: $1"
    exit 1 ;;
esac

echo "<hwut-end>"
