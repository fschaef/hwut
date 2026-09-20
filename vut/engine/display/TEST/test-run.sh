#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "The hwut.run face: the tree run, rendered live."
#     choices    = ["busy", "colour", "empty", "fail", "green",
#                   "tree-ink",
#                   "jobs-budget", "labels", "linear-raw", "nostore",
#                   "refused", "short-form", "strategy-refused",
#                   "tiers", "timing", "tree-fail", "tree-green"]
#     tolerance { eq_pattern = ["STATUS: [0-9]", ", [0-9]+\\.[0-9]+ \\[sec\\]"] }
# }
#
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
# THE LABELS (disc-8): a bare run SILENCES what the standard label
# marks; naming a label lifts the silence; a label that does not
# stand is refused by name. The view is built at the boundary before
# anything runs; a broken 'hwut-root.labels' is a FAULT at the door.
# AN EXPLICIT LITERAL TARGET OVERRIDES THE SILENCE; a glob does not,
# and where it meets only silenced runs it WARNS, naming the remedy.
#
# THE SHORT FORM OF HWUT 1.0: 'hwut.run test-app.sh one' -- bare
# words are targets, the first naming files, each further one a
# choice, globbing allowed in both. Sugar for '--glob' and nothing
# else.
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
ACCEPT="python3 -m vut.services.accept"
export PYTHONPATH="$ROOT"
export PATH="$ROOT/vut/bin:$PATH"    # '#! /usr/bin/env hwut.pype' filters
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "The hwut.run face: the tree run, rendered live.;"
        echo "CHOICES: green, fail, nostore, timing, empty, refused, tiers, colour, tree-green, tree-fail, jobs-budget, linear-raw, busy, strategy-refused, labels, short-form;"
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

mask() {                # THE RAW PATH's deterministicalization: the
                        # wall clock and the mktemp ground are facts
                        # about the machine and the morning, not
                        # about the subject. The DIGESTED path is
                        # masked by 'test-run.pype', which swallows
                        # these and the flow's own columns besides.
    sed -E "s/[0-9]{2}:[0-9]{2}:[0-9]{2}/hh:mm:ss/g; s|$WORK|WORK|g"
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

app() {                 # <dir> <name> <title> <prints> [<nominal>]
                        # A test application whose nominal is RECORDED
                        # THROUGH hwut's own face -- 'accept --whole'
                        # provisions the candidate and takes it as it
                        # stands (E-109) -- so the book and the register
                        # hold it as a user's would (E-41). With a fifth
                        # word, the nominal is that and the application
                        # then prints the fourth: the failing fixture,
                        # made the way a failure is made -- accepted
                        # once, changed since. '\n' in a text is a line
                        # break, so a text may carry '<hwut-end>'.
    local dir=$1 name=$2 title=$3 prints=$4 nominal=${5:-$4}
    printf '#!/bin/bash\n# @hwut { title = "%s" }\nprintf "%%b\\n" "%s"\n' \
        "$title" "$nominal" > "$dir/$name"
    chmod +x "$dir/$name"
    $ACCEPT --whole --directory="$dir" "$name" > /dev/null 2>&1 \
        || { echo "FAULT: the fixture's nominal of '$name' was not recorded"; exit 1; }
    [ "$nominal" = "$prints" ] \
        || printf '#!/bin/bash\n# @hwut { title = "%s" }\nprintf "%%b\\n" "%s"\n' \
               "$title" "$prints" > "$dir/$name"
    #  THE CANDIDATE accept provisioned is NOT the fixture's: the run
    #  under test must RUN, not replay a recording -- a rewrite within
    #  the same second reads as current by mtime -- and a '--no-store'
    #  run must find no candidate it did not make. The book stays.
    rm -rf "$dir/TMP" "$dir/OUT"
}

digest() {              # <args...>  -- status, digested stdout, stderr
    #  '$?' after a pipe is the pipe's: the face's status is taken from
    #  PIPESTATUS. The digest filter sits beside this suite and is
    #  called by path; IT masks the clock and the job column, and the
    #  ground is masked after it, on what it passed through.
    $RUN "$@" 2> err.txt | "$HERE/${PYPE:-test-run.pype}" \
        | mask > out.txt
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

fixture_tree() {        # [<beta-two-nominal>] -- three directories,
                        # two passing tests each; with the word, beta's
                        # second test was accepted saying THAT, and
                        # differs now
    local d t
    for d in alpha beta gamma; do
        mkdir -p tree/$d/TEST/GOOD
        printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n}\n' \
            > tree/$d/TEST/hwut.conf
        for t in one two; do
            if [ "$d/$t" = "beta/two" ] && [ -n "$1" ]; then
                app tree/$d/TEST test-$t.sh $t "steady $t\n<hwut-end>" "$1"
            else
                app tree/$d/TEST test-$t.sh $t "steady $t\n<hwut-end>"
            fi
        done
    done
}

fixture_tree_fail() {   # the tree; one test of beta differs, gamma's
                        # entry fails and its tests never run
    fixture_tree "what the GOOD expects\n<hwut-end>"
    printf 'hwut {\n    on_entry = "false"\n    on_exit  = "true"\n}\n' \
        > tree/gamma/TEST/hwut.conf
}

fixture_green() {       # one directory, one passing test
    mkdir -p tree/suite/TEST/GOOD
    printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n}\n' \
        > tree/suite/TEST/hwut.conf
    app tree/suite/TEST test-ok.sh Ok "steady line\n<hwut-end>"
}

