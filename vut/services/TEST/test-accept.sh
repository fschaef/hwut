#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "The hwut.accept face: promotion, and what it refuses."
#     choices    = ["ask", "bless", "first", "labels", "merge", "onedoor",
#                   "opening", "stderr", "sugar", "token", "interactive",
#                   "unaccepted"]
#     #  the run's TOTAL is wall time since the face began: this machine's,
#     #  not the page's subject
#     tolerance { eq_pattern = [", [0-9]+\\.[0-9]+ \\[sec\\] total"] }
# }
#
# ---------------------------------------------------------------------------
#
# THE 'hwut.accept' FACE, IN ITS NATURAL HABITAT: real runs record real
# candidates, then acceptance promotes them. What is under test:
#
#     bless      a candidate without a nominal becomes the FIRST pole
#     merge      a standing nominal is DETECTED and left alone;
#                '--force' overwrites it, said out loud
#     stderr     STDERR IS NEVER SUBJECT TO TESTING: it is never
#                promoted; where it SPOKE there is NO DEFAULT -- the
#                choice is refused until '--stderr-tol' notes IGNORED
#     sugar      the short form desugars into the wish's own '--glob'
#     ask        the interactive question shows the CANDIDATE and
#                anything but 'y' leaves the pole alone
#
# The wall clock is masked; fixture paths are relative.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
RUN="python3 -m vut.services.run"
ACCEPT="python3 -m vut.services.accept"
WISHLIST="python3 -m vut.services.lib.report.wishlist"
export PYTHONPATH="$ROOT"

case "$1" in
    --hwut-info)
        echo "The hwut.accept face: promotion, and what it refuses.;"
        echo "CHOICES: bless, merge, stderr, sugar, labels, ask, token, interactive, unaccepted, first, opening, onedoor;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

#  THE TREE'S BOUNDARY. Every face ASCENDS collecting 'hwut.conf'
#  until it meets this file; a tree without one is refused, so a
#  fixture states its own. Empty says only 'the tree ends here'.
printf 'hwut {\n}\n' > hwut-root.conf

mask() { sed -E 's/[0-9]{2}:[0-9]{2}:[0-9]{2}/hh:mm:ss/g'; }

face() {                # <args...>  -- status, stdout
    $ACCEPT "$@" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"
    mask < out.txt | sed 's/^/    /'
    echo "}"
    if [ -s err.txt ]; then
        echo "STDERR {"; mask < err.txt | sed 's/^/    /'; echo "}"
    fi
}

