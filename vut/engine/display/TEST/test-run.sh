#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
# ---------------------------------------------------------------------------
#
# THE 'hwut.run' FACE, IN ITS NATURAL HABITAT: real bash test
# applications under the real dispatcher, driven from the shell. The
# wall clock is the user's stopwatch and no GOOD's business -- every
# 'hh:mm:ss' is masked by ONE substitution before comparison.
#
# EXIT STATUS under test (E-1): 0 green, 1 a test failed or a fault
# was met, 2 the command line cannot be read, 3 it reads and asks for
# nothing.
#
# THE COLOUR DECISION under test, not the escapes' spelling: piped is
# plain; '--colour' enforces, 'NO_COLOR' notwithstanding;
# '--no-colour' refuses.
#
# MANY DIRECTORIES (O-11..O-15): the flow tier may interleave across
# directories and is blessed THROUGH THE DIGEST FILTER 'test-run.pype'
# beside this file -- per directory, sorted; the closing blocks pass
# through verbatim. THE DIGEST IS STRATEGY-FREE: it records WHAT ran,
# not when. Every tree choice runs the LINEAR strategy and shows its
# digest, then runs every other strategy and shows that its digest is
# byte-identical -- the homogeneity law (O-15). '--strategy=linear
# --jobs=1' is blessed raw: the serial run of old.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../../.." && pwd)
RUN="python3 -m vut.services.run"
export PYTHONPATH="$ROOT"
export PATH="$ROOT/vut/bin:$PATH"    # '#! /usr/bin/env hwut.pype' filters
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "The hwut.run face: the tree run, rendered live."
        echo "CHOICES: green, fail, nostore, timing, empty, refused, tiers, colour, tree-green, tree-fail, jobs-budget, linear-raw, busy, strategy-refused;"
        echo "HAPPY: STATUS: [0-9];"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

mask() {                # hh:mm:ss -> the one masked token
    sed -E 's/[0-9]{2}:[0-9]{2}:[0-9]{2}/hh:mm:ss/g'
}

face() {                # <args...>  -- status, masked stdout, stderr
    $RUN "$@" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"
    mask < out.txt | sed 's/^/    /'
    echo "}"
    if [ -s err.txt ]; then
        echo "STDERR {"
        mask < err.txt | sed 's/^/    /'
        echo "}"
    fi
}

put() {                 # <path> <content...>
    printf '%s\n' "$2" > "$1"
}

digest() {              # <args...>  -- status, digested stdout, stderr
    #  '$?' after a pipe is the pipe's: the face's status is taken from
    #  PIPESTATUS. The digest filter sits beside this suite and is
    #  called by path; times are masked before it reads.
    $RUN "$@" 2> err.txt | mask | "$HERE/${PYPE:-test-run.pype}" > out.txt
    echo "STATUS: ${PIPESTATUS[0]}"
    echo "STDOUT {"
    sed 's/^/    /' < out.txt
    echo "}"
    if [ -s err.txt ]; then
        echo "STDERR {"
        mask < err.txt | sed 's/^/    /'
        echo "}"
    fi
}

every_strategy() {      # <args...> -- the linear digest shown, every
                        # other strategy's digest compared to it
    digest --strategy=linear "$@" | tee digest-linear.txt
    for strategy in successor parallel; do
        digest --strategy=$strategy "$@" > digest-$strategy.txt
        cmp -s digest-linear.txt digest-$strategy.txt \
            && echo "$strategy: digest identical to linear: True" \
            || { echo "$strategy: digest identical to linear: FALSE";
                 diff digest-linear.txt digest-$strategy.txt; }
    done
}

fixture_tree() {        # three directories, two passing tests each
    local d t
    for d in alpha beta gamma; do
        mkdir -p tree/$d/TEST/GOOD
        printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n}\n' \
            > tree/$d/TEST/hwut.conf
        for t in one two; do
            printf '#!/bin/bash\n# hwut { title = "%s" }\necho "steady %s"\necho "<hwut-end>"\n' \
                $t $t > tree/$d/TEST/test-$t.sh
            chmod +x tree/$d/TEST/test-$t.sh
            printf 'steady %s\n<hwut-end>\n' $t \
                > tree/$d/TEST/GOOD/test-$t.stdout
        done
    done
}

