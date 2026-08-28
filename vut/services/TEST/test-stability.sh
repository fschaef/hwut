#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# hwut {
#     title      = "The hwut.stability face: what did not stay the same."
#     choices    = ["bytes", "cadence", "length", "refused", "stain",
#                   "steady", "verbose", "verdict"]
#     eq-pattern = ["STATUS: [0-9]"]
# }
#
# ---------------------------------------------------------------------------
#
# THE 'hwut.stability' FACE -- the same wish run several times, and what
# did not stay the same.
#
# THE FIXTURES ARE DELIBERATELY UNSTEADY, which is the difficulty: a
# suite whose subject is instability must be steady ABOUT it. Each
# fixture is unsteady in exactly one way and steady in every other, and
# the face prints COUNTS AND NAMES, never a delta or a ratio -- so what
# is blessed here is what the face FOUND, never what the machine timed.
#
# steady      a tree where nothing moves: the steady statement, tally,
#             status 0.
# verdict     a test that flips its own output: THE FAULT -- the verdict
#             word differs between repeats, status 1.
# bytes       a number that drifts inside a numeric tolerance: same
#             verdict, differing bytes. A warning; status stays 0.
# length      lines swallowed by a 'nothing' pattern, a differing number
#             of them each run: the cadence cannot be aligned, so it is
#             not timed. A warning.
# cadence     one line preceded by a wait that is never the same twice:
#             the unsteady LINE is named. A warning.
# verbose     the same, with '--verbose': the numbers appear. Only the
#             SHAPE is blessed -- the numbers are masked, being the
#             machine's.
# refused     every door: an unreadable wish, a bad '--repeat', a bad
#             '--rt-max', a bad '--epsilon', an unknown option, a
#             directory that is not there.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
FACE="python3 -m vut.services.stability"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "The hwut.stability face: what did not stay the same.;"
        echo "CHOICES: steady, verdict, bytes, length, cadence, verbose, stain, refused;"
        echo "HAPPY: STATUS: [0-9];"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

#  THE TREE'S BOUNDARY. Every face ASCENDS collecting 'hwut.conf'
#  until it meets this file; a tree without one is refused, so a
#  fixture states its own. Empty says only 'the tree ends here'.
printf 'hwut {\n}\n' > hwut-root.conf

face() {                # <args...> -- status and stdout
    $FACE "$@" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"
    sed 's/^/    /' < out.txt
    echo "}"
    if [ -s err.txt ]; then
        echo "STDERR {"
        sed 's/^/    /' < err.txt
        echo "}"
    fi
}

mask() {                # THE ELAPSED STAMP IS THE MACHINE'S: a run
                        # that crosses a second prints a different
                        # one, and a GOOD holding it would be a lie.
    sed -E 's/[0-9]{2}:[0-9]{2}:[0-9]{2}/hh:mm:ss/g'
}

masked() {              # <args...> -- as 'face', every number the
                        # machine chose replaced by a token
    $FACE "$@" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"
    sed -E 's/spread=[0-9]+\.[0-9]+s/spread=<s>/; s/factor=[0-9]+x/factor=<f>/; s/[0-9]+\.[0-9]{6}/<delta>/g' \
        < out.txt | sed 's/^/    /'
    echo "}"
}

conf() {                # <extra-lines...>
    mkdir -p tree/suite/TEST/GOOD
    { echo 'hwut {'
      echo '    on_entry = "true"'
      echo '    on_exit  = "true"'
      printf '%s\n' "$@"
      echo '}'
    } > tree/suite/TEST/hwut.conf
}

app() {                 # <name> <body...>
    { echo '#!/bin/bash'
      echo "# hwut { title = \"$1\" }"
      shift
      printf '%s\n' "$@"
    } > tree/suite/TEST/test-app.sh
    chmod +x tree/suite/TEST/test-app.sh
}

good() {                # <line...>
    printf '%s\n' "$@" > tree/suite/TEST/GOOD/test-app.sh.txt
}

# ---------------------------------------------------------------------------
case "$1" in

steady)
    #  Nothing moves: the steady statement, and the tally counts it.
    conf
    app "Steady" 'echo "steady line"'
    good "steady line"
    face --directory=tree
    ;;

verdict)
    #  THE FAULT. The test alternates its own output by a counter it
    #  keeps in a file -- deterministic in the SEQUENCE, so the verdict
    #  words are the same on every host: ok, test-failed, ok, ...
    conf
    app "Flip" \
        'n=0' \
        '[ -f count.txt ] && n=$(cat count.txt)' \
        'echo $((n + 1)) > count.txt' \
        'if [ $((n % 2)) -eq 0 ]; then echo "steady line";' \
        'else echo "other line"; fi'
    good "steady line"
    face --directory=tree --repeat=4
    ;;