fixture() {             # one directory, one plain test, one two-choice
    rm -rf tree
    mkdir -p tree/suite/TEST
    printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n}\n' \
        > tree/suite/TEST/hwut.conf
    printf '#!/bin/bash\n# @hwut { title = "Ok" }\necho "steady line"\necho "<hwut-end>"\n' \
        > tree/suite/TEST/test-ok.sh
    printf '#!/bin/bash\n# @hwut { title = "Two"\n#        choices = ["a", "b"] }\necho "choice $1"\necho "<hwut-end>"\n' \
        > tree/suite/TEST/test-two.sh
    chmod +x tree/suite/TEST/*.sh
    $RUN --directory=tree --silent 2> /dev/null
}

good() { ls tree/suite/TEST/GOOD/ 2>/dev/null | grep -v -e book.csv -e result_db; }

case "$1" in

bless)
    #  No nominal stands: every stdout candidate becomes the first
    #  pole; stderr is NEVER among them.
    fixture
    face --directory=tree/suite/TEST --force
    echo "GOOD holds:"
    good | sed 's/^/    /'
    ;;

merge)
    #  ONE FLAG (E-57): '--force' is 'do not ask' AND 'overwrite what
    #  stands' -- the two were one act once accept SHOWS a change
    #  instead of refusing it. A script that must never overwrite is
    #  'hwut.accept.new' (owed).
    #  A nominal stands: DETECTED, named, left alone -- status 1.
    #  '--force' overwrites the pole, said out loud -- status 0.
    fixture
    $ACCEPT --directory=tree/suite/TEST --force > /dev/null
    echo "== a second accept: the nominals stand =="
    face --directory=tree/suite/TEST --force
    echo "== --force =="
    face --directory=tree/suite/TEST --force
    ;;

stderr)
    #  STDERR IS NEVER SUBJECT TO TESTING. Where it SPOKE there is no
    #  default: refused by name with both remedies; '--stderr-tol'
    #  notes IGNORED, and the note GOVERNS -- the re-run is green.
    fixture
    printf '#!/bin/bash\n# @hwut { title = "Ok" }\necho "steady line"\necho "a warning" >&2\necho "<hwut-end>"\n' \
        > tree/suite/TEST/test-ok.sh
    chmod +x tree/suite/TEST/test-ok.sh
    $RUN --directory=tree --silent 2> /dev/null
    echo "== stderr spoke, no flag =="
    face --directory=tree/suite/TEST --force
    echo "== --stderr-tol =="
    face --directory=tree/suite/TEST --force --stderr-tol
    echo "== the note governs: the suite re-runs green =="
    $RUN --directory=tree --silent 2> /dev/null
    echo "run status: $?"
    echo "GOOD holds (no stderr nominal):"
    good | sed 's/^/    /'
    ;;

labels)
    #  AN EXPLICIT TARGET DOMINATES THE SILENCE (disc-8): a face that
    #  names a run and then declines to bless it is the silent
    #  failure this feature exists to prevent, arriving from the
    #  other side.
    fixture
    python3 -m vut.services.lib.labels.add meta \
        --glob "test-two.sh a" --directory=tree > /dev/null
    echo "== a BARE accept passes the silenced run by =="
    face --directory=tree/suite/TEST --force
    echo "GOOD holds:"
    good | sed 's/^/    /'
    echo "== NAMING it literally blesses it =="
    face --directory=tree/suite/TEST --force test-two.sh a
    echo "GOOD holds:"
    good | sed 's/^/    /'
    echo "== a GLOB wholly swallowed warns instead =="
    fixture
    python3 -m vut.services.lib.labels.add meta \
        --glob "test-two.sh a" --directory=tree > /dev/null
    face --directory=tree/suite/TEST --force "test-two.s?" a
    echo "GOOD holds:"
    good | sed 's/^/    /'
    ;;

sugar)
    #  The short form is SUGAR over '--glob': the first word names
    #  files, every further word a choice. One selection language.
    fixture
    echo "== hwut.accept 'test-two.sh' a =="
    face --directory=tree/suite/TEST --force "test-two.sh" a
    echo "GOOD holds:"
    good | sed 's/^/    /'
    echo "== the same thing, spelled as the wish =="
    fixture
    face --directory=tree/suite/TEST --force --glob "test-two.sh a"
    echo "GOOD holds:"
    good | sed 's/^/    /'
    ;;

token)
    #  THE CLOSING TOKEN (R-70): a candidate whose stdout does not end
    #  in '<hwut-end>' never COMPLETED. REFUSED atomically -- nothing
    #  is promotable while one incomplete stream stands in the
    #  selection, and no flag bypasses.
    fixture
    printf '#!/bin/bash\n# @hwut { title = "Cut" }\necho "half a line"\n' \
        > tree/suite/TEST/test-cut.sh
    chmod +x tree/suite/TEST/test-cut.sh
    $RUN --directory=tree --silent 2> /dev/null
    face --directory=tree/suite/TEST --force
    echo "GOOD holds:"
    good | sed 's/^/    /'
    ;;

ask)
    #  Interactive: the CANDIDATE is shown -- what the framework
    #  compares -- and anything but 'y' leaves the pole alone.
    fixture
    printf 'y\nn\n' | $ACCEPT --directory=tree/suite/TEST \
        > out.txt 2> /dev/null
    echo "STATUS: $?"
    mask < out.txt | sed 's/^/    /'
    echo "GOOD holds (first blessed, second left alone):"
    good | sed 's/^/    /'
    ;;

interactive)
    #  A CHANGE, accepted by hand (E-51): the checklist, one session
    #  per case, 't' takes the subject whole, 'q' leaves alone; a
    #  commit is an acceptance through the same three writes; the
    #  candidate stays as the run left it.
    fixture
    $ACCEPT --directory=tree/suite/TEST --force > /dev/null
    sed -i 's/echo "choice \$1"/echo "changed choice $1"/' tree/suite/TEST/test-two.sh
    $RUN --directory=tree --silent 2> /dev/null
    INTERACTIVE="python3 -m vut.services.lib.accept.interactive"
    echo "--- a plain accept refuses the change"
    $ACCEPT --directory=tree/suite/TEST --force > out.txt 2>&1; echo "STATUS: $?"
    grep -E 'merge required|first blessing' out.txt | sed 's/^/    /'
    echo "--- interactive: the checklist (both marked), 't' takes 'a', 'q' leaves 'b'"
    printf '\nt\nq\n' | $INTERACTIVE --directory=tree/suite/TEST --plain \
        > out.txt 2> ui.txt; echo "STATUS: $?"
    grep -E '^\s+\[|^=\[|accepted|blessed|left alone|ACCEPTED' ui.txt | sed 's/^/    /'
    echo "--- the nominal of 'a' is what the run printed; 'b' stands"
    cat tree/suite/TEST/GOOD/test-two.sh--a.txt tree/suite/TEST/GOOD/test-two.sh--b.txt | sed 's/^/    /'
    echo "--- the candidate stayed: the next run judges anew"
    #  A raw flow of three runs: '--deterministic --jobs=1' (display D-16).
    $RUN --directory=tree/suite/TEST --deterministic --jobs=1 2>&1 \
        | grep -E '\[OK\]|\[FAIL\]' | sed 's/ \.\+/ /; s/^/    /'
    echo "--- the book notes the acceptance of 'a' only"
    grep -c 'test-two.sh;a;' tree/suite/TEST/GOOD/book.csv | sed 's/^/    a: /'
    ;;

first)
    #  ACCEPT IS PARTIAL BY DEFAULT (E-60). A first acceptance WITHOUT
    #  '--force' records the candidate's SHAPE with nothing decided:
    #  one '##! unaccepted' region per chunk, one filler per line, the
    #  closing token outside. The next run reads '[ ?! ]' (O-25), not
    #  '[OK]' -- nobody has judged it yet. '--force' is the old
    #  blessing, the candidate whole ('bless' above).
    fixture
    printf 'y\n' | $ACCEPT --directory=tree/suite/TEST test-ok.sh \
        > out.txt 2> /dev/null
    echo "STATUS: $?"
    grep -E 'blessed|ACCEPTED' out.txt | sed 's/^/    /'
    echo "--- what stands in GOOD: the shape, undecided"
    sed 's/^/    | /' tree/suite/TEST/GOOD/test-ok.sh.txt
    echo "--- the next run: not a failure, a decision still owed"
    $RUN --directory=tree --plain test-ok.sh > out.txt 2> err.txt
    echo "STATUS: $?"
    grep -E '\[ \?! \]|\[FAIL\]|\[OK\]|RESULTS' out.txt \
        | sed 's/ \.\+ / /; s/, [0-9.]* \[sec\]//; s/^/    /'
    ;;

onedoor)
    #  ONE FACE (E-59). A change is MERGED by 'hwut.accept' itself where
    #  there is a terminal to merge in -- through the SAME engine
    #  'hwut.accept.interactive' runs, so the three writes and every
    #  refusal have one implementation. Off a terminal -- a pipe, a
    #  script, this suite -- it says 'merge required' as it always did.
    fixture
    $ACCEPT --directory=tree/suite/TEST --force > /dev/null 2>&1
    sed -i 's/echo "choice \$1"/echo "changed choice $1"/' tree/suite/TEST/test-two.sh
    $RUN --directory=tree --silent 2> /dev/null
    echo "--- off a terminal: the refusal, and the way out"
    $ACCEPT --directory=tree/suite/TEST > out.txt 2>&1; echo "STATUS: $?"
    grep -E 'merge required|first blessing|hwut.accept.interactive' out.txt \
        | sed 's/^/    /'
    echo "--- the engine both doors call"
    python3 - <<'PYEOF' | sed 's/^/    /'
from vut.services.lib.accept import engine
import vut.services.lib.accept.interactive as face
import vut.services.accept as plain
print("merge_text is the engine's:", face.merge_text is engine.merge_text)
print("the face calls run_sessions:", "run_sessions" in open(face.__file__).read())
print("hwut.accept calls it too   :", "run_sessions" in open(plain.__file__).read())
print("one refusal implementation :",
      open(plain.__file__).read().count("def refusal") == 0)
PYEOF
    ;;

opening)
    #  A FIRST ACCEPTANCE BY HAND (E-60). No nominal stands, and the
    #  session OPENS anyway -- on the candidate's shape, nothing
    #  decided. It is an ASPIRANT (B-14), so what the report says of
    #  it is BLESSED, not accepted: there was no pole to reconcile
    #  with. The checklist hands over ONE case per ask and marks what
    #  it handed over (E-65/E-67): '<enter>' takes the first, then the
    #  menu stands again with it marked. 't' takes the subject whole
    #  and commits it; 'q' leaves
    #  the case with NO nominal at all: nothing was written, so nothing
    #  half-decided lingers.
    fixture
    $RUN --directory=tree --silent 2> /dev/null
    INTERACTIVE="python3 -m vut.services.lib.accept.interactive"
    echo "--- the checklist offers every case, nominal or not"
    printf '\nt\n2\nq\nq\n' | $INTERACTIVE --directory=tree/suite/TEST --plain \
        > out.txt 2> ui.txt; echo "STATUS: $?"
    grep -E '^\s+\[|^=\[|accepted|blessed|left alone|ACCEPTED' ui.txt | sed 's/^/    /'
    echo "--- 't' on test-ok.sh: the nominal is the candidate whole"
    sed 's/^/    | /' tree/suite/TEST/GOOD/test-ok.sh.txt
    echo "--- 'q' on test-two.sh a: no nominal was written"
    good | sed 's/^/    /'
    ;;

unaccepted)
    #  A NOMINAL WITH AN '##! unaccepted' REGION (C-9, O-25): the run
    #  reads '[ ?! ]', not '[FAIL]'; it is counted apart; HINTS names
    #  it; and '--unaccepted' (E-58) selects what has NO nominal at
    #  all -- the same state at the grain of a whole case.
    fixture
    mkdir -p tree/suite/TEST/GOOD
    printf 'steady line\n##! unaccepted\nnobody looked here\n####\n<hwut-end>\n' \
        > tree/suite/TEST/GOOD/test-ok.sh.txt
    echo "--- the run: its own tag, its own count, its own hint"
    $RUN --directory=tree --plain > out.txt 2> err.txt
    echo "STATUS: $?"
    grep -E '\[ \?! \]|\[FAIL\]|\[OK\]|RESULTS|nobody has accepted' out.txt \
        | sed 's/ \.\+ / /; s/, [0-9.]* \[sec\]//; s/^/    /'
    echo "--- '--unaccepted' selects the cases with NO nominal: test-two.sh"
    $WISHLIST --directory=tree/suite/TEST --unaccepted | sed 's/^/    /'
    echo "--- accepting them, and nothing else, without a question"
    $ACCEPT --directory=tree/suite/TEST --unaccepted --force > out.txt 2>&1
    echo "STATUS: $?"
    grep -E 'blessed|ACCEPTED' out.txt | sed 's/^/    /'
    echo "--- test-ok.sh stands untouched, still unaccepted"
    grep -c 'unaccepted' tree/suite/TEST/GOOD/test-ok.sh.txt | sed 's/^/    regions: /'
    ;;

*)
    echo "unknown choice '$1'"
    exit 1 ;;
esac

echo "<hwut-end>"