fixture_fail() {        # the green one, one differing test beside it
    fixture_green
    app tree/suite/TEST test-diff.sh Diff "what the run says\n<hwut-end>" \
                                          "what the GOOD expects\n<hwut-end>"
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
    #  A CANDIDATE STANDS IN 'OUT/' AS '<key>.txt' -- the nominal's own
    #  spelling; only the directory tells them apart.
    n=$(find tree -path "*/OUT/*.txt" | wc -l)
    echo "candidates after --no-store: $n"
    rm -rf tree; fixture_green
    face --directory=tree > /dev/null
    n=$(find tree -path "*/OUT/*.txt" | wc -l)
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
d = json.load(open('tree/suite/TEST/TMP/store/test-ok.sh.stdout.times'))
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

tree-ink)
    #  THE TREE'S INK, BY CODE NOT BY EYE (display D-12). Escapes are
    #  made visible and the tree lines are kept; each is then reduced
    #  to the SEQUENCE OF SGR CODES it carries, so the oracle states
    #  which colour paints which part and nothing else:
    #      38;5;208  orange  the tree and a junction's name
    #      32        green   the road to a leaf, its '/' included
    #      38;5;196  red     the TEST directory itself
    fixture_tree
    #  and one JUNCTION: a directory that only leads somewhere, to
    #  TWO places -- one would collapse into its child's road.
    for d in inner other; do
        mkdir -p tree/deep/$d/TEST/GOOD
        printf 'hwut {\n}\n' > tree/deep/$d/TEST/hwut.conf
        app tree/deep/$d/TEST test-d.sh d "d\n<hwut-end>"
    done
    $RUN --directory=tree --colour 2> /dev/null \
        | sed -n '/^DIRECTORIES/,/^====/p' \
        | grep -e "+---" -e "'---" \
        | sed 's/\x1b\[\([0-9;]*\)m/<\1>/g; s/<0>//g' \
        | sed 's/ <2>.*$//' \
        | sed 's/^ *//'
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
    #  '--start-delay=0': this choice counts the most work standing at
    #  once by pairing START against END, so every START must exist.
    #  Held back, whether a line STANDS AT ALL would depend on the
    #  speed of the machine -- the one thing a GOOD may never hold.
    PYPE=test-run--jobs-budget.pype every_strategy --directory=tree \
        --jobs=2 --start-delay=0
    echo "== --jobs=1 =="
    PYPE=test-run--jobs-budget.pype every_strategy --directory=tree \
        --jobs=1 --start-delay=0
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
    mkdir -p tree/beta/TEST/TMP/lock
    python3 - tree/beta/TEST/TMP/lock/holder.json <<'PY' &
import json, os, sys, time, psutil
json.dump({"pid": os.getpid(),
           "started": psutil.Process().create_time()},
          open(sys.argv[1], "w"))
time.sleep(60)
PY
    holder=$!
    while [ ! -s tree/beta/TEST/TMP/lock/holder.json ]; do sleep 0.05; done
    every_strategy --directory=tree
    echo "== --quiet: the fault in the closing FAULTS block =="
    every_strategy --directory=tree --quiet
    kill $holder 2> /dev/null; wait $holder 2> /dev/null
    ;;

short-form)
    #  What HWUT 1.0 spelled, spelled again.
    fixture_tree
    echo "--- one app, every choice of it"
    face --plain --strategy=linear --jobs=1 --no-store --directory=tree \
         test-one.sh
    echo "--- a globbed app"
    face --plain --strategy=linear --jobs=1 --no-store --directory=tree \
         "test-*.sh"
    echo "--- a bare word that names nothing selects nothing"
    face --plain --no-store --directory=tree test-nowhere.sh
    echo "--- an unknown OPTION is still refused by name"
    face --plain --no-store --directory=tree --sideways
    ;;

labels)
    #  The silence, live in the run itself.
    fixture_tree
    python3 -m vut.services.lib.labels.add meta \
        --glob "tree/*/TEST/test-two.sh" > /dev/null
    echo "--- bare: the standard label is silent (no test-two runs)"
    face --plain --strategy=linear --jobs=1 --no-store --directory=tree
    echo "--- '--label meta' lifts the silence (only test-two runs)"
    face --plain --strategy=linear --jobs=1 --no-store --directory=tree \
         --label meta
    echo "--- '--label all' is the universe"
    face --plain --strategy=linear --jobs=1 --no-store --directory=tree \
         --label all
    echo "--- a label that does not stand, refused by name"
    face --plain --no-store --directory=tree --label cocnern
    echo "--- a LITERAL target overrides the silence"
    face --plain --strategy=linear --jobs=1 --no-store --directory=tree \
         alpha/TEST/test-two.sh
    echo "--- a GLOB does not; wholly swallowed, it warns"
    face --plain --no-store --directory=tree "alpha/TEST/test-tw*.sh"
    echo "--- a broken labels file is a FAULT at the door"
    echo "x : y" >> hwut-root.labels
    face --plain --no-store --directory=tree
    ;;

*)
    echo "unknown choice '$1'"
    exit 1 ;;
esac

#  THE CLOSING TOKEN, PRINTED BY THE APPLICATION ITSELF. An
#  application the framework does not run prints it as its last line;
#  without it 'hwut.accept' refuses the candidate -- a stream with no
#  terminal token never COMPLETED, and an oracle that cannot be
#  re-recorded is an oracle that can never be corrected.
echo "<hwut-end>"