bytes)
    #  TRAILING WHITESPACE, a differing amount each run. Whitespace is
    #  tolerant by default, so the verdict holds while the recorded
    #  bytes do not -- the tolerance absorbing it is the point. The
    #  amount follows a counter, so the SEQUENCE is the same on every
    #  host and only the finding is blessed.
    conf
    app "Drift" \
        'n=0' \
        '[ -f count.txt ] && n=$(cat count.txt)' \
        'echo $((n + 1)) > count.txt' \
        'printf "steady line%*s\\n" $n ""'
    good "steady line"
    face --directory=tree --repeat=3
    ;;

length)
    #  Lines a 'nothing' pattern swallows, a differing NUMBER of them
    #  each run: the verdict holds, the cadence cannot be aligned.
    conf '    test-app.sh { nothing = ["noise.*"] }'
    app "Length" \
        'n=0' \
        '[ -f count.txt ] && n=$(cat count.txt)' \
        'echo $((n + 1)) > count.txt' \
        'echo "steady line"' \
        'for i in $(seq 0 $n); do echo "noise $i"; done'
    good "steady line"
    face --directory=tree --repeat=3 --cadence
    ;;

cadence)
    #  One line preceded by a wait that alternates long and short: the
    #  UNSTEADY LINE is named, and it is line 3.
    conf
    app "Cadence" \
        'n=0' \
        '[ -f count.txt ] && n=$(cat count.txt)' \
        'echo $((n + 1)) > count.txt' \
        'echo "line one"' \
        'echo "line two"' \
        'if [ $n -eq 0 ]; then sleep 6; fi' \
        'echo "line three"' \
        'echo "line four"'
    good "line one" "line two" "line three" "line four"
    face --directory=tree --repeat=4 --cadence
    ;;

verbose)
    #  '--verbose' opens the numbers. They are the machine's, so they
    #  are MASKED here: what is blessed is that the detail line stands
    #  and what its shape is.
    conf
    app "Cadence" \
        'n=0' \
        '[ -f count.txt ] && n=$(cat count.txt)' \
        'echo $((n + 1)) > count.txt' \
        'echo "line one"' \
        'echo "line two"' \
        'if [ $n -eq 0 ]; then sleep 6; fi' \
        'echo "line three"'
    good "line one" "line two" "line three"
    masked --directory=tree --repeat=4 --cadence --verbose
    ;;

stain)
    #  THE WHOLE CYCLE, in one reading: convict, refuse to run, refuse
    #  to bless, fail to clear with too few repeats, clear with enough,
    #  run again.
    conf
    app "Flip" \
        'n=0' \
        '[ -f count.txt ] && n=$(cat count.txt)' \
        'echo $((n + 1)) > count.txt' \
        'if [ $((n % 2)) -eq 0 ]; then echo "steady line";' \
        'else echo "other line"; fi'
    good "steady line"

    echo "--- 1. hwut.stability convicts over 4 repeats"
    face --directory=tree --repeat=4

    echo "--- 2. hwut.run does not run it: unstable, the directory fails"
    python3 -m vut.services.run --directory=tree --plain > run.txt 2>&1
    echo "STATUS: $?"
    grep -E "UNSTABLE|unstable|of +1 ok" run.txt | mask

    echo "--- 3. hwut.accept refuses to bless it"
    (cd tree/suite/TEST \
     && PYTHONPATH="$ROOT" python3 -m vut.services.accept --yes 2>&1 \
        | head -4)

    echo "--- 4. the test is mended; 2 repeats do not answer a 4-repeat charge"
    app "Mended" 'echo "steady line"'
    face --directory=tree --repeat=2

    echo "--- 5. four repeats do"
    face --directory=tree --repeat=4

    echo "--- 6. and it runs again"
    python3 -m vut.services.run --directory=tree --plain > run.txt 2>&1
    echo "STATUS: $?"
    grep -E "of +1 ok" run.txt | mask
    ;;

refused)
    #  Every door, by name, with the usage line.
    conf
    app "Steady" 'echo "steady line"'
    good "steady line"
    face --directory=tree --repeat=1
    face --directory=tree --repeat=two
    face --directory=tree --rt-max=-1
    face --directory=tree --epsilon=soon
    face --directory=tree --strategy=hopeful
    face --directory=tree --sideways
    face --directory=nowhere
    ;;

*)
    echo "no such choice: $1"
    exit 1 ;;
esac