fixture_tree_fail() {   # the tree; one test of beta differs, gamma's
                        # entry fails and its tests never run
    fixture_tree
    put tree/beta/TEST/GOOD/test-two.stdout "what the GOOD expects"
    printf 'hwut {\n    on_entry = "false"\n    on_exit  = "true"\n}\n' \
        > tree/gamma/TEST/hwut.conf
}

fixture_green() {       # one directory, one passing test
    mkdir -p tree/suite/TEST/GOOD
    printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n}\n' \
        > tree/suite/TEST/hwut.conf
    printf '#!/bin/bash\n# hwut { title = "Ok" }\necho "steady line"\n' \
        > tree/suite/TEST/test-ok.sh
    chmod +x tree/suite/TEST/test-ok.sh
    put tree/suite/TEST/GOOD/test-ok.stdout "steady line"
}

fixture_fail() {        # the green one, one differing test beside it
    fixture_green
    printf '#!/bin/bash\n# hwut { title = "Diff" }\necho "what the run says"\n' \
        > tree/suite/TEST/test-diff.sh
    chmod +x tree/suite/TEST/test-diff.sh
    put tree/suite/TEST/GOOD/test-diff.stdout "what the GOOD expects"
}

fixture_fault() {       # a dependency the directory does not offer
    fixture_green
    printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n    dependency { "test-ok.sh" = ["required.dat"] }\n}\n' \
        > tree/suite/TEST/hwut.conf
}

case "$1" in

green)
    #  Everything stands: the flow, the roll-call, status 0.
    fixture_green
    face --directory=tree
    ;;

fail)
    #  One test differs: its phrase inline, the FAILURES block,
    #  status 1.
    fixture_fail
    face --directory=tree
    ;;

nostore)
    #  The store knob: '--no-store' leaves no candidate behind;
    #  the default records the subject beside its freshness sidecar.
    fixture_green
    face --directory=tree --no-store > /dev/null
    n=$(find tree -name "*.stdout" -not -path "*/GOOD/*" | wc -l)
    echo "candidates after --no-store: $n"
    rm -rf tree; fixture_green
    face --directory=tree > /dev/null
    n=$(find tree -name "*.stdout" -not -path "*/GOOD/*" | wc -l)
    s=$(find tree -name "*.when" | wc -l)
    echo "candidates after the default: $n   freshness sidecars: $s"
    ;;

timing)
    #  The cadence knob: '--timing' leaves a per-line delta list beside
    #  the candidate; the default leaves none. The DELTAS THEMSELVES
    #  are the machine's, so only their presence and their count are
    #  shown -- never a number the machine chose.
    fixture_green
    face --directory=tree > /dev/null
    n=$(find tree -name "*.times" | wc -l)
    echo "cadence sidecars by default: $n"
    rm -rf tree; fixture_green
    face --directory=tree --timing > /dev/null
    n=$(find tree -name "*.times" | wc -l)
    echo "cadence sidecars with --timing: $n"
    python3 -c "
import json, sys
d = json.load(open('tree/suite/TEST/.hwut-store/test-ok.stdout.times'))
print('unit: %s   deltas: %d   every delta a number: %s'
      % (d['unit'], len(d['delta_list']),
         all(isinstance(x, float) for x in d['delta_list'])))"
    #  ONE MEASUREMENT AT A TIME: refused beside '--coverage'.
    face --directory=tree --timing --coverage
    ;;

empty)
    #  The command line reads, and asks for nothing: status 3.
    fixture_green
    face --directory=tree --glob 'nothing-*'
    ;;

refused)
    #  Refused at the door, by name, with the usage line: status 2.
    fixture_green
    echo "== a directory that does not exist =="
    face --directory=nowhere-such-dir
    echo "== an option nobody knows =="
    face --directory=tree --frobnicate
    echo "== tiers beside one another =="
    face --directory=tree --silent --verbose
    echo "== colour beside no-colour =="
    face --directory=tree --colour --no-colour
    echo "== jobs without a number =="
    face --directory=tree --jobs=many
    ;;

tiers)
    #  QUIET keeps the closing blocks and the FAULTS met; SILENT
    #  keeps nothing on stdout and the fault on stderr, prefixed.
    fixture_fault
    echo "== --quiet =="
    face --directory=tree --quiet
    echo "== --silent =="
    face --directory=tree --silent
    echo "== --plain, statable redundantly =="
    fixture_green
    face --directory=tree --plain > plain.txt
    head -1 plain.txt
    ;;

colour)
    #  THE DECISION, not the escapes' spelling: presence alone.
    fixture_green
    verdict() {         # <label> <args...>
        label=$1; shift
        $RUN --directory=tree "$@" > c.txt 2> /dev/null
        n=$(tr -cd '\033' < c.txt | wc -c)
        if [ "$n" -gt 0 ]; then echo "$label: escapes present"
        else                    echo "$label: plain"
        fi
    }
    verdict "piped, nothing spoken     "
    verdict "--colour                  " --colour
    NO_COLOR=1 verdict "--colour, NO_COLOR set    " --colour
    verdict "--no-colour               " --no-colour
    ;;

tree-green)
    #  Three directories, all standing: the digest names every line of
    #  every directory; the roll-call in walk order; status 0 -- under
    #  every strategy alike.
    fixture_tree
    every_strategy --directory=tree
    ;;

tree-fail)
    #  One differing test, one failing entry frame beside two running
    #  directories: attribution per directory, the FAILURES block in
    #  walk order, status 1 -- under every strategy alike.
    fixture_tree_fail
    every_strategy --directory=tree
    ;;

jobs-budget)
    #  '--jobs' is HOST-GLOBAL: two slots across three directories
    #  means at most two pieces of work ever stand at once; with one
    #  slot, one. The digest counts [START]/[END] and names the peak --
    #  the same peak under every strategy.
    fixture_tree
    echo "== --jobs=2 =="
    PYPE=test-run--jobs-budget.pype every_strategy --directory=tree --jobs=2
    echo "== --jobs=1 =="
    PYPE=test-run--jobs-budget.pype every_strategy --directory=tree --jobs=1
    ;;

linear-raw)
    #  The linear strategy with one slot is the serial run of old:
    #  directories in walk order, one piece of work at a time -- the
    #  flow blessed RAW; '--dbd' and its long spelling say the same.
    fixture_tree_fail
    echo "== --strategy=linear --jobs=1 =="
    face --directory=tree --strategy=linear --jobs=1
    echo "== --dbd --jobs=1 =="
    face --directory=tree --dbd --jobs=1 --quiet
    echo "== --directory-by-directory, the long spelling =="
    face --directory=tree --directory-by-directory --jobs=1 --quiet
    ;;

strategy-refused)
    #  A strategy nobody knows is refused at the door, the known ones
    #  named; status REFUSED.
    face --directory=tree --strategy=bogus
    ;;

busy)
    #  A directory HELD BY A LIVE PROCESS is refused at its door, a
    #  fault; its siblings run to a good end beside it; status 1.
    fixture_tree
    mkdir -p tree/beta/TEST/.hwut-lock
    python3 - tree/beta/TEST/.hwut-lock/holder.json <<'PY' &
import json, os, sys, time, psutil
json.dump({"pid": os.getpid(),
           "started": psutil.Process().create_time()},
          open(sys.argv[1], "w"))
time.sleep(60)
PY
    holder=$!
    while [ ! -s tree/beta/TEST/.hwut-lock/holder.json ]; do sleep 0.05; done
    every_strategy --directory=tree
    echo "== --quiet: the fault in the closing FAULTS block =="
    every_strategy --directory=tree --quiet
    kill $holder 2> /dev/null; wait $holder 2> /dev/null
    ;;

*)
    echo "unknown choice '$1'"
    exit 1 ;;
esac
